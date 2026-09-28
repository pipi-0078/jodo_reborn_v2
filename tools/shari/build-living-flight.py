"""Add bilateral eyelid closure and travelling tail waves to the v5 flight.

Preserves the approved wing rotations. Morphs are evaluated before skinning,
so tail displacements use the inverse body pitch to stay in world directions.
"""
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader

import numpy as np

rig = SourceFileLoader('flight_rig', str(Path(__file__).with_name('build-articulated-flight.py'))).load_module()


def read(doc, binary, index):
    a = doc['accessors'][index]
    v = doc['bufferViews'][a['bufferView']]
    width = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[a['type']]
    return np.frombuffer(binary, dtype='<f4', count=a['count'] * width,
                         offset=v.get('byteOffset', 0) + a.get('byteOffset', 0)).reshape(-1, width).copy()


def build(source, destination):
    doc, binary = rig.unpack(source)
    primitive = doc['meshes'][0]['primitives'][0]
    p = rig.read_positions(doc, binary)
    root = next(n for n in doc['nodes'] if n.get('name') == 'Shari_level_flight')
    pitch = 2 * np.arctan2(root['rotation'][2], root['rotation'][3])
    c, s = np.cos(pitch), np.sin(pitch)
    world_x = c * p[:, 0] - s * p[:, 1]
    world_y = s * p[:, 0] + c * p[:, 1]
    up_axis = np.array([s, c, 0])

    # Eye centers measured on the textured mesh in the level-flight frame.
    dx = world_x - 0.3480
    dy = world_y - 0.0970
    ellipse = (dx / 0.0115) ** 2 + (dy / 0.0100) ** 2
    eye = (1 - rig.smoothstep(ellipse, 0.85, 2.8)) * rig.smoothstep(abs(p[:, 2]), 0.012, 0.020)
    blink = (-0.985 * dy * eye)[:, None] * up_axis
    blink[:, 2] -= np.sign(p[:, 2]) * 0.0007 * eye

    # Tail base is fixed. Increasing amplitude and spatial phase create a
    # wave travelling toward the feather tips rather than a rigid fan swing.
    t = np.clip((-world_x - 0.015) / 0.43, 0, 1)
    tail = rig.smoothstep(t, 0, 0.22) * (1 - rig.smoothstep(p[:, 0], -0.015, 0.045))
    amplitude = 0.028 * t ** 1.6 * tail
    wave_phase = 2 * np.pi * (0.60 * t + 0.10 * p[:, 2] / 0.18)
    tail_sin = (amplitude * np.cos(wave_phase))[:, None] * up_axis
    tail_cos = (-amplitude * np.sin(wave_phase))[:, None] * up_axis
    fan_amp = 0.010 * t ** 2 * tail
    fan_sin = np.zeros_like(p)
    fan_cos = np.zeros_like(p)
    fan_sin[:, 2] = fan_amp * np.cos(wave_phase * 0.6)
    fan_cos[:, 2] = -fan_amp * np.sin(wave_phase * 0.6)
    targets = [blink, tail_sin, tail_cos, fan_sin, fan_cos]
    names = ['Blink', 'Tail wave sine', 'Tail wave cosine', 'Tail sway sine', 'Tail sway cosine']
    primitive['targets'] = []
    for delta in targets:
        index = rig.append_accessor(doc, binary, delta, 'VEC3', 5126, 34962)
        doc['accessors'][index].update(min=delta.min(axis=0).tolist(), max=delta.max(axis=0).tolist())
        primitive['targets'].append({'POSITION': index})
    doc['meshes'][0]['weights'] = [0] * len(targets)
    doc['meshes'][0].setdefault('extras', {})['targetNames'] = names

    # Repeat the approved 2.4-second wing cycle five times. The longer loop
    # gives blinks varied intervals while retaining a seamless flight loop.
    animation = doc['animations'][0]
    animation['name'] = 'Living flight'
    for sampler in animation['samplers']:
        old_times = read(doc, binary, sampler['input'])[:, 0]
        old_output = read(doc, binary, sampler['output'])
        width = old_output.shape[-1]
        triplets = old_output.reshape(-1, 3, width)
        times = np.concatenate([old_times[:-1] + k * 2.4 for k in range(5)] + [np.array([12.0])])
        values = np.concatenate([triplets[:-1]] * 5 + [triplets[-1:]], axis=0).reshape(-1, width)
        sampler['input'] = rig.append_accessor(doc, binary, times[:, None], 'SCALAR', 5126)
        doc['accessors'][sampler['input']].update(min=[0], max=[12])
        typ = 'VEC4' if width == 4 else 'VEC3'
        sampler['output'] = rig.append_accessor(doc, binary, values, typ, 5126)

    times = np.linspace(0, 12, 721)
    weights = np.zeros((len(times), len(targets)))
    derivatives = np.zeros_like(weights)
    # Quick closure and a slightly slower reopening, with smooth endpoints.
    for center in [1.8, 5.9, 9.5]:
        for start, end, closing in [(center - 0.09, center, True), (center, center + 0.16, False)]:
            active = (times >= start) & (times <= end)
            u = (times[active] - start) / (end - start)
            ease = u * u * (3 - 2 * u)
            rate = 6 * u * (1 - u) / (end - start)
            weights[active, 0] = ease if closing else 1 - ease
            derivatives[active, 0] = rate if closing else -rate
    for i, period, offset in [(1, 2.4, -0.65), (3, 6.0, 0.3)]:
        omega = 2 * np.pi / period
        phase = omega * times + offset
        weights[:, i] = np.sin(phase)
        weights[:, i + 1] = np.cos(phase)
        derivatives[:, i] = omega * np.cos(phase)
        derivatives[:, i + 1] = -omega * np.sin(phase)
    weights[-1] = weights[0]
    derivatives[-1] = derivatives[0]
    cubic = np.stack([derivatives, weights, derivatives], axis=1).reshape(-1, 1)
    time_id = rig.append_accessor(doc, binary, times[:, None], 'SCALAR', 5126)
    doc['accessors'][time_id].update(min=[0], max=[12])
    output = rig.append_accessor(doc, binary, cubic, 'SCALAR', 5126)
    animation['channels'].append({'sampler': len(animation['samplers']), 'target': {'node': 0, 'path': 'weights'}})
    animation['samplers'].append({'input': time_id, 'output': output, 'interpolation': 'CUBICSPLINE'})
    rig.write_glb(destination, doc, binary)
    print(f'{destination}: 3 blinks / 12 seconds; travelling tail wave; {np.count_nonzero(eye > .1)} eyelid vertices')


if __name__ == '__main__':
    build(*sys.argv[1:])
