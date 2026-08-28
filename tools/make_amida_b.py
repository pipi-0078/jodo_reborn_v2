#!/usr/bin/env python3
"""自作の阿弥陀如来坐像(説法印)をBlender(bpy)で生成してglb出力する。

既存のスキャン像(比率の参考)とは別の、完全手続き生成のオリジナル。
- 体躯: メタボール(有機的に融け合う塊)で結跏趺坐の量感を作り、滑らかに変換
- 相好: 肉髻・白毫・長い耳朶・伏し目・鼻・口を別造形で重ねる
- 印相: 説法印(転法輪印)。胸前で両手の親指と人差し指が輪を結ぶ
- 衣: 袈裟の縁と裾の襞を細い管で表す
- 表面: 磨き上げた黄金(ツルッとした面)

使い方: python3 tools/make_amida_b.py
出力: public/assets/amida_b.glb
"""
import math
import os
import sys

import bpy
from mathutils import Vector, Quaternion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_pavilion import cyl, sphere, torus, _poly_tube  # noqa: E402

GOLD = None


def gold():
    global GOLD
    if GOLD is None:
        GOLD = plain_material("gold_smooth", (0.85, 0.64, 0.22), 0.95, 0.16,
                              (0.45, 0.30, 0.08), 0.15)
    return GOLD


def island_count(obj):
    """メッシュの連結成分数(1でなければ体がばらばら)。"""
    n = len(obj.data.vertices)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in obj.data.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    return len({find(i) for i in range(n)})


def drape(body, pts, radius, lift=0.010, samples=14):
    """制御点間を補間した点列を体の表面へ投影し、沿う管として置く。"""
    ctrl = [Vector(pnt) for pnt in pts]
    line = []
    for i in range(samples + 1):
        t = i / samples * (len(ctrl) - 1)
        k = min(int(t), len(ctrl) - 2)
        f = t - k
        line.append(ctrl[k].lerp(ctrl[k + 1], f))
    proj = []
    for pnt in line:
        ok, loc, nrm, _ = body.closest_point_on_mesh(pnt)
        if ok:
            proj.append(tuple(Vector(loc) + Vector(nrm) * lift))
    _poly_tube(proj, radius, gold())


def quat_z_to(v):
    """ローカル+Z軸をvへ向ける回転。"""
    return Vector((0, 0, 1)).rotation_difference(Vector(v).normalized())


def make_meta(name, elements, resolution=0.03, threshold=0.22):
    """メタボール群をメッシュへ変換して返す。
    elements: (co, radius, size, rotation_dir or None) のリスト。
    しきい値は低め=面が名目半径に近づき、隣の塊とよく融合する。"""
    mb = bpy.data.metaballs.new(name)
    mb.resolution = resolution
    mb.threshold = threshold
    obj = bpy.data.objects.new(name, mb)
    bpy.context.collection.objects.link(obj)
    for co, radius, size, direction in elements:
        el = mb.elements.new(type="ELLIPSOID" if size else "BALL")
        el.co = co
        el.radius = radius
        if size:
            el.size_x, el.size_y, el.size_z = size
        if direction:
            el.rotation = quat_z_to(direction)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    mesh = bpy.context.active_object
    sm = mesh.modifiers.new("smooth", "SMOOTH")
    sm.factor = 0.9
    sm.iterations = 10
    ss = mesh.modifiers.new("subsurf", "SUBSURF")
    ss.levels = 1
    ss.render_levels = 1
    bpy.ops.object.shade_smooth()
    mesh.data.materials.append(gold())
    bb = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
    lo = Vector(map(min, *bb)); hi = Vector(map(max, *bb))
    print(f"[bbox] {name}: x {lo.x:.2f}..{hi.x:.2f}  y {lo.y:.2f}..{hi.y:.2f}  z {lo.z:.2f}..{hi.z:.2f}")
    return mesh


def build_hand(side):
    """説法印の手。親指と人差し指の輪は手の縁に半ば埋め、三指は軽く立てる。
    ローカル: 指+z、掌の法線+x。sideは+1=左(y+), -1=右(y-)。"""
    sgn = side
    els = []
    els.append(((0, 0, 0), 0.05, (0.42, 1.0, 1.15), None))              # 掌
    for y, ln in ((0.014 * sgn, 2.4), (0.036 * sgn, 2.1), (0.056 * sgn, 1.8)):
        els.append(((-0.004, y, 0.07), 0.015, (0.7, 0.7, ln),
                    (-0.12, y * 0.25, 1)))                               # 中・薬・小指
    els.append(((0, -0.030 * sgn, 0.055), 0.014, (0.7, 0.7, 1.6),
                (0.02, -0.03 * sgn, 1)))                                 # 人差し指の基節
    els.append(((0.004, -0.045 * sgn, -0.015), 0.016, (0.7, 0.7, 1.5),
                (0.05, -0.05 * sgn, 0.5)))                               # 親指
    hand = make_meta(f"hand_{'L' if sgn > 0 else 'R'}", els, resolution=0.012)
    # 親指と人差し指が結ぶ輪(手の縁に半分埋める)
    ring = torus((0.012, -0.052 * sgn, 0.035), 0.028, 0.009, gold())
    ring.rotation_euler = (0, math.radians(90), 0)
    return hand, ring


def build(path):
    reset_scene()
    g = gold()

    # ---- 体躯(結跏趺坐・正面+x)。接続部は太く重ねる ----
    body_els = [
        # 脚の量感(衣に覆われた結跏趺坐)
        ((0.05, 0.33, 0.20), 0.26, (0.95, 1.9, 0.6), None),
        ((0.05, -0.33, 0.20), 0.26, (0.95, 1.9, 0.6), None),
        ((0.30, 0, 0.18), 0.24, (0.9, 2.4, 0.55), None),
        ((-0.12, 0, 0.24), 0.30, (1.0, 1.8, 0.62), None),
        ((0.18, 0.60, 0.22), 0.16, None, None),
        ((0.18, -0.60, 0.22), 0.16, None, None),
        # 腰・腹・胸(肩まで届く幅で)
        ((-0.04, 0, 0.46), 0.30, (1.1, 1.35, 0.85), None),
        ((0.03, 0, 0.62), 0.24, (1.0, 1.05, 0.8), None),
        ((0.0, 0, 0.80), 0.30, (0.9, 1.4, 1.05), None),
        ((0.03, 0, 0.98), 0.26, (0.9, 1.18, 0.85), None),
        # 肩・腕
        ((0.0, 0.295, 1.005), 0.14, None, None),
        ((0.0, -0.295, 1.005), 0.14, None, None),
        ((0.01, 0.33, 0.85), 0.13, (0.75, 0.75, 1.3), (0.05, 0.04, -1)),
        ((0.01, -0.33, 0.85), 0.13, (0.75, 0.75, 1.3), (0.05, -0.04, -1)),
        ((0.10, 0.30, 0.68), 0.10, None, None),
        ((0.10, -0.30, 0.68), 0.10, None, None),
        # 前腕(肘(0.10,±0.37,0.70)→手首(0.335,±0.105,0.96)の中点に、向きを合わせて)
        ((0.20, 0.205, 0.80), 0.12, (0.72, 0.72, 1.45), (0.20, -0.19, 0.25)),
        ((0.20, -0.205, 0.80), 0.12, (0.72, 0.72, 1.45), (0.20, 0.19, 0.25)),
        # 首(太めに)・つなぎ・頭・顎
        ((0.04, 0, 1.15), 0.14, (0.85, 0.85, 1.0), None),
        ((0.045, 0, 1.23), 0.13, None, None),
        ((0.05, 0, 1.36), 0.21, (0.95, 0.85, 1.08), None),
        ((0.065, 0, 1.27), 0.125, None, None),
        # 相好の起伏(面に溶け込む、彫刻的なふくらみ)
        ((0.185, 0, 1.355), 0.05, (0.55, 0.38, 0.95), None),      # 鼻梁
        ((0.175, 0.052, 1.402), 0.032, (0.45, 1.05, 0.55), None),  # 右まぶた
        ((0.175, -0.052, 1.402), 0.032, (0.45, 1.05, 0.55), None), # 左まぶた
        ((0.168, 0, 1.445), 0.05, (0.4, 1.6, 0.45), None),         # 額・眉の張り
        ((0.185, 0, 1.315), 0.026, (0.45, 1.1, 0.5), None),        # 唇
    ]
    body = make_meta("body", body_els)
    n_isl = island_count(body)
    print(f"[check] body islands = {n_isl}")
    if n_isl != 1:
        raise RuntimeError("体がばらばらです(連結成分が1ではない)")

    # ---- 頭部: 球メッシュに数式で起伏を彫る(阿弥陀相) ----
    HC = Vector((0.05, 0, 1.375))          # 頭の中心
    RX, RY, RZ = 0.159, 0.155, 0.186       # 前後・左右・上下の半径

    def gauss(v, c, w):
        return math.exp(-((v - c) / w) ** 2)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=72, ring_count=48, radius=1.0)
    head = bpy.context.active_object
    for v in head.data.vertices:
        x, y, z = v.co
        # 顎へ向けてすぼめる(卵形)
        if z < 0:
            k = 1 + 0.16 * z
            x *= k
            y *= k
        if x > 0:
            f = x  # 顔面側の重み
            ay = abs(y)
            # 眉の張りと額
            x += f * 0.070 * gauss(z, 0.30, 0.14) * gauss(ay, 0, 0.55)
            # 眼窩のくぼみ
            x -= f * 0.065 * gauss(z, 0.12, 0.11) * gauss(ay, 0.30, 0.17)
            # 伏せたまぶた
            x += f * 0.050 * gauss(z, 0.06, 0.075) * gauss(ay, 0.28, 0.15)
            # 鼻梁(細く高く)
            x += f * 0.16 * gauss(z, -0.08, 0.17) * gauss(y, 0, 0.075)
            # 小鼻
            x += f * 0.05 * gauss(z, -0.20, 0.07) * gauss(ay, 0.09, 0.05)
            # 人中を経て唇
            x += f * 0.075 * gauss(z, -0.40, 0.07) * gauss(y, 0, 0.15)
            # 頤(おとがい)
            x += f * 0.045 * gauss(z, -0.66, 0.12) * gauss(y, 0, 0.22)
            # 頬のふくらみ
            x += f * 0.035 * gauss(z, -0.18, 0.24) * gauss(ay, 0.45, 0.24)
        v.co = (x * RX, y * RY, z * RZ)
    head.location = HC
    ss = head.modifiers.new("subsurf", "SUBSURF")
    ss.levels = 1
    bpy.ops.object.shade_smooth()
    head.data.materials.append(g)

    # 肉髻(頭頂)・白毫(眉間)
    sphere(tuple(HC + Vector((0.005, 0, RZ + 0.020))), 0.062, g)
    sphere(tuple(HC + Vector((RX * 0.985, 0, 0.052))), 0.012, g)
    # 耳と長い耳朶(頭の左右)
    for sy in (-1, 1):
        base = HC + Vector((-0.005, sy * RY * 0.96, -0.01))
        ear = sphere(tuple(base), 0.05, g)
        ear.scale = (0.55, 0.38, 1.4)
        cyl(tuple(base + Vector((0.002, 0, -0.085))), 0.016, 0.08, g)
        sphere(tuple(base + Vector((0.002, 0, -0.130))), 0.022, g)

    # ---- 説法印の両手 ----
    for sgn in (1, -1):
        hand, ring = build_hand(sgn)
        for obj in (hand, ring):
            obj.scale = (1.3, 1.3, 1.3)
            obj.location.x += 0.315
            obj.location.y += sgn * 0.082
            obj.location.z += 0.945
            obj.rotation_euler.z += math.radians(-14 * sgn)

    # ---- 衣: 脚を覆う裾の襞のみ(面のなめらかさを主役にする) ----
    for zc in (0.34, 0.26, 0.18):
        pts = [(0.7 * math.cos(t), 0.75 * math.sin(t), zc)
               for t in [(-0.40 + i / 9 * 0.80) * math.pi for i in range(10)]]
        drape(body, pts, 0.013)

    export(path)


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "amida_b.glb"))
    print("done", file=sys.stderr)
