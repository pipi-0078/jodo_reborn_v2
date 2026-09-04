#!/usr/bin/env python3
"""七重羅網(しちじゅうらもう)の一区画をBlender(bpy)で生成してglb出力する。

「七重欄楯 七重羅網 七重行樹 皆是四宝 周匝囲繞」
七つの並木の環(TREE_RINGS)の上空に、宝石の網を七重の環として渡す。
一区画 = 長さ 12.4m × 幅 6m の網の帯。空間側で各環の弦の長さに合わせて環状に並べる
(環ごとに区画数を 2πR/12 に丸め、弦 ≈ 12m。0.4m 重ねてつなぎ目を隠す)。

9/4 初版は「針金に玉」で「チープ、豪華さゼロ」と却下 → 宝飾品として作り直し → 参考図に合わせてスワッグ構造へ:
  - 支点(華鬘の金具+大きな色石)は区画の始端だけ(12.4m / 6.2m おき)。鎖は懸垂線(電線のたるみ)で、深さは間隔の 30/38/46%(三本重ね)
  - 幅方向に 3 列、高さをずらして重ねる。列どうしは斜めの鎖でつなぐ
  - 支点から長さ違い(1.3〜2.4m)の垂れ飾り。真珠と水晶を連ね、先に色石の雫
以下は旧版の構成メモ:
  - 糸: 金の芯線に 0.2m おきにブリリアントカットの宝石(金珠・玻璃・瑠璃)を連ねた瓔珞の鎖
  - 宝石は透過ガラス(屈折率 1.7〜1.95、粗さ 0.04)。塗った面に発光を足すとプラスチックに見える(9/4)
  - 交点: 八弁の華鬘(けまん)の金具。中央に大きめの宝石。一つおきに配置し、残りは金の珠
  - 縁: 太い金の綱に、宝石を留めた金の帯(0.35m おき)
  - 垂れ飾り: 縁から 0.75m おきに、長(1.3m)短(0.7m)を交互に。珠を連ねて赤珠の錘で終わる
  - 飾り房: 帯の中心線に 3m おきの十六弁の大きな華鬘。玻璃の大珠を抱き、宝珠の鎖が 1.5m 垂れる
  - 宝鈴: 縁の内側に 3m おき

構成(原点 = 帯の中心、+X が帯の長さ方向、+Z が上。帯は幅方向にたわむ)
ramou.glb(12.4m・外側の環用)/ ramou_short.glb(6.2m・内側の環用)。9/4: 環は池の上(r=14〜38m)に集約、岸側 14.8m → 中心側 22m の天蓋

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

    def sphere(self, center, r, segments=5, rings=3):
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

    def gem(self, center, r, elong=1.4, facets=8):
        """ブリリアントカット風の宝石: 上のテーブル面 + クラウンの斜面 + ガードル + パビリオン(下の尖り)。
        面が多いほど光を細かく返す。elong はパビリオンの深さ。"""
        crown_h = r * 0.45
        table_r = r * 0.55
        base = len(self.verts)
        verts, faces = [], []
        # テーブル(上面)
        for k in range(facets):
            a = k / facets * math.tau + 0.3
            verts.append(center + Vector((math.cos(a) * table_r, math.sin(a) * table_r, crown_h)))
        # ガードル(最大径)
        for k in range(facets):
            a = (k + 0.5) / facets * math.tau + 0.3
            verts.append(center + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
        apex = len(verts)
        verts.append(center + Vector((0, 0, -r * elong)))
        faces.append(tuple(range(facets)))  # テーブル
        for k in range(facets):
            t0, t1 = k, (k + 1) % facets
            g0, g1 = facets + (k - 1) % facets, facets + k
            faces.append((t0, g1, g0))            # クラウン: テーブルの頂点から下の二つのガードル点へ
            faces.append((t0, t1, g1))            # クラウンのつなぎ
            faces.append((apex, g1, g0))          # パビリオン
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


def gem_material(name, color, ior=1.78, emission=None, strength=0.0):
    """宝石: 透過するガラス。屈折率を高く、面は鏡のように滑らかに。色は内部に沈む(base color)。
    glTF には KHR_materials_transmission / ior として出る。発光は控えめ(強いとプラスチックに見える 9/4)"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Transmission Weight"].default_value = 0.8
    bsdf.inputs["Specular IOR Level"].default_value = 1.0
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def build_ramou(path, rich=True, length=LENGTH):
    K = 2.2  # 瓔珞(珠・宝石・金具)の寸法倍率。20m 下から見上げるので大きく(9/4「小さすぎる」)
    """スワッグ(花綱)構造の羅網。9/4 の参考図に合わせて作り直し:
    支点(華鬘の金具+大きな色石)を 3.1m おきに置き、支点のあいだに真珠と水晶の鎖が弧を描いて垂れる。
    幅方向に 3 列(高さをずらして重ねる)、支点からは長さ違いの垂れ飾り。色石は支点と垂れ飾りの先に集める。"""
    reset_scene()
    gold = plain_material("gold_polished", GOLD, 1.0, 0.22)
    pearl = plain_material("pearl", (0.97, 0.95, 0.91), 0.0, 0.22, (0.30, 0.28, 0.25), 0.3)
    lapis = gem_material("lapis_gem", (0.04, 0.10, 0.52), 1.72, (0.03, 0.06, 0.25), 0.25)
    hari = gem_material("hari_gem", (0.92, 0.96, 1.0), 1.95, (0.6, 0.7, 0.9), 0.12)
    shuju = gem_material("shuju_gem", (0.60, 0.04, 0.05), 1.78, (0.35, 0.02, 0.02), 0.3)
    wire = Batch("gold_wire", gold)
    goldsmith = Batch("gold_fitting", gold, smooth=False)
    pearls = Batch("pearl_batch", pearl)
    gems = {"lapis": Batch("lapis_batch", lapis, smooth=False), "hari": Batch("hari_batch", hari, smooth=False),
            "shuju": Batch("shuju_batch", shuju, smooth=False)}
    colored = [gems["shuju"], gems["lapis"], gems["hari"]]

    half_l = length / 2
    rows = [(1.4, 0.0), (0.0, -1.5), (-1.4, -3.0)] if rich else [(0.0, -0.4)]  # 幅 4m。列の高さ差 1.5m で層を見せる

    def chain(p0, p1, sag, spacing, pattern, wire_r=0.012 * 1.8):
        """p0→p1 を懸垂線(カテナリー: 電線のたるみの形)で垂らした鎖。pattern は珠の種類の並び。"""
        n = 32
        horizontal = Vector((p1.x - p0.x, p1.y - p0.y, 0)).length
        # sag = a (cosh(L/2a) - 1) を満たす a を二分法で求める
        lo, hi = 0.01, 1000.0
        for _ in range(60):
            a = (lo + hi) / 2
            if a * (math.cosh(horizontal / (2 * a)) - 1) > sag:
                lo = a
            else:
                hi = a
        a = (lo + hi) / 2
        top = a * math.cosh(horizontal / (2 * a))
        pts = []
        for i in range(n + 1):
            t = i / n
            p = p0.lerp(p1, t)
            x = (t - 0.5) * horizontal
            pts.append(Vector((p.x, p.y, p.z + a * math.cosh(x / a) - top)))
        wire.add(*tube(pts, wire_r, sides=4))
        length_total = sum((pts[i + 1] - pts[i]).length for i in range(n))
        count = max(2, int(length_total / spacing))
        k = 0
        for i in range(count + 1):
            t = i / count
            seg = t * n
            a_i = min(int(seg), n - 1)
            p = pts[a_i].lerp(pts[a_i + 1], seg - a_i)
            pattern[k % len(pattern)](p)
            k += 1

    def pearl_at(r):
        return lambda p: pearls.sphere(p, r)

    def gem_at(batch, r, elong=1.2):
        return lambda p: batch.gem(p, r, elong=elong, facets=8)

    def pendant(p, length, big_color):
        """支点から垂れる飾り: 真珠と水晶を交互に連ね、先に色石の雫。"""
        wire.add(*tube([p, p + Vector((0, 0, -length))], 0.01 * K, sides=4))
        n = int(length / (0.13 * K))
        for i in range(n):
            q = p + Vector((0, 0, -0.1 - i * 0.13 * K))
            if i % 3 == 2:
                gems["hari"].gem(q, 0.055 * K, elong=1.3, facets=8)
            else:
                pearls.sphere(q, 0.045 * K)
        goldsmith.petal_disc(p + Vector((0, 0, -length + 0.08 * K)), 0.09 * K, 6, tilt=-0.7, width=0.5)
        big_color.gem(p + Vector((0, 0, -length - 0.08 * K)), 0.11 * K, elong=1.8, facets=8)

    gem_idx = 0
    sag_ratios = (0.30, 0.38, 0.46)  # 弧の深さ / 支点間隔(電線のように長くしなる 9/4)
    for row, (y, z_row) in enumerate(rows):
        a = Vector((-half_l, y, z_row))              # 支点は区画の始端だけ(次の区画の始端が終点になる)
        b = Vector((half_l - 0.3, y, z_row))         # 区画の重なり分だけ手前で終える
        # 支持線(細い金の綱)
        wire.add(*tube([Vector((-half_l, y, z_row)), Vector((half_l, y, z_row))], 0.03, sides=6))
        # 支点: 華鬘の金具 + 大きな色石 + 垂れ飾り
        goldsmith.petal_disc(a, 0.30 * K, 8, tilt=0.3, width=0.4)
        goldsmith.petal_disc(a + Vector((0, 0, 0.03 * K)), 0.17 * K, 8, tilt=0.5, width=0.5)
        colored[gem_idx % 3].gem(a + Vector((0, 0, 0.08 * K)), 0.14 * K, elong=1.0, facets=8)
        if rich:
            drop = 5.0 + 1.5 * (row % 3)  # 5.0〜8.0m
            pendant(a + Vector((0, 0, -0.05)), drop, colored[(gem_idx + 1) % 3])
        gem_idx += 1
        # 花綱: 三本の鎖(真珠 / 水晶 / 真珠+色石)を深さ違いで
        chain(a, b, sag_ratios[0] * length, 0.11 * K, [pearl_at(0.045 * K)])
        if rich:
            chain(a, b, sag_ratios[1] * length, 0.14 * K, [gem_at(gems["hari"], 0.05 * K), pearl_at(0.035 * K)])
            chain(a, b, sag_ratios[2] * length, 0.11 * K, [pearl_at(0.04 * K)] * 4 + [gem_at(colored[gem_idx % 3], 0.06 * K)])
            # 弧の底の雫
            low = (a + b) / 2 + Vector((0, 0, -sag_ratios[2] * length))
            wire.add(*tube([low, low + Vector((0, 0, -1.2 * K))], 0.008 * K, sides=4))
            for i in range(6):
                pearls.sphere(low + Vector((0, 0, (-0.15 - i * 0.16) * K)), 0.04 * K)
            gems["hari"].gem(low + Vector((0, 0, -1.25 * K)), 0.10 * K, elong=1.8, facets=8)
            gem_idx += 1
        # 列どうしをつなぐ鎖(支点から次の列の支点へ)
        if rich and row + 1 < len(rows):
            y2, z2 = rows[row + 1]
            chain(a, Vector((-half_l, y2, z2)), 0.12 * length, 0.13 * K, [pearl_at(0.035 * K), gem_at(gems["hari"], 0.04 * K)])

    wire.finish()
    goldsmith.finish()
    pearls.finish()
    for b in gems.values():
        b.finish()
    export(path)


if __name__ == "__main__":
    build_ramou(os.path.join(OUT_DIR, "ramou.glb"), rich=True, length=12.4)        # 外側の環(r ≥ 26m)
    build_ramou(os.path.join(OUT_DIR, "ramou_short.glb"), rich=True, length=6.2)   # 内側の環(r < 26m、弦を短く)
    print("done", file=sys.stderr)
