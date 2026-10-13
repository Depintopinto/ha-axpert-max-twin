"""Linux-only hidraw transport. No binary dependencies or kernel driver detachment."""
import os
from pathlib import Path
import select
import threading
import time

from .protocol import COMMANDS, ProtocolError, output_reports, parse


class HidrawTransport:
    def __init__(self, path, timeout=5.0):
        self.path = path
        self.timeout = timeout
        self.lock = threading.Lock()
        self.last_command = 0.0
        self.diagnostics = {command: {'status': 'not_polled'}
                            for command in COMMANDS}

    def poll(self):
        # The complete polling cycle has exclusive ownership, including the optional queries.
        with self.lock:
            return self._poll()

    def _poll(self):
        import fcntl
        resolved = Path(self.path).resolve(strict=True)
        if resolved.parent != Path('/dev') or not resolved.name.startswith('hidraw'):
            raise OSError('Select a Linux /dev/hidraw device')
        info = (Path('/sys/class/hidraw') / resolved.name / 'device/uevent').read_text()
        if 'HID_ID=0003:00000665:00005161' not in info.upper():
            raise OSError('Device is not the captured USB VID:PID 0665:5161')
        fd = os.open(resolved, os.O_RDWR | os.O_NONBLOCK)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = {}
            for command in COMMANDS:
                try:
                    data, frame = self._query(fd, command)
                    result.update(data)
                    self.diagnostics[command] = {'status': 'ok', 'frame_hex': frame.hex(), 'bytes': len(frame)}
                except (OSError, ProtocolError) as err:
                    self.diagnostics[command] = {'status': type(err).__name__, 'error': str(err)}
                    if command == 'QPIGS':
                        # Nothing from a failed cycle may appear as fresh data.
                        for optional in COMMANDS[1:]:
                            self.diagnostics[optional] = {'status': 'not_polled'}
                        raise
            return result
        finally:
            os.close(fd)

    def _query(self, fd, command):
        time.sleep(max(0, 0.5 - (time.monotonic() - self.last_command)))
        # Drain queued reports with a bound: continuous unsolicited traffic is a failure.
        for _ in range(128):
            try:
                stale = os.read(fd, 8)
                if not stale:
                    raise OSError('USB disconnected while draining')
            except BlockingIOError:
                break
        else:
            raise ProtocolError('Input queue did not become idle')
        try:
            for report in output_reports(command):
                if os.write(fd, report) != len(report):
                    raise OSError('Short HID report write')
                time.sleep(0.01)
            deadline = time.monotonic() + self.timeout
            response = bytearray()
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
                if not ready:
                    break
                try:
                    chunk = os.read(fd, 8)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise OSError('USB disconnected during read')
                response.extend(chunk)
                if len(response) > 1024:
                    raise ProtocolError('Response exceeds limit')
                if b'\r' in response:
                    return parse(command, bytes(response)), bytes(response)
            if response:
                raise ProtocolError(f'{command}: incomplete response ({len(response)} bytes)')
            raise TimeoutError(f'{command}: no USB input before deadline')
        finally:
            self.last_command = time.monotonic()
