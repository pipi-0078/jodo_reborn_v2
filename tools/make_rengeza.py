#!/usr/bin/env python3
"""黄金の蓮華座(阿弥陀如来坐像の台座)をBlender(bpy)で生成してglb出力する。

伝統的な仏像台座の積層(下から):
  框座(八角二段)→ 反花(下向きの蓮弁)→ 敷茄子(瓔珞を垂らした珠)
  → 受座 → 蓮弁三重(上向きに開く)→ 蓮肉(像を受ける台)
花びらは make_lotus.py のパラメトリック曲面を流用し、全身を金で包む。

使い方: python3 tools/make_textures.py && python3 tools/make_rengeza.py
出力: public/assets/rengeza.glb
"""
import math
import os
import sys

import bpy
from mathutils import Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, reset_scene  # noqa: E402
from make_lotus import build_petal, rand  # noqa: E402
from make_pavilion import cyl, sphere, torus, textured, mat_of  # noqa: E402


def glow(mat, color, strength):
    """金に内側からの照りを足す(空の映り込みで色が濁らないように)。"""
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength


def gold_petal_whorl(mat, count, open_angle, length, width, curl, radius, base_z,
                     phase=0.0, thickness=0.022, jitter=True):
    """金の蓮弁を一輪(ひとまわり)並べる。open_angle>90で反花(下向き)になる。
    jitter=False で全弁同寸・等角(重なりを均等な鱗重ねにする)。"""
    for k in range(count):
        theta = (k / count) * math.tau + phase
        jw = rand.uniform(0.96, 1.04) if jitter else 1.0
        jl = rand.uniform(0.96, 1.04) if jitter else 1.0
        jc = rand.uniform(0.92, 1.08) if jitter else 1.0
        ja = rand.uniform(-2, 2) if jitter else 0.0
        petal = build_petal(
            length * jl, width * jw, open_angle, curl * jc,
            cup=0.42, roll=0.0, round_tip=True,
        )
        petal.data.materials.append(mat)
        # 台座の弁は厚めに、分割は増やさない(枚数が多く重くなりすぎないように)
        petal.modifiers["solidify"].thickness = thickness
        petal.modifiers["subsurf"].levels = 0
        petal.modifiers["subsurf"].render_levels = 0
        petal.matrix_world = (
            Matrix.Rotation(theta, 4, "Z")
            @ Matrix.Translation((0, -radius, base_z))
            @ Matrix.Rotation(math.radians(open_angle + ja), 4, "X")
        )


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
    petal_gold = textured("petal_gold", "petal_vein.png", normal="petal_vein_normal.png",
                          metallic=0.9, roughness=0.34, tile=(1, 1))
    glow(petal_gold, (0.95, 0.62, 0.20), 0.10)
    glow(kinpaku, (0.9, 0.62, 0.22), 0.06)
    glow(tsuchime, (0.9, 0.62, 0.22), 0.05)
    glow(migaki, (0.95, 0.68, 0.26), 0.07)

    # ---- 框座: 八角二段+金の框 ----
    cyl((0, 0, 0.07), 1.52, 0.14, tsuchime, vertices=8)
    cyl((0, 0, 0.20), 1.36, 0.12, kinpaku, vertices=8)
    for (r, z) in ((1.52, 0.14), (1.36, 0.26)):
        pts = [(r * math.cos(k * math.tau / 8 + math.pi / 8),
                r * math.sin(k * math.tau / 8 + math.pi / 8), z) for k in range(9)]
        from make_pavilion import _poly_tube
        _poly_tube(pts, 0.035, gold)

    # ---- 反花: 下向きに開いて框座へ垂れる蓮弁 ----
    gold_petal_whorl(petal_gold, 12, 118, 0.55, 0.40, 0.28, 0.66, 0.62, jitter=False)
    gold_petal_whorl(petal_gold, 12, 120, 0.44, 0.36, 0.30, 0.52, 0.76,
                     phase=math.pi / 12, jitter=False)

    # ---- 敷茄子: 潰した珠。赤道に金帯、瓔珞の垂れ飾り ----
    sphere((0, 0, 0.72), 0.58, migaki, scale_z=0.52)
    torus((0, 0, 0.72), 0.585, 0.035, gold)
    for k in range(16):
        th = k * math.tau / 16
        x, y = 0.56 * math.cos(th), 0.56 * math.sin(th)
        cyl((x, y, 0.86), 0.006, 0.10, gold, vertices=5)
        sphere((x, y, 0.80), 0.026, gold, segments=7, rings=5)
        sphere((x, y, 0.75), 0.026, gold, segments=7, rings=5)
        sphere((x, y, 0.69), 0.042, shuju, scale_z=1.3, segments=8, rings=6)

    # ---- 受座: 蓮弁を受ける皿 ----
    cyl((0, 0, 0.94), 0.66, 0.10, tsuchime, vertices=24)
    torus((0, 0, 0.99), 0.66, 0.028, gold)

    # ---- 蓮弁三重: 上向きに開く椀 ----
    gold_petal_whorl(petal_gold, 18, 74, 0.82, 0.56, 0.52, 0.72, 1.00)
    gold_petal_whorl(petal_gold, 16, 56, 0.78, 0.54, 0.46, 0.60, 1.02,
                     phase=math.pi / 16)
    gold_petal_whorl(petal_gold, 14, 36, 0.72, 0.50, 0.36, 0.48, 1.04,
                     phase=math.pi / 14)

    # ---- 蓮肉: 像を受ける台。縁に金の環と連珠 ----
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.86, depth=0.34,
                                        location=(0, 0, 1.28))
    dais = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    dais.data.materials.append(tsuchime)
    torus((0, 0, 1.45), 0.86, 0.03, gold)
    for k in range(36):
        th = k * math.tau / 36
        sphere((0.86 * math.cos(th), 0.86 * math.sin(th), 1.40), 0.028, gold,
               segments=7, rings=5)

    export(path)


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "rengeza.glb"))
    print("done", file=sys.stderr)
