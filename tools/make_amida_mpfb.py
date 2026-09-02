#!/usr/bin/env python3
"""MPFB2(MakeHuman)の素体から阿弥陀如来坐像の本体を組み立てる。

段階:
  1. 素体(アジア系・中庸な体格)に相好のターゲットを掛け、標準リグで結跏趺坐+阿弥陀定印に組む
  2. 頭部の造作(肉髻・螺髪・白毫)と衣
  3. 金箔マテリアル・最適化・書き出し

使い方: python3 tools/make_amida_mpfb.py [--stage N]
出力: public/assets/amida_wip.glb(制作中のプレビュー)
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from mpfb_bootstrap import bootstrap  # noqa: E402

OUT = os.path.join(ROOT, "public/assets/amida_wip.glb")
GOLD = (0.85, 0.62, 0.20)
BEAD_RADIUS = 0.0072  # 螺髪の粒(身長1.57m基準)
BEAD_SPACING = 0.0135

# 体型(MakeHuman のマクロ。gender 0=女 1=男、age 0.5=25歳相当)
MACRO = {
    "gender": 0.35, "age": 0.42, "muscle": 0.36, "weight": 0.56, "proportions": 0.5, "height": 0.5,
    "cupsize": 0.0, "firmness": 0.5,
    "race": {"asian": 1.0, "caucasian": 0.0, "african": 0.0},
}

# 相好(定朝様: 円満な面相・伏し目・長い耳朶)。値は 0..1
FACE_TARGETS = {
    # 中宮寺 菩薩半跏像を範に: 長めの卵形の面、高い額、細く高い弧の眉から続く通った鼻筋、
    # 伏せた長い目(瞼の折り目は作らない)、小さく薄い唇の口角だけを上げる
    "head-oval": 0.3, "head-round": 0.3, "head-scale-vert-incr": 0.4, "head-scale-horiz-incr": 0.6, "head-scale-depth-incr": 0.35,
    "head-fat-incr": 0.35, "forehead-scale-vert-incr": 0.3, "forehead-temple-incr": 0.7, "forehead-nubian-decr": 0.2,
    "l-cheek-volume-incr": 0.6, "r-cheek-volume-incr": 0.6, "l-cheek-inner-incr": 0.3, "r-cheek-inner-incr": 0.3,
    "l-cheek-bones-decr": 0.5, "r-cheek-bones-decr": 0.5,
    "chin-prominent-decr": 0.35, "chin-bones-decr": 0.6, "chin-width-incr": 0.35, "chin-cleft-decr": 0.4, "chin-height-decr": 0.1,
    "l-ear-lobe-incr": 1.0, "r-ear-lobe-incr": 1.0,
    "l-ear-scale-incr": 0.6, "r-ear-scale-incr": 0.6,
    "l-eye-height2-decr": 1.0, "r-eye-height2-decr": 1.0,            # 半眼(細い線)
    "l-eye-height1-decr": 0.5, "r-eye-height1-decr": 0.5, "l-eye-height3-decr": 0.5, "r-eye-height3-decr": 0.5,
    "l-eye-scale-incr": 0.35, "r-eye-scale-incr": 0.35,               # 目を長く
    "l-eye-trans-out": 0.3, "r-eye-trans-out": 0.3,
    "l-eye-corner2-up": 0.1, "r-eye-corner2-up": 0.1,
    "l-eye-bag-decr": 0.5, "r-eye-bag-decr": 0.5,
    "eyebrows-angle-up": 0.6, "eyebrows-trans-up": 0.25,
    "nose-greek-incr": 0.4, "nose-hump-decr": 0.5, "nose-scale-horiz-decr": 0.1, "nose-trans-backward": 0.15,
    "nose-nostrils-width-decr": 0.3, "nose-point-width-decr": 0.2, "nose-flaring-decr": 0.3,
    "mouth-scale-horiz-decr": 0.35, "mouth-angles-up": 0.65,
    "mouth-upperlip-volume-decr": 0.35, "mouth-lowerlip-volume-decr": 0.15, "mouth-cupidsbow-incr": 0.15,
    "mouth-dimples-in": 0.45, "mouth-laugh-lines-in": 0.1,
    "neck-scale-vert-decr": 0.3, "neck-scale-horiz-incr": 0.15,
}


def log(*args):
    print(*args, file=sys.stderr)


# ---------------------------------------------------------------- ポーズ
def rotate_bone(arm, name, axis, degrees, pivot=None):
    """ポーズボーンをアーマチュア空間の軸まわりに回す(親から順に呼ぶ)。"""
    pb = arm.pose.bones[name]
    bpy.context.view_layer.update()
    head = pivot if pivot is not None else pb.head.copy()
    rot = Matrix.Rotation(math.radians(degrees), 4, Vector(axis).normalized())
    pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()


def aim_bone(arm, name, target_dir):
    """ボーンの向き(head→tail)を target_dir へ最小回転で合わせる。"""
    pb = arm.pose.bones[name]
    bpy.context.view_layer.update()
    current = (pb.tail - pb.head).normalized()
    target = Vector(target_dir).normalized()
    quat = current.rotation_difference(target)
    head = pb.head.copy()
    pb.matrix = Matrix.Translation(head) @ quat.to_matrix().to_4x4() @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()


def palm_normal(arm, side):
    """掌の法線。手の平面の法線のうち、親指の先がある側を掌側とする。"""
    bpy.context.view_layer.update()
    b = arm.pose.bones
    fingers = (b[f"finger3-1.{side}"].head - b[f"wrist.{side}"].head).normalized()
    across = (b[f"metacarpal1.{side}"].head - b[f"metacarpal4.{side}"].head).normalized()
    n = across.cross(fingers).normalized()
    thumb = b[f"finger1-3.{side}"].tail - b[f"finger3-1.{side}"].head
    if n.dot(thumb) < 0:
        n = -n
    return n


def roll_to_palm_up(arm, side, bone, axis, pivot):
    """bone を axis まわりに回して掌の法線を最も +Z に向ける。"""
    best = None
    for deg in range(-180, 180, 5):
        rotate_bone(arm, bone, axis, deg, pivot=pivot)
        n = palm_normal(arm, side)
        rotate_bone(arm, bone, axis, -deg, pivot=pivot)
        if best is None or n.z > best[1]:
            best = (deg, n.z)
    rotate_bone(arm, bone, axis, best[0], pivot=pivot)
    return best


def bone_dir(arm, name):
    pb = arm.pose.bones[name]
    bpy.context.view_layer.update()
    return (pb.tail - pb.head).normalized()


def pose_lotus_legs(arm, side, lift_deg):
    """結跏趺坐。side: 'L' or 'R'。lift_deg: 脛を持ち上げる角(上に組む脚ほど大きく)。"""
    s = 1 if side == "L" else -1
    leg = f"upperleg01.{side}"
    # 股関節: 前へ 90° 曲げ、外へ 46° 開く(膝を前へ出して奥行きをつくる)
    rotate_bone(arm, leg, (1, 0, 0), -90)
    rotate_bone(arm, leg, (0, 0, 1), s * 46)
    # 膝: 脛を反対側へ折り畳む(水平面内)、次に大腿軸まわりに持ち上げる
    thigh = bone_dir(arm, leg)
    knee = arm.pose.bones[f"lowerleg01.{side}"].head.copy()
    rotate_bone(arm, f"lowerleg01.{side}", (0, 0, 1), -s * 148, pivot=knee)
    rotate_bone(arm, f"lowerleg01.{side}", thigh, -s * lift_deg, pivot=knee)
    # 足首: 足の甲を上へ向ける
    rotate_bone(arm, f"foot.{side}", bone_dir(arm, f"lowerleg02.{side}"), s * 40)


def pose_arms_dhyana(arm, lap_z):
    """阿弥陀定印: 腹の前で両手を重ね、人差し指を曲げて親指と輪をつくる。"""
    for side, s in (("L", 1), ("R", -1)):
        ua = f"upperarm01.{side}"
        rotate_bone(arm, ua, (0, 1, 0), s * 32)      # 腕を体側へ下ろす
        rotate_bone(arm, ua, (1, 0, 0), -14)          # わずかに前へ
        # 前腕を腹の前へ。手首が中心線の手前で交差し、右手が下・左手が上(指先は反対側へ)
        hand_z = lap_z + ROBE_OFFSET + (0.077 if side == "L" else 0.042)   # 右手の甲が衣に載り、左手はその上
        wrist_target = Vector((-s * 0.05, -0.245, hand_z))
        elbow = arm.pose.bones[f"lowerarm01.{side}"].head
        # lowerarm01 の先は lowerarm02→wrist と続くので、肘→手首の距離ぶんだけ伸ばした方向を狙う
        target = wrist_target - elbow
        aim_bone(arm, f"lowerarm01.{side}", target)
        # 手のひらを上へ(前腕軸まわりの回内外)
        axis = bone_dir(arm, f"lowerarm01.{side}")
        pivot = arm.pose.bones[f"lowerarm01.{side}"].head.copy()
        best = roll_to_palm_up(arm, side, f"lowerarm01.{side}", axis, pivot)
        log(f"  palm {side}: forearm roll {best[0]} deg, normal.z {best[1]:.2f}")
        # 手首: 指先を反対側へ向け(右手は +X、左手は -X)、掌を上に保つ
        wrist = arm.pose.bones[f"wrist.{side}"]
        aim_bone(arm, f"wrist.{side}", (-s * 1.0, -0.12, 0.0))
        best = roll_to_palm_up(arm, side, f"wrist.{side}", bone_dir(arm, f"wrist.{side}"), wrist.head.copy())
        log(f"  palm {side}: wrist roll {best[0]} deg, normal.z {best[1]:.2f}, fingers", [round(v, 2) for v in bone_dir(arm, f"finger3-1.{side}")])
        # 指: 人差し指を丸め、親指を寄せて輪に。他の指はゆるく伸ばす
        for joint, deg in (("finger2-1", 35), ("finger2-2", 55), ("finger2-3", 40)):
            pb = arm.pose.bones[f"{joint}.{side}"]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler.x = math.radians(deg)
        for joint, deg in (("finger1-1", 20), ("finger1-2", 30), ("finger1-3", 25)):
            pb = arm.pose.bones[f"{joint}.{side}"]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler.x = math.radians(deg)
        for f in ("finger3", "finger4", "finger5"):
            for j, deg in (("1", 8), ("2", 12), ("3", 8)):
                pb = arm.pose.bones[f"{f}-{j}.{side}"]
                pb.rotation_mode = "XYZ"
                pb.rotation_euler.x = math.radians(deg)
    bpy.context.view_layer.update()


def measure_lap(human):
    """脚を組んだ後の、腹の前(手を置く場所)の脚の上面の高さを測る(腕・手の頂点は除く)。"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    me = human.evaluated_get(depsgraph).data
    arm_groups = {g.index for g in human.vertex_groups
                  if g.name.split(".")[0].startswith(("wrist", "finger", "metacarpal", "lowerarm", "upperarm"))}
    floor = min(v.co.z for v in me.vertices)
    lap = max(v.co.z for v in me.vertices
              if abs(v.co.x) < 0.09 and -0.30 < v.co.y < -0.15 and v.co.z < floor + 0.45
              and not any(g.group in arm_groups and g.weight > 0.3 for g in v.groups))
    return floor, lap


def pose_head(arm):
    rotate_bone(arm, "neck01", (1, 0, 0), 3)
    rotate_bone(arm, "head", (1, 0, 0), 5)  # わずかに伏せる
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- 頭部の造作
def group_center(obj, mesh, name):
    idx = obj.vertex_groups[name].index if name in obj.vertex_groups else None
    pts = [v.co for v in mesh.vertices if idx is not None and any(g.group == idx for g in v.groups)]
    if not pts:
        return None
    return sum(pts, Vector()) / len(pts)


def add_sphere(name, center, radius, scale=(1, 1, 1), segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def stretch_earlobes(body, mesh, factor=1.9):
    """耳の中心より下の頂点を下へ引き伸ばし、長い耳朶にする。"""
    idx = body.vertex_groups["ears"].index
    for side_sign in (1, -1):
        ear = [v for v in mesh.vertices if any(g.group == idx for g in v.groups) and v.co.x * side_sign > 0]
        if not ear:
            continue
        zc = sum(v.co.z for v in ear) / len(ear)
        zmin = min(v.co.z for v in ear)
        for v in ear:
            if v.co.z < zc:
                t = (zc - v.co.z) / max(zc - zmin, 1e-6)
                v.co.z -= (zc - zmin) * (factor - 1) * t * t
                v.co.x += side_sign * 0.004 * t  # わずかに外へ
    mesh.update()


def soften_face(body, mesh, factor=0.5, iterations=5):
    """顔の面をなめらかにして、人間的な細部より大きな面の流れで見せる(唇・耳・頭皮は除く)。"""
    import bmesh
    keep = {body.vertex_groups[n].index for n in ("lips", "ears", "scalp") if n in body.vertex_groups}
    z_chin = min(v.co.z for v in mesh.vertices if any(g.group in keep and body.vertex_groups[g.group].name == "lips" for g in v.groups)) - 0.03
    bm = bmesh.new()
    bm.from_mesh(mesh)
    dl = bm.verts.layers.deform.verify()
    verts = [v for v in bm.verts if v.co.z > z_chin and v.co.y < -0.02 and not any(v[dl].get(i, 0.0) > 0.2 for i in keep)]
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    log("  softened face verts", len(verts))


def add_head_features(body, mesh, eyes):
    """目(半眼の奥を埋める球)・白毫・肉髻・螺髪。"""
    soften_face(body, mesh)
    stretch_earlobes(body, mesh)
    created = []
    for side, (c, r) in eyes.items():
        created.append(add_sphere(f"Amida_Eye_{side.upper()}", c, r * 1.02))
    # 白毫: 眉間。両目の中点から前へ出し、眉間の肌の上に半分埋める
    mid = (eyes["l"][0] + eyes["r"][0]) / 2
    front = min(v.co.y for v in mesh.vertices if abs(v.co.x) < 0.01 and abs(v.co.z - (mid.z + 0.03)) < 0.008)
    created.append(add_sphere("Amida_Urna", Vector((0, front + 0.002, mid.z + 0.03)), 0.0065))
    # 肉髻: 頭頂の丸い盛り上がり
    scalp_idx = body.vertex_groups["scalp"].index
    scalp = [v.co for v in mesh.vertices if any(g.group == scalp_idx for g in v.groups)]
    top = max(scalp, key=lambda p: p.z)
    apex = Vector((0, top.y + 0.01, top.z - 0.015))
    created.append(add_sphere("Amida_Ushnisha", apex, 0.052, scale=(1.0, 1.05, 0.9)))
    # 頭皮の下地: 頭皮の頂点を法線方向へ少し盛って、粒の隙間に肌が見えないようにする
    for v in mesh.vertices:
        if any(g.group == scalp_idx for g in v.groups):
            v.co += v.normal * 0.004
    mesh.update()
    hair = place_rahotsu(body, mesh, scalp_idx, apex)
    created.append(hair)
    return created




# ---------------------------------------------------------------- 螺髪
def spiral_knob_mesh():
    """右巻きの渦を刻んだ粒(半球より少し高い)。頂点座標は半径1、+Z が先端。"""
    import bmesh
    bm = bmesh.new()
    segs, rings = 10, 6
    grid = []
    for i in range(rings + 1):
        ph = math.pi * 0.62 * i / rings          # 0(先端)〜 約112°(裾)
        row = []
        for j in range(segs):
            th = 2 * math.pi * j / segs
            groove = 0.5 + 0.5 * math.cos(th * 1 + ph * 6.0)   # 渦の溝(下るほど回る)
            r = 1.0 - 0.16 * groove ** 2 * min(1.0, ph / 0.5)
            x = r * math.sin(ph) * math.cos(th)
            y = r * math.sin(ph) * math.sin(th)
            z = r * math.cos(ph) * 1.15
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for i in range(rings):
        for j in range(segs):
            a, b = grid[i][j], grid[i][(j + 1) % segs]
            c, d = grid[i + 1][(j + 1) % segs], grid[i + 1][j]
            if i == 0:
                pass
            bm.faces.new((a, b, c, d))
    # 先端を閉じる
    tip = bm.verts.new((0, 0, 1.18))
    for j in range(segs):
        bm.faces.new((tip, grid[0][(j + 1) % segs], grid[0][j]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    me = bpy.data.meshes.new("knob")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    return me


def place_rahotsu(body, mesh, scalp_idx, apex):
    """頭皮と肉髻の面に、緯線に沿った列で渦巻きの粒を据える。"""
    import bmesh
    scalp_verts = {v.index for v in mesh.vertices if any(g.group == scalp_idx for g in v.groups)}
    scalp_faces = {f.index for f in mesh.polygons if all(i in scalp_verts for i in f.vertices)}
    pts = [mesh.vertices[i].co for i in scalp_verts]
    center = sum(pts, Vector()) / len(pts)
    center.z -= 0.03
    radius = sum((p - center).length for p in pts) / len(pts)
    spacing = BEAD_SPACING
    placed = []   # (location, normal)
    # 頭皮: 頭の中心から放射状にレイを飛ばし、頭皮の面に当たった所へ置く
    n_rings = int(math.pi * 0.7 * radius / spacing) + 1
    for k in range(n_rings + 1):
        ph = math.pi * 0.7 * k / n_rings
        n = max(1, round(2 * math.pi * radius * math.sin(ph) / spacing))
        for j in range(n):
            th = 2 * math.pi * (j + 0.5 * (k % 2)) / n
            d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)))
            hit, loc, nrm, fi = body.ray_cast(center, d)
            if hit and fi in scalp_faces and all((loc - q).length > spacing * 0.8 for q, _ in placed):
                placed.append((loc.copy(), nrm.copy()))
    # 肉髻(球)にも同じ列で
    rx, ry, rz = 0.052, 0.0546, 0.0468
    n_rings2 = int(math.pi * 0.55 * rx / spacing) + 1
    for k in range(n_rings2 + 1):
        ph = math.pi * 0.55 * k / n_rings2
        n = max(1, round(2 * math.pi * rx * math.sin(ph) / spacing))
        for j in range(n):
            th = 2 * math.pi * (j + 0.5 * (k % 2)) / n
            d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)))
            loc = apex + Vector((d.x * rx, d.y * ry, d.z * rz))
            if all((loc - q).length > spacing * 0.8 for q, _ in placed):
                placed.append((loc, d))
    knob = spiral_knob_mesh()
    bm = bmesh.new()
    for loc, nrm in placed:
        rot = nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
        mat = Matrix.Translation(loc - nrm * 0.0015) @ rot @ Matrix.Scale(BEAD_RADIUS, 4)
        tmp = bmesh.new()
        tmp.from_mesh(knob)
        bmesh.ops.transform(tmp, matrix=mat, verts=tmp.verts)
        tmp_me = bpy.data.meshes.new("k")
        tmp.to_mesh(tmp_me)
        tmp.free()
        bm.from_mesh(tmp_me)
        bpy.data.meshes.remove(tmp_me)
    me = bpy.data.meshes.new("Amida_Hair")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    hair = bpy.data.objects.new("Amida_Hair", me)
    bpy.context.collection.objects.link(hair)
    log("  rahotsu:", len(placed), "tris", len(me.polygons) * 2)
    return hair


# ---------------------------------------------------------------- 陰影(くぼみを暗く)
def cavity_colors(obj, strength, floor=0.45):
    """頂点色でくぼみを暗くし、金属の面でも輪郭が読めるようにする。"""
    import bmesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    values = []
    for v in bm.verts:
        nbrs = [e.other_vert(v) for e in v.link_edges]
        if not nbrs:
            values.append(1.0)
            continue
        avg = sum((n.co for n in nbrs), Vector()) / len(nbrs)
        edge = sum(((n.co - v.co).length for n in nbrs)) / len(nbrs)
        c = (avg - v.co).dot(v.normal) / max(edge, 1e-6)   # >0 でくぼみ
        values.append(max(floor, 1.0 - max(0.0, c) * strength))
    bm.free()
    attr = me.color_attributes.new("Color", "FLOAT_COLOR", "POINT")
    for i, val in enumerate(values):
        attr.data[i].color = (val, val, val, 1.0)
    me.color_attributes.active_color = attr
    return attr


# ---------------------------------------------------------------- 衣
NECK_Z = 0.60          # 衣の上端(首の付け根)。接地後の座標
ROBE_OFFSET = 0.018    # 体との隙間


def hand_group_indices(body):
    return [g.index for g in body.vertex_groups
            if g.name.split(".")[0].startswith(("wrist", "finger", "metacarpal"))]


def hand_bottom(body, mesh):
    """手の頂点の最下点(接地後の座標)。"""
    groups = hand_group_indices(body)
    return min(v.co.z for v in mesh.vertices if any(g.group in groups and g.weight > 0.3 for g in v.groups))


def robe_target(body, mesh):
    """衣を沿わせる対象: 本体から頭と手を除いた複製。"""
    groups = hand_group_indices(body)
    target_mesh = mesh.copy()
    target = bpy.data.objects.new("robe_target", target_mesh)
    bpy.context.collection.objects.link(target)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(target_mesh)
    dl = bm.verts.layers.deform.verify()
    doomed = [v for v in bm.verts if v.co.z > NECK_Z]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(target_mesh)
    bm.free()
    hand_points = [v.co.copy() for v in target_mesh.vertices
                   if any(g.group in groups and g.weight > 0.3 for g in v.groups)]
    log("  robe target verts", len(target_mesh.vertices), "hand verts", len(hand_points))
    return target, hand_points


def hull_mesh(name, target, levels):
    """対象の凸包を細分化した面。布を張ったときの外形(くぼみを橋渡しする)から出発する。"""
    import bmesh
    bm = bmesh.new()
    for v in target.data.vertices:
        bm.verts.new(v.co)
    bm.verts.ensure_lookup_table()
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    doomed = {g for g in res["geom_unused"] + res["geom_interior"] if isinstance(g, bmesh.types.BMVert)}
    bmesh.ops.delete(bm, geom=list(doomed), context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    sub = obj.modifiers.new("sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = levels
    apply_modifier(obj, sub)
    # 細長い三角形が残らないよう、一度リメッシュ気味に均す
    tri = obj.modifiers.new("tri", "TRIANGULATE")
    apply_modifier(obj, tri)
    return obj


def apply_modifier(obj, mod):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def build_robe(body, mesh):
    """通肩の衣。粗い筒を体に沿わせ、緩めて、体の外側に保つ、を繰り返して布の張りを出す。"""
    target, hand_points = robe_target(body, mesh)
    robe = hull_mesh("Amida_Robe", target, levels=3)
    log("  hull verts", len(robe.data.vertices))
    bpy.ops.object.select_all(action="DESELECT")
    robe.select_set(True)
    bpy.context.view_layer.objects.active = robe
    # 底面(接地)は動かさない
    pinned = robe.vertex_groups.new(name="free")
    free = [v.index for v in robe.data.vertices if v.co.z > 0.012]
    pinned.add(free, 1.0, "REPLACE")

    def project(offset, limit):
        m = robe.modifiers.new("proj", "SHRINKWRAP")
        m.target = target
        m.wrap_method = "PROJECT"
        m.use_negative_direction = True
        m.use_positive_direction = False
        m.project_limit = limit
        m.offset = offset
        m.vertex_group = "free"
        apply_modifier(robe, m)

    def wrap(offset, mode):
        m = robe.modifiers.new("wrap", "SHRINKWRAP")
        m.target = target
        m.wrap_method = "NEAREST_SURFACEPOINT"
        m.wrap_mode = mode
        m.offset = offset
        if "free" in robe.vertex_groups:
            m.vertex_group = "free"
        apply_modifier(robe, m)

    def smooth(factor, iterations):
        m = robe.modifiers.new("smooth", "SMOOTH")
        m.factor = factor
        m.iterations = iterations
        m.vertex_group = "free"
        apply_modifier(robe, m)

    # 凸包から法線の内向きに布を落とす(届かないくぼみは張ったまま残る)
    project(ROBE_OFFSET, 0.055)
    for factor, it in ((0.5, 16), (0.4, 8)):
        smooth(factor, it)
        wrap(ROBE_OFFSET, "OUTSIDE")
    # 閉じた塊のうちにボクセルで貼り直し、面の粗密と細長い三角形をなくす
    rm = robe.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = 0.007
    rm.use_smooth_shade = True
    apply_modifier(robe, rm)
    robe.vertex_groups.clear()
    sm = robe.modifiers.new("smooth2", "SMOOTH")
    sm.factor = 0.5
    sm.iterations = 4
    apply_modifier(robe, sm)
    wrap(ROBE_OFFSET, "OUTSIDE")
    dec = robe.modifiers.new("dec", "DECIMATE")
    dec.ratio = max(0.05, min(1.0, 36000 / max(1, len(robe.data.polygons))))
    apply_modifier(robe, dec)
    log("  remeshed+decimated robe verts", len(robe.data.vertices))
    # 底面を接地面へ揃える(座面に載る)
    for v in robe.data.vertices:
        if v.co.z < 0.012:
            v.co.z = 0.0
    log("  robe z max", round(max(v.co.z for v in robe.data.vertices), 3))
    # 衿: 首まわりと胸元の V 字を開ける
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(robe.data)
    def collar_z(x):
        return min(NECK_Z - 0.005, NECK_Z - 0.20 + abs(x) * 1.35)   # 胸元の V

    def above(v):
        front = v.co.y < -0.05
        return v.co.z > (collar_z(v.co.x) if front else NECK_Z - 0.005)
    from mathutils.kdtree import KDTree
    kd = KDTree(len(hand_points))
    for i, p in enumerate(hand_points):
        kd.insert(p, i)
    kd.balance()

    def over_hand(v):
        co, _, dist = kd.find(v.co)
        return dist < ROBE_OFFSET + 0.016 and v.co.z > co.z - 0.006   # 手の上に被さる布だけ(袖口)
    doomed = [v for v in bm.verts if above(v) or over_hand(v)]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    # 切り口をならす(縁の頂点を縁に沿った隣と平均)
    for _ in range(12):
        moves = {}
        for v in bm.verts:
            if not v.is_boundary or v.co.z < 0.05:
                continue
            nbrs = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nbrs) >= 2:
                moves[v] = (v.co + sum((n.co for n in nbrs), Vector())) / (len(nbrs) + 1)
        for v, co in moves.items():
            v.co = co
    # 残った縁の頂点を衿の線の上へ持ち上げて、縁を滑らかに
    for v in bm.verts:
        if v.is_boundary and v.co.z > 0.1:
            limit = collar_z(v.co.x) if v.co.y < -0.05 else NECK_Z - 0.005
            v.co.z = min(limit, v.co.z + 0.02)
    bm.to_mesh(robe.data)
    bm.free()
    solid = robe.modifiers.new("solid", "SOLIDIFY")
    solid.thickness = 0.012
    solid.offset = 1.0
    apply_modifier(robe, solid)
    for poly in robe.data.polygons:
        poly.use_smooth = True
    bpy.data.objects.remove(target, do_unlink=True)
    lap = max((v.co.z for v in robe.data.vertices if abs(v.co.x) < 0.12 and -0.31 < v.co.y < -0.17 and v.co.z < 0.30), default=0)
    log("  robe verts", len(robe.data.vertices), "polys", len(robe.data.polygons), "robe lap z", round(lap, 3))
    return robe, lap


# ---------------------------------------------------------------- 組み立て
def build(stage, matte=False):
    services = bootstrap()
    HumanService = services["HumanService"]
    TargetService = services["TargetService"]

    human = HumanService.create_human(macro_detail_dict=MACRO)
    for name, weight in FACE_TARGETS.items():
        path = TargetService.target_full_path(name)
        if not path:
            log("target not found:", name)
            continue
        TargetService.load_target(human, path, weight=weight)
    keys = human.data.shape_keys.key_blocks
    applied = [(k.name, round(k.value, 2)) for k in keys if not k.name.startswith("$") and k.name != "Basis"]
    log("targets applied:", len(applied), applied[:6])

    arm = HumanService.add_builtin_rig(human, "default")
    sub = human.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1

    def pose_all(hand_lift):
        bpy.context.view_layer.objects.active = arm
        arm.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix()
        bpy.context.view_layer.update()
        pose_lotus_legs(arm, "R", 18)
        pose_lotus_legs(arm, "L", 34)
        floor_z, lap_z = measure_lap(human)
        log(f"  floor z {floor_z:.3f}, lap top z {lap_z:.3f} (above floor {lap_z - floor_z:.3f}), hand lift {hand_lift:.3f}")
        pose_arms_dhyana(arm, lap_z + hand_lift)
        pose_head(arm)
        bpy.ops.object.mode_set(mode="OBJECT")
        for n in ("wrist.L", "wrist.R", "foot.L", "foot.R"):
            log(f"  {n:12s} tail", [round(v, 3) for v in arm.pose.bones[n].tail])

    def bake():
        # 眼球ヘルパー(マスクで消える前)から目の中心と半径を取る
        mask = human.modifiers["Hide helpers"]
        mask.show_viewport = False
        depsgraph = bpy.context.evaluated_depsgraph_get()
        full = human.evaluated_get(depsgraph).data
        eyes = {}
        for side in ("l", "r"):
            idx = human.vertex_groups[f"helper-{side}-eye"].index
            pts = [v.co.copy() for v in full.vertices if any(g.group == idx for g in v.groups)]
            c = sum(pts, Vector()) / len(pts)
            eyes[side] = (c, max((q - c).length for q in pts))
        mask.show_viewport = True
        depsgraph = bpy.context.evaluated_depsgraph_get()
        baked = bpy.data.meshes.new_from_object(human.evaluated_get(depsgraph), depsgraph=depsgraph)
        body = bpy.data.objects.new("Amida_Body", baked)
        bpy.context.collection.objects.link(body)
        # 接地: 最下点を z=0 に、左右中心を x=0 に。下半身は前後に 1.2 倍して坐像の奥行きをつくる
        zs = [v.co.z for v in baked.vertices]
        xs = [v.co.x for v in baked.vertices]
        shift = Vector((-(max(xs) + min(xs)) / 2, 0, -min(zs)))
        baked.transform(Matrix.Translation(shift))
        for v in baked.vertices:
            k = 1.0 + 0.2 * max(0.0, min(1.0, (0.50 - v.co.z) / 0.15))
            v.co.y *= k
        for side in eyes:
            eyes[side] = (eyes[side][0] + shift, eyes[side][1])
        ys = [v.co.y for v in baked.vertices]
        log("  body bbox y", round(min(ys), 3), round(max(ys), 3), "verts", len(baked.vertices))
        return body, baked, eyes

    pose_all(ROBE_OFFSET + 0.045)
    body, baked, eyes = bake()
    if stage >= 2:
        robe, robe_lap = build_robe(body, baked)
        log(f"  robe lap {robe_lap:.3f}, hand bottom {hand_bottom(body, baked):.3f}")
    for obj in (human, arm):
        bpy.data.objects.remove(obj, do_unlink=True)

    add_head_features(body, baked, eyes)

    mat = bpy.data.materials.new("AmidaGold")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.55, 0.52, 0.48, 1) if matte else (*GOLD, 1)
    bsdf.inputs["Metallic"].default_value = 0.0 if matte else 0.72
    bsdf.inputs["Roughness"].default_value = 0.85 if matte else 0.5
    baked.materials.append(mat)
    for poly in baked.polygons:
        poly.use_smooth = True

    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and not obj.data.materials:
            obj.data.materials.append(mat)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name in ("Amida_Body", "Amida_Robe", "Amida_Hair"):
            cavity_colors(obj, strength=1.3 if obj.name == "Amida_Body" else 1.4)
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
        lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
        log(f"  {obj.name:16s} verts {len(pts):6d} min {lo} max {hi}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = body
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_vertex_color="ACTIVE", export_all_vertex_colors=False)
    log("->", OUT, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, default=2)
    parser.add_argument("--matte", action="store_true", help="検品用に灰色の艶消しで書き出す")
    args = parser.parse_args()
    build(args.stage, args.matte)
