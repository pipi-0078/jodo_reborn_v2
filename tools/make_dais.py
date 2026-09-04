#!/usr/bin/env python3
"""中島の壇(須弥壇)と宝幢をBlender(bpy)で生成してglb出力する。

「2. 高さと中心軸」: 中島の頂(金の円盤 r=10)に、蓮華座を載せる上段と欄干・階段・灯籠を足す。

island_dais.glb(原点 = 中島の頂の中心、+Z が上。据え付けは y=ISLAND_TOP)
  - 上段: 半径 7m・高さ 1.2m の円壇。側面は槌目の金、上面は金の敷石、上下に金の刳形と朱の帯
  - 階段: 四方の階道の軸に 5 段(蹴上 0.24・踏面 0.32)、袖石と親柱
  - 欄干: 下段の縁(r=9.7、橋の袂 4 か所を空ける)と上段の縁(r=6.7、階段 4 か所を空ける)。橋と同じ意匠
    (親柱に擬宝珠・束・金の手すり・朱の中桟)
  - 灯籠: 下段の四隅方向に 8 基
  蓮華座(rengeza, 倍率 3 = 直径 9.1m)は上段の中央、y = ISLAND_TOP + 1.2 に据える(別アセット)

houdou.glb(宝幢: 原点 = 柱の足元、高さ約 9m)
  - 三重の台座、八角の柱、頂の宝珠(玻璃)、金の笠から四方へ下がる瑠璃の幡(金の縁取り、五本の垂れ)

使い方: python3 tools/make_dais.py
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene, textured_material  # noqa: E402
from make_bridge import GOLD, LAPIS, SHU, box_at, giboshi, grid_strip, lantern  # noqa: E402

UPPER_R = 7.0      # 上段の半径
UPPER_H = 1.2      # 上段の高さ
LOWER_RAIL_R = 9.7  # 下段の欄干の半径(中島の頂 r=10 の内側)
UPPER_RAIL_R = 6.7  # 上段の欄干の半径
BRIDGE_GAP = 2.3   # 橋の袂で欄干を空ける半幅(橋幅 3m + 橋台)
STAIR_W = 3.0      # 階段の幅
STAIR_STEPS = 5
RISE = UPPER_H / STAIR_STEPS
RUN = 0.32
AXES = [0.0, math.pi / 2, math.pi, math.pi * 1.5]


def polar(r, a, z=0.0):
    return (math.cos(a) * r, math.sin(a) * r, z)


def cylinder(name, radius, depth, location, material, vertices=64, smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if smooth:
        bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def torus_ring(name, radius, minor, z, material, segments=96):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=minor, major_segments=segments,
                                     minor_segments=10, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def rail_curve(points, radius, material):
    """点列に沿った丸棒(手すり・中桟)。"""
    curve = bpy.data.curves.new("rail", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for i, p in enumerate(points):
        spline.points[i].co = (p[0], p[1], p[2], 1)
    obj = bpy.data.objects.new("rail", curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    rail = bpy.context.active_object
    rail.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return rail


def railing_arc(radius, z, a0, a1, gold_mat, lapis_mat, spacing=1.0):
    """円弧 a0..a1 に沿った欄干(橋と同じ意匠)。両端は必ず擬宝珠付きの親柱。"""
    length = (a1 - a0) * radius
    bays = max(2, round(length / spacing))
    if bays % 2 == 1:
        bays += 1  # 親柱を 1 本おきにしても両端が親柱になるよう偶数に
    posts = bays + 1
    rail_height = 0.88
    for k in range(posts):
        a = a0 + (a1 - a0) * k / bays
        major = k % 2 == 0
        height = 1.02 if major else rail_height
        size = 0.11 if major else 0.08
        x, y, _ = polar(radius, a)
        box_at("post", (x, y, z + height / 2), (size, size, height), gold_mat, rotation=(0, 0, a))
        if major:
            giboshi((x, y, z + height), gold_mat)
        if k < posts - 1:
            for s in range(1, 4):
                aa = a + (a1 - a0) / bays * s / 4
                xx, yy, _ = polar(radius, aa)
                bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=rail_height,
                                                    location=(xx, yy, z + rail_height / 2))
                bpy.context.active_object.data.materials.append(gold_mat)
    samples = max(8, int(length / 0.5))
    for z_off, r_bar, mat in ((rail_height, 0.05, gold_mat), (rail_height * 0.55, 0.028, lapis_mat)):
        pts = [polar(radius, a0 + (a1 - a0) * i / samples, z + z_off) for i in range(samples + 1)]
        rail_curve(pts, r_bar, mat)


def railing_ring(radius, z, gap_half_width, gold_mat, lapis_mat):
    """四方の軸に隙間を空けた円環の欄干。"""
    half = gap_half_width / radius
    for axis in AXES:
        a0 = axis + half
        a1 = axis + math.pi / 2 - half
        railing_arc(radius, z, a0, a1, gold_mat, lapis_mat)


def build_dais(path):
    reset_scene()
    gold_mat = plain_material("gold", GOLD, 0.85, 0.32)
    lapis_mat = plain_material("shu", SHU, 0.2, 0.35, (0.3, 0.06, 0.02), 0.3)  # 中桟と帯は朱(青は不評 9/4)
    glow_mat = plain_material("glow", (1.0, 0.92, 0.7), 0.1, 0.4, (1.0, 0.85, 0.55), 2.6)
    wall_mat = textured_material("wall", "tsuchime.png", normal="tsuchime_normal.png",
                                 metallic=0.8, roughness=0.4, tile=(14, 1))
    floor_mat = textured_material("floor", "paving.png", metallic=0.6, roughness=0.45, tile=(9, 9))

    # --- 上段の円壇: 側面は槌目、上面は敷石 ---
    drum = cylinder("drum", UPPER_R, UPPER_H, (0, 0, UPPER_H / 2), wall_mat, vertices=96, smooth=False)
    drum.data.materials.append(floor_mat)
    for poly in drum.data.polygons:
        poly.use_smooth = abs(poly.normal.z) < 0.5
        if poly.normal.z > 0.5:
            poly.material_index = 1
    # 刳形(くりかた): 上端の金の縁と足元の腰、瑠璃の帯
    torus_ring("cornice", UPPER_R + 0.02, 0.09, UPPER_H - 0.02, gold_mat)
    torus_ring("plinth", UPPER_R + 0.06, 0.12, 0.08, gold_mat)
    torus_ring("band", UPPER_R + 0.015, 0.03, UPPER_H * 0.55, lapis_mat)
    # 下段の縁石
    torus_ring("kerb", 9.92, 0.07, 0.02, gold_mat)

    # --- 階段(四方) ---
    for axis in AXES:
        c, s = math.cos(axis), math.sin(axis)
        for i in range(1, STAIR_STEPS):  # 最下段は地面(高さ 0)なので作らない。高さ 0 の箱は法線が壊れて黒く写る
            top = UPPER_H - RISE * i
            r_mid = UPPER_R + RUN * (i - 0.5)
            box_at("step", (c * r_mid, s * r_mid, top / 2), (RUN + 0.02, STAIR_W, top), gold_mat,
                   rotation=(0, 0, axis))
        # 袖石: 階段の両脇に斜めの笠石(箱を勾配に合わせて傾ける)と、階段下の親柱
        r_top, r_bot = UPPER_R - 0.1, UPPER_R + RUN * STAIR_STEPS + 0.15
        slope = math.atan2(UPPER_H, r_bot - r_top)
        slope_len = math.hypot(UPPER_H, r_bot - r_top)
        for side in (-1, 1):
            y = side * (STAIR_W / 2 + 0.1)
            r_mid = (r_top + r_bot) / 2
            px = c * r_mid - s * y
            py = s * r_mid + c * y
            box_at("cheek", (px, py, UPPER_H / 2 + 0.12), (slope_len, 0.2, 0.26), gold_mat,
                   rotation=(0, slope, axis))
            # 笠石の下を埋める壁(段の側面を隠す)
            for i in range(1, STAIR_STEPS):
                top = UPPER_H - RISE * i
                rr = UPPER_R + RUN * (i - 0.5)
                box_at("cheek_wall", (c * rr - s * y, s * rr + c * y, top / 2), (RUN + 0.02, 0.2, top), gold_mat,
                       rotation=(0, 0, axis))
            # 階段下の親柱
            x, yy, _ = polar(r_bot + 0.15, axis)
            qx = x - s * y
            qy = yy + c * y
            box_at("stair_post", (qx, qy, 0.55), (0.12, 0.12, 1.1), gold_mat, rotation=(0, 0, axis))
            giboshi((qx, qy, 1.1), gold_mat)

    # --- 欄干 ---
    railing_ring(LOWER_RAIL_R, 0.0, BRIDGE_GAP, gold_mat, lapis_mat)
    railing_ring(UPPER_RAIL_R, UPPER_H, STAIR_W / 2 + 0.25, gold_mat, lapis_mat)

    # --- 灯籠: 四隅方向に二基ずつ ---
    for k in range(4):
        for da in (-0.28, 0.28):
            x, y, _ = polar(9.0, math.pi / 4 + k * math.pi / 2 + da)
            lantern((x, y, 0.0), gold_mat, glow_mat)

    export(path)


def build_houdou(path):
    reset_scene()
    gold_mat = plain_material("gold", GOLD, 0.85, 0.32)
    lapis_mat = plain_material("shu", SHU, 0.2, 0.35, (0.3, 0.06, 0.02), 0.3)  # 柱の帯と垂れは朱
    banner_mat = plain_material("banner", (0.14, 0.26, 0.74), 0.1, 0.6, (0.06, 0.12, 0.45), 0.5)
    hoju_mat = plain_material("hoju", (0.95, 0.97, 1.0), 0.1, 0.1, (0.9, 0.95, 1.0), 1.4)
    banner_mat.use_backface_culling = False

    height = 8.2
    # 三重の台座
    for i, (r, h) in enumerate(((0.75, 0.16), (0.58, 0.14), (0.42, 0.12))):
        z0 = sum(hh for _, hh in ((0.75, 0.16), (0.58, 0.14), (0.42, 0.12))[:i])
        cylinder("base", r, h, (0, 0, z0 + h / 2), gold_mat, vertices=16, smooth=False)
    base_top = 0.42
    # 八角の柱
    cylinder("shaft", 0.17, height - base_top, (0, 0, base_top + (height - base_top) / 2), gold_mat,
             vertices=8, smooth=False)
    torus_ring("collar1", 0.2, 0.04, base_top + 0.05, lapis_mat, segments=24)
    torus_ring("collar2", 0.2, 0.04, height - 0.6, lapis_mat, segments=24)
    # 頂: 皿と宝珠
    cylinder("cap", 0.42, 0.08, (0, 0, height + 0.04), gold_mat, vertices=16, smooth=False)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=0.3, location=(0, 0, height + 0.4))
    hoju = bpy.context.active_object
    hoju.scale = (1, 1, 1.3)
    bpy.ops.object.shade_smooth()
    hoju.data.materials.append(hoju_mat)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.1, radius2=0.0, depth=0.3, location=(0, 0, height + 0.9))
    bpy.context.active_object.data.materials.append(gold_mat)

    # 笠(かさ): 宝珠の下の円い天蓋。その縁から四方へ幡が下がる
    bar_z = height - 0.55
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=1.05, radius2=0.35, depth=0.35, location=(0, 0, bar_z + 0.1))
    canopy = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    canopy.data.materials.append(gold_mat)
    torus_ring("canopy_rim", 1.05, 0.05, bar_z - 0.07, lapis_mat, segments=48)
    width, length = 0.8, 5.0
    hang_r = 0.85
    for k in range(4):
        a = k * math.pi / 2
        c, s = math.cos(a), math.sin(a)
        rows = []
        for i in range(27):
            t = i / 26
            z = bar_z - 0.12 - length * t
            sway = 0.12 * math.sin(t * math.pi * 1.6 + k) * t  # 下へ行くほど風に揺れる
            row = []
            for j in range(7):
                u = j / 6 - 0.5
                r = hang_r + sway + 0.02 * math.sin(u * math.pi * 2 + t * 5)
                row.append(Vector((c * r - s * u * width, s * r + c * u * width, z)))
            rows.append(row)
        grid_strip("banner", rows, banner_mat, 0.012)
        # 上下の金の縁取りと、五本の垂れ(瑠璃と金を交互に)
        box_at("trim_top", (c * hang_r, s * hang_r, bar_z - 0.12), (0.05, width + 0.06, 0.08), gold_mat, rotation=(0, 0, a))
        bottom_z = bar_z - 0.12 - length
        r_bot = hang_r + 0.12 * math.sin(math.pi * 1.6 + k)
        box_at("trim_bottom", (c * r_bot, s * r_bot, bottom_z), (0.05, width + 0.06, 0.08), gold_mat, rotation=(0, 0, a))
        for j in range(5):
            u = (j - 2) * (width / 5)
            mat = lapis_mat if j % 2 == 0 else gold_mat
            box_at("tail", (c * r_bot - s * u, s * r_bot + c * u, bottom_z - 0.5), (0.02, width / 5 - 0.05, 0.9), mat,
                   rotation=(0, 0, a))

    export(path)


if __name__ == "__main__":
    build_dais(os.path.join(OUT_DIR, "island_dais.glb"))
    build_houdou(os.path.join(OUT_DIR, "houdou.glb"))
    print("done", file=sys.stderr)
