"""Replace v4's tilted stroke and stop/start key poses with a vertical cycle.

All wing joints rotate about world X, expressed in their pitched parent's
coordinates. Consequently wing vertices have no fore/aft displacement.
Analytic periodic curves and their derivatives are baked as glTF CUBICSPLINE.
"""
import math
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader

import numpy as np

rig = SourceFileLoader('flight_rig', str(Path(__file__).with_name('build-articulated-flight.py'))).load_module()


def build(source, destination):
    doc, binary = rig.unpack(source)
    parent = next(i for i, n in enumerate(doc['nodes']) if n.get('name') == 'Shari_level_flight')
    rotation = doc['nodes'][parent]['rotation']
    pitch = 2 * math.atan2(rotation[2], rotation[3])
    # Inverse parent rotation applied to the world horizontal forward axis.
    axis = np.array([math.cos(pitch), -math.sin(pitch), 0.0])
    duration = 2.4
    times = np.linspace(0, duration, 145)
    omega = 2 * math.pi / duration
    phase = omega * times
    up = np.maximum(-np.sin(phase), 0)
    fold = up ** 4
    fold_rate = -4 * up ** 3 * np.cos(phase) * omega
    angles = [58 * np.cos(phase), 26 * fold, 20 * fold]
    rates = [-58 * np.sin(phase) * omega, 26 * fold_rate, 20 * fold_rate]
    time_id = rig.append_accessor(doc, binary, times[:, None], 'SCALAR', 5126)
    doc['accessors'][time_id].update(min=[0], max=[duration])
    animation = {'name': 'Vertical smooth flight', 'samplers': [], 'channels': []}

    def channel(node, path, values, derivatives, typ):
        # Make both pose and velocity identical at the loop seam.
        values[-1] = values[0]
        derivatives[-1] = derivatives[0]
        cubic = np.stack([derivatives, values, derivatives], axis=1).reshape(-1, values.shape[-1])
        output = rig.append_accessor(doc, binary, cubic, typ, 5126)
        animation['channels'].append({'sampler': len(animation['samplers']),
                                      'target': {'node': node, 'path': path}})
        animation['samplers'].append({'input': time_id, 'output': output,
                                     'interpolation': 'CUBICSPLINE'})

    for side, label in [(1, 'left'), (-1, 'right')]:
        for joint, angle, rate in zip(['shoulder', 'elbow', 'wrist'], angles, rates):
            node = next(i for i, n in enumerate(doc['nodes']) if n.get('name') == f'{label}_{joint}')
            half = np.deg2rad(-side * angle) / 2
            half_rate = np.deg2rad(-side * rate) / 2
            values = np.column_stack([np.sin(half)[:, None] * axis, np.cos(half)])
            derivatives = np.column_stack([np.cos(half)[:, None] * half_rate[:, None] * axis,
                                            -np.sin(half) * half_rate])
            channel(node, 'rotation', values, derivatives, 'VEC4')

    bob = np.zeros((len(times), 3))
    velocity = np.zeros_like(bob)
    bob[:, 1] = 0.005 * (np.sin(phase - 0.45) - math.sin(-0.45))
    velocity[:, 1] = 0.005 * np.cos(phase - 0.45) * omega
    channel(parent, 'translation', bob, velocity, 'VEC3')
    doc['animations'] = [animation]
    rig.write_glb(destination, doc, binary)
    print(f'{destination}: world-horizontal flap axis {axis.tolist()}, {duration}s periodic cubic cycle')


if __name__ == '__main__':
    build(*sys.argv[1:])
