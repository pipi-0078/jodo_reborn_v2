#!/usr/bin/env python3
"""Hitem3D 生成の阿弥陀如来坐像(amida_hitem3d.glb、約200万tris・50MB)の軽い版を作る。

減面(Decimate: Collapse)だけを行い、テクスチャ・UV・形はそのまま。法線は元データに無いので滑らかに再計算。
教訓(LESSONS 2-2): スキャン像は減面で彫りが消えた。今回は元が 200 万面あるので、1/2 と 1/4 を作って
ギャラリーで原型と並べ、施主に選んでもらう。
出力: amida_hitem3d_half.glb(1/2) / amida_hitem3d_quarter.glb(1/4) / amida_hitem3d_eighth.glb(1/8)
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, reset_scene  # noqa: E402


def build(ratio, name):
    reset_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(OUT_DIR, "amida_hitem3d.glb"))
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.ops.object.shade_smooth()
        print(f"  {name}: {len(obj.data.polygons)} faces", file=sys.stderr)
    export(os.path.join(OUT_DIR, name))


if __name__ == "__main__":
    build(0.5, "amida_hitem3d_half.glb")
    build(0.25, "amida_hitem3d_quarter.glb")
    build(0.125, "amida_hitem3d_eighth.glb")
    print("done", file=sys.stderr)
