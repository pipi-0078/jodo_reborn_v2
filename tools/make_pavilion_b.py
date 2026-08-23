#!/usr/bin/env python3
"""七宝楼閣・別案「黄金八角楼」をBlender(bpy)で生成してglb出力する。

第一案(入母屋の二層)とは全く別の型。夢殿のような八角平面を三層に積み、
全身を黄金で包み、頂に九輪の相輪を立てる塔型の楼閣。
文様は唐草(壁)・花菱(基壇と軒)・蓮弁(基壇の縁)・金瓦(屋根)。

使い方: python3 tools/make_textures.py && python3 tools/make_pavilion_b.py
出力: public/assets/pavilion_b.glb
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, reset_scene  # noqa: E402
from make_bridge import box_at, grid_strip  # noqa: E402
from make_pavilion import (cyl, sphere, torus, _poly_tube, textured,  # noqa: E402
                           hari_material, mat_of, patch_blend)

OCT = math.pi / 4          # 八角の一辺が張る角
HALF = math.pi / 8


def rb(theta, R):
    """頂点を角度 k*45°に置いた正八角形の、方位thetaでの境界半径。"""
    d = (theta % OCT) - HALF
    return R * math.cos(HALF) / math.cos(d)


def corner(theta):
    """最寄りの隅への近さ 0..1。"""
    a = theta % OCT
    dv = min(a, OCT - a)
    return max(0.0, 1.0 - dv / HALF)


def octo_roof(R, height, lift, base_z, tiles, gold, shuju=None,
              rings=13, mseg=6, bells=True):
    """八角の反り屋根。金瓦面+隅棟8本+軒縁+垂木+瓦当+風鐸+瓔珞。"""
    N = 8 * mseg

    def zf(u, th):
        return base_z + height * (1 - u) ** 1.6 + lift * corner(th) ** 2 * u ** 2.2

    rows = []
    for i in range(rings + 1):
        u = 0.05 + 0.95 * i / rings
        row = []
        for j in range(N + 1):
            th = 2 * math.pi * j / N
            r = rb(th, R) * u
            row.append(Vector((r * math.cos(th), r * math.sin(th), zf(u, th))))
        rows.append(row)
    grid_strip("oroof", rows, tiles, 0.12)
    # 頂の塞ぎ
    cyl((0, 0, base_z + height + 0.02), R * 0.08, 0.10, gold, vertices=8)
    # 隅棟8本
    for k in range(8):
        th = k * OCT
        pts = []
        for m in range(9):
            t = 0.06 + 0.94 * m / 8
            r = R * (1 - t)
            pts.append((r * math.cos(th), r * math.sin(th), zf(1 - t, th) + 0.07))
        _poly_tube(pts, 0.05, gold)
    # 軒縁
    rim = []
    for j in range(N + 1):
        th = 2 * math.pi * j / N
        r = rb(th, R)
        rim.append((r * math.cos(th), r * math.sin(th), zf(1, th) + 0.08))
    _poly_tube(rim, 0.05, gold)
    # 垂木(放射状)と瓦当
    side = 2 * R * math.sin(HALF)
    cnt = max(4, int(side / 0.36))
    for k in range(8):
        th0 = k * OCT + HALF   # 辺の中心方位
        for m in range(cnt):
            t = -0.42 + 0.84 * m / (cnt - 1)
            th = th0 + t * OCT * 0.92
            r = rb(th, R)
            x, y = r * math.cos(th), r * math.sin(th)
            ez = zf(1, th)
            ux, uy = math.cos(th), math.sin(th)
            box_at("taruki", (x - ux * 0.22, y - uy * 0.22, ez - 0.14),
                   (0.5, 0.065, 0.085), gold, rotation=(0, 0.25, th))
            cyl((x + ux * 0.05, y + uy * 0.05, ez + 0.01), 0.05, 0.035,
                gold, vertices=8, rotation=(0, math.pi / 2, th))
        # 瓔珞: 各辺に二連
        if shuju is not None:
            for t in (-0.22, 0.22):
                th = th0 + t * OCT
                r = rb(th, R)
                x, y, gz = r * math.cos(th), r * math.sin(th), zf(1, th) - 0.02
                cyl((x, y, gz - 0.05), 0.006, 0.10, gold, vertices=5)
                sphere((x, y, gz - 0.13), 0.030, gold, segments=7, rings=5)
                sphere((x, y, gz - 0.19), 0.030, gold, segments=7, rings=5)
                sphere((x, y, gz - 0.27), 0.048, shuju, scale_z=1.35, segments=8, rings=6)
    # 風鐸(隅)
    if bells:
        for k in range(8):
            th = k * OCT
            r = R - 0.14
            bx, by = r * math.cos(th), r * math.sin(th)
            bz = zf(1 - 0.14 / R, th)
            cyl((bx, by, bz - 0.06), 0.008, 0.14, gold, vertices=6)
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.075, radius2=0.03,
                                            depth=0.12, location=(bx, by, bz - 0.19))
            bell = bpy.context.active_object
            bpy.ops.object.shade_smooth()
            bell.data.materials.append(gold)
            sphere((bx, by, bz - 0.28), 0.02, gold)


def obracket(th0, r, z, gold):
    """八角用の三つ手組物。辺の向きに合わせて回す。"""
    x, y = r * math.cos(th0), r * math.sin(th0)
    tang = th0 + math.pi / 2
    box_at("kumi_daito", (x, y, z - 0.07), (0.20, 0.20, 0.12), gold, rotation=(0, 0, tang))
    box_at("kumi_hijiki", (x, y, z + 0.035), (0.58, 0.11, 0.09), gold, rotation=(0, 0, tang))
    for t in (-0.22, 0.0, 0.22):
        mx = x + t * math.cos(tang)
        my = y + t * math.sin(tang)
        box_at("kumi_makito", (mx, my, z + 0.13), (0.13, 0.13, 0.10), gold, rotation=(0, 0, tang))


def gcolumn(x, y, base_z, shaft_h, goldcol, gold, radius=0.16):
    """黄金の柱: 八角の礎盤+蓮華座+紋様の柱身+金帯+柱頭。"""
    cyl((x, y, base_z + 0.05), radius + 0.14, 0.10, gold, vertices=8)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=radius + 0.10, radius2=radius + 0.02,
                                    depth=0.10, location=(x, y, base_z + 0.14))
    renge = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    renge.data.materials.append(gold)
    cyl((x, y, base_z + 0.10 + shaft_h / 2), radius, shaft_h, goldcol)
    cyl((x, y, base_z + 0.16), radius + 0.03, 0.06, gold)
    cyl((x, y, base_z + 0.10 + shaft_h - 0.05), radius + 0.03, 0.06, gold)
    cyl((x, y, base_z + 0.10 + shaft_h + 0.07), radius + 0.09, 0.14, gold, vertices=8)


def orailing(r, base_z, gold, hari, shuju, post_h=0.76):
    """八角の欄干(頂点間の8辺)。子柱・中桟・擬宝珠つき。"""
    for k in range(8):
        a0, a1 = k * OCT, (k + 1) * OCT
        x0, y0 = r * math.cos(a0), r * math.sin(a0)
        x1, y1 = r * math.cos(a1), r * math.sin(a1)
        length = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        box_at("rpost", (x0, y0, base_z + post_h / 2), (0.07, 0.07, post_h), gold)
        sphere((x0, y0, base_z + post_h + 0.09), 0.062, gold, scale_z=1.25)
        box_at("rail", (cx, cy, base_z + post_h), (length, 0.09, 0.07), gold, rotation=(0, 0, ang))
        box_at("midrail", (cx, cy, base_z + post_h * 0.52), (length, 0.05, 0.045), gold, rotation=(0, 0, ang))
        box_at("shikii", (cx, cy, base_z + 0.05), (length, 0.07, 0.06), gold, rotation=(0, 0, ang))
        box_at("panel", (cx, cy, base_z + post_h * 0.55), (length, 0.03, post_h * 0.5), hari, rotation=(0, 0, ang))
        nb = max(3, int(length / 0.26))
        for m in range(1, nb):
            t = m / nb
            bx, by = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            box_at("kobashira", (bx, by, base_z + post_h * 0.28),
                   (0.032, 0.05, post_h * 0.46), gold, rotation=(0, 0, ang))
        # 赤珠の垂れ飾り
        for t in (0.33, 0.67):
            bx, by = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            cyl((bx, by, base_z - 0.09), 0.007, 0.18, gold, vertices=5)
            sphere((bx, by, base_z - 0.22), 0.055, shuju, segments=8, rings=6)


def doors(r, base_z, h, gold, goldcol):
    """核壁の四方に付く両開きの金扉。framed+鋲+引手。"""
    for k in range(4):
        th = k * math.pi / 2
        ux, uy = math.cos(th), math.sin(th)
        tang = th + math.pi / 2
        def at(off_t, off_n, z, size, mat, name):
            box_at(name, (r * ux + off_n * ux + off_t * math.cos(tang),
                          r * uy + off_n * uy + off_t * math.sin(tang), z),
                   size, mat, rotation=(0, 0, tang))
        at(0, 0.045, base_z + h - 0.05, (1.62, 0.08, 0.10), gold, "doorframe_t")
        at(0, 0.045, base_z + 0.05, (1.62, 0.08, 0.10), gold, "doorframe_b")
        for sd in (-1, 1):
            at(sd * 0.76, 0.045, base_z + h / 2, (0.10, 0.08, h), gold, "doorframe_s")
            at(sd * 0.36, 0.035, base_z + h / 2, (0.66, 0.05, h - 0.20), goldcol, "doorpanel")
            for rz in (0.35, 0.75, 1.15, 1.5):
                for ry in (0.14, 0.58):
                    at(sd * ry, 0.075, base_z + rz, (0.045, 0.03, 0.045), gold, "byou")
            torus((r * ux + 0.09 * ux + sd * 0.14 * math.cos(tang),
                   r * uy + 0.09 * uy + sd * 0.14 * math.sin(tang), base_z + 0.85),
                  0.055, 0.012, gold, rotation=(0, math.pi / 2, th))


def renji_ring(r, z, h, gold, hari, slat_step=0.30):
    """連子窓の帯: 八角の各面に玻瓈+金の縦子。"""
    for k in range(8):
        th = k * OCT + HALF
        side = 2 * r * math.tan(HALF)
        ux, uy = math.cos(th), math.sin(th)
        tang = th + math.pi / 2
        box_at("renji_win", (r * ux, r * uy, z), (side * 0.92, 0.04, h), hari, rotation=(0, 0, tang))
        ns = max(3, int(side / slat_step))
        for m in range(ns + 1):
            t = -side * 0.42 + side * 0.84 * m / ns
            box_at("renji", (r * ux + t * math.cos(tang) + 0.02 * ux,
                             r * uy + t * math.sin(tang) + 0.02 * uy, z),
                   (0.055, 0.06, h + 0.10), gold, rotation=(0, 0, tang))


def build(path):
    reset_scene()
    gold = mat_of("gold")
    shuju = mat_of("shuju")
    hari = hari_material()
    karakusa = textured("karakusa", "karakusa.png", normal="karakusa_normal.png",
                        metallic=0.88, roughness=0.32, tile=(6, 2))
    hanabishi = textured("hanabishi", "hanabishi.png", normal="hanabishi_normal.png",
                         metallic=0.85, roughness=0.34, tile=(10, 1))
    renben = textured("renben", "renben.png", normal="renben_normal.png",
                      metallic=0.85, roughness=0.34, tile=(14, 1))
    gtiles = textured("gtiles", "gold_tiles.png", normal="gold_tiles_normal.png",
                      metallic=0.88, roughness=0.46, tile=(5, 4))
    goldcol = textured("goldcol_b", "column_gold.png", normal="column_gold_normal.png",
                       metallic=0.85, roughness=0.35, tile=(2, 1))
    goldfloor = textured("goldfloor_b", "hanabishi.png", normal="hanabishi_normal.png",
                         metallic=0.7, roughness=0.4, tile=(5, 5))

    # ---- 基壇二段(蓮弁の帯+花菱の帯)+金の框 ----
    cyl((0, 0, 0.30), 7.6, 0.60, renben, vertices=8)
    cyl((0, 0, 0.88), 6.9, 0.56, hanabishi, vertices=8)
    for (R, z) in ((7.6, 0.60), (6.9, 1.16)):
        ringpts = [(R * math.cos(k * OCT), R * math.sin(k * OCT), z) for k in range(9)]
        _poly_tube(ringpts, 0.045, gold)

    # ---- 正面(+x)の階段+手すり ----
    for i in range(6):
        top = 0.19 * (i + 1)
        outer = 6.9 + (5 - i) * 0.38
        box_at("step", (outer + 0.19, 0, top - 0.095), (0.38, 4.2, 0.19), goldfloor)
        box_at("stepnose", (outer + 0.37, 0, top - 0.03), (0.06, 4.2, 0.06), gold)
    slope = math.atan2(1.14, 1.9)
    for sy in (-1, 1):
        yk = sy * 2.15
        box_at("stringer", (7.9, yk, 0.60), (2.45, 0.12, 0.22), gold, rotation=(0, slope, 0))
        box_at("stair_rail", (7.9, yk, 1.38), (2.3, 0.07, 0.07), gold, rotation=(0, slope, 0))
        for (px, pz) in ((6.95, 1.14), (8.9, 0.02)):
            box_at("stair_post", (px, yk, pz + 0.40), (0.09, 0.09, 0.80), gold)
            sphere((px, yk, pz + 0.90), 0.06, gold, scale_z=1.25)

    # ---- 一層: 床・列柱・核壁(唐草)・扉・貫・欄間 ----
    cyl((0, 0, 1.24), 5.7, 0.16, goldfloor, vertices=8)
    for k in range(8):
        th = k * OCT
        gcolumn(4.9 * math.cos(th), 4.9 * math.sin(th), 1.32, 3.05, goldcol, gold)
    core = cyl((0, 0, 2.95), 3.3, 3.1, karakusa, vertices=8)
    core.rotation_euler = (0, 0, HALF)
    doors(3.32, 1.42, 1.85, gold, goldcol)
    for bz in (2.55, 4.05):
        ringpts = [(4.9 * math.cos(k * OCT), 4.9 * math.sin(k * OCT), bz) for k in range(9)]
        _poly_tube(ringpts, 0.06, gold)
    renji_ring(4.85, 4.30, 0.34, gold, hari)

    # ---- 一層の軒(花菱)+組物+屋根 ----
    cyl((0, 0, 4.56), 6.0, 0.16, hanabishi, vertices=8)
    for k in range(8):
        for t in (-0.25, 0.0, 0.25):
            obracket(k * OCT + HALF + t * OCT, 5.55, 4.42, gold)
    octo_roof(6.9, 0.95, 0.5, 4.66, gtiles, gold, shuju)

    # ---- 二層: 縁(欄干)+列柱+核壁+連子窓+屋根 ----
    cyl((0, 0, 5.90), 3.9, 0.16, goldfloor, vertices=8)
    orailing(3.75, 6.0, gold, hari, shuju)
    for k in range(8):
        th = k * OCT
        gcolumn(3.0 * math.cos(th), 3.0 * math.sin(th), 5.98, 2.25, goldcol, gold, radius=0.13)
    core2 = cyl((0, 0, 7.2), 2.2, 2.3, karakusa, vertices=8)
    core2.rotation_euler = (0, 0, HALF)
    renji_ring(2.95, 7.9, 0.30, gold, hari)
    cyl((0, 0, 8.42), 3.6, 0.15, hanabishi, vertices=8)
    for k in range(8):
        for t in (-0.22, 0.22):
            obracket(k * OCT + HALF + t * OCT, 3.3, 8.28, gold)
    octo_roof(4.5, 0.85, 0.42, 8.50, gtiles, gold, shuju)

    # ---- 三層(小さな灯りの層)+屋根 ----
    core3 = cyl((0, 0, 10.05), 1.55, 1.5, karakusa, vertices=8)
    core3.rotation_euler = (0, 0, HALF)
    renji_ring(1.58, 10.05, 0.55, gold, hari, slat_step=0.24)
    cyl((0, 0, 10.86), 2.25, 0.13, hanabishi, vertices=8)
    octo_roof(3.2, 1.0, 0.4, 10.94, gtiles, gold, shuju, rings=10, mseg=5)

    # ---- 相輪: 露盤・伏鉢・受け花・九輪・宝珠 ----
    top = 11.94
    cyl((0, 0, top + 0.07), 0.52, 0.14, gold, vertices=8)
    sphere((0, 0, top + 0.30), 0.34, gold, scale_z=0.55)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.14, radius2=0.30,
                                    depth=0.12, location=(0, 0, top + 0.52))
    uke = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    uke.data.materials.append(gold)
    cyl((0, 0, top + 1.65), 0.065, 2.3, gold)
    for i in range(9):
        torus((0, 0, top + 0.72 + i * 0.185), 0.30 - i * 0.018, 0.028, gold)
    sphere((0, 0, top + 2.62), 0.19, gold, scale_z=1.35)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.07, radius2=0.0,
                                    depth=0.24, location=(0, 0, top + 2.95))
    tip = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    tip.data.materials.append(gold)

    export(path)
    patch_blend(path, {"hari"})
    print("patched hari->BLEND")


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "pavilion_b.glb"))
    print("done", file=sys.stderr)
