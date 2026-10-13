import json
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from load_component import ROOT, load

t = load('transport')
p = load('protocol')
FIXTURE = json.loads((ROOT / 'tests/fixtures/capture_queries.json').read_text())


class TransportTests(unittest.TestCase):
    def test_optional_failure_keeps_qpigs_and_closes_device(self):
        client = t.HidrawTransport('/dev/hidraw0')
        fcntl = SimpleNamespace(flock=lambda *args: None, LOCK_EX=1, LOCK_NB=2)
        with patch.dict(sys.modules, {'fcntl':fcntl}), \
             patch.object(t.os,'O_NONBLOCK',2048,create=True), \
             patch.object(t.Path,'resolve',return_value=t.Path('/dev/hidraw0')), \
             patch.object(t.Path,'read_text',return_value='HID_ID=0003:00000665:00005161\n'), \
             patch.object(t.os,'open',return_value=42), patch.object(t.os,'close') as close, \
             patch.object(client,'_query',side_effect=[({'load_power':2696},b'valid'),TimeoutError('no input'),({'mode':'B'},b'valid'),({'alarm_state':'normal'},b'valid')]):
            self.assertEqual(client.poll(),{'load_power':2696,'mode':'B','alarm_state':'normal'})
            self.assertEqual(client.diagnostics['QPIGS2']['status'],'TimeoutError')
            close.assert_called_once_with(42)

    def test_mandatory_failure_does_not_poll_optional(self):
        client = t.HidrawTransport('/dev/hidraw0')
        fcntl = SimpleNamespace(flock=lambda *args: None, LOCK_EX=1, LOCK_NB=2)
        with patch.dict(sys.modules, {'fcntl':fcntl}), \
             patch.object(t.os,'O_NONBLOCK',2048,create=True), \
             patch.object(t.Path,'resolve',return_value=t.Path('/dev/hidraw0')), \
             patch.object(t.Path,'read_text',return_value='HID_ID=0003:00000665:00005161\n'), \
             patch.object(t.os,'open',return_value=42), patch.object(t.os,'close') as close, \
             patch.object(client,'_query',side_effect=p.ProtocolError('CRC mismatch')) as query:
            with self.assertRaises(p.ProtocolError): client.poll()
            query.assert_called_once_with(42,'QPIGS')
            close.assert_called_once_with(42)
            self.assertEqual(client.diagnostics['QMOD']['status'],'not_polled')
            self.assertEqual(client.diagnostics['QPIWS']['status'],'not_polled')

    def test_optional_alarm_failure_keeps_core_status(self):
        client=t.HidrawTransport('/dev/hidraw0')
        fcntl=SimpleNamespace(flock=lambda *args:None,LOCK_EX=1,LOCK_NB=2)
        with patch.dict(sys.modules,{'fcntl':fcntl}), patch.object(t.os,'O_NONBLOCK',2048,create=True), \
             patch.object(t.Path,'resolve',return_value=t.Path('/dev/hidraw0')), \
             patch.object(t.Path,'read_text',return_value='HID_ID=0003:00000665:00005161'), \
             patch.object(t.os,'open',return_value=42), patch.object(t.os,'close'), \
             patch.object(client,'_query',side_effect=[({'load_power':1},b'x'),({'pv2_power':2},b'x'),({'mode':'B'},b'x'),p.UnsupportedCommand('NAK')]):
            self.assertEqual(client.poll(),{'load_power':1,'pv2_power':2,'mode':'B'})
            self.assertEqual(client.diagnostics['QPIWS']['status'],'UnsupportedCommand')

    def test_wrong_usb_identity_never_writes(self):
        with patch.object(t.Path,'resolve',return_value=t.Path('/dev/hidraw0')), \
             patch.object(t.Path,'read_text',return_value='HID_ID=0003:00001234:00005678\n'), \
             patch.object(t.os,'open') as opened, patch.dict(sys.modules, {'fcntl':SimpleNamespace()}):
            with self.assertRaisesRegex(OSError,'not the captured'): t.HidrawTransport('/dev/hidraw0').poll()
            opened.assert_not_called()

    def test_replay_fragmented_usb_reports(self):
        for tx in FIXTURE['transactions']:
            if b'\r' not in bytes.fromhex(tx['response_hex']):
                continue
            chunks = [bytes.fromhex(r['hex']) for r in tx['reports']]
            with self.subTest(packet=tx['packet']), \
                 patch.object(t.os, 'read', side_effect=[BlockingIOError(), *chunks]), \
                 patch.object(t.os, 'write', side_effect=lambda fd, data: len(data)) as write, \
                 patch.object(t.select, 'select', return_value=([42],[],[])), \
                 patch.object(t.time, 'sleep'):
                data, frame = t.HidrawTransport('/dev/hidraw0')._query(42,tx['command'])
                self.assertEqual(frame.hex(),tx['response_hex'])
                self.assertEqual(data,p.parse(tx['command'],frame))
                self.assertEqual([c.args[1] for c in write.call_args_list],p.output_reports(tx['command']))

    def test_no_response_timeout(self):
        with patch.object(t.os,'read',side_effect=BlockingIOError()), \
             patch.object(t.os,'write',side_effect=lambda fd,data:len(data)), \
             patch.object(t.select,'select',return_value=([],[],[])), patch.object(t.time,'sleep'):
            with self.assertRaisesRegex(TimeoutError,'no USB input'):
                t.HidrawTransport('/dev/hidraw0')._query(42,'QPIGS')

    def test_short_write(self):
        with patch.object(t.os,'read',side_effect=BlockingIOError()), \
             patch.object(t.os,'write',return_value=2), patch.object(t.time,'sleep'):
            with self.assertRaisesRegex(OSError,'Short HID'):
                t.HidrawTransport('/dev/hidraw0')._query(42,'QPIGS')

    def test_usb_disconnect(self):
        with patch.object(t.os,'read',side_effect=[BlockingIOError(),b'']), \
             patch.object(t.os,'write',side_effect=lambda fd,data:len(data)), \
             patch.object(t.select,'select',return_value=([42],[],[])), patch.object(t.time,'sleep'):
            with self.assertRaisesRegex(OSError,'disconnected'):
                t.HidrawTransport('/dev/hidraw0')._query(42,'QPIGS')

    def test_incomplete_response(self):
        with patch.object(t.os,'read',side_effect=[BlockingIOError(),b'(000.0 ']), \
             patch.object(t.os,'write',side_effect=lambda fd,data:len(data)), \
             patch.object(t.select,'select',side_effect=[([42],[],[]),([],[],[])]), patch.object(t.time,'sleep'):
            with self.assertRaisesRegex(p.ProtocolError,'incomplete'):
                t.HidrawTransport('/dev/hidraw0')._query(42,'QPIGS')

    def test_stale_input_is_drained(self):
        tx=next(x for x in FIXTURE['transactions'] if x['command']=='QMOD')
        response=bytes.fromhex(tx['response_hex'])
        with patch.object(t.os,'read',side_effect=[b'stale123',BlockingIOError(),response]), \
             patch.object(t.os,'write',side_effect=lambda fd,data:len(data)), \
             patch.object(t.select,'select',return_value=([42],[],[])), patch.object(t.time,'sleep'):
            self.assertEqual(t.HidrawTransport('/dev/hidraw0')._query(42,'QMOD')[0],{'mode':'B'})
