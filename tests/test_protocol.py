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
        self.assertEqual(complete, 40)

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
            actual=p.parse(command, bytes.fromhex(tx['response_hex']))
            self.assertEqual({key:actual[key] for key in values}, values)

    def test_added_qpigs_fields_from_capture(self):
        tx=next(t for t in FIXTURE['transactions'] if t['command']=='QPIGS')
        values=p.parse('QPIGS',bytes.fromhex(tx['response_hex']))
        self.assertEqual({key:values[key] for key in ('grid_voltage','grid_frequency','output_voltage',
            'output_frequency','load_apparent_power','load_percent','temperature')},
            {'grid_voltage':0,'grid_frequency':0,'output_voltage':230.1,'output_frequency':50,
             'load_apparent_power':2696,'load_percent':24,'temperature':54})

    def test_captured_warning_is_line_fail(self):
        tx=next(t for t in FIXTURE['transactions'] if t['command']=='QPIWS')
        values=p.parse('QPIWS',bytes.fromhex(tx['response_hex']))
        self.assertEqual(values['active_warnings'],['line_fail'])
        self.assertEqual(values['alarm_state'],'warning')

    def test_synthetic_warning_fault_and_unknown_states(self):
        # Synthetic bit changes test decoding; they do not claim captured fault support.
        for bit,state in ((None,'normal'),(1,'fault'),(9,'warning'),(22,'unknown'),(32,'unknown')):
            body=bytearray(b'('+b'0'*36)
            if bit is not None: body[bit+1]=ord('1')
            values=p.parse('QPIWS',bytes(body)+p.crc(body)+b'\r')
            self.assertEqual(values['alarm_state'],state)

    def test_warning_layout_not_guessed(self):
        for payload in (b'('+b'0'*32,b'('+b'0'*35+b'2'):
            with self.assertRaises(p.ProtocolError): p.parse('QPIWS',payload+p.crc(payload)+b'\r')

    def test_derived_power_current_and_mode(self):
        values=p.derived({'output_voltage':230,'load_apparent_power':2700,'load_power':2500,
                         'pv1_power':1427,'pv2_power':1290,'mode':'B'})
        self.assertAlmostEqual(values['output_current_calculated'],11.7391304)
        self.assertAlmostEqual(values['power_factor_calculated'],0.925925926)
        self.assertEqual(values['solar_power_total'],2717)
        self.assertEqual(values['operating_mode'],'battery')

    def test_derived_invalid_denominators_and_missing_pv2(self):
        values=p.derived({'output_voltage':0,'load_apparent_power':0,'load_power':0,'pv1_power':100})
        self.assertNotIn('output_current_calculated',values)
        self.assertNotIn('power_factor_calculated',values)
        self.assertNotIn('solar_power_total',values)
        self.assertNotIn('power_factor_calculated',p.derived({'load_apparent_power':10,'load_power':11}))

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
