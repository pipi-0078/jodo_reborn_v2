#!/usr/bin/env python3
"""七宝楼閣をBlender(bpy)で生成してglb出力する。

「上有樓閣 亦以金銀瑠璃玻瓈硨磲赤珠碼碯 而嚴飾之」

構成(z-up、正面=+x):
  基壇二段(碼碯の縞装飾)/背面に幅広の階段(銀の縁)
  一階の開放列柱(硨磲の柱頭・玻瓈の床飾り)/露台と半透明欄干
  中央主楼(玻瓈の壁・瑠璃の反り屋根二層・宝珠)
  左右の小楼と回廊/正面の水上舞台/組物・赤珠の垂れ飾り

使い方: python3 tools/make_textures.py && python3 tools/make_pavilion.py
出力: public/assets/pavilion.glb
"""
import json
import math
import os
import struct
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_bridge import box_at, grid_strip  # noqa: E402

# 七宝の質感設定(色, metallic, roughness, 発光色, 発光強さ)
SHIPPO = {
    "gold":   ((0.85, 0.62, 0.20), 0.90, 0.30, (0.45, 0.30, 0.08), 0.18),
    "silver": ((0.88, 0.90, 0.94), 0.95, 0.25, None, 0.0),
    "ruri":   ((0.10, 0.20, 0.55), 0.30, 0.30, (0.03, 0.07, 0.25), 0.35),  # 瑠璃
    "shako":  ((0.93, 0.90, 0.84), 0.20, 0.35, (0.30, 0.28, 0.24), 0.15),  # 硨磲
    "shuju":  ((0.75, 0.10, 0.12), 0.30, 0.20, (0.50, 0.05, 0.05), 0.80),  # 赤珠
    "stone":  ((0.88, 0.82, 0.68), 0.30, 0.50, None, 0.0),
}


def mat_of(key):
    color, metal, rough, emissive, strength = SHIPPO[key]
    return plain_material(key, color, metal, rough, emissive, strength)


def hari_material():
    """玻瓈: 半透明の水晶。glb後処理でBLENDにする。"""
    mat = bpy.data.materials.new("hari")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 0.93, 0.98, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.1
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Alpha"].default_value = 0.32
    return mat


def textured(name, image, *, normal=None, metallic, roughness, tile=None):
    """画像+法線マップ付きマテリアル。tileで文様の繰り返し数を指定。"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, image))
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    vector_out = None
    if tile:
        coords = tree.nodes.new("ShaderNodeTexCoord")
        mapping = tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (tile[0], tile[1], 1)
        tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        vector_out = mapping.outputs["Vector"]
    if normal:
        nimg = tree.nodes.new("ShaderNodeTexImage")
        nimg.image = bpy.data.images.load(os.path.join(TEX, normal))
        nimg.image.colorspace_settings.name = "Non-Color"
        if vector_out is not None:
            tree.links.new(vector_out, nimg.inputs["Vector"])
        nmap = tree.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 1.0
        tree.links.new(nimg.outputs["Color"], nmap.inputs["Color"])
        tree.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def patch_blend(path, names):
    """指定マテリアルを半透明(BLEND)にする後処理。"""
    with open(path, "rb") as f:
        magic, version, _ = struct.unpack("<III", f.read(12))
        jlen, _ = struct.unpack("<II", f.read(8))
        g = json.loads(f.read(jlen))
        rest = f.read()
    for m in g.get("materials", []):
        if m.get("name") in names:
            m["alphaMode"] = "BLEND"
            m["doubleSided"] = True
    payload = json.dumps(g, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", magic, version, 12 + 8 + len(payload) + len(rest)))
        f.write(struct.pack("<II", len(payload), 0x4E4F534A))
        f.write(payload)
        f.write(rest)


def cyl(location, radius, depth, material, vertices=14, rotation=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.active_object
    if rotation:
        obj.rotation_euler = rotation
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def torus(location, major, minor, material, rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=18, minor_segments=6, location=location)
    obj = bpy.context.active_object
    if rotation:
        obj.rotation_euler = rotation
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def sphere(location, radius, material, scale_z=1.0, segments=16, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=location)
    obj = bpy.context.active_object
    obj.scale = (1, 1, scale_z)
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def _poly_tube(points, radius, material):
    curve = bpy.data.curves.new("trim", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for cp, p in zip(spline.points, points):
        cp.co = (p[0], p[1], p[2], 1)
    obj = bpy.data.objects.new("trim", curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    mesh = bpy.context.active_object
    mesh.data.materials.append(material)
    bpy.ops.object.shade_smooth()


def curved_roof(width, depth, height, lift, base_z, material, gold=None,
                xc=0.0, yc=0.0, steps=18, bells=True,
                ridge_len=0.0, rafters=True, yoraku=None):
    """ゆるく反った屋根。ridge_len>0でy軸方向の大棟+鴟尾を持つ入母屋型。
    瓦面+金の軒縁と降り棟+二重の垂木と瓦当+四隅の風鐸+瓔珞の垂れ飾り。"""
    hw, hd = width / 2, depth / 2
    rl = ridge_len

    def zf(x, y):
        ry = max(0.0, abs(y) - rl) / (hd - rl) if rl > 0 else abs(y) / hd
        u = max(abs(x) / hw, ry)
        corner = ((abs(x) / hw) * (abs(y) / hd)) ** 2
        return base_z + height * (1 - u) ** 1.6 + lift * corner

    rows = []
    for i in range(steps + 1):
        x = -hw + width * i / steps
        row = []
        for j in range(steps + 1):
            y = -hd + depth * j / steps
            row.append(Vector((xc + x, yc + y, zf(x, y))))
        rows.append(row)
    grid_strip("roof", rows, material, 0.14)

    if gold is None:
        return
    # 軒縁: 屋根の外周に沿う金の縁
    rim = []
    n = 14
    for edge in range(4):
        for k in range(n):
            t = k / n
            if edge == 0:
                x, y = -hw + width * t, -hd
            elif edge == 1:
                x, y = hw, -hd + depth * t
            elif edge == 2:
                x, y = hw - width * t, hd
            else:
                x, y = -hw, hd - depth * t
            rim.append((xc + x, yc + y, zf(x, y) + 0.09))
    rim.append(rim[0])
    _poly_tube(rim, 0.055, gold)
    # 垂木(二軒=地垂木+飛檐垂木の二重) / 瓦当: 軒先の丸い飾り金具
    if rafters:
        for nx, ny in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            span = width if ny != 0 else depth
            cnt = max(5, int(span / 0.32))
            for k in range(cnt):
                t = 0.05 + 0.90 * k / (cnt - 1)
                if ny != 0:
                    x, y = -hw + width * t, ny * hd
                    size, rot = (0.065, 0.5, 0.085), (-0.25 * ny, 0, 0)
                    drot = (math.pi / 2, 0, 0)
                else:
                    x, y = nx * hw, -hd + depth * t
                    size, rot = (0.5, 0.065, 0.085), (0, 0.25 * nx, 0)
                    drot = (0, math.pi / 2, 0)
                ez = zf(x, y)
                box_at("taruki", (xc + x - nx * 0.20, yc + y - ny * 0.20, ez - 0.15), size, gold, rotation=rot)
                box_at("jitaruki", (xc + x - nx * 0.52, yc + y - ny * 0.52, ez - 0.28), size, gold, rotation=rot)
                cyl((xc + x + nx * 0.05, yc + y + ny * 0.05, ez + 0.01), 0.05, 0.035,
                    gold, vertices=8, rotation=drot)
    # 瓔珞: 軒先から下がる珠飾りの連(金の珠+赤珠の雫)
    if yoraku is not None:
        for nx, ny in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            span = width if ny != 0 else depth
            cnt = max(3, int(span / 1.0))
            for k in range(cnt):
                t = 0.14 + 0.72 * k / (cnt - 1)
                x = (-hw + width * t) if ny != 0 else nx * hw
                y = ny * hd if ny != 0 else (-hd + depth * t)
                gx, gy, gz = xc + x + nx * 0.04, yc + y + ny * 0.04, zf(x, y) - 0.02
                cyl((gx, gy, gz - 0.05), 0.006, 0.10, gold, vertices=5)
                sphere((gx, gy, gz - 0.13), 0.030, gold, segments=7, rings=5)
                sphere((gx, gy, gz - 0.19), 0.030, gold, segments=7, rings=5)
                sphere((gx, gy, gz - 0.27), 0.048, yoraku, scale_z=1.35, segments=8, rings=6)
    # 降り棟: 四隅から棟端(宝形なら頂)へ走る金の棟
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = []
            for k in range(9):
                t = k / 8
                x = sx * hw * (1 - t)
                y = sy * (hd * (1 - t) + rl * t)
                pts.append((xc + x, yc + y, zf(x, y) + 0.08))
            _poly_tube(pts, 0.05, gold)
    if rl > 0:
        # 大棟と、その両端に反り立つ金の鴟尾
        top = zf(0, 0)
        box_at("omune", (xc, yc, top + 0.10), (0.24, rl * 2 + 0.24, 0.20), gold)
        for sy in (-1, 1):
            ye = rl + 0.10
            box_at("shibi_base", (xc, yc + sy * ye, top + 0.24), (0.20, 0.30, 0.16), gold)
            horn = []
            for k in range(8):
                t = k / 7
                horn.append((xc, yc + sy * (ye + 0.06 + 0.24 * t),
                             top + 0.28 + 0.50 * t ** 1.6))
            _poly_tube(horn, 0.062, gold)
            sphere((xc, yc + sy * (ye + 0.32), top + 0.84), 0.055, gold, segments=10, rings=8)
            if bells:
                # 風鐸: 反り上がった軒先に吊る小さな鐘
                bx, by = xc + sx * (hw - 0.12), yc + sy * (hd - 0.12)
                bz = zf(sx * (hw - 0.12), sy * (hd - 0.12))
                cyl((bx, by, bz - 0.06), 0.008, 0.14, gold, vertices=6)
                bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.075, radius2=0.03,
                                                depth=0.12, location=(bx, by, bz - 0.19))
                bell = bpy.context.active_object
                bpy.ops.object.shade_smooth()
                bell.data.materials.append(gold)
                sphere((bx, by, bz - 0.28), 0.02, gold)


def column(x, y, base_z, shaft_h, gold, shako, radius=0.17):
    """柱: 銀の礎盤+金の帯+象牙色の柱身+硨磲の柱頭。"""
    box_at("colbase", (x, y, base_z + 0.06), (0.5, 0.5, 0.12), mat_of("silver"))
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=radius + 0.11, radius2=radius + 0.02,
                                    depth=0.10, location=(x, y, base_z + 0.17))
    renge = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    renge.data.materials.append(mat_of("gold"))
    cyl((x, y, base_z + 0.12 + shaft_h / 2), radius, shaft_h, shako)
    cyl((x, y, base_z + 0.18), radius + 0.03, 0.06, gold)          # 根元の金帯
    cyl((x, y, base_z + 0.12 + shaft_h - 0.05), radius + 0.03, 0.06, gold)  # 頂の金帯
    cyl((x, y, base_z + 0.12 + shaft_h + 0.08), radius + 0.09, 0.16, mat_of("shako"))  # 柱頭


def railing(points, base_z, silver, hari, shuju, post_h=0.78, pearls=True):
    """欄干: 銀の柱と手すり+玻瓈の面板+赤珠の垂れ飾り。pointsは辺の(始点,終点)列。"""
    for (x0, y0), (x1, y1) in points:
        length = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(length / 1.1))
        for k in range(n + 1):
            t = k / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            box_at("rpost", (x, y, base_z + post_h / 2), (0.07, 0.07, post_h), silver)
        # 手すりと面板(辺の向きに合わせた薄い箱)
        # 親柱の頂に金の擬宝珠
        for (px, py) in ((x0, y0), (x1, y1)):
            sphere((px, py, base_z + post_h + 0.10), 0.065, mat_of("gold"), scale_z=1.25)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ang = math.atan2(y1 - y0, x1 - x0)
        box_at("rail", (cx, cy, base_z + post_h), (length, 0.09, 0.07), silver, rotation=(0, 0, ang))
        box_at("midrail", (cx, cy, base_z + post_h * 0.52), (length, 0.05, 0.045), silver, rotation=(0, 0, ang))
        box_at("shikii", (cx, cy, base_z + 0.05), (length, 0.07, 0.06), silver, rotation=(0, 0, ang))
        box_at("panel", (cx, cy, base_z + post_h * 0.55), (length, 0.03, post_h * 0.5), hari, rotation=(0, 0, ang))
        # 子柱: 地覆と中桟のあいだに細い銀の縦子
        nb = max(3, int(length / 0.26))
        for k in range(1, nb):
            t = k / nb
            bx, by = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            box_at("kobashira", (bx, by, base_z + post_h * 0.28),
                   (0.032, 0.05, post_h * 0.46), silver, rotation=(0, 0, ang))
        if pearls:
            for k in range(1, int(length / 1.4)):
                t = k / int(length / 1.4 + 1e-9) if int(length / 1.4) else 0.5
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                cyl((x, y, base_z - 0.10), 0.008, 0.2, silver, vertices=6)
                sphere((x, y, base_z - 0.24), 0.06, shuju)


def bracket(x, y, z, gold, along_x):
    """三つ手の組物: 大斗の上に肘木、その上に巻斗を三つ載せる。"""
    box_at("kumi_daito", (x, y, z - 0.07), (0.20, 0.20, 0.12), gold)
    arm = (0.62, 0.11, 0.09) if along_x else (0.11, 0.62, 0.09)
    box_at("kumi_hijiki", (x, y, z + 0.035), arm, gold)
    for t in (-0.24, 0.0, 0.24):
        mx, my = (x + t, y) if along_x else (x, y + t)
        box_at("kumi_makito", (mx, my, z + 0.13), (0.13, 0.13, 0.10), gold)


def kumimono(width, depth, z, gold, spacing=0.9):
    """組物: 軒下に並ぶ三つ手の斗きょう。"""
    hw, hd = width / 2, depth / 2
    for s in (-1, 1):
        for k in range(int(width / spacing)):
            x = -hw + spacing / 2 + k * spacing
            bracket(x, s * hd, z, gold, along_x=True)
        for k in range(int(depth / spacing)):
            y = -hd + spacing / 2 + k * spacing
            bracket(s * hw, y, z, gold, along_x=False)


def hoju(x, y, z, gold, scale=1.0):
    box_at("roban", (x, y, z + 0.035 * scale), (0.56 * scale, 0.56 * scale, 0.07 * scale), gold)
    cyl((x, y, z + 0.16 * scale), 0.12 * scale, 0.20 * scale, gold)
    # 受け花: 珠を受ける開いた花弁
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.13 * scale, radius2=0.30 * scale,
                                    depth=0.10 * scale, location=(x, y, z + 0.30 * scale))
    uke = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    uke.data.materials.append(gold)
    sphere((x, y, z + 0.5 * scale), 0.26 * scale, gold, scale_z=1.3)
    torus((x, y, z + 0.80 * scale), 0.13 * scale, 0.018 * scale, gold)
    torus((x, y, z + 0.88 * scale), 0.10 * scale, 0.016 * scale, gold)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.09 * scale, radius2=0.0,
                                    depth=0.3 * scale, location=(x, y, z + 0.9 * scale))
    tip = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    tip.data.materials.append(gold)


def build_pavilion(path):
    reset_scene()
    gold = mat_of("gold")
    silver = mat_of("silver")
    shuju = mat_of("shuju")
    hari = hari_material()
    # 面には文様テクスチャを張る(細かさと豪華さの主役)
    ruri = textured("ruri_tiles", "roof_tiles.png", normal="roof_tiles_normal.png",
                    metallic=0.35, roughness=0.35, tile=(4, 4))
    shippo = textured("shippo_gold", "shippo.png", normal="shippo_normal.png",
                      metallic=0.8, roughness=0.35, tile=(3, 3))
    shippo_wide = textured("shippo_wide", "shippo.png", normal="shippo_normal.png",
                           metallic=0.8, roughness=0.35, tile=(10, 1))
    goldcol = textured("goldcol", "column_gold.png", normal="column_gold_normal.png",
                       metallic=0.85, roughness=0.35, tile=(2, 1))
    goldfloor = textured("goldfloor", "paving.png", metallic=0.6, roughness=0.45, tile=(4, 4))
    stone = goldfloor  # 床・軒はすべて金に
    shako_soft = goldcol  # 柱身も金(柱頭の硨磲は残す)
    meno = textured("meno", "agate.png", metallic=0.15, roughness=0.45, tile=(10, 1))

    # ---- 基壇(碼碯の帯+石の上段) ----
    box_at("podium1", (0, 0, 0.30), (11, 21, 0.60), meno)
    box_at("podium2", (0, 0, 0.90), (10, 20, 0.60), shippo_wide)
    for (w, d, z) in ((11.0, 21.0, 0.60), (10.0, 20.0, 1.20)):
        hw2, hd2 = w / 2, d / 2
        _poly_tube([(hw2, -hd2, z), (hw2, hd2, z), (-hw2, hd2, z),
                    (-hw2, -hd2, z), (hw2, -hd2, z)], 0.045, gold)

    # ---- 背面(-x)の幅広階段: 銀の縁 ----
    for i in range(6):
        top = 0.2 * (i + 1)
        inner = -5 - (5 - i) * 0.4
        box_at("step", (inner - 0.2, 0, top - 0.1), (0.4, 6, 0.2), stone)
        box_at("stepnose", (inner - 0.38, 0, top - 0.03), (0.06, 6, 0.06), silver)
    slope = math.atan2(1.2, 2.4)
    for sy in (-1, 1):
        yk = sy * 3.05
        box_at("stringer", (-6.3, yk, 0.62), (2.9, 0.12, 0.22), silver, rotation=(0, -slope, 0))
        box_at("stair_rail", (-6.3, yk, 1.42), (2.7, 0.07, 0.07), silver, rotation=(0, -slope, 0))
        for (px, pz) in ((-5.15, 1.2), (-7.45, 0.02)):
            box_at("stair_post", (px, yk, pz + 0.42), (0.09, 0.09, 0.84), silver)
            sphere((px, yk, pz + 0.94), 0.06, gold, scale_z=1.25)

    # ---- 一階の床と玻瓈の床飾り ----
    box_at("hallfloor", (0, 0, 1.29), (6.5, 9, 0.18), stone)
    box_at("hallinlay", (0, 0, 1.41), (3, 5, 0.06), hari)

    # ---- 一階の列柱 ----
    for x in (-2.7, 2.7):
        for y in (-3.8, -1.9, 0, 1.9, 3.8):
            column(x, y, 1.38, 3.3, gold, shako_soft)
    for y in (-3.8, 3.8):
        column(0, y, 1.38, 3.3, gold, shako_soft)
    # 貫: 柱列を結ぶ横材(内法貫と腰貫、端は木鼻として突き出す)
    for bz, th in ((4.30, 0.13), (2.45, 0.11)):
        for sx in (-1, 1):
            box_at("nuki", (sx * 2.7, 0, bz), (th, 8.1, th), gold)
        for sy in (-1, 1):
            box_at("nuki", (0, sy * 3.8, bz), (5.95, th, th), gold)
    # 欄間: 柱頂の間を埋める玻瓈と金の格子
    for sx in (-1, 1):
        box_at("ranma", (sx * 2.7, 0, 4.58), (0.04, 7.6, 0.42), hari)
        for k in range(23):
            box_at("ranma_koushi", (sx * 2.7, -3.52 + k * 0.32, 4.58), (0.06, 0.055, 0.46), gold)
    for sy in (-1, 1):
        box_at("ranma", (0, sy * 3.8, 4.58), (5.4, 0.04, 0.42), hari)
        for k in range(16):
            box_at("ranma_koushi", (-2.4 + k * 0.32, sy * 3.8, 4.58), (0.055, 0.06, 0.46), gold)

    # ---- 露台(一階の屋根床)+欄干 ----
    box_at("terrace", (0, 0, 4.94), (7, 9.5, 0.2), shippo)
    box_at("terracetrim", (0, 0, 5.05), (7.1, 9.6, 0.06), gold)
    e = (3.55, 4.8)
    railing([((-e[0], -e[1]), (e[0], -e[1])), ((e[0], -e[1]), (e[0], e[1])),
             ((e[0], e[1]), (-e[0], e[1])), ((-e[0], e[1]), (-e[0], -e[1]))],
            5.08, silver, hari, shuju)

    # ---- 主楼(二階) ----
    for x in (-2.2, 0, 2.2):
        for y in (-2.2, 2.2):
            column(x, y, 5.04, 2.5, gold, shako_soft, radius=0.14)
    for y in (0,):
        for x in (-2.2, 2.2):
            column(x, y, 5.04, 2.5, gold, shako_soft, radius=0.14)
    for sx, sy, w in ((1, 0, 4.2), (-1, 0, 4.2)):
        box_at("wall", (sx * 2.2, 0, 6.45), (0.06, w, 2.2), hari)
    for sy in (-1, 1):
        box_at("wall", (0, sy * 2.2, 6.45), (4.2, 0.06, 2.2), hari)
    # 正面の両開きの金扉: 框に囲まれた二枚。飾り鋲と引手の環
    box_at("doorframe_t", (2.25, 0, 7.14), (0.08, 1.62, 0.10), gold)
    box_at("doorframe_b", (2.25, 0, 5.24), (0.08, 1.62, 0.10), gold)
    for syd in (-1, 1):
        box_at("doorframe_s", (2.25, syd * 0.76, 6.19), (0.08, 0.10, 2.0), gold)
        box_at("doorpanel", (2.24, syd * 0.36, 6.19), (0.05, 0.66, 1.80), gold)
        box_at("doorstile", (2.27, syd * 0.36, 6.19), (0.03, 0.08, 1.80), silver)
        for rz in (5.5, 6.0, 6.5, 6.9):
            for ry in (0.14, 0.58):
                box_at("byou", (2.28, syd * ry, rz), (0.03, 0.045, 0.045), silver)
        torus((2.30, syd * 0.14, 6.05), 0.055, 0.012, silver, rotation=(0, math.pi / 2, 0))

    # 長押: 玻瓈壁を押さえる金の水平帯
    for nz in (5.62, 7.32):
        for sx in (-1, 1):
            box_at("nageshi", (sx * 2.26, 0, nz), (0.07, 4.55, 0.15), gold)
        for sy in (-1, 1):
            box_at("nageshi", (0, sy * 2.26, nz), (4.55, 0.07, 0.15), gold)
    box_at("towereave", (0, 0, 7.78), (5.6, 5.6, 0.18), shippo)
    _poly_tube([(2.82, -2.82, 7.88), (2.82, 2.82, 7.88), (-2.82, 2.82, 7.88),
                (-2.82, -2.82, 7.88), (2.82, -2.82, 7.88)], 0.04, gold)
    kumimono(5.4, 5.4, 7.62, gold)
    curved_roof(7.0, 7.0, 1.0, 0.55, 7.85, ruri, gold, ridge_len=1.4, yoraku=shuju)

    # 上層(小さな階+上屋根)
    box_at("clerestory", (0, 0, 8.45), (3.4, 3.4, 1.2), shippo)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box_at("cpost", (sx * 1.7, sy * 1.7, 8.45), (0.14, 0.14, 1.2), gold)
    # 連子窓: 各面に玻瓈の帯と金の縦子
    for sgn in (-1, 1):
        box_at("renji_win", (sgn * 1.72, 0, 8.45), (0.05, 2.6, 0.62), hari)
        box_at("renji_win", (0, sgn * 1.72, 8.45), (2.6, 0.05, 0.62), hari)
        for k in range(7):
            off = -1.14 + k * 0.38
            box_at("renji", (sgn * 1.74, off, 8.45), (0.05, 0.075, 0.72), gold)
            box_at("renji", (off, sgn * 1.74, 8.45), (0.075, 0.05, 0.72), gold)
    curved_roof(4.4, 4.4, 1.5, 0.4, 9.05, ruri, gold, ridge_len=0.9, yoraku=shuju)
    hoju(0, 0, 10.72, gold)

    # ---- 小楼(左右)と回廊 ----
    for sy in (-1, 1):
        yc = sy * 7.8
        box_at("sidefloor", (0, yc, 1.275), (4, 4, 0.15), stone)
        for sx in (-1, 1):
            for syy in (-1, 1):
                column(sx * 1.6, yc + syy * 1.6, 1.35, 2.3, gold, shako_soft, radius=0.13)
        for sx in (-1, 1):
            box_at("nuki", (sx * 1.6, yc, 3.05), (0.11, 3.7, 0.11), gold)
            box_at("nuki", (0, yc + sx * 1.6, 3.05), (3.7, 0.11, 0.11), gold)
        box_at("sideeave", (0, yc, 3.83), (4.6, 4.6, 0.16), shippo)
        _poly_tube([(2.32, yc - 2.32, 3.92), (2.32, yc + 2.32, 3.92), (-2.32, yc + 2.32, 3.92),
                    (-2.32, yc - 2.32, 3.92), (2.32, yc - 2.32, 3.92)], 0.04, gold)
        for sgn in (-1, 1):
            for k in range(5):
                bracket(-2.0 + 0.5 + k * 0.9, yc + sgn * 2.2, 3.72, gold, along_x=True)
                bracket(sgn * 2.2, yc - 2.0 + 0.5 + k * 0.9, 3.72, gold, along_x=False)
        curved_roof(5.6, 5.6, 1.2, 0.4, 3.9, ruri, gold, xc=0, yc=yc, steps=14, yoraku=shuju)
        hoju(0, yc, 5.1, gold, scale=0.6)
        # 回廊
        yc2 = sy * 5.15
        box_at("corrfloor", (0, yc2, 1.275), (2.2, 1.5, 0.15), stone)
        for sx in (-1, 1):
            for syy in (-1, 1):
                cyl((sx * 0.9, yc2 + syy * 0.55, 1.35 + 0.975), 0.1, 1.95, shako_soft)
        box_at("corrroof", (0, yc2, 3.34), (2.6, 1.9, 0.10), shippo)
        curved_roof(3.0, 2.3, 0.38, 0.12, 3.40, ruri, gold, xc=0, yc=yc2,
                    steps=8, bells=False, rafters=False)

    # ---- 舞台(正面+xの水上デッキ)+欄干+支柱 ----
    box_at("stage", (6.6, 0, 1.11), (3.2, 7, 0.18), stone)
    box_at("stagetrim", (6.6, 0, 1.21), (3.3, 7.1, 0.05), gold)
    railing([((8.15, -3.5), (8.15, 3.5)), ((5.0, -3.5), (8.15, -3.5)), ((5.0, 3.5), (8.15, 3.5))],
            1.24, silver, hari, shuju)
    for y in (-3.2, 3.2):
        cyl((8.0, y, 0.1), 0.15, 2.0, stone)

    export(path)
    patch_blend(path, {"hari"})
    print("patched hari->BLEND")




if __name__ == "__main__":
    build_pavilion(os.path.join(OUT_DIR, "pavilion.glb"))
    print("done", file=sys.stderr)
