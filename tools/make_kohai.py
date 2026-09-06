#!/usr/bin/env python3
"""光背(こうはい): 阿弥陀如来坐像(amida_hitem3d 系)の背に立てる、二重円光の舟形光背をglb出力する。

坐像と同じ座標系(glb: y-up、像の高さ 1.0、正面 +z)で作るので、像と同じ変換で置けば重なる。
  Blender(z-up)では glb(x, y, z) = Blender(x, -z, y)。像の背は glb z=-0.25 → Blender y=+0.25。
寸法は像の実測(9/6): 頭の中心 高さ 0.40・半径 0.10、肩幅 ±0.22、台座の上面 高さ約 -0.20。

構成:
  頭光: 蓮華文の中心盤+宝石を留めた環+三十二条の放射光
  身光: 二重の環+四十八条の放射光+宝石
  舟形の枠: 金の縁に沿って火焔が立ち上がる。枠と身光のあいだに唐草(渦巻き)の透かし
  枠の内側に七つの宝珠(桜色・水色・水晶の雫を金の華鬘で留める)
  支柱: 台座の背から光背の裏へ
出力: public/assets/kohai.glb
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_bridge import box_at, GOLD  # noqa: E402
from make_pavilion import cyl, sphere, torus, _poly_tube  # noqa: E402
from make_ramou import Batch, gem_material  # noqa: E402

Y = 0.30          # 光背の面(像の背より少し後ろ)
HEAD = (0.0, 0.40)  # 頭光の中心 (x, z)
BODY = (0.0, 0.08)  # 身光の中心


def ring(center, r, tube, mat, y=Y):
    torus((center[0], y, center[1]), r, tube, mat, rotation=(math.pi / 2, 0, 0))


def rays(center, r0, r1, count, mat, w0=0.014, w1=0.006, th=0.012, y=Y, phase=0.0):
    """放射光: 中心から外へ細くなる金の条"""
    cx, cz = center
    for k in range(count):
        a = phase + k / count * math.tau
        rm = (r0 + r1) / 2
        length = r1 - r0
        box_at("ray", (cx + math.cos(a) * rm, y, cz + math.sin(a) * rm), (length, th, (w0 + w1) / 2), mat,
               rotation=(0, -a, 0))


def boat_outline(n=80):
    """舟形の輪郭 (x, z)。下は台座の背に隠れる丸み、上は尖る"""
    pts = []
    zb, zt = -0.22, 1.02   # 下端・上端
    for k in range(n + 1):
        t = k / n            # 0: 下端 → 1: 上端(右半分)
        z = zb + (zt - zb) * t
        # 幅: 下で丸く、身光あたりで最大 0.50、上へ尖る
        w = 0.50 * math.sin(math.pi * min(1.0, (t + 0.04) / 1.04)) ** 0.55
        u = max(0.0, t - 0.55) / 0.45
        w *= 1 - 0.65 * (3 * u * u - 2 * u ** 3)   # 上へ滑らかに絞る(折れ線にならないように)
        pts.append((w, z))
    right = pts
    left = [(-x, z) for (x, z) in reversed(pts)]
    return right + left[1:]


def flame(base, direction, length, mat, y=Y, sway=1.0):
    """火焔: 外へ立ち上がり、先で S 字にゆれる細い舌"""
    bx, bz = base
    dx, dz = direction
    px, pz = -dz, dx   # 接線方向
    pts = []
    for k in range(7):
        t = k / 6
        s = math.sin(t * math.pi * 1.4) * 0.22 * sway * length
        x = bx + dx * length * t + px * s
        z = bz + dz * length * t + pz * s + 0.15 * length * t * t
        pts.append((x, y - 0.006 + 0.012 * (k % 2), z))
    _poly_tube(pts, 0.011 * (1 - 0.0), mat, resolution=1)
    tip = pts[-1]
    sphere(tip, 0.006, mat, segments=6, rings=4)


def spiral(center, r_max, turns, mat, y=Y, mirror=1, phase=0.0):
    """唐草の渦巻き(アルキメデス螺旋)"""
    pts = []
    n = 34
    for k in range(n + 1):
        t = k / n
        a = phase + mirror * t * turns * math.tau
        r = r_max * (0.12 + 0.88 * t)
        pts.append((center[0] + math.cos(a) * r, y, center[1] + math.sin(a) * r))
    _poly_tube(pts, 0.007, mat, resolution=1)
    sphere(pts[0], 0.012, mat, segments=8, rings=6)


def build(path):
    reset_scene()
    gold = plain_material("gold", GOLD, 1.0, 0.36)
    polished = plain_material("gold_polished", GOLD, 1.0, 0.18)
    shuju = gem_material("shuju_gem", (0.60, 0.04, 0.05), 1.78, (0.35, 0.02, 0.02), 0.3)
    hari = gem_material("hari_gem", (0.92, 0.96, 1.0), 1.95, (0.6, 0.7, 0.9), 0.12)
    sakura = gem_material("sakura_gem", (0.98, 0.80, 0.84), 1.55, (0.5, 0.3, 0.33), 0.1)
    mizu = gem_material("mizu_gem", (0.80, 0.93, 0.98), 1.55, (0.35, 0.48, 0.55), 0.1)
    gems = {"shuju": Batch("g_shuju", shuju, smooth=False), "hari": Batch("g_hari", hari, smooth=False),
            "sakura": Batch("g_sakura", sakura, smooth=False), "mizu": Batch("g_mizu", mizu, smooth=False)}
    fittings = Batch("fittings", polished, smooth=False)

    # ---- 頭光 ----
    hx, hz = HEAD
    cyl((hx, Y, hz), 0.135, 0.012, gold, vertices=48, rotation=(math.pi / 2, 0, 0))          # 中心盤
    fittings.petal_disc(Vector((hx, Y - 0.012, hz)), 0.11, 8, tilt=0.0, width=0.55)            # 蓮華文
    fittings.petal_disc(Vector((hx, Y - 0.018, hz)), 0.065, 8, tilt=0.0, width=0.6)
    sphere((hx, Y - 0.02, hz), 0.02, polished, segments=12, rings=8)
    ring((hx, hz), 0.145, 0.010, polished)
    ring((hx, hz), 0.175, 0.008, gold)
    for k in range(16):                                                                       # 環の宝石
        a = k / 16 * math.tau
        gems["shuju" if k % 2 == 0 else "hari"].sphere(Vector((hx + math.cos(a) * 0.160, Y - 0.012, hz + math.sin(a) * 0.160)), 0.011)
    rays((hx, hz), 0.18, 0.235, 32, polished, w0=0.016, w1=0.005)
    ring((hx, hz), 0.24, 0.006, gold)

    # ---- 身光 ----
    bx, bz = BODY
    ring((bx, bz), 0.30, 0.009, gold)
    ring((bx, bz), 0.34, 0.007, gold)
    rays((bx, bz), 0.305, 0.345, 48, polished, w0=0.012, w1=0.006, th=0.010, phase=math.pi / 48)
    for k in range(24):
        a = k / 24 * math.tau
        gems["mizu" if k % 2 == 0 else "hari"].sphere(Vector((bx + math.cos(a) * 0.30, Y - 0.011, bz + math.sin(a) * 0.30)), 0.010)
    rays((bx, bz), 0.36, 0.44, 48, gold, w0=0.020, w1=0.005, th=0.012)                        # 外側の放射光
    ring((bx, bz), 0.445, 0.007, gold)

    # ---- 舟形の枠と火焔 ----
    outline = boat_outline()
    frame = [(x, Y, z) for (x, z) in outline] + [(outline[0][0], Y, outline[0][1])]
    _poly_tube(frame, 0.016, gold)
    inner = [(x * 0.94, Y, z * 0.96 + 0.01) for (x, z) in outline]
    _poly_tube(inner + [inner[0]], 0.009, polished, resolution=1)
    n = len(outline)
    for k in range(0, n, 2):
        x, z = outline[k]
        if z < -0.05:
            continue                     # 台座に隠れる下端には火焔を付けない
        x2, z2 = outline[(k + 1) % n]
        tx, tz = x2 - x, z2 - z
        ln = math.hypot(tx, tz) or 1.0
        nx, nz = tz / ln, -tx / ln       # 外向き法線(右回りの輪郭)
        if x < 0:
            nx, nz = -nx, -nz if False else nz
            nx = -abs(nx)
        else:
            nx = abs(nx)
        height_t = (z + 0.22) / 1.24
        length = 0.07 + 0.06 * math.sin(math.pi * height_t) + (0.05 if height_t > 0.9 else 0)
        flame((x, z), (nx, nz), length, polished, sway=1.0 if k % 4 == 0 else -0.8)
        if k % 4 == 0:
            flame((x * 0.985, z * 0.985 + 0.004), (nx, nz), length * 0.55, gold, sway=-0.6)

    # ---- 唐草の透かし(身光と枠のあいだ、左右対称) ----
    for mirror in (1, -1):
        for (cx, cz, r, ph) in ((0.40, 0.02, 0.055, 0.3), (0.44, 0.22, 0.05, 1.2), (0.36, 0.42, 0.05, 2.0),
                                (0.26, 0.60, 0.045, 0.8), (0.14, 0.74, 0.04, 2.6), (0.30, -0.14, 0.045, 1.6)):
            spiral((mirror * cx, cz), r, 1.6, gold, mirror=mirror, phase=ph)
    # 枠の内側に七つの宝珠(華鬘に留める)
    for k in range(7):
        t = -0.42 + 0.84 * k / 6
        a = math.pi / 2 + t * math.pi      # 上を中心に左右へ
        rr = 0.50
        x, z = math.cos(a) * rr * 0.86, 0.34 + math.sin(a) * rr * 1.10
        fittings.petal_disc(Vector((x, Y - 0.014, z)), 0.03, 6, tilt=0.0, width=0.55)
        gems[("sakura", "mizu", "hari")[k % 3]].gem(Vector((x, Y - 0.028, z + 0.018)), 0.017, elong=1.5, facets=8)

    # ---- 支柱: 台座の背から光背の裏へ ----
    cyl((0, Y + 0.02, -0.02), 0.022, 0.42, gold, vertices=10)
    box_at("stay", (0, Y + 0.05, -0.20), (0.16, 0.10, 0.05), gold)
    cyl((0, Y + 0.02, 0.08), 0.05, 0.02, gold, vertices=12)

    for b in (fittings, *gems.values()):
        b.finish()
    export(path)


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "kohai.glb"))
    print("done", file=sys.stderr)
