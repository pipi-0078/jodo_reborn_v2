#!/usr/bin/env python3
"""七重羅網(しちじゅうらもう)の一区画をBlender(bpy)で生成してglb出力する。

「七重欄楯 七重羅網 七重行樹 皆是四宝 周匝囲繞」
七つの並木の環(TREE_RINGS)の上空に、宝石の網を七重の環として渡す。
一区画 = 長さ 12.4m × 幅 6m の網の帯。空間側で各環の弦の長さに合わせて環状に並べる
(環ごとに区画数を 2πR/12 に丸め、弦 ≈ 12m。0.4m 重ねてつなぎ目を隠す)。

9/4 初版は「針金に玉」で「チープ、豪華さゼロ」と却下 → 宝飾品として作り直し:
  - 糸: 金の芯線に 0.2m おきに面取りした宝石(金珠・玻璃・瑠璃)を連ねた瓔珞の鎖
  - 交点: 八弁の華鬘(けまん)の金具。中央に大きめの宝石。一つおきに配置し、残りは金の珠
  - 縁: 太い金の綱に、宝石を留めた金の帯(0.35m おき)
  - 垂れ飾り: 縁から 0.75m おきに、長(1.3m)短(0.7m)を交互に。珠を連ねて赤珠の錘で終わる
  - 飾り房: 帯の中心線に 3m おきの十六弁の大きな華鬘。玻璃の大珠を抱き、宝珠の鎖が 1.5m 垂れる
  - 宝鈴: 縁の内側に 3m おき

構成(原点 = 帯の中心、+X が帯の長さ方向、+Z が上。帯は幅方向にたわむ)
ramou.glb(豪華版・内側 3 環用)/ ramou_lod.glb(軽量版・外側 4 環用、遠景)

使い方: python3 tools/make_ramou.py
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_bridge import GOLD, LAPIS  # noqa: E402

LENGTH = 12.4
WIDTH = 6.0
CELL = 0.85      # 菱形の目(糸の間隔)
SAG = 0.5        # 幅方向のたわみ
WIRE_R = 0.014
ROPE_R = 0.05

rand = random.Random(7)


def sag_z(y, x):
    """網面の高さ: 幅方向に放物線でたわみ、長さ方向にもごく浅くたわむ。"""
    return -SAG * (1 - (2 * y / WIDTH) ** 2) - 0.08 * (1 - (2 * x / LENGTH) ** 2)


def tube(points, radius, sides=5):
    verts, faces = [], []
    n = len(points)
    for i, p in enumerate(points):
        if i == 0:
            d = (points[1] - points[0]).normalized()
        elif i == n - 1:
            d = (points[-1] - points[-2]).normalized()
        else:
            d = (points[i + 1] - points[i - 1]).normalized()
        helper = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(helper).normalized()
        v = d.cross(u)
        for k in range(sides):
            a = k / sides * math.tau
            verts.append(p + u * (math.cos(a) * radius) + v * (math.sin(a) * radius))
    for i in range(n - 1):
        for k in range(sides):
            a = i * sides + k
            b = i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    return verts, faces


class Batch:
    """同じマテリアルの小部品をひとつのメッシュに詰める。smooth=False で宝石の面取りを出す。"""

    def __init__(self, name, material, smooth=True):
        self.name, self.material, self.smooth = name, material, smooth
        self.verts, self.faces = [], []

    def add(self, verts, faces):
        base = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend(tuple(i + base for i in f) for f in faces)

    def sphere(self, center, r, segments=6, rings=4):
        verts, faces = [], []
        for i in range(rings + 1):
            phi = i / rings * math.pi
            for k in range(segments):
                a = k / segments * math.tau
                verts.append(center + Vector((math.cos(a) * math.sin(phi) * r, math.sin(a) * math.sin(phi) * r,
                                              math.cos(phi) * r)))
        for i in range(rings):
            for k in range(segments):
                a = i * segments + k
                b = i * segments + (k + 1) % segments
                faces.append((a, b, b + segments, a + segments))
        self.add(verts, faces)

    def gem(self, center, r, elong=1.4, facets=6):
        """面取りした宝石: 上下に尖った双錐(facets 面 × 2)。"""
        verts = [center + Vector((0, 0, r * elong))]
        for k in range(facets):
            a = k / facets * math.tau + 0.3
            verts.append(center + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
        verts.append(center + Vector((0, 0, -r * elong)))
        faces = []
        for k in range(facets):
            faces.append((0, 1 + k, 1 + (k + 1) % facets))
            faces.append((1 + facets, 1 + (k + 1) % facets, 1 + k))
        self.add(verts, faces)

    def petal_disc(self, center, r, petals, tilt=0.35, width=0.42):
        """華鬘(けまん)の金具: 菱形の花弁を放射状に並べた円盤。花弁の先はわずかに上へ反る。"""
        for k in range(petals):
            a = k / petals * math.tau
            c, s = math.cos(a), math.sin(a)
            n = Vector((-s, c, 0))
            base = len(self.verts)
            tip = center + Vector((c * r, s * r, r * tilt))
            mid = center + Vector((c * r * 0.55, s * r * 0.55, r * 0.06))
            self.verts.extend([center + Vector((0, 0, 0.01)), mid + n * (r * width * 0.5), tip, mid - n * (r * width * 0.5),
                               mid + Vector((0, 0, -0.03))])
            self.faces.extend([(base, base + 1, base + 2), (base, base + 2, base + 3),
                               (base + 4, base + 2, base + 1), (base + 4, base + 3, base + 2)])

    def finish(self):
        if not self.verts:
            return None
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.validate()
        mesh.update()
        for poly in mesh.polygons:
            poly.use_smooth = self.smooth
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(self.material)
        return obj


def build_ramou(path, rich=True):
    reset_scene()
    gold = plain_material("gold", GOLD, 0.9, 0.3, (1.0, 0.8, 0.4), 0.12)
    silver = plain_material("silver", (0.9, 0.92, 0.95), 0.95, 0.25)
    lapis = plain_material("lapis", LAPIS, 0.3, 0.15, (0.10, 0.18, 0.55), 0.7)
    hari = plain_material("hari", (0.95, 0.98, 1.0), 0.1, 0.05, (0.85, 0.92, 1.0), 0.9)
    shuju = plain_material("shuju", (0.85, 0.12, 0.10), 0.3, 0.15, (0.6, 0.06, 0.03), 0.7)
    wire = Batch("gold_wire", gold)              # 芯線・綱(滑らか)
    goldsmith = Batch("gold_fitting", gold, smooth=False)  # 華鬘・面取り珠(角を出す)
    gems = {m.name: Batch(m.name + "_gem", m, smooth=False) for m in (silver, lapis, hari, shuju)}
    pearls = Batch("gold_pearl", gold)           # 丸い金珠

    half_l, half_w = LENGTH / 2, WIDTH / 2
    step = CELL * math.sqrt(2)
    cs = []
    c = -half_l - half_w
    while c <= half_l + half_w:
        cs.append(c)
        c += step

    # --- 糸: 金の芯線 + 瓔珞の鎖(面取りした宝石を 0.2m おきに連ねる) ---
    chain_kinds = [pearls, gems["hari"], goldsmith, gems["lapis"]]
    for sign in (1, -1):
        for c in cs:
            pts = []
            for i in range(25):
                x = -half_l + LENGTH * i / 24
                y = sign * (x - c)
                if -half_w <= y <= half_w:
                    pts.append(Vector((x, y, sag_z(y, x))))
            if len(pts) < 2:
                continue
            wire.add(*tube(pts, WIRE_R, sides=4))
            if rich:
                # 鎖の珠: 糸に沿って等間隔
                x0 = max(-half_l, c - half_w) if sign == 1 else max(-half_l, c - half_w)
                x1 = min(half_l, c + half_w)
                t = x0 + 0.1
                k = 0
                while t < x1 - 0.05:
                    y = sign * (t - c)
                    p = Vector((t, y, sag_z(y, t)))
                    kind = chain_kinds[k % 4]
                    if kind is pearls:
                        pearls.sphere(p, 0.05)
                    else:
                        kind.gem(p, 0.045 if kind is goldsmith else 0.05)
                    t += 0.2 / math.sqrt(2) * 1.4
                    k += 1

    # --- 交点: 一つおきに八弁の華鬘、残りは金珠 ---
    idx = 0
    for i, c1 in enumerate(cs):
        for j, c2 in enumerate(cs):
            x, y = (c1 + c2) / 2, (c2 - c1) / 2
            if abs(x) > half_l - 0.15 or abs(y) > half_w - 0.05:
                continue
            p = Vector((x, y, sag_z(y, x)))
            if rich and (i + j) % 2 == 0:
                goldsmith.petal_disc(p, 0.2, 8)
                gem = [gems["hari"], gems["lapis"], gems["shuju"]][idx % 3]
                gem.gem(p + Vector((0, 0, 0.05)), 0.075, elong=1.1, facets=8)
                idx += 1
            else:
                pearls.sphere(p, 0.07)

    # --- 縁: 太い綱 + 宝石を留めた帯 + 垂れ飾り + 宝鈴 ---
    for side in (-1, 1):
        y = side * half_w
        pts = [Vector((-half_l + LENGTH * i / 24, y, sag_z(y, -half_l + LENGTH * i / 24))) for i in range(25)]
        wire.add(*tube(pts, ROPE_R, sides=6))
        if rich:
            # 帯の宝石: 0.35m おき、玻璃と瑠璃を交互に、金の台座付き
            x = -half_l + 0.2
            k = 0
            while x < half_l - 0.1:
                p = Vector((x, y, sag_z(y, x) + 0.04))
                goldsmith.petal_disc(p, 0.09, 6, tilt=0.5, width=0.6)
                [gems["hari"], gems["lapis"]][k % 2].gem(p + Vector((0, 0, 0.04)), 0.05, elong=1.0, facets=6)
                x += 0.35
                k += 1
        # 垂れ飾り: 0.75m おきに長短交互。珠を連ねて赤珠の錘で終わる
        x = -half_l + 0.4
        k = 0
        while x < half_l - 0.2:
            z0 = sag_z(y, x)
            long = k % 2 == 0
            length = 1.3 if long else 0.7
            wire.add(*tube([Vector((x, y, z0)), Vector((x, y, z0 - length))], 0.01, sides=4))
            n_beads = 6 if long else 3
            for b in range(n_beads):
                zz = z0 - 0.12 - b * (length - 0.3) / n_beads
                kind = [gems["hari"], pearls, gems["lapis"], pearls, gems["silver"], pearls][b % 6]
                if kind is pearls:
                    pearls.sphere(Vector((x, y, zz)), 0.055)
                else:
                    kind.gem(Vector((x, y, zz)), 0.06)
            gems["shuju"].gem(Vector((x, y, z0 - length - 0.02)), 0.09, elong=1.3, facets=8)
            if rich and long:
                goldsmith.petal_disc(Vector((x, y, z0 - length + 0.1)), 0.11, 6, tilt=-0.6, width=0.5)  # 錘の上の受け皿(逆さの華)
            x += 0.75
            k += 1
        # 宝鈴: 3m おき
        x = -half_l + 1.5
        while x < half_l:
            z0 = sag_z(y - side * 0.25, x)
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.12, radius2=0.045, depth=0.17,
                                            location=(x, y - side * 0.25, z0 - 0.15))
            bell = bpy.context.active_object
            bell.data.materials.append(gold)
            pearls.sphere(Vector((x, y - side * 0.25, z0 - 0.26)), 0.035)
            x += 3.0

    # --- 飾り房: 中心線に 3m おきの大きな華鬘と宝珠の鎖 ---
    if rich:
        x = -half_l + 1.55
        while x < half_l:
            p = Vector((x, 0, sag_z(0, x)))
            goldsmith.petal_disc(p, 0.42, 16, tilt=0.25, width=0.35)
            goldsmith.petal_disc(p + Vector((0, 0, 0.03)), 0.26, 8, tilt=0.45, width=0.5)
            gems["hari"].gem(p + Vector((0, 0, 0.1)), 0.13, elong=1.0, facets=8)
            # 宝珠の鎖: 1.5m 垂れる
            wire.add(*tube([p, p + Vector((0, 0, -1.5))], 0.012, sides=4))
            for b in range(7):
                zz = p.z - 0.2 - b * 0.17
                kind = [pearls, gems["lapis"], pearls, gems["hari"], pearls, gems["silver"], pearls][b]
                if kind is pearls:
                    pearls.sphere(Vector((x, 0, zz)), 0.06)
                else:
                    kind.gem(Vector((x, 0, zz)), 0.07)
            goldsmith.petal_disc(Vector((x, 0, p.z - 1.38)), 0.14, 8, tilt=-0.6, width=0.5)
            gems["shuju"].gem(Vector((x, 0, p.z - 1.55)), 0.14, elong=1.3, facets=8)
            x += 3.0

    for b in (wire, goldsmith, pearls, *gems.values()):
        b.finish()
    export(path)


if __name__ == "__main__":
    build_ramou(os.path.join(OUT_DIR, "ramou.glb"), rich=True)
    build_ramou(os.path.join(OUT_DIR, "ramou_lod.glb"), rich=False)
    print("done", file=sys.stderr)
