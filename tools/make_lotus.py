#!/usr/bin/env python3
"""蓮華(車輪大の蓮)をBlender(bpy)で生成してglb出力する。

「池中蓮華大如車輪 青色青光 黄色黄光 赤色赤光 白色白光」

花びらは1枚ずつパラメトリック曲面で成形する:
  - 長さ方向: 根元から立ち上がり、先端へ向けて内へ反る(開き角は花弁輪ごとに変える)
  - 幅方向: お椀状のふくらみ(カップ)、外面に走る中肋の畝、縁のごく浅い揺らぎ
  - 先端は倒卵形に丸く納め、わずかに尖る(尖りすぎは「クワガタ」になる)
  - 1枚ごとに大きさ・傾き・ねじれの揺らぎ。同じ輪の隣どうしは開き角を互い違いにして重なりを自然に(覆瓦状)
構成: 外輪9枚 + 第2輪9枚 + 第3輪7枚 + 内輪5枚(花托を抱く)+ 花托(逆円錐・実19粒)+ 雄しべ120本
マテリアル: petal は色(petal.png)+法線(petal_normal.png)+発光マップ(petal_emit.png)。
  色は実行時に乗算(青・黄・赤・白の4色はギャラリー/空間側で指定)。発光も同じ色で、芯から先端へ薄れる

使い方: python3 tools/make_textures.py && python3 tools/make_lotus.py
出力: public/assets/lotus.glb(直径約1.3m)、public/assets/lotus_bud.glb(蕾・茎付き)
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402

rand = random.Random(17)

PETAL_U = 28  # 長さ方向の分割
PETAL_V = 16  # 幅方向の分割


def petal_material():
    """花びら: 色・法線・発光の三枚を同じUVで貼る。裏面も描く(両面)。"""
    mat = bpy.data.materials.new("petal")
    mat.use_nodes = True
    mat.use_backface_culling = False  # glTF の doubleSided になる(花弁は厚みを持たせない)
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.5

    color = tree.nodes.new("ShaderNodeTexImage")
    color.image = bpy.data.images.load(os.path.join(TEX, "petal.png"))
    tree.links.new(color.outputs["Color"], bsdf.inputs["Base Color"])

    nimg = tree.nodes.new("ShaderNodeTexImage")
    nimg.image = bpy.data.images.load(os.path.join(TEX, "petal_normal.png"))
    nimg.image.colorspace_settings.name = "Non-Color"
    nmap = tree.nodes.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = 0.6
    tree.links.new(nimg.outputs["Color"], nmap.inputs["Color"])
    tree.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    emit = tree.nodes.new("ShaderNodeTexImage")
    emit.image = bpy.data.images.load(os.path.join(TEX, "petal_emit.png"))
    tree.links.new(emit.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0  # 実際の強さと色は three.js 側で乗算
    return mat


def build_petal(length, width, open_angle, curl, cup, roll, keel=0.035, ruffle=0.3, phase=0.0):
    """花びら1枚のメッシュ(頂点とUV)を作る。原点=根元、+Zへ伸びる。
    先端は倒卵形(丸くて、ごくわずかに尖る)。"""
    verts = []
    uvs_grid = []
    for i in range(PETAL_U + 1):
        t = i / PETAL_U  # 0=根元 1=先端
        # 幅: 根元は細く、6割の位置で最大、先端は丸く納まる
        if t > 0.58:
            u = (t - 0.58) / 0.42
            taper = math.sqrt(max(0.0, 1 - u ** 2.6))
        else:
            taper = 1.0
        half_width = width * 0.5 * math.sin(math.pi * min(t / 0.58, 1) * 0.5) ** 0.75 * taper
        # 背骨: 先端へ向けて内側(+Y=花の中心側)へ反り上がる
        spine_y = curl * (t ** 2.2) * length
        spine_z = t * length
        twist = roll * t  # 先端ほどねじれる
        for j in range(PETAL_V + 1):
            s = j / PETAL_V * 2 - 1  # -1..1
            x = s * half_width
            # カップ: 縁が内側へ立ち上がる
            y = -cup * (1 - s * s) * half_width * 1.1
            # 中肋: 外面(-Y)へ浅い畝。根元と先端で消える
            y -= keel * width * math.exp(-(s / 0.22) ** 2) * math.sin(math.pi * t) ** 0.7
            # 縁の揺らぎ: 縁だけがごく浅く波打つ(先端側ほど)
            y += ruffle * half_width * 0.12 * (s * s) ** 1.5 * math.sin(t * 6.5 * math.pi + phase + s) * t ** 1.5
            # ねじれ
            xr = x * math.cos(twist) - y * math.sin(twist)
            yr = x * math.sin(twist) + y * math.cos(twist)
            verts.append(Vector((xr, spine_y + yr, spine_z)))
            uvs_grid.append((j / PETAL_V, t))

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
        for loop_index in poly.loop_indices:
            vi = mesh.loops[loop_index].vertex_index
            layer.data[loop_index].uv = uvs_grid[vi]

    obj = bpy.data.objects.new("petal", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- 小さな形状ユーティリティ

def lathe(profile, segments, name, smooth=True):
    """(r, z) の輪郭を Z 軸まわりに回した回転体。両端は r=0 で閉じておく。"""
    verts = []
    faces = []
    for r, z in profile:
        for k in range(segments):
            a = k / segments * math.tau
            verts.append(Vector((math.cos(a) * r, math.sin(a) * r, z)))
    for i in range(len(profile) - 1):
        for k in range(segments):
            a = i * segments + k
            b = i * segments + (k + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def tube_geo(points, radius, sides, verts, faces):
    """折れ線に沿った管を verts/faces へ追加する(1メッシュに多数を詰める用)。"""
    base = len(verts)
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
        taper = radius * (1.0 - 0.35 * i / (n - 1))  # 先へ細る
        for k in range(sides):
            a = k / sides * math.tau
            verts.append(p + u * (math.cos(a) * taper) + v * (math.sin(a) * taper))
    for i in range(n - 1):
        for k in range(sides):
            a = base + i * sides + k
            b = base + i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))


def ellipsoid_geo(center, axis, r, length, verts, faces, segments=8, rings=6):
    """軸 axis 方向に長さ length、半径 r の楕円体を追加する(葯・実用)。"""
    base = len(verts)
    axis = axis.normalized()
    helper = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(helper).normalized()
    v = axis.cross(u)
    for i in range(rings + 1):
        phi = i / rings * math.pi
        z = math.cos(phi) * length * 0.5
        rr = math.sin(phi) * r
        for k in range(segments):
            a = k / segments * math.tau
            verts.append(center + axis * z + u * (math.cos(a) * rr) + v * (math.sin(a) * rr))
    for i in range(rings):
        for k in range(segments):
            a = base + i * segments + k
            b = base + i * segments + (k + 1) % segments
            faces.append((a, b, b + segments, a + segments))


def mesh_object(name, verts, faces, material, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


# 満開: (枚数, 開き角, 長さ, 幅, 反り, 基準半径)
WHORLS_BLOOM = [
    (9, 74, 0.60, 0.42, 0.50, 0.115),  # 外輪: 大きく開いて先端が反り上がる
    (9, 54, 0.58, 0.40, 0.46, 0.095),  # 第2輪
    (7, 44, 0.52, 0.34, 0.38, 0.075),  # 第3輪: 立ち気味に中心を包む
    (5, 30, 0.42, 0.26, 0.30, 0.055),  # 内輪: 花托を抱きつつ、上からは花托と雄しべが見える
]

# 蕾: 花びらが中心を包み、先端がすぼまる涙滴型
WHORLS_BUD = [
    (9, 14, 0.52, 0.44, 0.30, 0.055),  # 外輪: わずかに開きかけ
    (8, 6, 0.56, 0.40, 0.22, 0.04),    # 中輪: 立って包む
    (6, -2, 0.50, 0.34, 0.16, 0.028),  # 内輪: 内へ傾いて先端を閉じる
]


def build_lotus(path, whorls, with_center=True, stem_height=0.0, cup=0.5):
    reset_scene()
    petal_mat = petal_material()
    pod_mat = plain_material("pod", (0.78, 0.74, 0.30), 0.0, 0.55)
    socket_mat = plain_material("socket", (0.42, 0.40, 0.14), 0.0, 0.6)
    seed_mat = plain_material("seed", (0.62, 0.52, 0.20), 0.1, 0.35)
    filament_mat = plain_material("filament", (1.0, 0.93, 0.62), 0.2, 0.4, (1.0, 0.85, 0.45), 0.35)
    anther_mat = plain_material("anther", (1.0, 0.80, 0.36), 0.4, 0.35, (1.0, 0.78, 0.35), 0.6)  # 強いと白飛びして金に見えない

    base_z = stem_height
    # 茎: 水面から立ち上がり、わずかにしなる
    if stem_height > 0:
        lean = rand.uniform(0.06, 0.12)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.022, depth=stem_height * 1.05,
                                            location=(lean * stem_height * 0.4, 0, stem_height * 0.5))
        stem = bpy.context.active_object
        stem.rotation_euler = (0, lean, 0)
        bpy.ops.object.shade_smooth()
        stem.data.materials.append(plain_material("stem", (0.5, 0.52, 0.24), 0.0, 0.6))

    for w, (count, open_angle, length, width, curl, radius) in enumerate(whorls):
        for k in range(count):
            theta = (k / count) * math.tau + w * (math.pi / count)  # 輪ごとに半位相ずらす
            petal = build_petal(
                length * rand.uniform(0.95, 1.05),
                width * rand.uniform(0.95, 1.05),
                open_angle,
                curl * rand.uniform(0.9, 1.1),
                cup=cup,
                roll=rand.uniform(-0.10, 0.10),
                phase=rand.uniform(0, math.tau),
            )
            petal.data.materials.append(petal_mat)
            # 隣どうしを互い違いに(偶数番をやや開き、奇数番をやや立てる)→ 縁が覆瓦状に重なる
            stagger = 3.5 if k % 2 == 0 else -3.5
            lift = 0.0 if k % 2 == 0 else 0.006
            # 中心から放射状に配置。行列は明示的に合成する
            # (matrix_worldの遅延評価に頼ると開き角が失われる)
            petal.matrix_world = (
                Matrix.Rotation(theta, 4, "Z")
                @ Matrix.Translation((0, -radius, base_z + 0.02 + w * 0.015 + lift))
                @ Matrix.Rotation(math.radians(open_angle + stagger + rand.uniform(-2, 2)), 4, "X")
                @ Matrix.Rotation(rand.uniform(-0.04, 0.04), 4, "Z")
            )

    if with_center:
        # 花托(かたく): 上へ広がる逆円錐。上面はわずかに盛り上がり、縁は丸い
        z0 = base_z + 0.05
        top = z0 + 0.135
        profile = [(0.0, z0), (0.045, z0), (0.062, z0 + 0.03), (0.088, z0 + 0.075), (0.115, z0 + 0.11),
                   (0.128, z0 + 0.125), (0.130, top - 0.006), (0.122, top), (0.10, top + 0.004),
                   (0.05, top + 0.007), (0.0, top + 0.008)]
        pod = lathe(profile, 40, "pod")
        pod.data.materials.append(pod_mat)

        # 実: 黄金角で敷き、上面の穴に半ば埋まる。穴の縁は暗い環
        seed_v, seed_f = [], []
        sock_v, sock_f = [], []
        for k in range(19):
            golden = k * math.tau * 0.381966
            r = 0.098 * math.sqrt((k + 0.5) / 19)
            c = Vector((math.cos(golden) * r, math.sin(golden) * r, top + 0.004 - 0.005))
            ellipsoid_geo(c, Vector((0, 0, 1)), 0.0135, 0.030, seed_v, seed_f, segments=12, rings=8)
            # 縁の環: 平たいトーラス
            ring_r, ring_w = 0.0165, 0.0035
            base = len(sock_v)
            seg, sub = 16, 6
            for i in range(seg):
                a = i / seg * math.tau
                for j in range(sub):
                    b = j / sub * math.tau
                    rr = ring_r + math.cos(b) * ring_w
                    sock_v.append(Vector((c.x + math.cos(a) * rr, c.y + math.sin(a) * rr,
                                          top + 0.004 + math.sin(b) * ring_w * 0.5)))
            for i in range(seg):
                for j in range(sub):
                    a = base + i * sub + j
                    b = base + i * sub + (j + 1) % sub
                    c2 = base + ((i + 1) % seg) * sub + j
                    d = base + ((i + 1) % seg) * sub + (j + 1) % sub
                    sock_f.append((a, b, d, c2))
        mesh_object("seeds", seed_v, seed_f, seed_mat)
        mesh_object("sockets", sock_v, sock_f, socket_mat)

        # 雄しべ: 花托の周りに三重の輪。根元から外へ膨らみつつ立ち上がる糸+先端の葯(楕円体)
        fil_v, fil_f = [], []
        ant_v, ant_f = [], []
        rings = [(0.118, 40, 0.0), (0.132, 40, 0.5), (0.146, 40, 1.0)]
        for r0, count, ph in rings:
            for k in range(count):
                theta = (k + ph) / count * math.tau + rand.uniform(-0.03, 0.03)
                lean = rand.uniform(0.035, 0.075)
                height = rand.uniform(0.095, 0.145)
                start = Vector((math.cos(theta) * r0, math.sin(theta) * r0, z0 + 0.02 + rand.uniform(0, 0.02)))
                pts = []
                for i in range(6):
                    t = i / 5
                    bulge = math.sin(t * math.pi) * lean * 0.7 + lean * t
                    pts.append(Vector((math.cos(theta) * (r0 + bulge) + rand.uniform(-0.002, 0.002),
                                       math.sin(theta) * (r0 + bulge) + rand.uniform(-0.002, 0.002),
                                       start.z + height * (t ** 0.85))))
                tube_geo(pts, 0.0026, 5, fil_v, fil_f)
                axis = (pts[-1] - pts[-2]).normalized()
                ellipsoid_geo(pts[-1] + axis * 0.008, axis, 0.0055, 0.024, ant_v, ant_f, segments=8, rings=6)
        mesh_object("filaments", fil_v, fil_f, filament_mat)
        mesh_object("anthers", ant_v, ant_f, anther_mat)

    export(path)


if __name__ == "__main__":
    build_lotus(os.path.join(OUT_DIR, "lotus.glb"), WHORLS_BLOOM)
    build_lotus(os.path.join(OUT_DIR, "lotus_bud.glb"), WHORLS_BUD,
                with_center=False, stem_height=0.5, cup=0.62)
    print("done", file=sys.stderr)
