#!/usr/bin/env python3
"""フル解像度スキャンから「磨き・台座なし」の阿弥陀如来坐像を作る。

- 原型: wooden_amitabha_sitting_statue.glb (CC-BY-SA-4.0, 37万tris, 1024pxテクスチャ)
- 台座(z<0.37)を切除し、部品を結合・溶接
- 写真テクスチャの明暗を金の濃淡へ変換して張り戻す(目・口・衣文が陰影で残る)
- 法線マップは原型のまま(彫りの微細な凹凸を保持)
- 約12万trisへ減面、エッジ保存シェーディング

使い方: python3 tools/make_amida_polish.py
出力: public/assets/amida_polish.glb
"""
import io
import math
import os
import sys

import bpy
import bmesh
import mathutils
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "/root/.claude/uploads/99555b29-dbc6-57ef-840e-5178dab97e8a/871873a0-wooden_amitabha_sitting_statue.glb"
OUT = os.path.join(ROOT, "public/assets/amida_polish.glb")
TMP = "/tmp/claude-0/-home-user-jodo-reborn-v2/99555b29-dbc6-57ef-840e-5178dab97e8a/scratchpad"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

# ---- 結合・溶接・台座切除 ----
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
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
cut = [v for v in bm.verts if v.co.z < 0.37]
bmesh.ops.delete(bm, geom=cut, context="VERTS")
bm.to_mesh(obj.data)
bm.free()
print("after cut verts:", len(obj.data.vertices))

# ---- 色テクスチャを金の濃淡へ(法線はそのまま) ----
def to_gold(img):
    raw = bytes(img.packed_file.data) if img.packed_file else None
    pil = Image.open(io.BytesIO(raw)).convert("RGB") if raw else None
    if pil is None:
        return None
    arr = np.asarray(pil).astype(np.float32) / 255
    lum = arr[:, :, 0] * 0.30 + arr[:, :, 1] * 0.59 + arr[:, :, 2] * 0.11
    lum = np.clip((lum - lum.min()) / max(lum.max() - lum.min(), 1e-6), 0, 1) ** 0.85
    base = np.array([68, 44, 16], dtype=np.float32)
    lit = np.array([255, 222, 138], dtype=np.float32)
    out = (base[None, None] + (lit - base)[None, None] * lum[:, :, None]).astype(np.uint8)
    path = os.path.join(TMP, f"gold_{img.name}.png")
    Image.fromarray(out).save(path)
    new = bpy.data.images.load(path)
    new.pack()
    return new

for mat in obj.data.materials:
    if not mat or not mat.use_nodes:
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        continue
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.35
    for link in list(mat.node_tree.links):
        if link.to_node == bsdf and link.to_socket.name == "Base Color" \
                and link.from_node.type == "TEX_IMAGE":
            gold = to_gold(link.from_node.image)
            if gold:
                link.from_node.image = gold
                print("gilded:", mat.name)

# ---- 減面(UVを保って約1/3に)+エッジ保存シェーディング ----
dec = obj.modifiers.new("dec", "DECIMATE")
dec.ratio = 0.35
try:
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
except Exception:
    bpy.ops.object.shade_smooth()

# ---- 底を0へ、中心へ ----
lo = mathutils.Vector((1e9,) * 3)
hi = mathutils.Vector((-1e9,) * 3)
for v in obj.data.vertices:
    lo = mathutils.Vector(map(min, lo, v.co))
    hi = mathutils.Vector(map(max, hi, v.co))
obj.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
print("statue size:", [round(hi[i] - lo[i], 2) for i in range(3)])

obj["credit"] = ("Base: Amitabha statue scan by Atsushi Nakabayashi (Sketchfab, "
                 "CC-BY-SA-4.0). Modified: pedestal removed, gold-toned textures, decimated.")
bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True)
tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
print(f"exported (source tris before decimate: {tris})")
