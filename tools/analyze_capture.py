"""Offline USBPcap/pcapng extraction; never communicates with hardware."""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path


def packets(blob):
    offset, endian, interfaces, number = 0, '<', [], 0
    while offset + 12 <= len(blob):
        if blob[offset:offset+4] == b'\x0a\x0d\x0d\x0a':
            endian = '<' if blob[offset+8:offset+12] == b'\x4d\x3c\x2b\x1a' else '>'
            interfaces = []
        kind, length = struct.unpack_from(endian+'II', blob, offset)
        if length < 12 or length % 4 or offset+length > len(blob):
            raise ValueError('Invalid pcapng block length')
        if struct.unpack_from(endian+'I', blob, offset+length-4)[0] != length:
            raise ValueError('Invalid pcapng block trailer')
        if kind == 1:
            interfaces.append(struct.unpack_from(endian+'H', blob, offset+8)[0])
        if kind == 6:
            number += 1
            interface, _, _, captured, original = struct.unpack_from(endian+'IIIII', blob, offset+8)
            if captured > length-32 or captured != original:
                raise ValueError('Truncated capture packet')
            if interfaces[interface] == 249:
                yield number, blob[offset+28:offset+28+captured]
        offset += length
    if offset != len(blob):
        raise ValueError('Truncated pcapng')


def analyze(blob):
    transactions, descriptors, pending = [], [], {}
    for number, packet in packets(blob):
        if len(packet) < 27:
            continue
        header = struct.unpack_from('<H', packet)[0]
        status = struct.unpack_from('<I', packet, 10)[0]
        bus, device = struct.unpack_from('<HH', packet, 17)
        endpoint, transfer = packet[21:23]
        size = struct.unpack_from('<I', packet, 23)[0]
        data = packet[header:header+size]
        key = (bus, device)
        if status or len(data) != size:
            continue
        if transfer == 2 and endpoint == 0x80 and header == 28 and packet[27] == 3 and data:
            descriptors.append({'packet': number, 'bus': bus, 'device': device, 'hex': data.hex()})
        if transfer == 2 and endpoint == 0 and header == 28 and packet[27] == 0 and data[:8] == bytes.fromhex('2109000200000800'):
            chunk = data[8:]
            current = pending.get(key)
            if current is None or current['response_hex']:
                current = {'packet': number, 'bus': bus, 'device': device, 'request_hex': '', 'response_hex': '', 'reports': []}
                transactions.append(current)
                pending[key] = current
            current['request_hex'] += chunk.hex()
        if transfer == 1 and endpoint == 0x81 and data and key in pending:
            current = pending[key]
            current['reports'].append({'packet': number, 'hex': data.hex()})
            current['response_hex'] += data.hex()
    counts = collections.Counter()
    for tx in transactions:
        request = bytes.fromhex(tx['request_hex']).rstrip(b'\0')
        tx['command'] = request[:-3].decode('ascii', errors='replace') if request.endswith(b'\r') else 'incomplete'
        counts[tx['command']] += 1
    return {'sha256': hashlib.sha256(blob).hexdigest(), 'descriptors': descriptors, 'counts': dict(counts), 'transactions': transactions}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(analyze(args.capture.read_bytes()), indent=2)+'\n', encoding='utf-8')
