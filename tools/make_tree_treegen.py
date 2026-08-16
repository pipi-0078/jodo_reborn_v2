#!/usr/bin/env python3
"""tree-gen(Weber & Penn 1995)による宝樹の生成。

friggog/tree-gen (GPL-3.0, tools/vendor/ch_trees に同梱) をヘッドレスBlenderで駆動し、
Web向けに軽量化した設定で書き出す。

軽量化の要点(ベストプラクティス):
  - levels を 4→3 に(最末端の小枝階層を落とす。見た目への寄与が小さく最も重い)
  - branches / curve_res を絞る(枝の本数とカーブ分割数)
  - 葉は「少なく大きく」(leaf_blos_num を下げ leaf_scale を上げる)— 様式化にも合う
  - カーブのベベル解像度を変換前に落とす

使い方: python3 tools/make_tree_treegen.py
出力: public/assets/tree_meiboku.glb / tree_yanagi.glb
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools/vendor"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from make_trees import (  # noqa: E402  (共通基盤を再利用)
    OUT_DIR, bark_material, export, plain_material, reset_scene, triangle_count,
)

from ch_trees.parametric import gen  # noqa: E402
from ch_trees.parametric.tree_params import black_tupelo, weeping_willow  # noqa: E402

PALE_LEAF = (0.92, 0.9, 0.85)


def build(species, overrides, out_path, target_height, leaf_material_params, seed=7):
    reset_scene()
    params = dict(species.params)
    params.update(overrides)
    gen.construct(params, seed)

    trunk_mat = bark_material()
    twig_mat = plain_material("twig", (0.42, 0.3, 0.11), 0.7, 0.55)
    leaf_mat = plain_material("foliage", *leaf_material_params)

    # カーブは変換前に解像度を絞る(ここが最大の削減点)
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CURVE":
            obj.data.resolution_u = 2
            obj.data.bevel_resolution = 2 if obj.name in ("Trunk", "Branches1") else 0

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.convert(target="MESH")

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name.startswith(("Trunk", "Branches1")):
            obj.data.materials.append(trunk_mat)
        elif obj.name.startswith("Branches"):
            obj.data.materials.append(twig_mat)
        elif obj.name.startswith("Leaves"):
            obj.data.materials.append(leaf_mat)
        for poly in obj.data.polygons:
            poly.use_smooth = True

    # 目標樹高へ揃える
    zmax = 0.0
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for corner in obj.bound_box:
                zmax = max(zmax, (obj.matrix_world @ obj.data.vertices[0].co.__class__(corner)).z)
    if zmax > 0:
        factor = target_height / zmax
        for obj in bpy.context.scene.objects:
            if obj.parent is None:
                obj.scale = (factor, factor, factor)

    export(out_path)


if __name__ == "__main__":
    # 名木(ブラックテューペロ): 端正な広葉の大樹
    build(
        black_tupelo,
        {
            "g_scale": 9, "g_scale_v": 0,
            "levels": 3,
            "branches": [1, 55, 14, 0],
            "curve_res": [8, 5, 3, 1],
            "leaf_blos_num": 8,
            "leaf_scale": 0.5,
        },
        os.path.join(OUT_DIR, "tree_meiboku.glb"),
        target_height=8.5,
        leaf_material_params=(PALE_LEAF, 0.55, 0.45),
    )
    # 枝垂れ柳: 垂宝樹の本家
    build(
        weeping_willow,
        {
            "g_scale": 8, "g_scale_v": 0,
            "levels": 3,
            "branches": [1, 33, 10, 0],
            "curve_res": [8, 6, 4, 1],
            "leaf_blos_num": 12,
            "leaf_scale": 0.32,
        },
        os.path.join(OUT_DIR, "tree_yanagi.glb"),
        target_height=7.5,
        leaf_material_params=((0.95, 0.82, 0.45), 0.75, 0.35),
    )
    print("done", file=sys.stderr)
