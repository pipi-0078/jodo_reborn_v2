#!/usr/bin/env python3
"""黄金の蓮華座(阿弥陀如来坐像の台座)をBlender(bpy)で生成してglb出力する。

伝統的な仏像台座の積層(下から):
  框座(八角二段・格狭間・連珠)→ 反花(下向きの蓮弁二重)→ 敷茄子(瓔珞の連珠を垂らした珠)
  → 受座(轆轤挽きの華盤・連珠)→ 蓮弁四重(上向きに開く椀)→ 蓮肉(像を受ける台・連珠)

蓮弁は一枚ずつ独自の曲面で作る(make_lotus の生花の弁ではなく、木彫の金箔弁):
  ・稜線(中央の峰)と、子弁(弁の面に一回り小さな弁を浮彫にする定朝様の飾り)
  ・縁の反り(カップ)、先端のわずかな返り、鱗重ねのための捻り
  ・根元ほど暗い頂点色(椀の奥に落ちる陰)
枚数は「最大幅の位置の弧の長さ ÷ 目標の弁幅」から計算し、隣と 6% だけ重ねる。

使い方: python3 tools/make_textures.py && python3 tools/make_rengeza.py
出力: public/assets/rengeza.glb
"""
import math
import os
import sys

import bpy
import bmesh  # noqa: E402  (bpy の後でないと読めない)
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import reset_scene, triangle_count  # noqa: E402
from make_pavilion import cyl, sphere, torus, textured, mat_of, _poly_tube  # noqa: E402

PETAL_U = 30   # 長さ方向の分割
PETAL_V = 14   # 幅方向の分割
DAIS_R = 0.80  # 蓮肉の半径
DAIS_TOP = 1.44


def log(*a):
    print(*a, file=sys.stderr)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def link(obj):
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- マテリアル
def glow(mat, color, strength):
    """金に内側からの照りを足す(空の映り込みで色が濁らないように)。"""
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength


# ---------------------------------------------------------------- 蓮弁
def petal_profile(t):
    """弁の半幅の係数(0..1)。根元は細く、5割強で最大、先端は丸く納まる。"""
    u = max(0.0, (t - 0.50) / 0.50)
    taper = max(0.0, 1 - u ** 2.2) ** 0.65          # 楕円の先がわずかに尖る
    return math.sin(math.pi * min(t / 0.55, 1) * 0.5) ** 0.8 * taper


def build_gold_petal(length, width, curl, cup, roll, flick=0.04, relief=True,
                     thickness=0.02, relief_side=-1.0):
    """金箔押しの木彫の蓮弁一枚。原点=根元、+Zへ伸び、-Y が外側(見える面)。
    外側の面に稜線と子弁の浮彫を刻む。roll は弁を背骨まわりに捻る角(鱗重ね用)。"""
    verts, uvs, cols = [], [], []
    cr, sr = math.cos(roll), math.sin(roll)
    for i in range(PETAL_U + 1):
        t = i / PETAL_U
        hw = width * 0.5 * petal_profile(t)
        # 背骨: 先端へ向けて内側(+Y)へ反り、最後にわずかに外へ返る
        spine_y = curl * (t ** 2.2) * length - flick * length * max(0.0, (t - 0.82) / 0.18) ** 2
        spine_z = t * length
        # 子弁の輪郭(弁の 10%〜82% の範囲に、幅 6 割の相似形)
        tc = (t - 0.10) / 0.72
        child_hw = width * 0.5 * 0.60 * petal_profile(tc) if 0.0 <= tc <= 1.0 else -1.0
        for j in range(PETAL_V + 1):
            s = j / PETAL_V * 2 - 1
            x = s * hw
            y = spine_y - cup * (1 - s * s) * hw * 1.1     # 縁が内側へ立ち上がる椀形
            shade = 1.0
            if relief and hw > 1e-6:
                h = 0.0
                d = abs(x) - child_hw                        # 子弁の縁からの距離(内が負)
                plate = 1.0 - smoothstep(-0.012, 0.012, d) if child_hw > 0 else 0.0
                h += 0.0100 * plate                                          # 子弁の面
                h += 0.0060 * plate * math.exp(-(x / (0.09 * width)) ** 2)   # 子弁の稜線
                h += 0.0040 * (1 - plate) * math.exp(-(x / (0.07 * width)) ** 2) \
                    * smoothstep(0.02, 0.25, t)                              # 本弁の稜線
                h *= 1.0 - smoothstep(0.90, 1.0, t)                          # 先端で消える
                y += relief_side * h                                         # 見える面へ盛る
                if child_hw > 0:
                    shade -= 0.30 * math.exp(-(d / 0.012) ** 2)              # 浮彫の際の陰
            # 鱗重ねの捻り
            xr, yr = x * cr - y * sr, x * sr + y * cr
            verts.append(Vector((xr, yr, spine_z)))
            uvs.append((j / PETAL_V, t))
            shade *= 0.55 + 0.45 * smoothstep(0.0, 0.38, t)                  # 根元は椀の奥で暗い
            cols.append((shade, shade, shade, 1.0))

    faces = []
    stride = PETAL_V + 1
    for i in range(PETAL_U):
        for j in range(PETAL_V):
            a = i * stride + j
            faces.append((a, a + 1, a + stride + 1, a + stride))

    mesh = bpy.data.meshes.new("petal")
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    layer = mesh.uv_layers.new()
    for poly in mesh.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[mesh.loops[li].vertex_index]
    ca = mesh.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for k, c in enumerate(cols):
        ca.data[k].color = c
    obj = link(bpy.data.objects.new("petal", mesh))
    solid = obj.modifiers.new("solidify", "SOLIDIFY")
    solid.thickness = thickness
    solid.offset = 0
    return obj


def whorl_count(radius, open_angle, length, curl, target_w, overlap=1.06):
    """最大幅(t=0.55)の位置の弧の長さから枚数と弁幅を決める。隣と 6% だけ重ねる。"""
    a = math.radians(open_angle)
    t = 0.55
    along = t * length
    sy = curl * (t ** 2.2) * length
    ring_r = radius + along * math.sin(a) - sy * math.cos(a)
    circ = math.tau * ring_r
    n = max(8, math.ceil(circ / target_w))
    spacing = circ / n
    return n, spacing * overlap, ring_r


def gold_petal_whorl(mat, open_angle, length, radius, base_z, curl, cup,
                     target_w=0.50, phase=0.0, roll_deg=7.0, flick=0.04,
                     thickness=0.02, overlap=1.06, label=""):
    relief_side = 1.0 if open_angle > 90 else -1.0      # 反花は上面(+Y)が見える面
    """金の蓮弁を一輪(ひとまわり)並べる。open_angle>90 で反花(下向き)になる。"""
    n, width, ring_r = whorl_count(radius, open_angle, length, curl, target_w, overlap)
    log(f"  whorl {label}: n={n} width={width:.3f} L/W={length / width:.2f} ring_r={ring_r:.2f}")
    objs = []
    for k in range(n):
        theta = (k / n) * math.tau + phase
        petal = build_gold_petal(length, width, curl, cup, math.radians(roll_deg),
                                 flick=flick, thickness=thickness, relief_side=relief_side)
        petal.name = f"petal_{label}_{k}"
        petal.data.materials.append(mat)
        petal.matrix_world = (
            Matrix.Rotation(theta, 4, "Z")
            @ Matrix.Translation((0, -radius, base_z))
            @ Matrix.Rotation(math.radians(open_angle), 4, "X")
        )
        objs.append(petal)
    return objs


# ---------------------------------------------------------------- 轆轤挽きの部材
def lathe(profile, material, name, steps=48):
    """(r, z) の断面を Z 軸まわりに回して部材を作る。円筒座標の UV を付ける。"""
    bm = bmesh.new()
    prev = None
    for r, z in profile:
        v = bm.verts.new((r, 0.0, z))
        if prev is not None:
            bm.edges.new((prev, v))
        prev = v
    bmesh.ops.spin(bm, geom=bm.verts[:] + bm.edges[:], cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=math.tau, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    # 断面に沿った弧長を V、周を U にする
    arc = [0.0]
    for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
        arc.append(arc[-1] + math.hypot(r1 - r0, z1 - z0))
    total = arc[-1] or 1.0

    def v_of(co):
        r, z = math.hypot(co.x, co.y), co.z
        best, best_d = 0.0, 1e9
        for idx, ((r0, z0), (r1, z1)) in enumerate(zip(profile, profile[1:])):
            dx, dz = r1 - r0, z1 - z0
            seg = dx * dx + dz * dz or 1e-12
            u = min(1.0, max(0.0, ((r - r0) * dx + (z - z0) * dz) / seg))
            d = math.hypot(r0 + dx * u - r, z0 + dz * u - z)
            if d < best_d:
                best_d, best = d, (arc[idx] + u * (arc[idx + 1] - arc[idx])) / total
        return best
    layer = me.uv_layers.new()
    for poly in me.polygons:
        poly.use_smooth = True
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            us.append(math.atan2(co.y, co.x) / math.tau + 0.5)
        if max(us) - min(us) > 0.5:                      # 継ぎ目をまたぐ面
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u in zip(poly.loop_indices, us):
            co = me.vertices[me.loops[li].vertex_index].co
            layer.data[li].uv = (u, v_of(co))
    me.materials.append(material)
    return link(bpy.data.objects.new(name, me))


def bead_row(points, radius, material, segments=7, rings=5):
    for p in points:
        sphere(p, radius, material, segments=segments, rings=rings)


def octagon_ring(r, z, count, phase=math.pi / 8):
    """八角形の辺に沿って等間隔に並ぶ点。"""
    corners = [(r * math.cos(k * math.tau / 8 + phase), r * math.sin(k * math.tau / 8 + phase))
               for k in range(9)]
    side = math.hypot(corners[1][0] - corners[0][0], corners[1][1] - corners[0][1])
    per_side = max(1, round(count / 8))
    pts = []
    for k in range(8):
        (x0, y0), (x1, y1) = corners[k], corners[k + 1]
        for m in range(per_side):
            u = (m + 0.5) / per_side
            pts.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, z))
    return pts, side / per_side


def catmull_rom(points, per_seg=8, closed=False):
    """制御点を通るなめらかな折れ線。"""
    pts = list(points)
    if closed:
        pts = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (Vector(p) for p in pts[i - 1:i + 3])
        for m in range(per_seg):
            t = m / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    if not closed:
        out.append(Vector(pts[-2]))
    return out


def kozama_panel(face_angle, apothem, half_w, plate_mat, trim_mat):
    """框座の側面に格狭間(裾広がりの唐草風の窓)を一つ。浮き板+縁の紐。"""
    outline_uv = [(-half_w, 0.020), (half_w, 0.020), (half_w, 0.062), (half_w * 0.86, 0.098),
                  (half_w * 0.66, 0.104), (half_w * 0.44, 0.080), (half_w * 0.20, 0.100),
                  (0.0, 0.124), (-half_w * 0.20, 0.100), (-half_w * 0.44, 0.080),
                  (-half_w * 0.66, 0.104), (-half_w * 0.86, 0.098), (-half_w, 0.062)]
    curve = catmull_rom([(u, v, 0.0) for u, v in outline_uv], per_seg=6, closed=True)
    nx, ny = math.cos(face_angle), math.sin(face_angle)
    tx, ty = -ny, nx

    def to_world(u, v, out):
        return ((apothem + out) * nx + u * tx, (apothem + out) * ny + u * ty, v)
    # 浮き板(多角形一枚)
    bm = bmesh.new()
    vs = [bm.verts.new(to_world(p.x, p.y, 0.006)) for p in curve]
    bm.faces.new(vs)
    me = bpy.data.meshes.new("kozama")
    bm.to_mesh(me)
    bm.free()
    layer = me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            p = curve[me.loops[li].vertex_index]
            layer.data[li].uv = ((p.x + half_w) / (2 * half_w), p.y / 0.14)
    me.materials.append(plate_mat)
    link(bpy.data.objects.new("kozama", me))
    # 縁の紐
    ring = [to_world(p.x, p.y, 0.012) for p in curve] + [to_world(curve[0].x, curve[0].y, 0.012)]
    _poly_tube(ring, 0.010, trim_mat)


def garland(points, sag, beads, radius, material, surface_r):
    """隣り合う吊り点のあいだに垂れる連珠(瓔珞)。珠は珠体の面から少し外へ出す。"""
    n = len(points)
    for k in range(n):
        (x0, y0, z0), (x1, y1, z1) = points[k], points[(k + 1) % n]
        for m in range(1, beads + 1):
            u = m / (beads + 1)
            x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            z = z0 + (z1 - z0) * u - sag * math.sin(math.pi * u)
            rr = surface_r(z) + radius * 0.9
            ang = math.atan2(y, x)
            sphere((rr * math.cos(ang), rr * math.sin(ang), z), radius, material, segments=7, rings=5)


# ---------------------------------------------------------------- 検算
def petal_bvh(obj, keep):
    """評価後(厚み付き)のメッシュから BVH と面の中心を得る(keep で面を絞る)。"""
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).to_mesh()
    mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys, centers = [], []
    for p in me.polygons:
        c = mw @ p.center
        if keep(c):
            polys.append(list(p.vertices))
            centers.append(c)
    obj.evaluated_get(dg).to_mesh_clear()
    return (BVHTree.FromPolygons(verts, polys) if polys else None), centers


def describe_hits(pairs, ca, cb):
    if not pairs:
        return "なし"
    pts = [ca[i] for i, _ in pairs] + [cb[j] for _, j in pairs]
    zs = [p.z for p in pts]
    rs = [math.hypot(p.x, p.y) for p in pts]
    return f"{len(pairs)} 組  z {min(zs):.2f}..{max(zs):.2f}  r {min(rs):.2f}..{max(rs):.2f}"


def check_rows(rows, hidden):
    """隣り合う弁どうし・輪どうしで、見える部分の面が交差していないかを数える。"""
    keep = lambda c: not hidden(c)  # noqa: E731
    trees = {label: [petal_bvh(o, keep) for o in objs] for label, objs in rows}
    for label, items in trees.items():
        n = len(items)
        pairs = []
        for k in range(n):
            ta, ca = items[k]
            tb, cb = items[(k + 1) % n]
            if ta and tb:
                h = ta.overlap(tb)
                if h:
                    pairs.append(h)
        total = sum(len(h) for h in pairs)
        log(f"  check {label}: 隣どうしの交差 {total} 組 ({len(pairs)}/{n} 組の隣で)")
    labels = [r[0] for r in rows]
    for a, b in zip(labels, labels[1:]):
        hits, worst = [], (0, None)
        for ta, ca in trees[a]:
            for tb, cb in trees[b]:
                if ta and tb:
                    h = ta.overlap(tb)
                    if h:
                        hits.append((h, ca, cb))
        allpairs = [(ca[i], cb[j]) for h, ca, cb in hits for i, j in h]
        if allpairs:
            zs = [p.z for pr in allpairs for p in pr]
            rs = [math.hypot(p.x, p.y) for pr in allpairs for p in pr]
            log(f"  check {a} x {b}: 交差 {len(allpairs)} 組  z {min(zs):.2f}..{max(zs):.2f}  r {min(rs):.2f}..{max(rs):.2f}")
        else:
            log(f"  check {a} x {b}: 交差なし")


def extents(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    zs, rs = [], []
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        for v in me.vertices:
            w = o.matrix_world @ v.co
            zs.append(w.z)
            rs.append(math.hypot(w.x, w.y))
        o.evaluated_get(dg).to_mesh_clear()
    return min(zs), max(zs), min(rs), max(rs)


# ---------------------------------------------------------------- 組み立て
def build(path):
    reset_scene()
    gold = mat_of("gold")
    shuju = mat_of("shuju")
    kinpaku = textured("kinpaku_z", "kinpaku.png", normal="kinpaku_normal.png",
                       metallic=0.92, roughness=0.30, tile=(6, 2))
    tsuchime = textured("tsuchime_z", "tsuchime.png", normal="tsuchime_normal.png",
                        metallic=0.92, roughness=0.42, tile=(8, 2))
    migaki = textured("migaki_z", "migaki.png", normal="migaki_normal.png",
                      metallic=0.95, roughness=0.22, tile=(4, 3))
    petal_gold = textured("petal_gold", "kinpaku.png", normal="kinpaku_normal.png",
                          metallic=0.90, roughness=0.32, tile=(2, 3))
    glow(petal_gold, (0.95, 0.64, 0.22), 0.10)
    glow(kinpaku, (0.9, 0.62, 0.22), 0.06)
    glow(tsuchime, (0.9, 0.62, 0.22), 0.05)
    glow(migaki, (0.95, 0.68, 0.26), 0.07)

    # ---- 框座: 八角二段+金の框、下段の側面に格狭間、上段の天端に連珠 ----
    cyl((0, 0, 0.07), 1.52, 0.14, tsuchime, vertices=8)
    cyl((0, 0, 0.20), 1.36, 0.12, kinpaku, vertices=8)
    for (r, z) in ((1.52, 0.14), (1.36, 0.26), (1.52, 0.005)):
        pts = [(r * math.cos(k * math.tau / 8 + math.pi / 8),
                r * math.sin(k * math.tau / 8 + math.pi / 8), z) for k in range(9)]
        _poly_tube(pts, 0.035 if z > 0.01 else 0.025, gold)
    apothem = 1.52 * math.cos(math.pi / 8)
    half_w = 1.52 * math.sin(math.pi / 8) - 0.10
    for k in range(8):
        kozama_panel(k * math.tau / 8, apothem, half_w, migaki, gold)
    pts, gap = octagon_ring(1.30, 0.268, 104)
    bead_row(pts, 0.024, gold)
    log(f"  框座の連珠: {len(pts)} 粒, 間隔 {gap:.3f}")

    # ---- 反花の芯: 框座と敷茄子をつなぐ胴(花びらの根元の差し込み先) ----
    cyl((0, 0, 0.52), 0.55, 0.52, migaki, vertices=24)
    # ---- 反花: 芯から出て框座の天端(z=0.26)に着地する裾 ----
    kaeri_a = gold_petal_whorl(petal_gold, 111.5, 0.60, 0.50, 0.465, curl=0.05, cup=0.12,
                               target_w=0.42, roll_deg=6.0, flick=0.0, thickness=0.022,
                               overlap=1.0, label="反花外")
    kaeri_b = gold_petal_whorl(petal_gold, 120, 0.46, 0.52, 0.60, curl=0.05, cup=0.12,
                               target_w=0.38, phase=math.pi / 13, roll_deg=6.0, flick=0.0,
                               thickness=0.022, overlap=1.0, label="反花内")
    for label, objs in (("反花外", kaeri_a), ("反花内", kaeri_b)):
        z0, z1, r0, r1 = extents(objs)
        log(f"  {label}: z {z0:.3f}..{z1:.3f}  r {r0:.2f}..{r1:.2f} (天端 0.26 に着地)")

    # ---- 敷茄子: 潰した珠。赤道に金帯、瓔珞の連珠を垂らす ----
    sphere((0, 0, 0.72), 0.58, migaki, scale_z=0.52)
    torus((0, 0, 0.72), 0.585, 0.035, gold)

    def shikinasu_r(z):
        u = min(1.0, abs(z - 0.72) / (0.58 * 0.52))
        return 0.58 * math.sqrt(max(0.0, 1 - u * u))
    hang = []
    for k in range(16):
        th = k * math.tau / 16
        rr = shikinasu_r(0.82) + 0.02
        hang.append((rr * math.cos(th), rr * math.sin(th), 0.82))
        sphere(hang[-1], 0.030, gold, segments=8, rings=6)
        for z, rad, mat in ((0.77, 0.024, gold), (0.725, 0.024, gold)):
            r2 = shikinasu_r(z) + 0.022
            sphere((r2 * math.cos(th), r2 * math.sin(th), z), rad, mat, segments=7, rings=5)
        r3 = shikinasu_r(0.67) + 0.03
        sphere((r3 * math.cos(th), r3 * math.sin(th), 0.67), 0.040, shuju, scale_z=1.3,
               segments=8, rings=6)
    garland(hang, 0.075, 7, 0.02, gold, shikinasu_r)

    # ---- 受座(華盤): 轆轤挽きの反りのある皿、縁に連珠 ----
    lathe([(0.42, 0.84), (0.50, 0.86), (0.53, 0.90), (0.58, 0.94), (0.65, 0.975),
           (0.72, 0.995), (0.745, 1.01), (0.745, 1.03), (0.70, 1.04), (0.0, 1.04)],
          tsuchime, "ukeza")
    ring = [(0.735 * math.cos(k * math.tau / 44), 0.735 * math.sin(k * math.tau / 44), 1.035)
            for k in range(44)]
    bead_row(ring, 0.021, gold)

    # ---- 蓮弁四重: 上向きに開く椀。外ほど開き、内ほど立つ ----
    rows = [
        ("外",  gold_petal_whorl(petal_gold, 78, 0.84, 0.72, 1.00, curl=0.50, cup=0.30,
                                 target_w=0.50, label="外")),
        ("二",  gold_petal_whorl(petal_gold, 62, 0.78, 0.66, 1.04, curl=0.34, cup=0.30,
                                 target_w=0.50, phase=math.pi / 14, label="二")),
        ("三",  gold_petal_whorl(petal_gold, 48, 0.68, 0.62, 1.08, curl=0.22, cup=0.20,
                                 target_w=0.48, label="三")),
        ("内",  gold_petal_whorl(petal_gold, 30, 0.56, 0.60, 1.12, curl=0.15, cup=0.22,
                                 target_w=0.48, phase=math.pi / 11, flick=0.03, label="内")),
    ]
    for label, objs in rows:
        z0, z1, r0, r1 = extents(objs)
        log(f"  蓮弁{label}: z {z0:.2f}..{z1:.2f}  r {r0:.2f}..{r1:.2f}")

    # ---- 蓮肉: 像を受ける台。轆轤挽きの丸い肩、縁に連珠 ----
    lathe([(0.70, 1.05), (DAIS_R, 1.07), (DAIS_R, 1.36), (0.79, 1.40), (0.76, 1.43),
           (0.72, DAIS_TOP), (0.0, DAIS_TOP)], tsuchime, "dais")
    ring = [(0.80 * math.cos(k * math.tau / 40), 0.80 * math.sin(k * math.tau / 40), 1.395)
            for k in range(40)]
    bead_row(ring, 0.027, gold)

    # ---- 検算: 見える部分で弁が交差していないか(蓮肉・芯の中に隠れる面は除く) ----
    def hidden(c):
        r = math.hypot(c.x, c.y)
        return (r < DAIS_R + 0.01 and 1.05 < c.z < DAIS_TOP) or (r < 0.56 and 0.26 < c.z < 0.78)
    check_rows(rows, hidden)
    check_rows([("反花外", kaeri_a), ("反花内", kaeri_b)], hidden)

    bpy.ops.export_scene.gltf(filepath=path, export_apply=True, export_vertex_color="ACTIVE")
    log(f"  -> {os.path.relpath(path, ROOT)} ({triangle_count()} tris)")


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "rengeza.glb"))
    print("done", file=sys.stderr)
