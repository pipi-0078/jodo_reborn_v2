#!/usr/bin/env python3
"""蓮華(車輪大の蓮)をBlender(bpy)で生成してglb出力する。

「池中蓮華大如車輪 青色青光 黄色黄光 赤色赤光 白色白光」

花びらは1枚ずつパラメトリック曲面で成形する:
  - 長さ方向: 根元から立ち上がり、先端へ向けて内へ反る(開き角は花弁輪ごとに変える)
  - 幅方向: お椀状のふくらみ(カップ)と、先端の尖り
  - 1枚ごとに大きさ・傾き・ねじれの揺らぎ
構成: 外輪8枚(大きく開く)+中輪8枚+内輪6枚(立つ)+花托+雄しべ44本
色は実行時に乗算(青・黄・赤・白の4色はギャラリー側で指定)。

使い方: python3 tools/make_textures.py && python3 tools/make_lotus.py
出力: public/assets/lotus.glb(直径約1.3m)
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
TEX = os.path.join(ROOT, "tools/textures")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402

rand = random.Random(17)

PETAL_U = 14  # 長さ方向の分割
PETAL_V = 8   # 幅方向の分割


def petal_material():
    mat = bpy.data.materials.new("petal")
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.1
    bsdf.inputs["Roughness"].default_value = 0.32
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, "petal.png"))
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def build_petal(length, width, open_angle, curl, cup, roll, round_tip=False):
    """花びら1枚のメッシュ(頂点とUV)を作る。原点=根元、+Zへ伸びる。
    round_tip=True で先端が楕円状に丸くなる(蓮華座の厚弁用)。"""
    verts = []
    uvs_grid = []
    for i in range(PETAL_U + 1):
        t = i / PETAL_U  # 0=根元 1=先端
        # 幅: 根元は細く、5割強の位置で最大、先端はゆるやかに尖る(または丸く納まる)
        if round_tip:
            u = max(0.0, (t - 0.50) / 0.50)
            taper = math.sqrt(max(0.0, 1 - u ** 2.4))
        else:
            taper = 1 - max(0, (t - 0.55) / 0.45) ** 1.35
        half_width = width * 0.5 * math.sin(math.pi * min(t / 0.55, 1) * 0.5) ** 0.8 * taper
        # 背骨: 先端へ向けて内側(+Y=花の中心側)へ反り上がる
        spine_y = curl * (t ** 2.2) * length
        spine_z = t * length
        for j in range(PETAL_V + 1):
            s = j / PETAL_V * 2 - 1  # -1..1
            x = s * half_width
            # カップ: 縁が内側へ立ち上がる
            y = spine_y - cup * (1 - s * s) * half_width * 1.1
            verts.append(Vector((x, y, spine_z)))
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

    # 厚みと滑らかさ
    solidify = obj.modifiers.new("solidify", "SOLIDIFY")
    solidify.thickness = 0.012
    solidify.offset = 0
    subsurf = obj.modifiers.new("subsurf", "SUBSURF")
    subsurf.levels = 1
    subsurf.render_levels = 1
    return obj


# 満開: (枚数, 開き角, 長さ, 幅, 反り, 基準半径)
WHORLS_BLOOM = [
    (8, 68, 0.62, 0.42, 0.55, 0.10),  # 外輪: 開いて先端が反り上がる
    (8, 48, 0.58, 0.38, 0.48, 0.08),  # 中輪
    (6, 28, 0.50, 0.32, 0.36, 0.06),  # 内輪: 立って中心を包む
]

# 蕾: 花びらが中心を包み、先端がすぼまる涙滴型
WHORLS_BUD = [
    (8, 14, 0.52, 0.46, 0.30, 0.055),  # 外輪: わずかに開きかけ
    (8, 6, 0.56, 0.42, 0.22, 0.04),    # 中輪: 立って包む
    (6, -2, 0.50, 0.36, 0.16, 0.028),  # 内輪: 内へ傾いて先端を閉じる
]


def build_lotus(path, whorls, with_center=True, stem_height=0.0, cup=0.5):
    reset_scene()
    petal_mat = petal_material()
    pod_mat = plain_material("pod", (0.85, 0.78, 0.35), 0.3, 0.5)
    seed_mat = plain_material("seed", (0.55, 0.45, 0.15), 0.4, 0.4)
    stamen_mat = plain_material("stamen", (1.0, 0.85, 0.45), 0.5, 0.35, (1.0, 0.8, 0.4), 1.2)

    base_z = stem_height
    # 茎: 水面から立ち上がり、わずかにしなる
    if stem_height > 0:
        lean = rand.uniform(0.06, 0.12)
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.022, depth=stem_height * 1.05,
                                            location=(lean * stem_height * 0.4, 0, stem_height * 0.5))
        stem = bpy.context.active_object
        stem.rotation_euler = (0, lean, 0)
        bpy.ops.object.shade_smooth()
        stem.data.materials.append(plain_material("stem", (0.5, 0.52, 0.24), 0.25, 0.55))

    for w, (count, open_angle, length, width, curl, radius) in enumerate(whorls):
        for k in range(count):
            theta = (k / count) * math.tau + w * (math.pi / count)  # 輪ごとに半位相ずらす
            petal = build_petal(
                length * rand.uniform(0.94, 1.06),
                width * rand.uniform(0.94, 1.06),
                open_angle,
                curl * rand.uniform(0.9, 1.1),
                cup=cup,
                roll=rand.uniform(-0.05, 0.05),
            )
            petal.data.materials.append(petal_mat)
            # 中心から放射状に配置。行列は明示的に合成する
            # (matrix_worldの遅延評価に頼ると開き角が失われる)
            petal.matrix_world = (
                Matrix.Rotation(theta, 4, "Z")
                @ Matrix.Translation((0, -radius, base_z + 0.02 + w * 0.015))
                @ Matrix.Rotation(math.radians(open_angle + rand.uniform(-3, 3)), 4, "X")
                @ Matrix.Rotation(rand.uniform(-0.05, 0.05), 4, "Z")
            )

    if with_center:
        # 花托(かたく): 蓮の実の台
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.11, depth=0.09,
                                            location=(0, 0, base_z + 0.16))
        pod = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        pod.data.materials.append(pod_mat)
        # 実
        for k in range(13):
            golden = k * math.tau * 0.381966
            r = 0.075 * math.sqrt(k / 13)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.013,
                                                 location=(math.cos(golden) * r, math.sin(golden) * r,
                                                           base_z + 0.21))
            seed = bpy.context.active_object
            bpy.ops.object.shade_smooth()
            seed.data.materials.append(seed_mat)

        # 雄しべ: 花托の周りに細い糸+先端の葯
        for k in range(44):
            theta = (k / 44) * math.tau + rand.uniform(-0.04, 0.04)
            r0 = 0.115
            lean = rand.uniform(0.12, 0.3)
            top = Vector((math.cos(theta) * (r0 + lean * 0.35), math.sin(theta) * (r0 + lean * 0.35),
                          base_z + 0.2 + rand.uniform(0, 0.03)))
            base = Vector((math.cos(theta) * r0, math.sin(theta) * r0, base_z + 0.12))
            mid = (base + top) / 2
            direction = top - base
            bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.0035, depth=direction.length, location=mid)
            stamen = bpy.context.active_object
            stamen.rotation_mode = "QUATERNION"
            stamen.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
            stamen.data.materials.append(stamen_mat)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.009, location=top)
            anther = bpy.context.active_object
            bpy.ops.object.shade_smooth()
            anther.data.materials.append(stamen_mat)

    export(path)


if __name__ == "__main__":
    build_lotus(os.path.join(OUT_DIR, "lotus.glb"), WHORLS_BLOOM)
    build_lotus(os.path.join(OUT_DIR, "lotus_bud.glb"), WHORLS_BUD,
                with_center=False, stem_height=0.5, cup=0.62)
    print("done", file=sys.stderr)
