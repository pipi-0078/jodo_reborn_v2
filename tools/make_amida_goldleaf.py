#!/usr/bin/env python3
"""スキャン原型の「表面の色だけ」を金に替えた阿弥陀如来坐像(台座なし)。

形・法線・分割は原型のまま(減面・溶接・平滑化・法線増幅・箔の皺、いずれもしない)。
9/3 の教訓: 法線を強めたり微細な皺を混ぜたりすると「チョコレートをかけたよう」に溶けて見え、
螺髪が崩れる。施主の望みは色の置き換えだけ。

手順:
  1. 原型を読み込み、台座(z<0.37)の頂点を落とす
  2. 各材質: ベースカラーの写真テクスチャを外し、金一色に。法線マップは原型の強さ(0.3)のまま
  3. 金属感は蓮華座と同じ値: metallic 0.75 / roughness 0.48 / 弱い発光

使い方: python3 tools/make_amida_goldleaf.py
出力: public/assets/amida_polish.glb(ギャラリー「阿弥陀如来坐像(磨き・台座なし)」)
"""
import os
import sys

import bpy
import bmesh
import mathutils

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "/root/.claude/uploads/99555b29-dbc6-57ef-840e-5178dab97e8a/871873a0-wooden_amitabha_sitting_statue.glb"
OUT = os.path.join(ROOT, "public/assets/amida_polish.glb")

GOLD = (0.83, 0.59, 0.18)          # 蓮華座の金と同じ系統(リニア)
METALLIC = 0.75                    # 鏡面すぎると空の青緑が顔に映る(LESSONS 2-3)
ROUGHNESS = 0.48
EMISSION = (0.45, 0.30, 0.08)
EMISSION_STRENGTH = 0.15


def log(*a):
    print(*a, file=sys.stderr)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)

    # ---- 結合と台座切除だけ(溶接・減面はしない) ----
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.join()
    obj = bpy.context.active_object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    cut = [v for v in bm.verts if v.co.z < 0.37]
    bmesh.ops.delete(bm, geom=cut, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    log("verts", len(obj.data.vertices), "polys", len(obj.data.polygons))

    # ---- 材質: 写真テクスチャを外して金一色。法線マップは原型のまま ----
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        for lk in list(tree.links):
            if lk.to_node == bsdf and lk.to_socket.name in ("Base Color", "Metallic", "Roughness", "Alpha"):
                tree.links.remove(lk)
        for n in [n for n in tree.nodes if n.type == "TEX_IMAGE"
                  and not any(lk.from_node == n for lk in tree.links)]:
            tree.nodes.remove(n)
        bsdf.inputs["Base Color"].default_value = (*GOLD, 1.0)
        bsdf.inputs["Metallic"].default_value = METALLIC
        bsdf.inputs["Roughness"].default_value = ROUGHNESS
        bsdf.inputs["Emission Color"].default_value = (*EMISSION, 1.0)
        bsdf.inputs["Emission Strength"].default_value = EMISSION_STRENGTH
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.5
        strength = [n.inputs["Strength"].default_value for n in tree.nodes if n.type == "NORMAL_MAP"]
        log("gilded:", mat.name, "normal strength", [round(s, 2) for s in strength])

    # ---- 底を0へ、中心へ ----
    lo = mathutils.Vector((1e9,) * 3)
    hi = mathutils.Vector((-1e9,) * 3)
    for v in obj.data.vertices:
        lo = mathutils.Vector(map(min, lo, v.co))
        hi = mathutils.Vector(map(max, hi, v.co))
    obj.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
    log("statue size:", [round(hi[i] - lo[i], 2) for i in range(3)])

    obj["credit"] = ("Base: Amitabha statue scan by Atsushi Nakabayashi (Sketchfab, "
                     "CC-BY-SA-4.0). Modified: pedestal removed, photo color replaced by a uniform gold material.")
    bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    log(f"exported {os.path.relpath(OUT, ROOT)} tris={tris} size={os.path.getsize(OUT) / 1e6:.1f}MB")


if __name__ == "__main__":
    main()
