"""Pose the generated head and feet for level flight before applying body pitch.

The source is an already rigged GLB. Only the mesh rest pose is changed; wing
joint positions and animation tracks stay intact.
"""

import sys
from pathlib import Path

import numpy as np

from importlib.machinery import SourceFileLoader

rig = SourceFileLoader('flight_rig', str(Path(__file__).with_name('build-articulated-flight.py'))).load_module()


def accessor_array(doc, binary, name):
    primitive = doc['meshes'][0]['primitives'][0]
    accessor = doc['accessors'][primitive['attributes'][name]]
    view = doc['bufferViews'][accessor['bufferView']]
    assert accessor['componentType'] == 5126 and 'byteStride' not in view
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    return np.frombuffer(binary, dtype='<f4', count=accessor['count'] * 3,
                         offset=offset).reshape(-1, 3), accessor


def rotate_z(points, angle):
    c, s = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    result = points.copy()
    result[:, 0] = c * points[:, 0] - s * points[:, 1]
    result[:, 1] = s * points[:, 0] + c * points[:, 1]
    return result


def refine(source, destination):
    doc, binary = rig.unpack(source)
    positions, pos_accessor = accessor_array(doc, binary, 'POSITION')
    normals, _ = accessor_array(doc, binary, 'NORMAL')
    original = positions.copy()
    original_normals = normals.copy()

    # The generated neck rises from the breast. Counter-rotate the head so
    # its beak faces forward after the entire body pitches down 45 degrees.
    neck_pivot = np.array([0.17, 0.16, 0], dtype=np.float32)
    head_mask = (rig.smoothstep(original[:, 0], 0.17, 0.225)
                 * rig.smoothstep(original[:, 1], 0.12, 0.20)
                 * (1 - rig.smoothstep(abs(original[:, 2]), 0.05, 0.095)))
    head_rotated = rotate_z(original - neck_pivot, 39) + neck_pivot
    positions[:] = original + head_mask[:, None] * (head_rotated - original)
    head_normals = rotate_z(original_normals, 39)
    normals[:] = original_normals + head_mask[:, None] * (head_normals - original_normals)

    # Bring the feet toward the tail, tucked against the belly. Keep the hip
    # attachment stable and blend the lower legs into the pose.
    hip_pivot = np.array([0.145, -0.055, 0], dtype=np.float32)
    foot_mask = (rig.smoothstep(-original[:, 1], 0.065, 0.125)
                 * rig.smoothstep(original[:, 0], 0.075, 0.14)
                 * (1 - rig.smoothstep(abs(original[:, 2]), 0.055, 0.11)))
    feet_rotated = rotate_z(original - hip_pivot, -65) + hip_pivot
    positions[:] += foot_mask[:, None] * (feet_rotated - original)
    foot_normals = rotate_z(original_normals, -65)
    normals[:] += foot_mask[:, None] * (foot_normals - original_normals)
    normals[:] /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)

    pos_accessor['min'] = positions.min(axis=0).tolist()
    pos_accessor['max'] = positions.max(axis=0).tolist()
    rig.write_glb(destination, doc, binary)
    print(f'{destination}: head and feet posed for level flight')


if __name__ == '__main__':
    refine(*sys.argv[1:])
