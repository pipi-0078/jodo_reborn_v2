#!/usr/bin/env python3
"""宝樹3パターンをBlender(bpy)で生成してglb出力する(v2)。

v1の反省: 円錐や球のプリミティブを積むだけではthree.jsの手続き生成と大差なかった。
v2はBlenderらしい作り方に全面刷新:
  - 幹・枝はNURBSカーブ+点ごとの半径テーパー(自然な先細り・うねり・重力の垂れ)
  - 葉は枝先に数百枚を散布(金貨状の葉・針葉の房・数珠の飾り)

使い方: python3 tools/make_trees.py
出力: public/assets/tree_conifer.glb / tree_broadleaf.glb / tree_weeping.glb
前提: pip install bpy (Blender 5.x ヘッドレス)
"""
import math
import random
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

OUT_DIR = "public/assets"

GOLD_TRUNK = (0.5, 0.34, 0.11)
GOLD_LEAF = (1.0, 0.72, 0.24)
PALE_LEAF = (0.92, 0.9, 0.85)  # 実行時に四宝の色を乗せられる明るい葉


# ---------------------------------------------------------------- 基盤

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, color, metallic, roughness, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def triangle_count():
    total = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            mesh = obj.evaluated_get(depsgraph).to_mesh()
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
    return total


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_apply=True)
    print(f"  -> {path} ({triangle_count()} tris)")


# ---------------------------------------------------------------- 枝(カーブ)

class BranchSet:
    """1本の木の枝群。NURBSスプラインの集合として持ち、最後にメッシュ化する。"""

    def __init__(self, name):
        self.curve = bpy.data.curves.new(name, "CURVE")
        self.curve.dimensions = "3D"
        self.curve.bevel_depth = 1.0  # 実半径は点ごとのradiusで決める
        self.curve.bevel_resolution = 4
        self.curve.use_fill_caps = True

    def add(self, points, radii):
        spline = self.curve.splines.new("NURBS")
        spline.points.add(len(points) - 1)
        for pt, p, r in zip(spline.points, points, radii):
            pt.co = (p.x, p.y, p.z, 1)
            pt.radius = r
        spline.use_endpoint_u = True

    def realize(self, material):
        obj = bpy.data.objects.new(self.curve.name, self.curve)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        mesh_obj = bpy.context.active_object
        mesh_obj.data.materials.append(material)
        bpy.ops.object.shade_smooth()
        return mesh_obj


def grow(start, direction, length, segments, droop, wiggle, rand, up_pull=0.0):
    """1本の枝の背骨を伸ばす。重力の垂れ(droop)と揺らぎ(wiggle)、上向きの引き(up_pull)。"""
    points = [Vector(start)]
    d = Vector(direction).normalized()
    step = length / segments
    for _ in range(segments):
        jitter = Vector((rand.uniform(-1, 1) * wiggle, rand.uniform(-1, 1) * wiggle, 0))
        d = (d + jitter + Vector((0, 0, up_pull - droop))).normalized()
        points.append(points[-1] + d * step)
    return points


def taper(r0, r1, count):
    return [r0 + (r1 - r0) * (i / (count - 1)) for i in range(count)]


def sample(points, t):
    """背骨上の位置tの座標と進行方向を返す。"""
    index = min(int(t * (len(points) - 1)), len(points) - 2)
    a, b = points[index], points[index + 1]
    frac = t * (len(points) - 1) - index
    return a.lerp(b, frac), (b - a).normalized()


# ---------------------------------------------------------------- 葉の散布

def template_pydata(create_op, **kwargs):
    create_op(**kwargs)
    obj = bpy.context.active_object
    verts = [v.co.copy() for v in obj.data.vertices]
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    bpy.data.objects.remove(obj, do_unlink=True)
    return verts, faces


def scatter(name, verts, faces, transforms, material, smooth=True):
    all_verts, all_faces = [], []
    for matrix in transforms:
        base = len(all_verts)
        all_verts.extend(matrix @ v for v in verts)
        all_faces.extend(tuple(i + base for i in f) for f in faces)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(all_verts, [], all_faces)
    mesh.validate()
    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    bpy.context.collection.objects.link(obj)
    return obj


def orient(direction):
    return Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized())


def transform_at(location, rotation, scale):
    return Matrix.LocRotScale(location, rotation, Vector(scale))


# ---------------------------------------------------------------- パターン1: 針葉宝樹

def build_conifer(path):
    reset_scene()
    rand = random.Random(7)
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    leaf_mat = make_material("foliage", PALE_LEAF, 0.4, 0.5)
    hoju_mat = make_material("hoju", (1.0, 0.9, 0.6), 0.9, 0.15, (1.0, 0.85, 0.5), 2.0)

    branches = BranchSet("conifer")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.03, -0.02, 1)), 7.4, 10, 0.0, 0.015, rand)
    branches.add(trunk_pts, taper(0.24, 0.03, len(trunk_pts)))

    tuft_verts, tuft_faces = template_pydata(bpy.ops.mesh.primitive_ico_sphere_add, subdivisions=1, radius=1)
    tufts = []

    whorls = 7
    for w in range(whorls):
        t = w / (whorls - 1)
        z = 1.1 + t * 5.2
        base, _ = sample(trunk_pts, z / 7.4)
        count = 8 - int(t * 3)
        length = 2.5 * (1 - 0.72 * t) + 0.3
        for b in range(count):
            theta = (b / count) * math.tau + rand.uniform(0, 0.7)
            direction = Vector((math.cos(theta), math.sin(theta), 0.28 - 0.1 * t))
            pts = grow(base, direction, length, 6, droop=0.13, wiggle=0.03, rand=rand)
            branches.add(pts, taper(0.055 * (1 - 0.4 * t), 0.012, len(pts)))
            # 枝に沿って針葉の房を伏せる
            for k in range(5):
                s = 0.25 + 0.75 * (k / 4)
                pos, tangent = sample(pts, s)
                size = 0.5 * (1 - 0.35 * t) * (1 - 0.3 * s + 0.3)
                rot = orient(tangent)
                tufts.append(transform_at(pos, rot, (size * 0.5, size * 0.5, size * 1.1)))
    # 頂の房と宝珠
    top = trunk_pts[-1]
    tufts.append(transform_at(top + Vector((0, 0, 0.18)), Quaternion(), (0.28, 0.28, 0.62)))
    scatter("foliage", tuft_verts, tuft_faces, tufts, leaf_mat)
    branches.realize(trunk_mat)

    hoju_verts, hoju_faces = template_pydata(
        bpy.ops.mesh.primitive_uv_sphere_add, segments=20, ring_count=12, radius=0.2)
    scatter("hoju", hoju_verts, hoju_faces,
            [transform_at(top + Vector((0, 0, 0.95)), Quaternion(), (1, 1, 1.35))], hoju_mat)

    export(path)


# ---------------------------------------------------------------- パターン2: 金葉樹(銀杏の金貨)

def build_broadleaf(path):
    reset_scene()
    rand = random.Random(11)
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    leaf_mat = make_material("foliage", GOLD_LEAF, 0.95, 0.3)

    branches = BranchSet("broadleaf")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.06, 0.03, 1)), 4.6, 8, 0.0, 0.03, rand)
    branches.add(trunk_pts, taper(0.3, 0.1, len(trunk_pts)))

    coin_verts, coin_faces = template_pydata(bpy.ops.mesh.primitive_cylinder_add, vertices=10, radius=1, depth=0.1)
    coins = []

    def leaves_at(position, tangent, count, size):
        for _ in range(count):
            offset = Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), rand.uniform(-1, 1))) * 0.34
            rot = Quaternion(
                Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), rand.uniform(-1, 1))).normalized(),
                rand.uniform(0, math.tau))
            s = size * rand.uniform(0.75, 1.25)
            coins.append(transform_at(position + tangent * 0.1 + offset, rot, (s, s, s)))

    primaries = 8
    for b in range(primaries):
        t_attach = 0.5 + 0.5 * (b / (primaries - 1)) * 0.95
        base, _ = sample(trunk_pts, min(t_attach, 1.0))
        theta = (b / primaries) * math.tau + rand.uniform(0, 0.8)
        direction = Vector((math.cos(theta), math.sin(theta), rand.uniform(0.55, 1.0)))
        length = rand.uniform(2.1, 3.0) * (1 - 0.25 * (t_attach - 0.5))
        pts = grow(base, direction, length, 7, droop=0.05, wiggle=0.05, rand=rand, up_pull=0.02)
        branches.add(pts, taper(0.09, 0.018, len(pts)))
        # 二次枝と葉
        for _ in range(3):
            s = rand.uniform(0.45, 0.9)
            start, tangent = sample(pts, s)
            side = tangent.cross(Vector((0, 0, 1))).normalized()
            direction2 = (tangent * 0.5 + side * rand.uniform(-1, 1) + Vector((0, 0, rand.uniform(0.1, 0.5)))).normalized()
            pts2 = grow(start, direction2, rand.uniform(0.8, 1.4), 4, droop=0.06, wiggle=0.06, rand=rand)
            branches.add(pts2, taper(0.03, 0.008, len(pts2)))
            for k in range(4):
                pos, tan = sample(pts2, 0.35 + 0.65 * (k / 3))
                leaves_at(pos, tan, count=5, size=0.16)
        tip_pos, tip_tan = sample(pts, 1.0)
        leaves_at(tip_pos, tip_tan, count=8, size=0.17)

    scatter("foliage", coin_verts, coin_faces, coins, leaf_mat, smooth=False)
    branches.realize(trunk_mat)
    export(path)


# ---------------------------------------------------------------- パターン3: 垂宝樹(数珠の柳)

def build_weeping(path):
    reset_scene()
    rand = random.Random(31)
    trunk_mat = make_material("trunk", GOLD_TRUNK, 0.85, 0.45)
    strand_mat = make_material("strand", GOLD_LEAF, 0.9, 0.3)
    jewel_mat = make_material("jewel", (1.0, 0.95, 0.75), 0.6, 0.1, (1.0, 0.9, 0.6), 2.2)

    branches = BranchSet("weeping")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.08, -0.04, 1)), 5.6, 8, 0.0, 0.03, rand)
    branches.add(trunk_pts, taper(0.26, 0.07, len(trunk_pts)))

    bead_verts, bead_faces = template_pydata(bpy.ops.mesh.primitive_ico_sphere_add, subdivisions=1, radius=1)
    beads = []

    primaries = 6
    for b in range(primaries):
        base, _ = sample(trunk_pts, rand.uniform(0.75, 1.0))
        theta = (b / primaries) * math.tau + rand.uniform(0, 0.9)
        direction = Vector((math.cos(theta), math.sin(theta), rand.uniform(0.5, 0.9)))
        pts = grow(base, direction, rand.uniform(1.4, 2.0), 5, droop=0.1, wiggle=0.04, rand=rand)
        branches.add(pts, taper(0.06, 0.02, len(pts)))
        # 各枝から数珠の房を垂らす
        for _ in range(7):
            s = rand.uniform(0.3, 1.0)
            start, _tangent = sample(pts, s)
            out = Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), 0)).normalized() * 0.22
            length = rand.uniform(2.0, 3.4)
            strand_pts = []
            for step in range(9):
                u = step / 8
                sway = out * math.sin(u * math.pi * 0.5)
                drop = Vector((0, 0, -1)) * (u ** 1.7) * length
                strand_pts.append(start + sway + drop)
            branches.add(strand_pts, taper(0.02, 0.008, len(strand_pts)))
            # 房に数珠を通す(下半分に密に)
            for k in range(6):
                u = 0.45 + 0.55 * (k / 5)
                pos, _ = sample(strand_pts, u)
                r = 0.05 if k < 5 else 0.085  # 末端はひと回り大きな親玉
                beads.append(transform_at(pos, Quaternion(), (r, r, r)))

    scatter("jewels", bead_verts, bead_faces, beads, jewel_mat)
    branches.realize(trunk_mat)
    # 幹・枝・房は同じマテリアルだが、房の金色を強調するため全体をstrand色に寄せる
    export(path)


if __name__ == "__main__":
    build_conifer(f"{OUT_DIR}/tree_conifer.glb")
    build_broadleaf(f"{OUT_DIR}/tree_broadleaf.glb")
    build_weeping(f"{OUT_DIR}/tree_weeping.glb")
    print("done", file=sys.stderr)
