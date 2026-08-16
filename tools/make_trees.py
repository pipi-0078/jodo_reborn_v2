#!/usr/bin/env python3
"""宝樹3パターンをBlender(bpy)で生成してglb出力する(v3)。

v2からの品質向上:
  - 葉を「描いたテクスチャ」のカードにする(銀杏の葉・針葉の小枝)。図形ではなく絵で見せる
  - 幹・枝に樹皮テクスチャ+法線マップ(tools/make_textures.py で生成)
  - 透過はglb後処理でalphaMode=MASKを付与

使い方: python3 tools/make_textures.py && python3 tools/make_trees.py
出力: public/assets/tree_conifer.glb / tree_broadleaf.glb / tree_weeping.glb
"""
import json
import math
import os
import random
import struct
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")


# ---------------------------------------------------------------- 基盤

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def plain_material(name, color, metallic, roughness, emission=None, emission_strength=0.0):
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


def textured_material(name, image, *, normal=None, metallic, roughness, alpha=False, tile=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, image))
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])

    if tile:
        coords = tree.nodes.new("ShaderNodeTexCoord")
        mapping = tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (tile[0], tile[1], 1)
        tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        vector_out = mapping.outputs["Vector"]
    else:
        vector_out = None

    if normal:
        nimg = tree.nodes.new("ShaderNodeTexImage")
        nimg.image = bpy.data.images.load(os.path.join(TEX, normal))
        nimg.image.colorspace_settings.name = "Non-Color"
        if vector_out is not None:
            tree.links.new(vector_out, nimg.inputs["Vector"])
        nmap = tree.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.9
        tree.links.new(nimg.outputs["Color"], nmap.inputs["Color"])
        tree.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
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


def export(path, leaf_materials=()):
    bpy.ops.export_scene.gltf(filepath=path, export_apply=True)
    if leaf_materials:
        patch_glb(path, leaf_materials)
    print(f"  -> {os.path.relpath(path, ROOT)} ({triangle_count()} tris)")


def patch_glb(path, leaf_materials):
    """葉のマテリアルに alphaMode=MASK と doubleSided を後付けする。"""
    with open(path, "rb") as f:
        magic, version, _length = struct.unpack("<III", f.read(12))
        json_len, _type = struct.unpack("<II", f.read(8))
        gltf = json.loads(f.read(json_len))
        rest = f.read()
    for mat in gltf.get("materials", []):
        if mat.get("name") in leaf_materials:
            mat["alphaMode"] = "MASK"
            mat["alphaCutoff"] = 0.35
            mat["doubleSided"] = True
    payload = json.dumps(gltf, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    with open(path, "wb") as f:
        total = 12 + 8 + len(payload) + len(rest)
        f.write(struct.pack("<III", magic, version, total))
        f.write(struct.pack("<II", len(payload), 0x4E4F534A))
        f.write(payload)
        f.write(rest)


# ---------------------------------------------------------------- 枝(カーブ)

class BranchSet:
    def __init__(self, name):
        self.curve = bpy.data.curves.new(name, "CURVE")
        self.curve.dimensions = "3D"
        self.curve.bevel_depth = 1.0
        self.curve.bevel_resolution = 3
        self.curve.use_fill_caps = True  # Blender 5.0はカーブ→メッシュ変換で自動的にUVが付く

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
    index = min(int(t * (len(points) - 1)), len(points) - 2)
    a, b = points[index], points[index + 1]
    frac = t * (len(points) - 1) - index
    return a.lerp(b, frac), (b - a).normalized()


# ---------------------------------------------------------------- カードの散布(UV付き)

CARD_VERTS = [Vector((-0.5, 0, 0)), Vector((0.5, 0, 0)), Vector((0.5, 1, 0)), Vector((-0.5, 1, 0))]
CARD_FACE = (0, 1, 2, 3)
CARD_UV = [(0, 0), (1, 0), (1, 1), (0, 1)]


def scatter_cards(name, transforms, material):
    verts, faces, uvs = [], [], []
    for matrix in transforms:
        base = len(verts)
        verts.extend(matrix @ v for v in CARD_VERTS)
        faces.append(tuple(i + base for i in CARD_FACE))
        uvs.extend(CARD_UV)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    layer = mesh.uv_layers.new()
    for loop_index, uv in zip(range(len(mesh.loops)), uvs):
        layer.data[loop_index].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    bpy.context.collection.objects.link(obj)
    return obj


def scatter_spheres(name, transforms, material, subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1)
    template = bpy.context.active_object
    verts_t = [v.co.copy() for v in template.data.vertices]
    faces_t = [tuple(p.vertices) for p in template.data.polygons]
    bpy.data.objects.remove(template, do_unlink=True)
    verts, faces = [], []
    for matrix in transforms:
        base = len(verts)
        verts.extend(matrix @ v for v in verts_t)
        faces.extend(tuple(i + base for i in f) for f in faces_t)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    bpy.context.collection.objects.link(obj)
    return obj


def card_transform(position, facing, roll, scale):
    """+Y方向がfacingを向くカードの行列。"""
    quat = Vector((0, 1, 0)).rotation_difference(Vector(facing).normalized())
    quat = quat @ Quaternion((0, 1, 0), roll)
    return Matrix.LocRotScale(position, quat, Vector((scale, scale, scale)))


def bark_material():
    return textured_material("bark", "bark.png", normal="bark_normal.png",
                             metallic=0.55, roughness=0.55, tile=(2.2, 5.0))


# ---------------------------------------------------------------- パターン1: 針葉宝樹

def build_conifer(path):
    reset_scene()
    rand = random.Random(7)
    trunk_mat = bark_material()
    needle_mat = textured_material("needles", "needle.png", metallic=0.35, roughness=0.55, alpha=True)
    hoju_mat = plain_material("hoju", (1.0, 0.9, 0.6), 0.9, 0.15, (1.0, 0.85, 0.5), 2.0)

    branches = BranchSet("conifer")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.03, -0.02, 1)), 7.4, 10, 0.0, 0.015, rand)
    branches.add(trunk_pts, taper(0.24, 0.02, len(trunk_pts)))

    cards = []
    whorls = 8
    for w in range(whorls):
        t = w / (whorls - 1)
        z = 1.0 + t * 5.6
        base, _ = sample(trunk_pts, z / 7.4)
        count = 9 - int(t * 4)
        length = 2.4 * (1 - 0.74 * t) + 0.25
        for b in range(count):
            theta = (b / count) * math.tau + rand.uniform(0, 0.7)
            direction = Vector((math.cos(theta), math.sin(theta), 0.3 - 0.12 * t))
            pts = grow(base, direction, length, 5, droop=0.14, wiggle=0.03, rand=rand)
            branches.add(pts, taper(0.05 * (1 - 0.4 * t), 0.008, len(pts)))
            # 枝に沿って針葉のカードを寝かせて並べる(2枚交差)
            for k in range(4):
                s = 0.3 + 0.7 * (k / 3)
                pos, tangent = sample(pts, s)
                size = (0.95 - 0.5 * t) * (1.05 - 0.35 * s)
                for roll in (0.0, math.pi / 2):
                    jitter = rand.uniform(-0.25, 0.25)
                    cards.append(card_transform(pos - tangent * size * 0.15, tangent, roll + jitter, size))
    # 頂の穂
    top = trunk_pts[-1]
    for roll in (0.0, math.pi / 2):
        cards.append(card_transform(top - Vector((0, 0, 0.1)), Vector((0, 0, 1)), roll, 1.0))
    scatter_cards("foliage", cards, needle_mat)
    branches.realize(trunk_mat)
    scatter_spheres("hoju", [Matrix.LocRotScale(top + Vector((0, 0, 1.2)), Quaternion(), Vector((0.2, 0.2, 0.27)))],
                    hoju_mat, subdivisions=2)

    export(path, leaf_materials={"needles"})


# ---------------------------------------------------------------- パターン2: 金葉樹(銀杏)

def build_broadleaf(path):
    reset_scene()
    rand = random.Random(11)
    trunk_mat = bark_material()
    leaf_mat = textured_material("ginkgo", "ginkgo.png", metallic=0.75, roughness=0.4, alpha=True)

    branches = BranchSet("broadleaf")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.06, 0.03, 1)), 4.4, 8, 0.0, 0.03, rand)
    branches.add(trunk_pts, taper(0.3, 0.1, len(trunk_pts)))

    cards = []

    def leaves_at(position, count, size):
        for _ in range(count):
            offset = Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), rand.uniform(-1, 1))) * 0.3
            facing = Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), rand.uniform(-1.2, 0.4))).normalized()
            cards.append(card_transform(position + offset, facing, rand.uniform(0, math.tau),
                                        size * rand.uniform(0.75, 1.3)))

    primaries = 9
    for b in range(primaries):
        t_attach = min(0.5 + 0.5 * (b / (primaries - 1)) * 0.96, 1.0)
        base, _ = sample(trunk_pts, t_attach)
        theta = (b / primaries) * math.tau + rand.uniform(0, 0.8)
        direction = Vector((math.cos(theta), math.sin(theta), rand.uniform(0.5, 1.0)))
        length = rand.uniform(2.2, 3.0) * (1 - 0.25 * (t_attach - 0.5))
        pts = grow(base, direction, length, 7, droop=0.05, wiggle=0.05, rand=rand, up_pull=0.02)
        branches.add(pts, taper(0.085, 0.015, len(pts)))
        for _ in range(4):
            s = rand.uniform(0.4, 0.92)
            start, tangent = sample(pts, s)
            side = tangent.cross(Vector((0, 0, 1))).normalized()
            direction2 = (tangent * 0.5 + side * rand.uniform(-1, 1)
                          + Vector((0, 0, rand.uniform(0.05, 0.45)))).normalized()
            pts2 = grow(start, direction2, rand.uniform(0.8, 1.4), 4, droop=0.07, wiggle=0.06, rand=rand)
            branches.add(pts2, taper(0.028, 0.007, len(pts2)))
            for k in range(4):
                pos, _tan = sample(pts2, 0.3 + 0.7 * (k / 3))
                leaves_at(pos, count=7, size=0.34)
        tip_pos, _tt = sample(pts, 1.0)
        leaves_at(tip_pos, count=10, size=0.36)

    scatter_cards("foliage", cards, leaf_mat)
    branches.realize(trunk_mat)
    export(path, leaf_materials={"ginkgo"})


# ---------------------------------------------------------------- パターン3: 垂宝樹(数珠の柳)

def build_weeping(path):
    reset_scene()
    rand = random.Random(31)
    trunk_mat = bark_material()
    jewel_mat = plain_material("jewel", (1.0, 0.95, 0.75), 0.6, 0.1, (1.0, 0.9, 0.6), 2.2)
    leaf_mat = textured_material("ginkgo", "ginkgo.png", metallic=0.75, roughness=0.4, alpha=True)

    branches = BranchSet("weeping")
    trunk_pts = grow(Vector((0, 0, 0)), Vector((0.08, -0.04, 1)), 5.6, 8, 0.0, 0.03, rand)
    branches.add(trunk_pts, taper(0.26, 0.06, len(trunk_pts)))

    beads = []
    cards = []
    primaries = 9
    for b in range(primaries):
        base, _ = sample(trunk_pts, 0.72 + 0.28 * ((b * 5) % primaries) / (primaries - 1))
        theta = (b / primaries) * math.tau + rand.uniform(0, 0.35)
        direction = Vector((math.cos(theta), math.sin(theta), rand.uniform(0.55, 0.8)))
        pts = grow(base, direction, rand.uniform(1.5, 2.1), 5, droop=0.11, wiggle=0.04, rand=rand)
        branches.add(pts, taper(0.05, 0.014, len(pts)))
        for _ in range(6):
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
            branches.add(strand_pts, taper(0.016, 0.006, len(strand_pts)))
            # 房の上半分に小さな金の葉、下半分に数珠
            for k in range(3):
                pos, tan = sample(strand_pts, 0.12 + 0.3 * (k / 2))
                facing = Vector((rand.uniform(-1, 1), rand.uniform(-1, 1), -0.8)).normalized()
                cards.append(card_transform(pos, facing, rand.uniform(0, math.tau), 0.2))
            for k in range(5):
                u = 0.5 + 0.5 * (k / 4)
                pos, _ = sample(strand_pts, u)
                r = 0.048 if k < 4 else 0.08
                beads.append(Matrix.LocRotScale(pos, Quaternion(), Vector((r, r, r))))

    scatter_spheres("jewels", beads, jewel_mat)
    scatter_cards("foliage", cards, leaf_mat)
    branches.realize(trunk_mat)
    export(path, leaf_materials={"ginkgo"})


if __name__ == "__main__":
    build_conifer(os.path.join(OUT_DIR, "tree_conifer.glb"))
    build_broadleaf(os.path.join(OUT_DIR, "tree_broadleaf.glb"))
    build_weeping(os.path.join(OUT_DIR, "tree_weeping.glb"))
    print("done", file=sys.stderr)
