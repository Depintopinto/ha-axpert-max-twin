"""Strict parser for the profile observed in prueba.pcapng (24 fields)."""
import binascii
import math
import re

COMMANDS = ('QPIGS', 'QPIGS2', 'QMOD')


class ProtocolError(ValueError):
    """Invalid or unsupported protocol data."""


class UnsupportedCommand(ProtocolError):
    """CRC-validated NAK."""


def crc(data: bytes) -> bytes:
    value = binascii.crc_hqx(data, 0)
    return bytes(byte + 1 if byte in (0x28, 0x0D, 0x0A) else byte
                 for byte in value.to_bytes(2, 'big'))


def request(command: str) -> bytes:
    if command not in COMMANDS:
        raise ProtocolError('Command is not in the read-only allowlist')
    data = command.encode('ascii')
    return data + crc(data) + b'\r'


def output_reports(command: str) -> list[bytes]:
    """Linux hidraw requires report ID 0 before each unnumbered 8-byte report."""
    frame = request(command)
    return [b'\0' + frame[pos:pos+8].ljust(8, b'\0') for pos in range(0, len(frame), 8)]


def decode(frame: bytes) -> str:
    """Accept only a complete frame and zero padding after CR; CRC includes '(' and spaces."""
    end = frame.find(b'\r')
    if end < 0:
        raise ProtocolError('Missing terminator (incomplete response)')
    if any(frame[end+1:]):
        raise ProtocolError('Nonzero data after terminator')
    body = frame[:end]
    if len(body) < 3 or body[:1] != b'(':
        raise ProtocolError('Invalid response start or length')
    if crc(body[:-2]) != body[-2:]:
        raise ProtocolError('CRC mismatch')
    try:
        payload = body[1:-2].decode('ascii')
    except UnicodeDecodeError as err:
        raise ProtocolError('Non-ASCII payload') from err
    if payload == 'NAK':
        raise UnsupportedCommand('Query rejected with NAK')
    return payload


def number(text: str) -> float:
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        raise ProtocolError('Invalid numeric field')
    value = float(text)
    if not math.isfinite(value):
        raise ProtocolError('Non-finite field')
    return value


def parse(command: str, frame: bytes) -> dict:
    if command not in COMMANDS:
        raise ProtocolError('Unsupported parser command')
    payload = decode(frame)
    fields = payload.split()
    if command == 'QMOD':
        if payload not in ('P', 'S', 'L', 'B', 'F', 'D', 'C', 'Y', 'E'):
            raise ProtocolError('Unknown mode')
        return {'mode': payload}
    expected = 24 if command == 'QPIGS' else 3
    if len(fields) != expected:
        raise ProtocolError(f'{command}: expected {expected} fields, received {len(fields)}')
    if command == 'QPIGS2':
        return dict(zip(('pv2_current', 'pv2_voltage', 'pv2_power'), map(number, fields)))
    if not re.fullmatch('[01]{8}', fields[16]) or not re.fullmatch('[01]{3}', fields[20]):
        raise ProtocolError('Invalid status flags')
    # Validate the entire known numeric layout, including fields not exposed as sensors.
    for index, field in enumerate(fields):
        if index not in (16, 20):
            number(field)
    indices = {'load_power': 5, 'battery_voltage': 8, 'battery_charge_current': 9,
               'battery_soc': 10, 'pv1_current': 12, 'pv1_voltage': 13,
               'battery_discharge_current': 15, 'pv1_power': 19}
    result = {key: number(fields[index]) for key, index in indices.items()}
    if not 0 <= result['battery_soc'] <= 100:
        raise ProtocolError('Battery percentage outside 0..100')
    return result
