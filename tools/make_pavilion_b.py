#!/usr/bin/env python3
"""七宝楼閣・別案「黄金八角楼」をBlender(bpy)で生成してglb出力する。

第一案(入母屋の二層)とは全く別の型。夢殿のような八角平面を三層に積み、
全身を黄金で包み、頂に九輪の相輪を立てる塔型の楼閣。
文様は唐草(壁)・花菱(基壇と軒)・蓮弁(基壇の縁)。屋根は主楼と同じ瑠璃瓦(9/5 施主「屋根の色も統一」)。
細部(9/5): 放射状の丸瓦と軒丸瓦、熨斗瓦を積んだ隅棟と鬼瓦、二手先の組物と蟇股と通肘木、
密な二軒の垂木と隅木と茅負、八隅の風鐸、軒下の吊灯籠、真珠と宝石の瓔珞、貫の宝石鋲、欄干の擬宝珠と腰羽目

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
                           hari_material, mat_of, patch_blend, wind_bell, hanging_lantern, gem_studs)
from make_ramou import Batch, gem_material  # noqa: E402
from make_trees import plain_material  # noqa: E402

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
              rings=13, mseg=6, bells=True, maru=None, lanterns=False, glow=None):
    """八角の反り屋根。瑠璃瓦の面+放射状の丸瓦と軒丸瓦+熨斗瓦を積んだ隅棟8本と鬼瓦
    +軒縁と茅負+二軒の垂木と隅木+風鐸+真珠と宝石の瓔珞+吊灯籠。"""
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
    side = 2 * R * math.sin(HALF)
    # 丸瓦: 各面で軒から頂へ放射状に。頂に近づくと列が詰まるので、一列おきに途中で止める
    if maru is not None:
        tr = 0.055
        cnt = max(3, int(side / 0.30))
        for k in range(8):
            th0 = k * OCT + HALF
            for m in range(cnt + 1):
                t = -0.5 + m / cnt
                if abs(t) > 0.47:
                    continue
                th = th0 + t * OCT
                u_end = 0.16 if m % 2 == 0 else 0.5
                steps = 6
                pts = []
                for i in range(steps + 1):
                    u = 1.0 - (1.0 - u_end) * i / steps
                    r = rb(th, R) * u
                    pts.append((r * math.cos(th), r * math.sin(th), zf(u, th) + tr * 0.55))
                _poly_tube(pts, tr, maru, resolution=1)
                r = rb(th, R)
                ux, uy = math.cos(th), math.sin(th)
                ez = zf(1, th) + tr * 0.55
                cyl((r * ux + ux * 0.03, r * uy + uy * 0.03, ez), tr * 1.15, 0.05, gold, vertices=10,
                    rotation=(0, math.pi / 2, th))
                sphere((r * ux + ux * 0.06, r * uy + uy * 0.06, ez), tr * 0.35, gold, segments=8, rings=6)
    # 隅棟8本: 熨斗瓦(瑠璃)の上に金の棟。下端に鬼瓦
    for k in range(8):
        th = k * OCT
        pts, under = [], []
        for m in range(9):
            t = 0.06 + 0.94 * m / 8
            r = R * (1 - t)
            pts.append((r * math.cos(th), r * math.sin(th), zf(1 - t, th) + 0.09))
            under.append((r * math.cos(th), r * math.sin(th), zf(1 - t, th) + 0.03))
        if maru is not None:
            _poly_tube(under, 0.08, maru, resolution=1)
        _poly_tube(pts, 0.05, gold)
        ox, oy = (R - 0.22) * math.cos(th), (R - 0.22) * math.sin(th)
        oz = zf(1 - 0.22 / R, th)
        box_at("onigawara", (ox, oy, oz + 0.20), (0.24, 0.24, 0.26), gold, rotation=(0, 0, th))
        sphere((ox, oy, oz + 0.40), 0.07, gold, scale_z=1.3, segments=10, rings=8)
    # 軒縁と、その下の茅負
    for inset, dz, rad in ((0.0, 0.08, 0.05), (0.16, -0.16, 0.045)):
        rim = []
        for j in range(N + 1):
            th = 2 * math.pi * j / N
            r = rb(th, R) - inset
            rim.append((r * math.cos(th), r * math.sin(th), zf(1, th) + dz))
        _poly_tube(rim, rad, gold, resolution=3 if inset == 0 else 1)
    # 垂木(放射状・二軒)と隅木
    cnt = max(6, int(side / 0.22))
    for k in range(8):
        th0 = k * OCT + HALF   # 辺の中心方位
        for m in range(cnt):
            t = -0.44 + 0.88 * m / (cnt - 1)
            th = th0 + t * OCT * 0.92
            r = rb(th, R)
            x, y = r * math.cos(th), r * math.sin(th)
            ez = zf(1, th)
            ux, uy = math.cos(th), math.sin(th)
            box_at("taruki", (x - ux * 0.22, y - uy * 0.22, ez - 0.14),
                   (0.55, 0.055, 0.075), gold, rotation=(0, 0.25, th))
            box_at("jitaruki", (x - ux * 0.56, y - uy * 0.56, ez - 0.28),
                   (0.55, 0.055, 0.075), gold, rotation=(0, 0.25, th))
        th = k * OCT
        ux, uy = math.cos(th), math.sin(th)
        z0, z1 = zf(1, th) - 0.13, zf(1 - 1.2 / R, th) - 0.19
        pitch = -math.atan2(z1 - z0, 1.2)
        box_at("sumigi", ((R - 0.6) * ux, (R - 0.6) * uy, (z0 + z1) / 2), (1.5, 0.12, 0.13), gold,
               rotation=(0, pitch, th))
        # 瓔珞: 各辺に三連(真珠の連と宝石の雫)。吊灯籠は辺の中央
        if shuju is not None:
            pearls = Batch("yoraku_pearl", plain_material("pearl", (0.97, 0.95, 0.91), 0.0, 0.22, (0.30, 0.28, 0.25), 0.3))
            drops = Batch("yoraku_gem", shuju, smooth=False)
            for i, t in enumerate((-0.3, 0.0, 0.3)):
                th = th0 + t * OCT
                r = rb(th, R)
                x, y, gz = r * math.cos(th), r * math.sin(th), zf(1, th) - 0.02
                cyl((x, y, gz - 0.05), 0.006, 0.10, gold, vertices=5)
                n_pearl = 4 if i == 1 else 3
                for j in range(n_pearl):
                    pearls.sphere(Vector((x, y, gz - 0.13 - j * 0.065)), 0.030)
                drops.gem(Vector((x, y, gz - 0.13 - n_pearl * 0.065 - 0.05)), 0.045, elong=1.7, facets=8)
            pearls.finish()
            drops.finish()
        if lanterns and glow is not None:
            r = rb(th0, R) - 0.34
            hanging_lantern(r * math.cos(th0), r * math.sin(th0), zf(1 - 0.34 / R, th0) - 0.12, gold, glow)
    # 風鐸(隅)
    if bells:
        for k in range(8):
            th = k * OCT
            r = R - 0.12
            wind_bell(r * math.cos(th), r * math.sin(th), zf(1 - 0.12 / R, th) - 0.02, gold)


def obracket(th0, r, z, gold, two_tier=True):
    """八角用の二手先組物。辺の向きに合わせて回し、二手目は外(半径方向)へ出す。尾垂木付き"""
    x, y = r * math.cos(th0), r * math.sin(th0)
    tang = th0 + math.pi / 2
    ux, uy = math.cos(th0), math.sin(th0)
    box_at("kumi_daito", (x, y, z - 0.07), (0.24, 0.24, 0.14), gold, rotation=(0, 0, tang))
    box_at("kumi_daito_sara", (x, y, z - 0.15), (0.30, 0.30, 0.04), gold, rotation=(0, 0, tang))
    box_at("kumi_hijiki", (x, y, z + 0.035), (0.66, 0.11, 0.09), gold, rotation=(0, 0, tang))
    for t in (-0.25, 0.0, 0.25):
        mx = x + t * math.cos(tang)
        my = y + t * math.sin(tang)
        box_at("kumi_makito", (mx, my, z + 0.13), (0.14, 0.14, 0.10), gold, rotation=(0, 0, tang))
    if two_tier:
        box_at("kumi_hijiki2", (x + ux * 0.20, y + uy * 0.20, z + 0.23), (0.60, 0.10, 0.09), gold, rotation=(0, 0, th0))
        box_at("kumi_makito2", (x + ux * 0.42, y + uy * 0.42, z + 0.325), (0.13, 0.13, 0.10), gold, rotation=(0, 0, th0))
        box_at("odaruki", (x + ux * 0.40, y + uy * 0.40, z + 0.30), (0.95, 0.09, 0.10), gold, rotation=(0, -0.40, th0))


def okaerumata(th, r, z, gold):
    """八角用の蟇股: 組物のあいだの、蛙の股のように開いた束"""
    x, y = r * math.cos(th), r * math.sin(th)
    tang = th + math.pi / 2
    for t in (-1, 1):
        dx, dy = t * 0.09 * math.cos(tang), t * 0.09 * math.sin(tang)
        box_at("kaerumata_leg", (x + dx, y + dy, z + 0.02), (0.06, 0.09, 0.30), gold, rotation=(0, 0, tang + t * 0.55))
    box_at("kaerumata_top", (x, y, z + 0.19), (0.42, 0.11, 0.06), gold, rotation=(0, 0, tang))
    sphere((x, y, z + 0.04), 0.04, mat_of("shuju"), segments=8, rings=6)


def okumimono(r, z, gold, offsets):
    """八角の各辺に組物を並べ、あいだに蟇股、上に通肘木の環を渡す"""
    for k in range(8):
        th0 = k * OCT + HALF
        for i, t in enumerate(offsets):
            obracket(th0 + t * OCT, r, z, gold)
            if i < len(offsets) - 1:
                okaerumata(th0 + (t + offsets[i + 1]) / 2 * OCT, r, z, gold)
    pts = [((r + 0.05) * math.cos(k * OCT), (r + 0.05) * math.sin(k * OCT), z + 0.21) for k in range(9)]
    _poly_tube(pts, 0.06, gold, resolution=1)


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


def orailing(r, base_z, gold, hari, shuju, post_h=0.76, koshi=None):
    """八角の欄干(頂点間の8辺)。子柱・中桟・全柱の擬宝珠・花菱文の腰羽目つき。"""
    for k in range(8):
        a0, a1 = k * OCT, (k + 1) * OCT
        x0, y0 = r * math.cos(a0), r * math.sin(a0)
        x1, y1 = r * math.cos(a1), r * math.sin(a1)
        length = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        box_at("rpost", (x0, y0, base_z + post_h / 2), (0.075, 0.075, post_h), gold)
        sphere((x0, y0, base_z + post_h + 0.10), 0.065, gold, scale_z=1.25, segments=10, rings=8)
        torus((x0, y0, base_z + post_h + 0.035), 0.06, 0.012, gold)
        box_at("rpost_mid", (cx, cy, base_z + post_h / 2), (0.06, 0.06, post_h), gold, rotation=(0, 0, ang))
        sphere((cx, cy, base_z + post_h + 0.07), 0.042, gold, scale_z=1.25, segments=10, rings=8)
        box_at("rail", (cx, cy, base_z + post_h), (length, 0.09, 0.07), gold, rotation=(0, 0, ang))
        box_at("midrail", (cx, cy, base_z + post_h * 0.52), (length, 0.05, 0.045), gold, rotation=(0, 0, ang))
        box_at("shikii", (cx, cy, base_z + 0.05), (length, 0.07, 0.06), gold, rotation=(0, 0, ang))
        box_at("panel", (cx, cy, base_z + post_h * 0.76), (length, 0.03, post_h * 0.44), hari, rotation=(0, 0, ang))
        if koshi is not None:
            box_at("koshi", (cx, cy, base_z + post_h * 0.29), (length, 0.035, post_h * 0.40), koshi, rotation=(0, 0, ang))
        nb = max(3, int(length / 0.22))
        for m in range(1, nb):
            t = m / nb
            bx, by = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            box_at("kobashira", (bx, by, base_z + post_h * 0.76),
                   (0.03, 0.05, post_h * 0.44), gold, rotation=(0, 0, ang))
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


def sankarado(R, th, z0, h, gold, panel_mat, hari, w=1.30):
    """桟唐戸ふうの板戸。框に囲まれた二枚の鏡板+格狭間の抜き。"""
    ux, uy = math.cos(th), math.sin(th)
    tang = th + math.pi / 2

    def at(t, n, z, size, mat, name):
        box_at(name, ((R + n) * ux + t * math.cos(tang),
                      (R + n) * uy + t * math.sin(tang), z),
               size, mat, rotation=(0, 0, tang))

    at(0, 0.05, z0 + h - 0.05, (w + 0.30, 0.08, 0.10), gold, "dframe_t")
    at(0, 0.05, z0 + 0.05, (w + 0.30, 0.08, 0.10), gold, "dframe_b")
    for sd in (-1, 1):
        at(sd * (w / 2 + 0.07), 0.05, z0 + h / 2, (0.10, 0.08, h), gold, "dframe_s")
        at(sd * w / 4, 0.035, z0 + h / 2, (w / 2 - 0.06, 0.05, h - 0.20), panel_mat, "dpanel")
        # 中桟(上下二段の鏡板に割る)
        at(sd * w / 4, 0.055, z0 + h * 0.62, (w / 2 - 0.06, 0.04, 0.07), gold, "dsan")
        # 上段は玻瓈の抜き(明かり取り)
        at(sd * w / 4, 0.045, z0 + h * 0.81, (w / 2 - 0.20, 0.03, h * 0.26), hari, "dhikari")
        for m in range(4):
            at(sd * w / 4 - (w / 2 - 0.16) / 2 + m * (w / 2 - 0.16) / 3, 0.055,
               z0 + h * 0.81, (0.05, 0.045, h * 0.30), gold, "dkoushi")
        for rz in (0.22, 0.48):
            for ry in (0.10, 0.30):
                at(sd * (w / 4 + ry - 0.2), 0.075, z0 + h * rz, (0.045, 0.03, 0.045), gold, "byou")


def renji_panel(R, th, z, h, gold, hari, w=1.35, step=0.155):
    """連子窓一枚: 玻瓈の面に細かい金の縦子を並べる。"""
    ux, uy = math.cos(th), math.sin(th)
    tang = th + math.pi / 2

    def at(t, n, zz, size, mat, name):
        box_at(name, ((R + n) * ux + t * math.cos(tang),
                      (R + n) * uy + t * math.sin(tang), zz),
               size, mat, rotation=(0, 0, tang))

    at(0, 0.03, z, (w, 0.04, h), hari, "rwin")
    at(0, 0.05, z + h / 2 + 0.05, (w + 0.22, 0.07, 0.09), gold, "rframe_t")
    at(0, 0.05, z - h / 2 - 0.05, (w + 0.22, 0.07, 0.09), gold, "rframe_b")
    for sd in (-1, 1):
        at(sd * (w / 2 + 0.06), 0.05, z, (0.09, 0.07, h + 0.20), gold, "rframe_s")
    n = int(w / step)
    for m in range(n + 1):
        t = -w / 2 + w * m / n
        at(t, 0.05, z, (0.045, 0.055, h), gold, "renji")


def wall_frame(R, z0, z1, gold, mids=(), pil=0.16, tube=0.05):
    """壁面の分節: 八隅の柱形と、上下(と中間)を巡る長押。
    「ただの面」を避け、板張りが框に納まって見えるようにする。"""
    for z in (z0 + 0.11, z1 - 0.11, *mids):
        pts = [((R + 0.035) * math.cos(k * OCT + HALF),
                (R + 0.035) * math.sin(k * OCT + HALF), z) for k in range(9)]
        _poly_tube(pts, tube, gold)
    for k in range(8):
        th = k * OCT + HALF          # 八角の頂点(稜)に柱形を立てる
        box_at("hashiragata", ((R + 0.02) * math.cos(th), (R + 0.02) * math.sin(th),
                               (z0 + z1) / 2), (pil, pil, z1 - z0), gold, rotation=(0, 0, th))


def build(path):
    reset_scene()
    gold = mat_of("gold")
    shuju = mat_of("shuju")
    hari = hari_material()
    # 文様ではなく材質そのもの: 壁は金箔押し、帯と床は鎚目、扉は磨き
    kinpaku = textured("kinpaku", "kinpaku.png", normal="kinpaku_normal.png",
                       metallic=0.92, roughness=0.28, tile=(4, 2))
    # 壁は金の羽目板張り。周長に合わせて板幅がそろうよう、階ごとに繰り返し数を変える
    hameita_l = textured("hameita_l", "hameita.png", normal="hameita_normal.png",
                         metallic=0.92, roughness=0.32, tile=(4, 1))
    hameita_m = textured("hameita_m", "hameita.png", normal="hameita_normal.png",
                         metallic=0.92, roughness=0.32, tile=(3, 1))
    hameita_s = textured("hameita_s", "hameita.png", normal="hameita_normal.png",
                         metallic=0.92, roughness=0.32, tile=(2, 1))
    hanabishi = textured("tsuchime", "tsuchime.png", normal="tsuchime_normal.png",
                         metallic=0.92, roughness=0.36, tile=(7, 1))
    renben = textured("tsuchime_low", "tsuchime.png", normal="tsuchime_normal.png",
                      metallic=0.92, roughness=0.36, tile=(8, 1))
    migaki = textured("migaki", "migaki.png", normal="migaki_normal.png",
                      metallic=0.95, roughness=0.24, tile=(2, 2))
    # 屋根は主楼と同じ瑠璃瓦(9/5 統一)。丸瓦は艶のある瑠璃
    gtiles = textured("ruri_tiles", "roof_tiles.png", normal="roof_tiles_normal.png",
                      metallic=0.35, roughness=0.35, tile=(4, 4))
    ruri_maru = plain_material("ruri_maru", (0.08, 0.16, 0.50), 0.35, 0.22, (0.02, 0.05, 0.20), 0.25)
    glow = plain_material("lantern_glow", (1.0, 0.86, 0.58), 0.0, 0.5, (1.0, 0.72, 0.36), 1.1)
    shuju_gem = gem_material("shuju_gem", (0.60, 0.04, 0.05), 1.78, (0.35, 0.02, 0.02), 0.3)
    pearl = plain_material("pearl", (0.97, 0.95, 0.91), 0.0, 0.22, (0.30, 0.28, 0.25), 0.3)
    studs = [Batch("stud_shuju", shuju_gem), Batch("stud_pearl", pearl)]
    hanabishi_koshi = textured("hanabishi_gold", "hanabishi.png", normal="hanabishi_normal.png",
                               metallic=0.85, roughness=0.35, tile=(6, 1))
    goldcol = textured("goldcol_b", "column_gold.png", normal="column_gold_normal.png",
                       metallic=0.85, roughness=0.35, tile=(2, 1))
    goldfloor = textured("goldfloor_b", "tsuchime.png", normal="tsuchime_normal.png",
                         metallic=0.9, roughness=0.46, tile=(4, 4))

    # ---- 基壇二段(蓮弁の帯+花菱の帯)+金の框 ----
    pod1 = cyl((0, 0, 0.30), 7.6, 0.60, renben, vertices=8)
    pod1.rotation_euler = (0, 0, HALF)
    pod2 = cyl((0, 0, 0.88), 6.9, 0.56, kinpaku, vertices=8)
    pod2.rotation_euler = (0, 0, HALF)
    for (R, z) in ((7.6, 0.60), (6.9, 1.16)):
        ringpts = [(R * math.cos(k * OCT + HALF), R * math.sin(k * OCT + HALF), z)
                   for k in range(9)]
        _poly_tube(ringpts, 0.045, gold)

    # ---- 正面(+x)の階段+手すり ----
    # 基壇二段目の面は x=6.375(内法半径)。段は面に正対し、地面から無垢で立てる
    rise = 1.16 / 6
    for i in range(6):
        top = rise * (i + 1)
        inner = 6.375 + (5 - i) * 0.38
        box_at("step", (inner + 0.19, 0, top / 2), (0.38, 4.2, top), goldfloor)
        box_at("stepnose", (inner + 0.35, 0, top - 0.03), (0.06, 4.2, 0.06), gold)
    slope = math.atan2(1.16, 2.28)
    for sy in (-1, 1):
        yk = sy * 2.15
        box_at("stringer", (7.515, yk, 0.62), (2.62, 0.12, 0.24), gold, rotation=(0, slope, 0))
        box_at("stair_rail", (7.515, yk, 1.40), (2.45, 0.07, 0.07), gold, rotation=(0, slope, 0))
        for (px, pz) in ((6.45, 1.16), (8.62, 0.0)):
            box_at("stair_post", (px, yk, pz + 0.40), (0.09, 0.09, 0.80), gold)
            sphere((px, yk, pz + 0.90), 0.06, gold, scale_z=1.25)

    # ---- 一層: 床・列柱・核壁(唐草)・扉・貫・欄間 ----
    cyl((0, 0, 1.24), 5.7, 0.16, goldfloor, vertices=8)
    for k in range(8):
        th = k * OCT
        gcolumn(4.9 * math.cos(th), 4.9 * math.sin(th), 1.32, 3.05, goldcol, gold)
    core = cyl((0, 0, 2.95), 3.3, 3.1, hameita_l, vertices=8)
    core.rotation_euler = (0, 0, HALF)
    wall_frame(3.3, 1.40, 4.50, gold, mids=(3.42,), pil=0.18, tube=0.055)
    doors(3.32, 1.42, 1.85, gold, migaki)
    # 斜め四面には板戸、全八面の頭上に欄間の連子窓を入れて壁の続きを断つ
    for k in range(4):
        sankarado(3.30, k * math.pi / 2 + math.pi / 4, 1.42, 1.85, gold, migaki, hari)
    for k in range(8):
        renji_panel(3.30, k * math.pi / 4, 3.86, 0.62, gold, hari, w=1.55, step=0.17)
    for bz in (2.55, 4.05):
        ringpts = [(4.9 * math.cos(k * OCT), 4.9 * math.sin(k * OCT), bz) for k in range(9)]
        _poly_tube(ringpts, 0.06, gold)
        # 木鼻: 貫が柱を貫いて突き出た先
        for k in range(8):
            sphere((4.9 * math.cos(k * OCT), 4.9 * math.sin(k * OCT), bz), 0.09, gold, segments=10, rings=8)
    # 上の貫に宝石の鋲(赤珠と真珠を交互に)
    for k in range(8):
        a0, a1 = k * OCT, (k + 1) * OCT
        gem_studs((4.96 * math.cos(a0), 4.96 * math.sin(a0)), (4.96 * math.cos(a1), 4.96 * math.sin(a1)), 4.05, studs)
    renji_ring(4.85, 4.30, 0.34, gold, hari)

    # ---- 一層の軒(花菱)+組物+屋根 ----
    cyl((0, 0, 4.56), 6.0, 0.16, hanabishi, vertices=8)
    okumimono(5.55, 4.42, gold, (-0.25, 0.0, 0.25))
    octo_roof(6.9, 0.95, 0.5, 4.66, gtiles, gold, shuju_gem, maru=ruri_maru, lanterns=True, glow=glow)

    # ---- 二層: 胴(屋根を貫いて床を受ける)+縁+列柱+核壁+連子窓+屋根 ----
    drum1 = cyl((0, 0, 5.42), 3.45, 1.0, hameita_l, vertices=8)
    drum1.rotation_euler = (0, 0, HALF)
    wall_frame(3.45, 4.95, 5.90, gold, pil=0.17)
    for k in range(8):
        renji_panel(3.45, k * math.pi / 4, 5.42, 0.46, gold, hari, w=1.50, step=0.185)
    cyl((0, 0, 5.90), 3.9, 0.16, goldfloor, vertices=8)
    orailing(3.75, 6.0, gold, hari, shuju, koshi=hanabishi_koshi)
    for k in range(8):
        th = k * OCT
        gcolumn(3.0 * math.cos(th), 3.0 * math.sin(th), 5.98, 2.25, goldcol, gold, radius=0.13)
    core2 = cyl((0, 0, 7.15), 2.2, 2.4, hameita_m, vertices=8)
    core2.rotation_euler = (0, 0, HALF)
    wall_frame(2.2, 5.95, 8.35, gold, mids=(7.05,), pil=0.15)
    renji_ring(2.95, 7.9, 0.30, gold, hari)
    for k in range(8):
        renji_panel(2.20, k * math.pi / 4, 7.30, 1.00, gold, hari, w=1.05, step=0.145)
    cyl((0, 0, 8.42), 3.6, 0.15, hanabishi, vertices=8)
    okumimono(3.3, 8.28, gold, (-0.22, 0.22))
    octo_roof(4.5, 0.85, 0.42, 8.50, gtiles, gold, shuju_gem, maru=ruri_maru, lanterns=True, glow=glow)

    # ---- 三層(小さな灯りの層)+屋根 ----
    core3 = cyl((0, 0, 9.85), 1.55, 1.9, hameita_s, vertices=8)
    core3.rotation_euler = (0, 0, HALF)
    wall_frame(1.55, 8.90, 10.80, gold, pil=0.13, tube=0.045)
    renji_ring(1.58, 10.05, 0.55, gold, hari, slat_step=0.16)
    cyl((0, 0, 10.86), 2.25, 0.13, hanabishi, vertices=8)
    for k in range(8):
        obracket(k * OCT + HALF, 2.05, 10.80, gold)
    octo_roof(3.2, 1.0, 0.4, 10.94, gtiles, gold, shuju_gem, rings=10, mseg=5, maru=ruri_maru)

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

    for b in studs:
        b.finish()
    export(path)
    patch_blend(path, {"hari"})
    print("patched hari->BLEND")


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "pavilion_b.glb"))
    print("done", file=sys.stderr)
