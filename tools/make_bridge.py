#!/usr/bin/env python3
"""金の反橋(そりばし)をBlender(bpy)で生成してglb出力する。

参照: docs/reference_concept.png(金の欄干+灯籠+瑠璃の差し色)

構成:
  - 緩やかに反るデッキ(金の敷石テクスチャ)と側桁
  - 欄干: 親柱に擬宝珠(ぎぼし)、細い束(スピンドル)、金の手すり、瑠璃の中桟
  - 四隅の灯籠(ほのかに発光)
  - 水中への支柱4本

使い方: python3 tools/make_textures.py && python3 tools/make_bridge.py
出力: public/assets/bridge.glb(全長8m・幅2.4m・反り高1.1m)
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402

SPAN = 8.0
RISE = 1.1
WIDTH = 2.4
RADIUS = 0.0
HALF_ANGLE = 0.0


def configure(span, rise, width):
    """橋の寸法を設定する(池の幅に合わせて架け替えるため)。"""
    global SPAN, RISE, WIDTH, RADIUS, HALF_ANGLE
    SPAN, RISE, WIDTH = span, rise, width
    RADIUS = (SPAN * SPAN) / (8 * RISE) + RISE / 2  # 反りの円弧半径
    HALF_ANGLE = math.asin((SPAN / 2) / RADIUS)


configure(SPAN, RISE, WIDTH)

GOLD = (0.85, 0.62, 0.2)
LAPIS = (0.16, 0.3, 0.78)


def arc_point(t):
    """t: 0..1 で橋の端から端まで。位置と接線方向を返す。"""
    phi = -HALF_ANGLE + 2 * HALF_ANGLE * t
    x = RADIUS * math.sin(phi)
    z = RADIUS * math.cos(phi) - (RADIUS - RISE)
    tangent = Vector((math.cos(phi), 0, -math.sin(phi)))
    return Vector((x, 0, z)), tangent


def paving_material():
    mat = bpy.data.materials.new("paving")
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.45
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, "paving.png"))
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (4, 1.2, 1)
    tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    return mat


def grid_strip(name, points_rows, material, thickness):
    """点列の行(row)を並べた帯メッシュ。solidifyで厚みを付ける。"""
    verts = []
    uvs_grid = []
    rows = len(points_rows)
    cols = len(points_rows[0])
    for i, row in enumerate(points_rows):
        for j, p in enumerate(row):
            verts.append(p)
            uvs_grid.append((i / (rows - 1), j / (cols - 1)))
    faces = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            faces.append((a, a + 1, a + cols + 1, a + cols))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    layer = mesh.uv_layers.new()
    for poly in mesh.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            layer.data[li].uv = uvs_grid[mesh.loops[li].vertex_index]
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("solidify", "SOLIDIFY")
    solidify.thickness = thickness
    obj.data.materials.append(material)
    return obj


def box_at(name, location, size, material, rotation=None):
    # size=1の立方体は±0.5なので、倍率=そのままの寸法で正しい大きさになる
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    if rotation:
        obj.rotation_euler = rotation
    obj.data.materials.append(material)
    return obj


def giboshi(location, material, scale=1.0):
    """擬宝珠: 台座+首+玉ねぎ型の宝珠。"""
    x, y, z = location
    box_at("plinth", (x, y, z + 0.03 * scale), (0.17 * scale, 0.17 * scale, 0.06 * scale), material)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055 * scale, depth=0.05 * scale,
                                        location=(x, y, z + 0.085 * scale))
    bpy.context.active_object.data.materials.append(material)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.075 * scale,
                                         location=(x, y, z + 0.175 * scale))
    onion = bpy.context.active_object
    onion.scale = (1, 1, 1.25)
    bpy.ops.object.shade_smooth()
    onion.data.materials.append(material)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.028 * scale, radius2=0.0, depth=0.07 * scale,
                                    location=(x, y, z + 0.29 * scale))
    tip = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    tip.data.materials.append(material)


def lantern(location, gold_mat, glow_mat):
    """灯籠: 柱+火袋(発光)+笠+宝珠。"""
    x, y, z = location
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.05, depth=1.1, location=(x, y, z + 0.55))
    bpy.context.active_object.data.materials.append(gold_mat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.14, depth=0.26, location=(x, y, z + 1.23))
    firebox = bpy.context.active_object
    firebox.data.materials.append(glow_mat)
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.2, radius2=0.03, depth=0.16, location=(x, y, z + 1.42))
    roof = bpy.context.active_object
    roof.data.materials.append(gold_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.045, location=(x, y, z + 1.52))
    hoju = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    hoju.data.materials.append(gold_mat)


def build_bridge(path):
    reset_scene()
    deck_mat = paving_material()
    gold_mat = plain_material("gold", GOLD, 0.92, 0.28)
    lapis_mat = plain_material("lapis", LAPIS, 0.35, 0.22, (0.05, 0.1, 0.4), 0.4)
    glow_mat = plain_material("glow", (1.0, 0.92, 0.7), 0.1, 0.4, (1.0, 0.85, 0.55), 2.6)

    steps = 32
    BASE = -0.55  # 基礎の底面(据え付け時に水面下へ沈む深さ)

    # デッキ(反りに沿った帯)
    rows = []
    for i in range(steps + 1):
        p, _ = arc_point(i / steps)
        rows.append([Vector((p.x, -WIDTH / 2, p.z)), Vector((p.x, WIDTH / 2, p.z))])
    grid_strip("deck", rows, deck_mat, 0.09)

    # 側桁(両側の帯)。デッキの縁に重ねて一体に見せる
    for side in (-1, 1):
        y = side * (WIDTH / 2 - 0.01)
        rows = []
        for i in range(steps + 1):
            p, _ = arc_point(i / steps)
            rows.append([Vector((p.x, y, p.z - 0.2)), Vector((p.x, y, p.z + 0.15))])
        grid_strip("girder", rows, gold_mat, 0.13)

    # 橋台(たもとの土台): デッキ両端をしっかり上に載せ、灯籠もこの上に立つ
    abutment_tops = {}
    for sx in (-1, 1):
        x = sx * (SPAN / 2 - 0.1)  # デッキ端が橋台の上に半分以上載るよう内側へ
        top = 0.05
        box_at("abutment", (x, 0, (top + BASE) / 2), (1.4, WIDTH + 1.3, top - BASE), gold_mat)
        abutment_tops[sx] = top

    # 欄干
    posts = max(9, int(SPAN / 1.0) | 1)
    rail_height = 0.88
    for side in (-1, 1):
        y = side * (WIDTH / 2 - 0.05)
        for k in range(posts):
            t = k / (posts - 1)
            p, _ = arc_point(t)
            major = k % 2 == 0  # 親柱は1本おき
            height = 1.02 if major else rail_height
            size = 0.11 if major else 0.08
            box_at("post", (p.x, y, p.z + height / 2), (size, size, height), gold_mat)
            if major:
                giboshi((p.x, y, p.z + height), gold_mat)
            # 束(スピンドル): 柱間に3本、手すりの高さまで届かせる
            if k < posts - 1:
                for s in range(1, 4):
                    tt = t + (s / 4) * (1 / (posts - 1))
                    pp, _ = arc_point(tt)
                    # 手すりの芯まで届かせて、頭を軸の中に埋める
                    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=rail_height,
                                                        location=(pp.x, y, pp.z + rail_height / 2))
                    bpy.context.active_object.data.materials.append(gold_mat)
        # 手すり(金)と中桟(瑠璃)。弧を密にサンプリングしてぴったり沿わせる
        for z_off, radius, mat in ((rail_height, 0.05, gold_mat), (rail_height * 0.55, 0.028, lapis_mat)):
            curve = bpy.data.curves.new("rail", "CURVE")
            curve.dimensions = "3D"
            curve.bevel_depth = radius
            curve.bevel_resolution = 4
            curve.use_fill_caps = True
            spline = curve.splines.new("POLY")
            samples = 32
            spline.points.add(samples)
            for i in range(samples + 1):
                p, _ = arc_point(i / samples)
                spline.points[i].co = (p.x, y, p.z + z_off, 1)
            obj = bpy.data.objects.new("rail", curve)
            bpy.context.collection.objects.link(obj)
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target="MESH")
            rail = bpy.context.active_object
            rail.data.materials.append(mat)
            bpy.ops.object.shade_smooth()

    # 四隅の灯籠(橋台の上、欄干の延長線上に立てる)
    for sx in (-1, 1):
        for sy in (-1, 1):
            lantern((sx * (SPAN / 2 - 0.1), sy * (WIDTH / 2 + 0.32), abutment_tops[sx]), gold_mat, glow_mat)

    # 水中への支柱(底面は橋台と同じ深さに揃え、上端はデッキ裏へ差し込む)
    for sx in (-1, 1):
        p, _ = arc_point(0.5 + sx * 0.28)
        depth = p.z - BASE
        for sy in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.11, depth=depth,
                                                location=(p.x, sy * (WIDTH / 2 - 0.12), (p.z + BASE) / 2))
            bpy.context.active_object.data.materials.append(gold_mat)

    export(path)


if __name__ == "__main__":
    configure(8.0, 1.1, 2.4)
    build_bridge(os.path.join(OUT_DIR, "bridge.glb"))
    # 池の四方に架ける長橋(中島r=10 → 岸r=30 を跨ぐ)
    configure(22.0, 2.6, 3.0)
    build_bridge(os.path.join(OUT_DIR, "bridge_long.glb"))
    print("done", file=sys.stderr)
