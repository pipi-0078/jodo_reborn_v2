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
HAIR_COLOR = (0.012, 0.016, 0.03)  # 螺髪: 紺青がかった黒漆
UPPER_LID_DEG = -34  # 上瞼ボーンの回転(閉じ目。深く重ねて合わせ目の影を出す)
USHNISHA_HEIGHT = 0.03  # 肉髻(二段目)の高さ(m)
USHNISHA_RADIUS = 0.052  # 肉髻の半径(m)
USHNISHA_EDGE = 0.012  # 肉髻の縁の帯(段差をなだらかにする幅、m)
HAIR_THICKNESS = 0.008  # 地髪の厚み(生え際で段差になる、m)
HAIRLINE_HEIGHT = 0.03
SIDEBURN_DROP = 0.054  # 耳の上端からもみあげの下端までの距離(m)
SIDEBURN_WIDTH = 0.04  # もみあげの最大幅(耳の前端から頬側へ、m)
SIDEBURN_TIP_R = 0.012  # もみあげの先端の丸み(半径、m)
SIDEBURN_TOP_W = 0.036  # こめかみの生え際の、耳の前端からの前方距離(m)
BEAD_SPACING = 0.0078
EYE_LINE_R = 0.0011  # 目の合わせ目の線の太さ(半径、m)
EAR_MARGIN = 0.009  # 耳の輪郭と髪の隙間(m)
RIM_RADIUS = 0.0022  # 生え際の縁取りの線の太さ(半径、m)
RIM_SMOOTH = 8  # 縁取りの曲線をならす回数
BEAD_RADIUS = BEAD_SPACING * 0.6  # 螺髪の粒。隣と少し重なって下地を隠す

# 体型(MakeHuman のマクロ。gender 0=女 1=男、age 0.5=25歳相当)
MACRO = {
    "gender": 0.65, "age": 0.5, "muscle": 0.45, "weight": 0.56, "proportions": 0.5, "height": 0.5,
    "cupsize": 0.0, "firmness": 0.5,
    "race": {"asian": 1.0, "caucasian": 0.0, "african": 0.0},
}

# 相好(定朝様: 円満な面相・伏し目・長い耳朶)。値は 0..1
FACE_TARGETS = {
    # 美男子系・アジア系。頬骨は浅く、口角を上げて微笑む。目はリグの瞼ボーンで閉じる
    "head-oval": 0.2, "head-round": 0.25, "head-scale-vert-incr": 0.1, "head-scale-horiz-incr": 0.42, "head-scale-depth-incr": 0.3,
    "forehead-temple-incr": 0.3, "forehead-nubian-decr": 0.4, "forehead-scale-vert-decr": 0.35,
    "l-cheek-bones-decr": 0.6, "r-cheek-bones-decr": 0.6,          # 頬骨は浅く
    "l-cheek-volume-incr": 0.38, "r-cheek-volume-incr": 0.38,
    "chin-bones-incr": 0.15, "chin-prominent-incr": 0.1, "chin-cleft-decr": 0.4, "chin-width-incr": 0.1,
    "l-ear-lobe-incr": 1.0, "r-ear-lobe-incr": 1.0,
    "l-ear-scale-incr": 0.5, "r-ear-scale-incr": 0.5,
    "l-ear-scale-vert-incr": 1.0, "r-ear-scale-vert-incr": 1.0,      # 耳全体を縦に長く(比率を保ったまま)
    "l-ear-shape-round": 0.6, "r-ear-shape-round": 0.6,
    "l-ear-flap-decr": 0.3, "r-ear-flap-decr": 0.3,
    "l-eye-scale-incr": 0.2, "r-eye-scale-incr": 0.2,
    "l-eye-epicanthus-in": 0.4, "r-eye-epicanthus-in": 0.4,
    "l-eye-bag-decr": 0.5, "r-eye-bag-decr": 0.5,
    "eyebrows-angle-up": 0.4, "eyebrows-trans-forward": 0.1,
    "nose-greek-incr": 0.4, "nose-hump-decr": 0.4, "nose-scale-horiz-decr": 0.35,
    "nose-nostrils-width-decr": 0.5, "nose-flaring-decr": 0.5, "nose-point-width-decr": 0.3,
    "mouth-angles-up": 0.7, "mouth-scale-horiz-decr": 0.1,           # 口角を上げて微笑む
    "mouth-upperlip-volume-decr": 0.35, "mouth-lowerlip-volume-decr": 0.2, "mouth-dimples-in": 0.3,
    "neck-scale-vert-decr": 0.5, "neck-scale-horiz-incr": 0.2,
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


def lid_z(human, bone_name):
    """瞼ボーンに強く付いている頂点の z の範囲(評価後メッシュ)。"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    me = human.evaluated_get(depsgraph).data
    gi = human.vertex_groups[bone_name].index
    zs = [v.co.z for v in me.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]
    return min(zs), max(zs)


def close_eyes_with_rig(arm, human):
    """上瞼のボーンを下ろし、下瞼をわずかに上げて目を閉じる(瞼の形は素体のまま)。"""
    for side in ("L", "R"):
        upper = arm.pose.bones[f"orbicularis03.{side}"]
        lower = arm.pose.bones[f"orbicularis04.{side}"]
        upper.rotation_mode = lower.rotation_mode = "XYZ"
        lo_rest = lid_z(human, f"orbicularis04.{side}")[1]
        # 下瞼: 上がる向きを試して決める
        best = (0.0, lo_rest)
        for deg in (11, -11):
            lower.rotation_euler.x = math.radians(deg)
            bpy.context.view_layer.update()
            top = lid_z(human, f"orbicularis04.{side}")[1]
            if top > best[1]:
                best = (deg, top)
        lower.rotation_euler.x = math.radians(best[0])
        # 上瞼: 下瞼に重なるまで下ろす(固定角。瞼の縁が下瞼の上端より 4mm 下に来る)
        deg = UPPER_LID_DEG
        upper.rotation_euler.x = math.radians(deg)
        bpy.context.view_layer.update()
        log(f"  eyelids {side}: upper edge z {lid_z(human, f'orbicularis03.{side}')[0]:.4f}, lower top z {best[1]:.4f}")
        log(f"  eyelids {side}: upper {deg} deg, lower {best[0]} deg")


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


def stretch_earlobes(body, mesh, factor=1.25):
    """耳の下半分を下へ伸ばして長い耳朶にする。
    下端付近はまとめて平行移動して元の丸い形を保ち、中ほどだけを引き伸ばす(尖らせない)。
    耳朶はわずかに厚く、丸く。"""
    idx = body.vertex_groups["ears"].index
    for side_sign in (1, -1):
        ear = [v for v in mesh.vertices if any(g.group == idx for g in v.groups) and v.co.x * side_sign > 0]
        if not ear:
            continue
        zc = sum(v.co.z for v in ear) / len(ear)
        zmin = min(v.co.z for v in ear)
        drop = (zc - zmin) * (factor - 1)
        for v in ear:
            if v.co.z < zc:
                t = (zc - v.co.z) / max(zc - zmin, 1e-6)          # 0(中心)〜1(下端)
                u = min(1.0, t / 0.55)                              # 下 45% はまとめて動かす
                w = u * u * (3 - 2 * u)
                v.co.z -= drop * w
                v.co.x += side_sign * 0.0025 * w                    # わずかに外へ
                v.co.y += -0.003 * w                                # 少し前へ
                # 耳朶を丸く厚く: 下端に近いほど、耳の面の内外へふくらませる
                v.co += v.normal * (0.0018 * max(0.0, t - 0.55) / 0.45)
    mesh.update()


def soften_face(body, mesh, factor=0.5, iterations=3):
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


def close_eyes(body, mesh, eyes):
    """目の領域を面ごと取り去って塞ぎ、細かく割ってから、頂点位置を解析的な面
    (眼球の丸み → 外周で顔の面へ溶ける)に置き換える。合わせ目は細い溝一本、上瞼はやわらかいふくらみ。"""
    import bmesh
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    def smoothstep(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)

    # 外周の輪の高さ(方向ごと)を、編集前の顔からレイキャストで取っておく
    tables = {}
    for side, (c, r) in eyes.items():
        R = r * 1.9
        table = []
        for k in range(72):
            th = 2 * math.pi * k / 72
            origin = Vector((c.x + R * math.cos(th), c.y - r * 4, c.z + R * math.sin(th)))
            hit, loc, _, _ = body.ray_cast(origin, Vector((0, 1, 0)), distance=r * 8, depsgraph=depsgraph)
            table.append(loc.y if hit else c.y - r)
        tables[side] = table

    bm = bmesh.new()
    bm.from_mesh(mesh)
    for side, (c, r) in eyes.items():
        R, R_ball, a = r * 1.9, r * 1.08, r * 1.55
        table = tables[side]

        def inside(v):
            return (v.co - c).length < r * 1.7 and v.co.y < c.y + r * 0.5
        doomed = [f for f in bm.faces if all(inside(v) for v in f.verts)]
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces and inside(v)]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        rim = [v for v in bm.verts if v.is_boundary and (v.co - c).length < r * 2.2]
        rim_edges = list({e for v in rim for e in v.link_edges if e.is_boundary})
        filled = bmesh.ops.holes_fill(bm, edges=rim_edges, sides=0)["faces"]
        tri = bmesh.ops.triangulate(bm, faces=filled)["faces"]
        inner_edges = list({e for f in tri for e in f.edges if all(fe in tri for fe in e.link_faces)})
        bmesh.ops.subdivide_edges(bm, edges=inner_edges, cuts=3, use_grid_fill=True)
        # 目のまわり一帯をもう一段細かく割る(溝を刻める密度にする)
        region_edges = [e for e in bm.edges if all((v.co - c).length < r * 2.05 and v.co.y < c.y + r * 0.6 for v in e.verts)]
        bmesh.ops.subdivide_edges(bm, edges=region_edges, cuts=1, use_grid_fill=True)

        # 頂点を解析的な面へ。球の前面は外周の面より 2.5mm だけ前に出す(閉じた瞼のわずかな丸み)
        y_front = sum(table) / len(table) - 0.0025
        cy_ball = y_front + R_ball
        rho_cap = R_ball * 0.8
        moved = 0
        for v in bm.verts:
            if not v.is_valid:
                continue
            x, z = v.co.x - c.x, v.co.z - c.z
            rho = math.hypot(x, z)
            if rho >= R or v.co.y > c.y + r * 0.6:
                continue
            th = math.atan2(z, x) % (2 * math.pi)
            k = th / (2 * math.pi) * 72
            k0, f = int(k) % 72, k - int(k)
            y_border = table[k0] * (1 - f) + table[(k0 + 1) % 72] * f
            rc = min(rho, rho_cap)
            y_ball = cy_ball - math.sqrt(R_ball * R_ball - rc * rc)
            w = 1.0 - smoothstep(rho_cap * 0.75, R, rho)
            y = w * y_ball + (1 - w) * y_border
            # 合わせ目の溝と上瞼のふくらみ
            tl = x / a
            line = -0.10 * r * tl * tl
            dz = z - line
            taper = max(0.0, 1 - tl * tl) ** 0.6
            groove = -0.0011 * max(0.0, 1 - abs(dz) / 0.0016)
            u = dz / (r * 0.55)
            swell = 0.0016 * math.sin(math.pi * u) ** 1.2 if 0 < u < 1 else 0.0
            n = Vector((x, -math.sqrt(max(1e-6, R_ball * R_ball - rc * rc)), z)).normalized()
            v.co = Vector((c.x + x, y, c.z + z)) + n * (taper * (groove + swell))
            moved += 1
        log("  eye", side, "faces removed", len(doomed), "verts reshaped", moved)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def build_eyelids(body, eyes):
    """閉じた目を、目のまわり一帯を覆う一枚の解析的なパッチとして作る。
    内側は眼球の丸み(球面)、外周は顔の面(外周の輪だけをレイキャストで取る)へ滑らかに溶かす。
    合わせ目は細い V 字の溝を一本、上瞼はそのすぐ上のやわらかいふくらみで示す。"""
    import bmesh
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()

    def smoothstep(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)

    for side, (c, r) in eyes.items():
        a = r * 1.55            # 合わせ目の線の半長
        R = r * 1.9             # パッチの半径(この外周で顔の面に溶ける)
        R_ball = r * 1.08       # 瞼の下の丸み
        nx, nv = 64, 14

        def skin_y(x, z):
            origin = Vector((c.x + x, c.y - r * 4, c.z + z))
            hit, loc, _, _ = body.ray_cast(origin, Vector((0, 1, 0)), distance=r * 8, depsgraph=depsgraph)
            return loc.y if hit else c.y - r

        def point(x, z, h):
            rho = math.hypot(x, z)
            theta = math.atan2(z, x)
            y_border = skin_y(R * math.cos(theta), R * math.sin(theta))
            inside = rho < R_ball * 0.999
            y_ball = c.y - math.sqrt(R_ball * R_ball - x * x - z * z) if inside else c.y
            # 球面の縁(rho=R_ball)から外周までは、球面の接線方向へなだらかに続ける
            y_tang = c.y + (rho - R_ball) * 0.35 if not inside else y_ball
            w = 1.0 - smoothstep(R_ball * 0.9, R, rho)
            y = w * min(y_ball, y_tang) + (1 - w) * y_border
            y = min(y, skin_y(x, z) - 0.0004)                    # 肌(鼻筋など)より奥へは入らない
            n = Vector((x, -math.sqrt(max(1e-6, R_ball * R_ball - x * x - z * z)), z)).normalized() if inside else Vector((0, -1, 0))
            return Vector((c.x + x, y, c.z + z)) + n * h

        for upper in (True, False):
            grid = []
            for i in range(nx + 1):
                t = -1 + 2 * i / nx
                x = R * t
                tl = x / a                                        # 線に沿った位置(-1..1 が線の範囲)
                line = -0.10 * r * tl * tl                        # 合わせ目: 両端でわずかに下がる長い弧
                border = math.sqrt(max(1e-6, R * R - x * x))
                row = []
                for j in range(nv + 1):
                    v = j / nv
                    z = line + (border - line) * v if upper else line - (border + line) * v
                    taper = max(0.0, 1 - tl * tl) ** 0.6          # 目頭・目尻で消える
                    groove = -0.0012 * max(0.0, 1 - v / 0.10)     # 合わせ目の細い溝
                    if upper:
                        u = v / 0.55
                        swell = 0.0016 * math.sin(math.pi * min(1.0, u)) ** 1.2 if u < 1 else 0.0
                    else:
                        swell = 0.0
                    h = taper * (groove + swell)
                    row.append(bm.verts.new(point(x, z, h)))
                grid.append(row)
            for i in range(nx):
                for j in range(nv):
                    quad = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                    if len(set(quad)) == 4:
                        try:
                            bm.faces.new(quad if upper else tuple(reversed(quad)))
                        except ValueError:
                            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Amida_Eyelids")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new("Amida_Eyelids", me)
    bpy.context.collection.objects.link(obj)
    log("  eyelids verts", len(me.vertices))
    return obj


def add_head_features(body, mesh, eyes):
    """閉じた目・白毫・肉髻・螺髪。"""
    stretch_earlobes(body, mesh)
    created = []
    for side, (c, r) in eyes.items():
        created.append(add_sphere(f"Amida_Eye_{side.upper()}", c + Vector((0, 0.002, 0)), r * 0.97))
    # 白毫: 眉間。両目の中点から前へ出し、眉間の肌の上に半分埋める
    mid = (eyes["l"][0] + eyes["r"][0]) / 2
    front = min(v.co.y for v in mesh.vertices if abs(v.co.x) < 0.01 and abs(v.co.z - (mid.z + 0.03)) < 0.008)
    created.append(add_sphere("Amida_Urna", Vector((0, front + 0.002, mid.z + 0.03)), 0.0065))
    # 肉髻: 頭頂の丸い盛り上がり
    scalp_idx = body.vertex_groups["scalp"].index
    hair_verts = {v.index for v in mesh.vertices if any(g.group == scalp_idx for g in v.groups)}
    scalp = [mesh.vertices[i].co for i in hair_verts]
    top = max(scalp, key=lambda p: p.z)
    apex = Vector((0, top.y + 0.01, top.z - 0.015))
    # 肉髻: 頭頂に二段目の丸い盛り上がりを作る(段差がはっきり見える二段構造)。
    # 頂点から半径 USHNISHA_RADIUS の内側を垂直に持ち上げ、縁の細い帯でなだらかに落とす
    def smoothstep(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)
    for i in hair_verts:
        v = mesh.vertices[i]
        d = (Vector((v.co.x, v.co.y, 0)) - Vector((apex.x, apex.y + 0.005, 0))).length
        if d < USHNISHA_RADIUS + USHNISHA_EDGE and v.co.z > apex.z - 0.07:
            w = 1.0 - smoothstep((d - USHNISHA_RADIUS) / USHNISHA_EDGE)
            dome = 1.0 - (min(d, USHNISHA_RADIUS) / USHNISHA_RADIUS) ** 2      # 上面の丸み
            v.co.z += USHNISHA_HEIGHT * w * (0.75 + 0.25 * dome)
    mesh.update()
    top = max((mesh.vertices[i].co for i in hair_verts), key=lambda p: p.z)
    apex = Vector((0, top.y, top.z))
    # 髪の領域を整える:
    #  - 耳とその周囲(1.2cm)は髪にしない。耳の上端より下の側頭部も髪にしない
    #  - 額側は滑らかな弧の生え際で切る(中央が最も低く、こめかみへ向かって上がる)
    ear_idx = body.vertex_groups["ears"].index
    ear_pts = [v.co.copy() for v in mesh.vertices if any(g.group == ear_idx for g in v.groups)]
    ear_top = max(p.z for p in ear_pts)
    ear_y = sum(p.y for p in ear_pts) / len(ear_pts)
    brow_z = mid.z + 0.03
    hair_z0 = brow_z + HAIRLINE_HEIGHT                     # 中央の生え際の高さ
    head_half = max(abs(v.co.x) for v in mesh.vertices if brow_z < v.co.z < top.z)
    def hairline_z(x):
        return hair_z0 - 0.5 * (x * x) / max(head_half, 1e-3) - 0.005 * math.exp(-(x / 0.012) ** 2)   # 深い弧、中央にわずかな切れ込み
    front_y = ear_y - 0.01                                  # 耳より前を「額側」とみなす
    # 側頭部の生え際: 額の弧の端(こめかみ)から一本の滑らかな線で下り、耳の前で頬側へふくらんで
    # 耳朶の高さの尖った先で終わる。高さ z ごとに「耳の前端からどれだけ前(頬側)まで髪か」を w(z) で決める
    face_half = 0.05                                        # ここより外は側頭部
    z_top = hairline_z(face_half)                            # こめかみで額の弧と接続する高さ
    z_tip = ear_top - SIDEBURN_DROP                          # もみあげの尖った先
    ear_front_y = min(p.y for p in ear_pts)                 # 耳の前端
    ear_back_y = max(p.y for p in ear_pts)                  # 耳の後端
    ear_bottom_z = min(p.z for p in ear_pts)                # 耳朶の下端
    z_mid = ear_top - 0.02                                   # ここから下が先端へ細くなる(耳の穴のあたり)
    w_top = SIDEBURN_TOP_W                                   # こめかみの生え際: 耳の前端からこれだけ前
    w_mid = SIDEBURN_WIDTH                                   # ふくらみの最大幅

    def burn_w(z):
        """高さ z で、耳の前端からどれだけ前(頬側)まで髪か。こめかみから先端へ、下るほど一様に細くなる。"""
        if z >= z_top:
            return w_top
        if z <= z_tip:
            return 0.0
        r = SIDEBURN_TIP_R                                   # 先端の丸み(この幅で丸く終わる)
        z_end = z_tip + r
        if z >= z_end:
            return r + (w_top - r) * (z - z_end) / max(z_top - z_end, 1e-6)   # 先端の丸みまで真っ直ぐ細くなる
        return math.sqrt(max(0.0, r * r - (z_end - z) ** 2))                # 丸い先端

    def side_hair(v):
        if abs(v.co.x) < face_half or v.co.z <= z_tip:
            return False
        if v.co.z >= z_top:
            return True                                     # こめかみの線より上は全部髪
        return v.co.y > ear_front_y - burn_w(v.co.z)

    candidates = set(hair_verts)
    for v in mesh.vertices:
        if v.co.y < front_y and v.co.z < top.z and ((abs(v.co.x) < face_half and v.co.z > hairline_z(v.co.x)) or side_hair(v)):
            candidates.add(v.index)
    hair_verts = set()
    for i in candidates:
        v = mesh.vertices[i]
        if any((v.co - q).length < EAR_MARGIN for q in ear_pts):
            continue                                        # 耳の周囲(輪郭に沿って一定の隙間)
        if v.co.y < front_y and abs(v.co.x) < face_half and v.co.z < hairline_z(v.co.x):
            continue                                        # 額: 生え際の弧より下は肌
        if v.co.y < front_y and abs(v.co.x) >= face_half and not side_hair(v):
            continue                                        # 側頭部: 生え際の線より前は肌
        if abs(v.co.x) > 0.04 and v.co.y > ear_front_y - 0.003 and v.co.y < ear_back_y + 0.012 and v.co.z < ear_bottom_z + 0.004:
            continue                                        # 耳の下: 肌(耳の後ろは耳の輪郭に沿って髪が回る)
        hair_verts.add(i)
    log(f"  sideburn: z_top {z_top:.3f} z_mid {z_mid:.3f} z_tip {z_tip:.3f}")
    log("  hair verts", len(hair_verts), "ear top z", round(ear_top, 3), "hairline z0", round(hair_z0, 3))
    # 地髪の下地: 髪の領域を法線方向へ厚く盛り、生え際で段差(帽子の縁のような厚み)を作る。
    # 縁は境界からの頂点の段数でなだらかに丸める
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    ring = {}
    frontier = []
    for i in hair_verts:
        v = bm.verts[i]
        if any(e.other_vert(v).index not in hair_verts for e in v.link_edges):
            ring[i] = 0
            frontier.append(v)
    level = 0
    while frontier and level < 3:
        level += 1
        nxt = []
        for v in frontier:
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.index in hair_verts and o.index not in ring:
                    ring[o.index] = level
                    nxt.append(o)
        frontier = nxt
    bm.free()
    profile = {0: 0.35, 1: 0.7, 2: 0.9}
    for i in hair_verts:
        v = mesh.vertices[i]
        v.co += v.normal * (HAIR_THICKNESS * profile.get(ring.get(i, 3), 1.0))
    mesh.update()
    hair = place_rahotsu(body, mesh, hair_verts, apex)
    created.append(hair)
    created.append(hairline_rim(body, mesh, hair_verts))
    created.append(eye_lines(body, mesh))
    return created, hair_verts




# ---------------------------------------------------------------- 螺髪
def spiral_knob_mesh():
    """右巻きの渦を巻いた粒(螺髪)。裾から先端へ 2.5 周の螺旋の畝と溝を持ち、先端は小さく尖る。
    頂点座標は半径 1、+Z が先端。"""
    import bmesh
    bm = bmesh.new()
    segs, rings = 8, 4
    grid = []
    for i in range(rings + 1):
        u = i / rings                                  # 0(先端)〜1(裾)
        ph = math.pi * (0.06 + 0.60 * u)               # 極角(裾は約 119°、少し下へ巻き込む)
        for j in range(segs):
            th = 2 * math.pi * j / segs
            # 螺旋: 裾から先端へ右巻きに 2.5 周。畝(山)と溝(谷)を交互に
            spiral = math.cos(th - 2.5 * 2 * math.pi * (1 - u))
            depth = 0.13 * (0.5 - 0.5 * spiral) ** 1.5 * min(1.0, u * 4)   # 先端付近では溝を浅く
            r = 1.0 - depth
            x = r * math.sin(ph) * math.cos(th)
            y = r * math.sin(ph) * math.sin(th)
            z = r * math.cos(ph) * 1.12 + 0.05 * (1 - u) ** 3     # 先端をわずかに立てる
            grid.append(bm.verts.new((x, y, z)) if i > 0 else None)
    # 先端は一点
    tip = bm.verts.new((0, 0, 1.2))
    def at(i, j):
        return tip if i == 0 else grid[i * segs + (j % segs)]
    for i in range(rings):
        for j in range(segs):
            a, b, c, d = at(i, j), at(i, j + 1), at(i + 1, j + 1), at(i + 1, j)
            if i == 0:
                bm.faces.new((a, c, d))
            else:
                bm.faces.new((a, b, c, d))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("knob")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    return me


def place_rahotsu(body, mesh, hair_verts, apex):
    """螺髪を隙間なく敷き詰める。髪の面の上に点を密に散らし、横の帯(列)ごとに角度順で
    詰めていく貪欲法で、互い違いの列状に均一な間隔で据える。"""
    import bmesh
    import random
    scalp_verts = set(hair_verts)
    scalp_faces = [f for f in mesh.polygons if all(i in scalp_verts for i in f.vertices)]
    pts = [mesh.vertices[i].co for i in scalp_verts]
    center = sum(pts, Vector()) / len(pts)
    spacing = BEAD_SPACING
    rng = random.Random(5)
    areas = [f.area for f in scalp_faces]
    samples = []
    for _ in range(60000):
        f = rng.choices(scalp_faces, weights=areas)[0]
        vs = [mesh.vertices[i].co for i in f.vertices]
        a_, b_ = rng.random(), rng.random()
        if a_ + b_ > 1:
            a_, b_ = 1 - a_, 1 - b_
        q = vs[0] + (vs[1] - vs[0]) * a_ + (vs[2] - vs[0]) * b_
        samples.append((q.copy(), f.normal.copy()))
    # 列: 高さの帯ごとに、頭の中心まわりの角度順に並べる(帯は互い違いに半ピッチずらす)
    row_h = spacing * 0.87
    zmin = min(q.z for q, _ in samples)
    def key(item):
        q, _ = item
        band = int((q.z - zmin) / row_h)
        ang = math.atan2(q.y - center.y, q.x - center.x) + (0.5 * spacing / max(0.01, math.hypot(q.x - center.x, q.y - center.y)) if band % 2 else 0)
        return (band, ang)
    samples.sort(key=key)
    cell = spacing
    grid = {}
    placed = []
    def free(q):
        cx, cy, cz = int(q.x // cell), int(q.y // cell), int(q.z // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for r in grid.get((cx + dx, cy + dy, cz + dz), ()):
                        if (q - r).length < spacing * 0.93:
                            return False
        return True
    for q, n in samples:
        if free(q):
            placed.append((q, n))
            grid.setdefault((int(q.x // cell), int(q.y // cell), int(q.z // cell)), []).append(q)

    # 間隔を均す: 近すぎる粒同士を押し離し、面へ戻す。空いた所へ粒を足す。これを数回
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    face_ids = {f.index for f in scalp_faces}
    pts = [q for q, _ in placed]
    nrms = [n for _, n in placed]
    for round_ in range(16):
        # 反発
        grid = {}
        for i, q in enumerate(pts):
            grid.setdefault((int(q.x // cell), int(q.y // cell), int(q.z // cell)), []).append(i)
        moves = [Vector() for _ in pts]
        for i, q in enumerate(pts):
            cx, cy, cz = int(q.x // cell), int(q.y // cell), int(q.z // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in grid.get((cx + dx, cy + dy, cz + dz), ()):
                            if j <= i:
                                continue
                            d = pts[j] - q
                            L = d.length
                            if 1e-6 < L < spacing:
                                push = d.normalized() * ((spacing - L) * 0.5)
                                moves[i] -= push
                                moves[j] += push
        for i in range(len(pts)):
            q = pts[i] + moves[i]
            ok, loc, nrm, fi = body.closest_point_on_mesh(q, depsgraph=depsgraph)
            if ok and fi in face_ids:
                pts[i], nrms[i] = loc.copy(), nrm.copy()
        # 隙間に足す
        grid = {}
        for i, q in enumerate(pts):
            grid.setdefault((int(q.x // cell), int(q.y // cell), int(q.z // cell)), []).append(i)
        added = 0
        for q, n in samples:
            cx, cy, cz = int(q.x // cell), int(q.y // cell), int(q.z // cell)
            near = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in grid.get((cx + dx, cy + dy, cz + dz), ()):
                            if (q - pts[j]).length < spacing * 0.74:
                                near = True
                                break
                        if near:
                            break
                    if near:
                        break
                if near:
                    break
            if not near:
                pts.append(q)
                nrms.append(n)
                grid.setdefault((cx, cy, cz), []).append(len(pts) - 1)
                added += 1
        log(f"  rahotsu relax round {round_}: {len(pts)} (+{added})")
    # 髪の輪郭からはみ出す粒は置かない(境界の頂点に粒の半径より近いものを除く)
    from mathutils.kdtree import KDTree
    boundary = []
    bm_b = bmesh.new()
    bm_b.from_mesh(mesh)
    bm_b.verts.ensure_lookup_table()
    for i in scalp_verts:
        v = bm_b.verts[i]
        if any(e.other_vert(v).index not in scalp_verts for e in v.link_edges):
            boundary.append(v.co.copy())
    bm_b.free()
    kd = KDTree(len(boundary))
    for i, b in enumerate(boundary):
        kd.insert(b, i)
    kd.balance()
    kept = [(q, n) for q, n in zip(pts, nrms) if kd.find(q)[2] >= BEAD_RADIUS * 0.85]
    log("  rahotsu trimmed at hair edge:", len(pts) - len(kept))
    placed = kept

    knob = spiral_knob_mesh()
    bm = bmesh.new()
    rng = random.Random(11)
    for loc, nrm in placed:
        rot = nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
        spin = Matrix.Rotation(rng.random() * 2 * math.pi, 4, "Z")
        mat = Matrix.Translation(loc - nrm * 0.0015) @ rot @ spin @ Matrix.Scale(BEAD_RADIUS, 4)
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



def hairline_rim(body, mesh, hair_verts):
    """髪と肌の境界に沿って、滑らかな黒い縁取りの線(細い管)を敷く。
    境界のジグザグをならした曲線を肌の面へ投影し、その上に円断面を掃引する。"""
    import bmesh
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    # 境界の辺(片側だけが髪の面)
    hair_faces = {f.index for f in bm.faces if all(v.index in hair_verts for v in f.verts)}
    adj = {}
    for e in bm.edges:
        fs = [f.index in hair_faces for f in e.link_faces]
        if len(fs) == 2 and fs[0] != fs[1]:
            a, b = e.verts[0].index, e.verts[1].index
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    # 辺をたどって閉じた輪にする
    loops = []
    seen = set()
    for start in adj:
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxt = [n for n in adj.get(cur, []) if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) >= 12:
            loops.append(loop)
    bm.free()

    out = bmesh.new()
    total = 0
    for loop in loops:
        pts = [mesh.vertices[i].co.copy() for i in loop]
        n = len(pts)
        # 輪に沿って均す(ジグザグを取る)
        for _ in range(RIM_SMOOTH):
            pts = [(pts[(i - 1) % n] + pts[i] * 2 + pts[(i + 1) % n]) / 4 for i in range(n)]
        # 肌の面へ投影し、法線を得る
        proj, nrm = [], []
        for q in pts:
            ok, loc, nr, _ = body.closest_point_on_mesh(q, depsgraph=depsgraph)
            proj.append(loc.copy() if ok else q)
            nrm.append(nr.copy() if ok else Vector((0, -1, 0)))
        # 円断面を掃引
        segs = 8
        rings = []
        for i in range(n):
            t = (proj[(i + 1) % n] - proj[(i - 1) % n]).normalized()
            up = nrm[i]
            side = t.cross(up).normalized()
            up = side.cross(t).normalized()
            center = proj[i] + up * (RIM_RADIUS * 0.35)
            ring = []
            for k in range(segs):
                a = 2 * math.pi * k / segs
                ring.append(out.verts.new(center + side * (RIM_RADIUS * math.cos(a)) + up * (RIM_RADIUS * math.sin(a))))
            rings.append(ring)
        for i in range(n):
            r0, r1 = rings[i], rings[(i + 1) % n]
            for k in range(segs):
                try:
                    out.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
                except ValueError:
                    pass
        total += n
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    me = bpy.data.meshes.new("Amida_HairRim")
    out.to_mesh(me)
    out.free()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new("Amida_HairRim", me)
    bpy.context.collection.objects.link(obj)
    log("  hair rim: loops", len(loops), "points", total)
    return obj



def eye_lines(body, mesh):
    """閉じた目の合わせ目に沿って、細い暗い線(管)を敷いて目の縁をはっきりさせる。
    上瞼ボーンに強く付く頂点のうち、横位置ごとの最下点をたどって曲線にする。"""
    import bmesh
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    out = bmesh.new()
    for side in ("L", "R"):
        gi = body.vertex_groups[f"orbicularis03.{side}"].index
        pts = [v.co.copy() for v in mesh.vertices if any(g.group == gi and g.weight > 0.4 for g in v.groups)]
        if len(pts) < 6:
            continue
        xs = [p.x for p in pts]
        x0, x1 = min(xs), max(xs)
        nb = 14
        line = []
        for b in range(nb):
            lo = x0 + (x1 - x0) * b / nb
            hi = x0 + (x1 - x0) * (b + 1) / nb
            cell = [p for p in pts if lo <= p.x < hi]
            if cell:
                line.append(min(cell, key=lambda p: p.z))
        # ならして肌へ投影
        for _ in range(3):
            line = [line[0]] + [(line[i - 1] + line[i] * 2 + line[i + 1]) / 4 for i in range(1, len(line) - 1)] + [line[-1]]
        proj, nrm = [], []
        for q in line:
            ok, loc, nr, _ = body.closest_point_on_mesh(q, depsgraph=depsgraph)
            proj.append(loc.copy() if ok else q)
            nrm.append(nr.copy() if ok else Vector((0, -1, 0)))
        n = len(proj)
        segs = 6
        rings = []
        for i in range(n):
            t = (proj[min(i + 1, n - 1)] - proj[max(i - 1, 0)]).normalized()
            up = nrm[i]
            sd = t.cross(up).normalized()
            up = sd.cross(t).normalized()
            taper = 1.0 - (abs(i - (n - 1) / 2) / ((n - 1) / 2)) ** 3      # 目頭・目尻で細く
            r = EYE_LINE_R * (0.35 + 0.65 * taper)
            center = proj[i] - up * (r * 0.4)                             # 半分ほど肌に埋める(彫った線)
            ring = [out.verts.new(center + sd * (r * math.cos(2 * math.pi * k / segs)) + up * (r * math.sin(2 * math.pi * k / segs)))
                    for k in range(segs)]
            rings.append(ring)
        for i in range(n - 1):
            for k in range(segs):
                try:
                    out.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][(k + 1) % segs], rings[i][(k + 1) % segs]))
                except ValueError:
                    pass
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    me = bpy.data.meshes.new("Amida_EyeLines")
    out.to_mesh(me)
    out.free()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new("Amida_EyeLines", me)
    bpy.context.collection.objects.link(obj)
    log("  eye lines verts", len(me.vertices))
    return obj


# ---------------------------------------------------------------- 陰影(くぼみを暗く)
def cavity_colors(obj, strength, floor=0.45, protect=()):
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
        k = strength
        for pc, pr in protect:
            if (v.co - pc).length < pr:
                k = strength * 0.8
        values.append(max(floor, 1.0 - max(0.0, c) * k))
    bm.free()
    attr = me.color_attributes.new("Color", "FLOAT_COLOR", "POINT")
    for i, val in enumerate(values):
        attr.data[i].color = (val, val, val, 1.0)
    me.color_attributes.active_color = attr
    return attr


# ---------------------------------------------------------------- 衣
NECK_Z = 0.60          # 衣の上端(首の付け根)。接地後の座標
ROBE_OFFSET = 0.015    # 体との隙間(布の厚みぶん)
ROBE_UPPER_Z0 = 0.30   # 上半身の衣(体の面をふくらませる)の下端
ROBE_LOWER_Z1 = 0.42   # 下半身の衣(凸包を落とす)に含める頂点の上端(前腕の下から下)
ROBE_DRAPE_LIMIT = 0.05  # 凸包から体へ落とす距離の上限(届かない所は布として張る)
ROBE_VOXEL = 0.006     # 一体化するボクセルの大きさ
ROBE_HEM_R = 0.004     # 衿・袖口の縁(ヘム)の太さ(半径)
FOLD_AMP = 0.0026      # 衣文の高さ


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


def arm_group_indices(body, prefixes=("wrist", "finger", "metacarpal")):
    return [g.index for g in body.vertex_groups if g.name.split(".")[0].startswith(prefixes)]


def weight_of(v, groups, threshold=0.3):
    return any(g.group in groups and g.weight > threshold for g in v.groups)


def robe_upper(body, mesh):
    """上半身(肩・胸・背・腕)の衣: 体の面を複製して外へ 1.5cm ふくらませ、なめらかにする。
    首から上と手は含めない。肌の細部(乳首・へそ等)は平滑化で消す。"""
    import bmesh
    hands = set(arm_group_indices(body))
    keep = set()
    for v in mesh.vertices:
        if v.co.z > ROBE_UPPER_Z0 and v.co.z < NECK_Z and not weight_of(v, hands):
            keep.add(v.index)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    doomed = [f for f in bm.faces if not all(v.index in keep for v in f.verts)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    def rng(tag):
        zs = [v.co.z for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        log(f"    upper {tag}: n={len(bm.verts)} y {min(ys):.3f}..{max(ys):.3f} z {min(zs):.3f}..{max(zs):.3f}")
    rng("after delete")
    for _ in range(12):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    rng("after smooth")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * ROBE_OFFSET
    rng("after offset")
    me = bpy.data.meshes.new("robe_upper")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("robe_upper", me)
    bpy.context.collection.objects.link(obj)
    # 厚みを付けて閉じた殻に(ボクセル再メッシュで結合するため)。モディファイアの方が尖りが出ない
    solid = obj.modifiers.new("solid", "SOLIDIFY")
    solid.thickness = ROBE_OFFSET * 1.6
    solid.offset = -1.0
    solid.use_even_offset = False
    solid.use_quality_normals = True
    apply_modifier(obj, solid)
    return obj


def robe_lower(body, mesh):
    """下半身(組んだ脚・膝・前腕の下)の衣: 前腕から下の頂点の凸包を体へ落として、
    膝の間や前腕の下に張る布(袖の垂れと膝前の衣)をつくる。"""
    import bmesh
    hands = set(arm_group_indices(body))
    pts = [v.co.copy() for v in mesh.vertices if v.co.z < ROBE_LOWER_Z1 and not weight_of(v, hands)]
    target_mesh = mesh.copy()
    target = bpy.data.objects.new("robe_target", target_mesh)
    bpy.context.collection.objects.link(target)
    tb = bmesh.new()
    tb.from_mesh(target_mesh)
    doomed = [v for v in tb.verts if v.co.z > NECK_Z or weight_of(mesh.vertices[v.index], hands)]
    bmesh.ops.delete(tb, geom=doomed, context="VERTS")
    tb.to_mesh(target_mesh)
    tb.free()

    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bm.verts.ensure_lookup_table()
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    doomed = {g for g in res["geom_unused"] + res["geom_interior"] if isinstance(g, bmesh.types.BMVert)}
    bmesh.ops.delete(bm, geom=list(doomed), context="VERTS")
    me = bpy.data.meshes.new("robe_lower")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("robe_lower", me)
    bpy.context.collection.objects.link(obj)
    sub = obj.modifiers.new("sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = 3
    apply_modifier(obj, sub)
    tri = obj.modifiers.new("tri", "TRIANGULATE")
    apply_modifier(obj, tri)
    grp = obj.vertex_groups.new(name="free")
    grp.add([v.index for v in obj.data.vertices if v.co.z > 0.012], 1.0, "REPLACE")
    m = obj.modifiers.new("proj", "SHRINKWRAP")
    m.target = target
    m.wrap_method = "PROJECT"
    m.use_negative_direction = True
    m.use_positive_direction = False
    m.project_limit = ROBE_DRAPE_LIMIT
    m.offset = ROBE_OFFSET
    m.vertex_group = "free"
    apply_modifier(obj, m)
    for factor, it in ((0.5, 12), (0.4, 6)):
        sm = obj.modifiers.new("smooth", "SMOOTH")
        sm.factor = factor
        sm.iterations = it
        sm.vertex_group = "free"
        apply_modifier(obj, sm)
        w = obj.modifiers.new("wrap", "SHRINKWRAP")
        w.target = target
        w.wrap_method = "NEAREST_SURFACEPOINT"
        w.wrap_mode = "OUTSIDE"
        w.offset = ROBE_OFFSET
        w.vertex_group = "free"
        apply_modifier(obj, w)
    for v in obj.data.vertices:
        if v.co.z < 0.012:
            v.co.z = 0.0
    bpy.data.objects.remove(target, do_unlink=True)
    return obj


def robe_folds(robe):
    """衣文(ひだ)。定朝様の浅く整った襞を、部位ごとの向きで法線方向の変位として刻む。"""
    me = robe.data
    me.calc_normals_split() if hasattr(me, "calc_normals_split") else None

    def smoothstep(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)

    def ridge(phase):
        return (0.5 + 0.5 * math.sin(phase)) ** 1.3 - 0.4      # 山はやや締まり谷は広く、平均をほぼ 0 に

    for v in me.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        n = v.normal
        front = smoothstep(0.0, -0.08, y)                        # 前面ほど 1
        vary = 0.65 + 0.35 * math.sin(x * 23.0 + z * 17.0)       # 単調にならないよう強さを揺らす
        d = 0.0
        # 膝の前: 腹の下の一点から広がる、ゆるい弧の襞(3〜4本)
        lap = smoothstep(0.34, 0.24, z) * front
        if lap > 0:
            r = math.hypot(x * 0.9, (z + 0.12))
            d += FOLD_AMP * lap * vary * ridge(2 * math.pi * r / 0.085)
        # 胸〜腹: 左肩から右腰へ流れる、まばらな斜めの襞
        torso = smoothstep(0.24, 0.32, z) * smoothstep(0.56, 0.46, z) * front
        if torso > 0:
            d += FOLD_AMP * 0.7 * torso * vary * ridge(2 * math.pi * (0.5 * x + 0.87 * z) / 0.09)
        # 腕・袖: 腕に沿って巻く襞
        arm = smoothstep(0.17, 0.25, abs(x)) * smoothstep(0.60, 0.54, z) * smoothstep(0.26, 0.34, z)
        if arm > 0:
            d += FOLD_AMP * 0.7 * arm * vary * ridge(2 * math.pi * (z + 0.25 * abs(x)) / 0.07)
        if d != 0.0:
            v.co += n * d
    me.update()


def rim_tubes(name, obj, radius, min_len=12, depsgraph=None):
    """メッシュの境界(穴・切り口)の輪ごとに、ならした曲線へ管を掃引して縁(ヘム)にする。"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts[0].index, e.verts[1].index
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [n for n in adj.get(cur, []) if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) >= min_len:
            loops.append([bm.verts[i].co.copy() for i in loop])
    bm.free()
    out = bmesh.new()
    for pts in loops:
        lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
        log(f"    loop n={len(pts)} min {lo} max {hi}")
        n = len(pts)
        for _ in range(6):
            pts = [(pts[(i - 1) % n] + pts[i] * 2 + pts[(i + 1) % n]) / 4 for i in range(n)]
        segs = 8
        rings = []
        for i in range(n):
            t = (pts[(i + 1) % n] - pts[(i - 1) % n]).normalized()
            up = Vector((0, -1, 0)) if abs(t.y) < 0.9 else Vector((0, 0, 1))
            side = t.cross(up).normalized()
            up = side.cross(t).normalized()
            rings.append([out.verts.new(pts[i] + side * (radius * math.cos(2 * math.pi * k / segs)) + up * (radius * math.sin(2 * math.pi * k / segs)))
                          for k in range(segs)])
        for i in range(n):
            r0, r1 = rings[i], rings[(i + 1) % n]
            for k in range(segs):
                try:
                    out.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
                except ValueError:
                    pass
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    me = bpy.data.meshes.new(name)
    out.to_mesh(me)
    out.free()
    for poly in me.polygons:
        poly.use_smooth = True
    hem = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(hem)
    log(f"  {name}: loops", len(loops))
    return hem


def build_robe(body, mesh):
    """通肩の衣。上半身は体の面をふくらませた殻、下半身は凸包を落とした布。
    二つをボクセルで一体化し、衣文を刻み、衿の V 字と袖口を開けて縁(ヘム)を付ける。"""
    import bmesh
    hands = set(arm_group_indices(body))
    hand_points = [v.co.copy() for v in mesh.vertices if weight_of(v, hands)]
    upper = robe_upper(body, mesh)
    lower = robe_lower(body, mesh)
    for o in (upper, lower):
        pts = [v.co for v in o.data.vertices]
        log(f"  {o.name}: verts {len(pts)} y {min(p.y for p in pts):.3f}..{max(p.y for p in pts):.3f} z {min(p.z for p in pts):.3f}..{max(p.z for p in pts):.3f}")
    bpy.ops.object.select_all(action="DESELECT")
    upper.select_set(True)
    lower.select_set(True)
    bpy.context.view_layer.objects.active = lower
    bpy.ops.object.join()
    robe = bpy.context.active_object
    robe.name = "Amida_Robe"
    rm = robe.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = ROBE_VOXEL
    rm.use_smooth_shade = True
    apply_modifier(robe, rm)
    sm = robe.modifiers.new("smooth", "SMOOTH")
    sm.factor = 0.5
    sm.iterations = 4
    apply_modifier(robe, sm)
    dec = robe.modifiers.new("dec", "DECIMATE")
    dec.ratio = max(0.05, min(1.0, 90000 / max(1, len(robe.data.polygons))))
    apply_modifier(robe, dec)
    rb = [robe.matrix_world @ v.co for v in robe.data.vertices]
    log("  robe merged verts", len(robe.data.vertices), "bbox y", round(min(p.y for p in rb), 3), round(max(p.y for p in rb), 3), "z", round(min(p.z for p in rb), 3), round(max(p.z for p in rb), 3))
    robe_folds(robe)

    # 衿の V 字と袖口(手に被さる布)を開ける
    bm = bmesh.new()
    bm.from_mesh(robe.data)

    def collar_z(x):
        return min(NECK_Z - 0.005, NECK_Z - 0.13 + abs(x) * 1.6)

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
        return dist < ROBE_OFFSET + 0.016 and v.co.z > co.z - 0.006
    doomed = [v for v in bm.verts if above(v) or over_hand(v)]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
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
    # 内側(体側)の面は要らない: 体の中に埋まる面を落として一枚の布にする
    bm.to_mesh(robe.data)
    bm.free()
    hem = rim_tubes("Amida_RobeHem", robe, ROBE_HEM_R)
    solid = robe.modifiers.new("solid", "SOLIDIFY")
    solid.thickness = 0.008
    solid.offset = -1.0
    apply_modifier(robe, solid)
    for poly in robe.data.polygons:
        poly.use_smooth = True
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
        close_eyes_with_rig(arm, human)
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

    _, hair_verts = add_head_features(body, baked, eyes)

    mat = bpy.data.materials.new("AmidaGold")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.55, 0.52, 0.48, 1) if matte else (*GOLD, 1)
    bsdf.inputs["Metallic"].default_value = 0.0 if matte else 0.72
    bsdf.inputs["Roughness"].default_value = 0.85 if matte else 0.5
    baked.materials.append(mat)
    for poly in baked.polygons:
        poly.use_smooth = True

    # 螺髪と頭皮の下地は黒漆(紺青)のマテリアル
    hair_mat = bpy.data.materials.new("AmidaHair")
    hair_mat.use_nodes = True
    hb = hair_mat.node_tree.nodes["Principled BSDF"]
    hb.inputs["Base Color"].default_value = (*HAIR_COLOR, 1)
    hb.inputs["Metallic"].default_value = 0.25
    hb.inputs["Roughness"].default_value = 0.42
    baked.materials.append(hair_mat)
    for poly in baked.polygons:
        if all(i in hair_verts for i in poly.vertices):
            poly.material_index = 1
    line_mat = bpy.data.materials.new("AmidaLine")
    line_mat.use_nodes = True
    lb = line_mat.node_tree.nodes["Principled BSDF"]
    lb.inputs["Base Color"].default_value = (0.20, 0.13, 0.05, 1)
    lb.inputs["Metallic"].default_value = 0.5
    lb.inputs["Roughness"].default_value = 0.6
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and not obj.data.materials:
            if obj.name.startswith(("Amida_Hair", "Amida_SideburnTip")):
                obj.data.materials.append(hair_mat)
            elif obj.name == "Amida_EyeLines":
                obj.data.materials.append(line_mat)
            else:
                obj.data.materials.append(mat)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name in ("Amida_Body", "Amida_Robe", "Amida_Hair"):
            cavity_colors(obj, strength=1.3 if obj.name == "Amida_Body" else 1.4,
                          protect=[(c, r * 2.0) for c, r in eyes.values()] if obj.name == "Amida_Body" else ())
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
