#!/usr/bin/env python3
"""七重羅網(しちじゅうらもう)の一区画をBlender(bpy)で生成してglb出力する。

「七重欄楯 七重羅網 七重行樹 皆是四宝 周匝囲繞」
七つの並木の環(TREE_RINGS)の上空に、宝石の網を七重の環として渡す。
一区画 = 長さ 12.4m × 幅 6m の網の帯。空間側で各環の弦の長さに合わせて環状に並べる
(環ごとに区画数を 2πR/12 に丸め、弦 ≈ 12m。0.4m 重ねてつなぎ目を隠す)。

構成(原点 = 帯の中心、+X が帯の長さ方向、+Z が上。帯は幅方向にたわむ):
  - 網: 45° に交差する二方向の金の糸(細い管)。菱形の目 約 0.85m。幅方向へ 0.5m たわむ
  - 縁綱: 長辺の両縁に太めの金の綱
  - 珠: 糸の交点に四宝の珠(金・銀・瑠璃・玻璃)を交互に
  - 瓔珞(ようらく): 外側の縁から 1.5m おきに三連の珠と赤珠の錘(おもり)が垂れる
  - 宝鈴: 縁綱の内側に 3m おきの小さな金の鈴

使い方: python3 tools/make_ramou.py
出力: public/assets/ramou.glb
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
CELL = 0.85      # 菱形の目の対角(糸の間隔)
SAG = 0.5        # 幅方向のたわみ
STRAND_R = 0.018
EDGE_R = 0.045

rand = random.Random(7)


def sag_z(y, x):
    """網面の高さ: 幅方向に放物線でたわみ、長さ方向にもごく浅くたわむ。"""
    return -SAG * (1 - (2 * y / WIDTH) ** 2) - 0.08 * (1 - (2 * x / LENGTH) ** 2)


def tube(points, radius, material, sides=5):
    """折れ線に沿った管を 1 メッシュとして作る(頂点データ直書き。曲線変換より速い)。"""
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
    """同じマテリアルの小部品をひとつのメッシュに詰める。"""

    def __init__(self, name, material):
        self.name, self.material = name, material
        self.verts, self.faces = [], []

    def add(self, verts, faces):
        base = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend(tuple(i + base for i in f) for f in faces)

    def sphere(self, center, r, segments=8, rings=6):
        verts, faces = [], []
        for i in range(rings + 1):
            phi = i / rings * math.pi
            for k in range(segments):
                a = k / segments * math.tau
                verts.append(center + Vector((math.cos(a) * math.sin(phi) * r, math.sin(a) * math.sin(phi) * r, math.cos(phi) * r)))
        for i in range(rings):
            for k in range(segments):
                a = i * segments + k
                b = i * segments + (k + 1) % segments
                faces.append((a, b, b + segments, a + segments))
        self.add(verts, faces)

    def finish(self):
        if not self.verts:
            return None
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.validate()
        mesh.update()
        for poly in mesh.polygons:
            poly.use_smooth = True
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(self.material)
        return obj


def build_ramou(path):
    reset_scene()
    gold = plain_material("gold", GOLD, 0.9, 0.3, (1.0, 0.8, 0.4), 0.15)
    silver = plain_material("silver", (0.9, 0.92, 0.95), 0.95, 0.25)
    lapis = plain_material("lapis", LAPIS, 0.3, 0.2, (0.08, 0.16, 0.5), 0.5)
    hari = plain_material("hari", (0.95, 0.98, 1.0), 0.1, 0.08, (0.8, 0.9, 1.0), 0.6)
    shuju = plain_material("shuju", (0.85, 0.12, 0.10), 0.3, 0.2, (0.5, 0.05, 0.03), 0.5)
    batches = {m.name: Batch(m.name, m) for m in (gold, silver, lapis, hari, shuju)}
    strands = Batch("gold_net", gold)

    # --- 網: ±45° の二方向の糸。交点を記録して珠を置く ---
    step = CELL  # 糸の間隔(対角方向)
    nodes = {}
    half_l, half_w = LENGTH / 2, WIDTH / 2
    for sign in (1, -1):
        # 直線 y = sign*(x - c) を c を変えて敷く
        c_min, c_max = -half_l - half_w, half_l + half_w
        c = c_min
        while c <= c_max:
            pts = []
            for i in range(41):
                x = -half_l + LENGTH * i / 40
                y = sign * (x - c)
                if -half_w <= y <= half_w:
                    pts.append(Vector((x, y, sag_z(y, x))))
            if len(pts) >= 2:
                strands.add(*tube(pts, STRAND_R, gold))
            c += step * math.sqrt(2)
    # 交点: 二方向の糸の交わり(x - c1 = -(x - c2) → x = (c1+c2)/2, y = (c2-c1)/2)
    cs = []
    c = -half_l - half_w
    while c <= half_l + half_w:
        cs.append(c)
        c += step * math.sqrt(2)
    kinds = [gold, silver, lapis, hari]
    count = 0
    for c1 in cs:
        for c2 in cs:
            x, y = (c1 + c2) / 2, (c2 - c1) / 2
            if abs(x) <= half_l - 0.1 and abs(y) <= half_w - 0.05:
                mat = kinds[count % 4]
                count += 1
                r = 0.075 if mat is gold else 0.07
                batches[mat.name].sphere(Vector((x, y, sag_z(y, x))), r)

    # --- 縁綱と瓔珞 ---
    for side in (-1, 1):
        y = side * half_w
        pts = [Vector((-half_l + LENGTH * i / 40, y, sag_z(y, -half_l + LENGTH * i / 40))) for i in range(41)]
        strands.add(*tube(pts, EDGE_R, gold, sides=6))
        # 瓔珞: 1.5m おきに三連の珠と赤珠の錘が垂れる
        x = -half_l + 0.75
        while x < half_l:
            z0 = sag_z(y, x)
            drop = [Vector((x, y, z0)), Vector((x, y, z0 - 0.75))]
            strands.add(*tube(drop, 0.012, gold, sides=4))
            for k, mat in enumerate((hari, gold, silver)):
                batches[mat.name].sphere(Vector((x, y, z0 - 0.18 - 0.2 * k)), 0.06)
            batches["shuju"].sphere(Vector((x, y, z0 - 0.82)), 0.09)
            x += 1.5
        # 宝鈴: 3m おきの小さな鈴(円錐+珠)
        x = -half_l + 1.5
        while x < half_l:
            z0 = sag_z(y - side * 0.25, x)
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.11, radius2=0.04, depth=0.16,
                                            location=(x, y - side * 0.25, z0 - 0.14))
            bell = bpy.context.active_object
            bell.data.materials.append(gold)
            batches["gold"].sphere(Vector((x, y - side * 0.25, z0 - 0.24)), 0.035)
            x += 3.0

    strands.finish()
    for b in batches.values():
        b.finish()
    export(path)


if __name__ == "__main__":
    build_ramou(os.path.join(OUT_DIR, "ramou.glb"))
    print("done", file=sys.stderr)
