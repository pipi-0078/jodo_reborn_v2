"""Rig the Tripo Shari mesh with shoulder, elbow and wrist joints.

The source is a single mesh. This creates a glTF skin with continuous vertex
weights along each wing and bakes one looping animation into a new GLB.
"""

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np


def unpack(path):
    data = Path(path).read_bytes()
    magic, version, total = struct.unpack_from('<4sII', data)
    assert magic == b'glTF' and version == 2 and total == len(data)
    json_length, json_type = struct.unpack_from('<II', data, 12)
    assert json_type == 0x4E4F534A
    doc = json.loads(data[20:20 + json_length])
    offset = 20 + json_length
    bin_length, bin_type = struct.unpack_from('<II', data, offset)
    assert bin_type == 0x004E4942
    return doc, bytearray(data[offset + 8:offset + 8 + bin_length])


def read_positions(doc, binary):
    primitive = doc['meshes'][0]['primitives'][0]
    a = doc['accessors'][primitive['attributes']['POSITION']]
    v = doc['bufferViews'][a['bufferView']]
    assert a['componentType'] == 5126 and 'byteStride' not in v
    return np.frombuffer(binary, dtype='<f4', count=a['count'] * 3,
                         offset=v.get('byteOffset', 0) + a.get('byteOffset', 0)).reshape(-1, 3).copy()


def append_accessor(doc, binary, values, accessor_type, component_type, target=None):
    if component_type == 5126:
        values = np.ascontiguousarray(values, dtype='<f4')
    elif component_type == 5123:
        values = np.ascontiguousarray(values, dtype='<u2')
    else:
        raise ValueError(component_type)
    binary.extend(b'\x00' * (-len(binary) % 4))
    view = {'buffer': 0, 'byteOffset': len(binary), 'byteLength': values.nbytes}
    if target is not None:
        view['target'] = target
    doc['bufferViews'].append(view)
    binary.extend(values.tobytes())
    accessor = {'bufferView': len(doc['bufferViews']) - 1,
                'componentType': component_type, 'count': len(values),
                'type': accessor_type}
    doc['accessors'].append(accessor)
    return len(doc['accessors']) - 1


def smoothstep(values, start, end):
    t = np.clip((values - start) / (end - start), 0, 1)
    return t * t * (3 - 2 * t)


def quaternion(axis, degrees):
    a = math.radians(degrees) / 2
    return np.array([axis[0] * math.sin(a), axis[1] * math.sin(a),
                     axis[2] * math.sin(a), math.cos(a)], dtype=np.float32)


def multiply(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], dtype=np.float32)


def curve(t, poses, field):
    for i in range(len(poses) - 1):
        t0, t1 = poses[i][0], poses[i + 1][0]
        if t <= t1 or i == len(poses) - 2:
            alpha = max(0, min(1, (t - t0) / (t1 - t0)))
            alpha = alpha * alpha * (3 - 2 * alpha)
            return poses[i][field] * (1 - alpha) + poses[i + 1][field] * alpha
    return poses[-1][field]


def add_channel(doc, binary, animation, node, path, times_accessor, values, typ):
    output = append_accessor(doc, binary, values, typ, 5126)
    animation['samplers'].append({'input': times_accessor, 'output': output,
                                  'interpolation': 'LINEAR'})
    animation['channels'].append({'sampler': len(animation['samplers']) - 1,
                                  'target': {'node': node, 'path': path}})


def write_glb(path, doc, binary):
    binary.extend(b'\x00' * (-len(binary) % 4))
    doc['buffers'][0]['byteLength'] = len(binary)
    j = json.dumps(doc, separators=(',', ':'), ensure_ascii=False).encode()
    j += b' ' * (-len(j) % 4)
    with Path(path).open('wb') as output:
        output.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(j) + 8 + len(binary)))
        output.write(struct.pack('<II', len(j), 0x4E4F534A))
        output.write(j)
        output.write(struct.pack('<II', len(binary), 0x004E4942))
        output.write(binary)


def build(source, destination):
    doc, binary = unpack(source)
    assert len(doc['meshes']) == 1 and not doc.get('skins') and not doc.get('animations')
    primitive = doc['meshes'][0]['primitives'][0]
    positions = read_positions(doc, binary)

    # Joint order: body root, left shoulder/elbow/wrist, right shoulder/elbow/wrist.
    shoulders = {1: np.array([0.17, 0.10, 0.075]),
                 -1: np.array([0.17, 0.10, -0.075])}
    elbows = {1: np.array([0.145, 0.11, 0.21]),
              -1: np.array([0.145, 0.11, -0.21])}
    wrists = {1: np.array([0.105, 0.115, 0.34]),
              -1: np.array([0.105, 0.115, -0.34])}

    root = len(doc['nodes'])
    doc['nodes'].append({'name': 'Shari_hover_root', 'children': [0]})
    joint_nodes = [root]
    for side, label in [(1, 'left'), (-1, 'right')]:
        shoulder = len(doc['nodes'])
        elbow = shoulder + 1
        wrist = shoulder + 2
        doc['nodes'].append({'name': f'{label}_shoulder',
                             'translation': shoulders[side].tolist(), 'children': [elbow]})
        doc['nodes'].append({'name': f'{label}_elbow',
                             'translation': (elbows[side] - shoulders[side]).tolist(),
                             'children': [wrist]})
        doc['nodes'].append({'name': f'{label}_wrist',
                             'translation': (wrists[side] - elbows[side]).tolist()})
        doc['nodes'][root]['children'].append(shoulder)
        joint_nodes.extend([shoulder, elbow, wrist])
    for scene in doc['scenes']:
        scene['nodes'] = [root if node == 0 else node for node in scene['nodes']]

    span = np.abs(positions[:, 2])
    # Wing points lie forward of the tail. Include swept-back wing tips (+X
    # around 0.08) while keeping the long tail feathers attached to the body.
    wing_region = smoothstep(positions[:, 0], -0.05, 0.07)
    s0 = smoothstep(span, 0.065, 0.125) * wing_region
    s1 = smoothstep(span, 0.17, 0.245)
    s2 = smoothstep(span, 0.285, 0.365)
    weights = np.stack([1 - s0, s0 * (1 - s1),
                        s0 * s1 * (1 - s2), s0 * s1 * s2], axis=1).astype(np.float32)
    joints = np.zeros((len(positions), 4), dtype=np.uint16)
    left = positions[:, 2] >= 0
    joints[left, 1:] = [1, 2, 3]
    joints[~left, 1:] = [4, 5, 6]
    assert np.allclose(weights.sum(axis=1), 1, atol=1e-6)
    primitive['attributes']['JOINTS_0'] = append_accessor(doc, binary, joints, 'VEC4', 5123, 34962)
    primitive['attributes']['WEIGHTS_0'] = append_accessor(doc, binary, weights, 'VEC4', 5126, 34962)
    doc['nodes'][0]['skin'] = 0

    bind_points = [np.zeros(3), shoulders[1], elbows[1], wrists[1],
                   shoulders[-1], elbows[-1], wrists[-1]]
    inverse_binds = np.tile(np.eye(4, dtype=np.float32), (7, 1, 1))
    for i, point in enumerate(bind_points):
        inverse_binds[i, :3, 3] = -point
    doc['skins'] = [{'name': 'Shari_wing_rig', 'joints': joint_nodes,
                     'skeleton': root,
                     'inverseBindMatrices': append_accessor(
                         doc, binary, inverse_binds.transpose(0, 2, 1).reshape(7, 16),
                         'MAT4', 5126)}]

    # Time, shoulder flap (+ raises wing), elbow fold, wrist fold, primary twist.
    # Downstroke is relatively fast and extended; upstroke folds and twists.
    poses = [(0.00, 48, 8, 10, -6),
             (0.18, 38, 2, 4, -2),
             (0.48, 5, 0, 0, 0),
             (0.82, -42, 0, 0, 3),
             (1.05, -34, 8, 12, -4),
             (1.42, -4, 30, 36, -24),
             (1.80, 32, 25, 29, -18),
             (2.20, 48, 8, 10, -6)]
    times = np.linspace(0, 2.2, 89, dtype=np.float32)
    times_a = append_accessor(doc, binary, times.reshape(-1, 1), 'SCALAR', 5126)
    animation = {'name': 'Articulated flight', 'samplers': [], 'channels': []}
    for side, joint_offset in [(1, 1), (-1, 4)]:
        shoulder_rot = []
        elbow_rot = []
        wrist_rot = []
        for time in times:
            flap = curve(time, poses, 1)
            elbow = curve(time, poses, 2)
            wrist = curve(time, poses, 3)
            twist = curve(time, poses, 4)
            shoulder_rot.append(quaternion((1, 0, 0), -side * flap))
            elbow_rot.append(quaternion((0, 1, 0), -side * elbow))
            wrist_rot.append(multiply(quaternion((0, 1, 0), -side * wrist),
                                      quaternion((0, 0, 1), side * twist)))
        for offset, rotations in [(0, shoulder_rot), (1, elbow_rot), (2, wrist_rot)]:
            add_channel(doc, binary, animation, joint_nodes[joint_offset + offset],
                        'rotation', times_a, rotations, 'VEC4')

    bob = np.zeros((len(times), 3), dtype=np.float32)
    phase = 2 * np.pi * times / times[-1]
    bob[:, 1] = 0.010 * (np.sin(phase - 0.45) - math.sin(-0.45))
    add_channel(doc, binary, animation, root, 'translation', times_a, bob, 'VEC3')
    doc['animations'] = [animation]
    write_glb(destination, doc, binary)
    print(f'{destination}: shoulder/elbow/wrist on both wings, 2.2s loop')


if __name__ == '__main__':
    build(*sys.argv[1:])
