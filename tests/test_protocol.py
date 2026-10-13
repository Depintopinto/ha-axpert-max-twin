import json
import unittest
from load_component import ROOT, load

p = load('protocol')
FIXTURE = json.loads((ROOT / 'tests/fixtures/capture_queries.json').read_text())


class ProtocolTests(unittest.TestCase):
    def test_xmodem_reference(self):
        self.assertEqual(p.crc(b'123456789').hex(), '31c3')

    def test_all_real_transactions(self):
        complete = 0
        for tx in FIXTURE['transactions']:
            command = tx['command']
            with self.subTest(packet=tx['packet'], command=command):
                actual = bytes.fromhex(tx['request_hex'])
                self.assertEqual(b''.join(r[1:] for r in p.output_reports(command)), actual)
                response = bytes.fromhex(tx['response_hex'])
                if b'\r' not in response:
                    with self.assertRaises(p.ProtocolError):
                        p.parse(command, response)
                else:
                    p.parse(command, response)
                    complete += 1
        self.assertEqual(complete, 29)

    def test_observed_values(self):
        expected = {
            'QPIGS': {'load_power': 2696, 'battery_voltage': 55.8, 'battery_charge_current': 2,
                      'battery_soc': 76, 'pv1_current': 7.8, 'pv1_voltage': 181,
                      'battery_discharge_current': 0, 'pv1_power': 1427},
            'QPIGS2': {'pv2_current': 3.4, 'pv2_voltage': 376.8, 'pv2_power': 1290},
            'QMOD': {'mode': 'B'},
        }
        for command, values in expected.items():
            tx = next(t for t in FIXTURE['transactions'] if t['command'] == command)
            self.assertEqual(p.parse(command, bytes.fromhex(tx['response_hex'])), values)

    def test_only_read_queries(self):
        for command in ('POP00', 'QPIRI', 'QPIGS\r', '', 'PBATCD111'):
            with self.assertRaises(p.ProtocolError):
                p.output_reports(command)

    def test_crc_corruption_and_garbage(self):
        good = bytes.fromhex(next(t for t in FIXTURE['transactions'] if t['command']=='QPIGS')['response_hex'])
        for bad in (b'X'+good[1:], good[:10]+b'X'+good[11:], good+b'X', good[:-8]):
            with self.assertRaises(p.ProtocolError):
                p.parse('QPIGS', bad)

    def test_nak_requires_valid_crc(self):
        body = b'(NAK'
        with self.assertRaises(p.UnsupportedCommand):
            p.decode(body+p.crc(body)+b'\r')
        with self.assertRaises(p.ProtocolError):
            p.decode(body+b'\r')

    def test_unsupported_layout(self):
        for payload in (b'(1 2', b'(nan 2 3', b'(1 2 inf', b'(1 -2 3'):
            with self.assertRaises(p.ProtocolError):
                p.parse('QPIGS2', payload+p.crc(payload)+b'\r')

    def test_modes_from_manufacturer(self):
        for mode in 'PSLBFDCYE':
            body = b'('+mode.encode()
            self.assertEqual(p.parse('QMOD',body+p.crc(body)+b'\r')['mode'],mode)
