"""Pitch the articulated Shari model into a level flying posture.

The generated model's body is upright. A parent transform rotates the whole
rig, including its wings and tail, while the hover channel stays vertical.
"""

import json
import math
import struct
import sys
from pathlib import Path


def orient(source, destination, pitch_degrees=-45):
    data = Path(source).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', data)
    assert magic == b'glTF' and version == 2 and total == len(data)
    json_len, json_type = struct.unpack_from('<II', data, 12)
    assert json_type == 0x4E4F534A
    doc = json.loads(data[20:20 + json_len])
    bin_offset = 20 + json_len
    bin_len, bin_type = struct.unpack_from('<II', data, bin_offset)
    assert bin_type == 0x004E4942
    binary = data[bin_offset + 8:bin_offset + 8 + bin_len]

    old_root = next(i for i, node in enumerate(doc['nodes']) if node.get('name') == 'Shari_hover_root')
    parent = len(doc['nodes'])
    half = math.radians(pitch_degrees) / 2
    doc['nodes'].append({'name': 'Shari_level_flight',
                         'rotation': [0, 0, math.sin(half), math.cos(half)],
                         'children': [old_root]})
    for scene in doc['scenes']:
        scene['nodes'] = [parent if node == old_root else node for node in scene['nodes']]
    doc['animations'][0]['name'] = 'Level flight'
    # In v2 this small vertical hover animated the rig root. Moving it to
    # the outer parent keeps the motion vertical after changing body pitch.
    for channel in doc['animations'][0]['channels']:
        target = channel['target']
        if target['node'] == old_root and target['path'] == 'translation':
            target['node'] = parent

    j = json.dumps(doc, separators=(',', ':'), ensure_ascii=False).encode()
    j += b' ' * (-len(j) % 4)
    with Path(destination).open('wb') as out:
        out.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(j) + 8 + len(binary)))
        out.write(struct.pack('<II', len(j), 0x4E4F534A))
        out.write(j)
        out.write(struct.pack('<II', len(binary), 0x004E4942))
        out.write(binary)
    print(f'{destination}: {pitch_degrees}° body pitch')


if __name__ == '__main__':
    orient(*sys.argv[1:])
