"""Strict parser for the profile observed in prueba.pcapng (24 fields)."""
import binascii
import math
import re

COMMANDS = ('QPIGS', 'QPIGS2', 'QMOD', 'QPIWS')

MODE_NAMES = {'P': 'power_on', 'S': 'standby', 'L': 'line', 'B': 'battery',
              'F': 'fault', 'D': 'shutdown', 'C': 'charge', 'Y': 'bypass', 'E': 'eco'}
# Manufacturer's TWIN document, section 2.13. Tail positions vary by model:
# keep 31..35 uninterpreted, including the ambiguous fault-code extension.
WARNING_NAMES = {0: 'pv_loss', 1: 'inverter_fault', 2: 'bus_over', 3: 'bus_under',
    4: 'bus_soft_fail', 5: 'line_fail', 6: 'output_short', 7: 'output_voltage_low',
    8: 'output_voltage_high', 9: 'over_temperature', 10: 'fan_locked',
    11: 'battery_voltage_high', 12: 'battery_low', 14: 'battery_under_shutdown',
    15: 'battery_derating', 16: 'overload', 17: 'eeprom_fault',
    18: 'inverter_over_current', 19: 'inverter_soft_fail', 20: 'self_test_fail',
    21: 'output_dc_voltage_over', 22: 'battery_open', 23: 'current_sensor_fail'}
FAULT_BITS = {1, 2, 3, 4, 6, 7, 8, 18, 19, 20, 21, 23}


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
    if command == 'QPIWS':
        if not re.fullmatch('[01]{36}', payload):
            raise ProtocolError('QPIWS: unsupported warning layout (expected 36 binary positions)')
        active = [index for index, value in enumerate(payload) if value == '1']
        known = [WARNING_NAMES[index] for index in active if index in WARNING_NAMES]
        unknown = [index for index in active if index not in WARNING_NAMES or index == 22]
        state = ('fault' if FAULT_BITS.intersection(active) else
                 'unknown' if unknown else 'warning' if active else 'normal')
        return {'warning_raw': payload, 'alarm_state': state,
                'active_warnings': known, 'uninterpreted_warning_positions': unknown}
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
    indices = {'grid_voltage': 0, 'grid_frequency': 1, 'output_voltage': 2,
               'output_frequency': 3, 'load_apparent_power': 4, 'load_power': 5,
               'load_percent': 6, 'battery_voltage': 8, 'battery_charge_current': 9,
               'battery_soc': 10, 'pv1_current': 12, 'pv1_voltage': 13,
               'temperature': 11, 'battery_discharge_current': 15, 'pv1_power': 19}
    result = {key: number(fields[index]) for key, index in indices.items()}
    if not 0 <= result['battery_soc'] <= 100:
        raise ProtocolError('Battery percentage outside 0..100')
    return result


def derived(data: dict) -> dict:
    """Calculations from a single validated cycle; missing channels stay missing."""
    result = dict(data)
    voltage, apparent, active = (data.get(key) for key in
                                ('output_voltage', 'load_apparent_power', 'load_power'))
    if voltage is not None and voltage > 0 and apparent is not None:
        result['output_current_calculated'] = apparent / voltage
    if apparent is not None and apparent > 0 and active is not None and 0 <= active <= apparent:
        result['power_factor_calculated'] = active / apparent
    if 'pv1_power' in data and 'pv2_power' in data:
        result['solar_power_total'] = data['pv1_power'] + data['pv2_power']
    if 'mode' in data:
        result['operating_mode'] = MODE_NAMES[data['mode']]
    return result
