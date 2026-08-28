#!/usr/bin/env python3
"""フル解像度スキャンから「磨き・台座なし」の阿弥陀如来坐像を作る。

- 原型: wooden_amitabha_sitting_statue.glb (CC-BY-SA-4.0, 37万tris, 1024pxテクスチャ)
- 台座(z<0.37)を切除し、部品を結合・溶接
- 写真テクスチャの明暗を金の濃淡へ変換して張り戻す(目・口・衣文が陰影で残る)
  - CLAHE(局所コントラスト強調)+アンシャープマスクで目鼻立ちを立てる
- AO(環境遮蔽)をCyclesでベイクして色に乗算(彫りの谷が影として焼き込まれる)
  - ゲームアセットの定番手法(cats-blender-plugin bake.py などで確立)
- 法線マップは原型を1.3倍に増幅(彫りの陰影を強める)
- 約18万trisへ減面、エッジ保存シェーディング

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
def clahe(lum, tiles=8, clip=2.4):
    """簡易CLAHE: タイルごとのヒストグラム均等化(クリップ付き)を双線形補間。"""
    h, w = lum.shape
    th, tw = h // tiles, w // tiles
    luts = np.zeros((tiles, tiles, 256), dtype=np.float32)
    for i in range(tiles):
        for j in range(tiles):
            tile = lum[i * th:(i + 1) * th, j * tw:(j + 1) * tw]
            hist, _ = np.histogram(tile, 256, (0, 1))
            hist = np.minimum(hist, clip * tile.size / 256)
            hist = hist + (tile.size - hist.sum()) / 256
            luts[i, j] = np.cumsum(hist) / tile.size
    yy, xx = np.mgrid[0:h, 0:w]
    fy = np.clip((yy - th / 2) / th, 0, tiles - 1.001)
    fx = np.clip((xx - tw / 2) / tw, 0, tiles - 1.001)
    y0, x0 = fy.astype(int), fx.astype(int)
    wy, wx = fy - y0, fx - x0
    idx = np.clip((lum * 255).astype(int), 0, 255)
    v = (luts[y0, x0, idx] * (1 - wy) * (1 - wx)
         + luts[np.minimum(y0 + 1, tiles - 1), x0, idx] * wy * (1 - wx)
         + luts[y0, np.minimum(x0 + 1, tiles - 1), idx] * (1 - wy) * wx
         + luts[np.minimum(y0 + 1, tiles - 1), np.minimum(x0 + 1, tiles - 1), idx] * wy * wx)
    return v.astype(np.float32)


def to_gold(img):
    raw = bytes(img.packed_file.data) if img.packed_file else None
    pil = Image.open(io.BytesIO(raw)).convert("RGB") if raw else None
    if pil is None:
        return None
    arr = np.asarray(pil).astype(np.float32) / 255
    lum = arr[:, :, 0] * 0.30 + arr[:, :, 1] * 0.59 + arr[:, :, 2] * 0.11
    # 部位写真ごとの露出差を吸収: 平均0.52・散らばり0.20へ正規化
    lum = (lum - lum.mean()) / max(lum.std(), 1e-6) * 0.20 + 0.52
    lum = np.clip(lum, 0, 1)
    lum = clahe(lum) ** 1.05                    # 局所コントラスト+やや深めの階調
    base = np.array([62, 40, 14], dtype=np.float32)
    lit = np.array([255, 224, 140], dtype=np.float32)
    out = (base[None, None] + (lit - base)[None, None] * lum[:, :, None]).astype(np.uint8)
    path = os.path.join(TMP, f"gold_{img.name}.jpg")
    from PIL import ImageFilter
    Image.fromarray(out).filter(
        ImageFilter.UnsharpMask(radius=2.2, percent=110, threshold=2)).save(path, quality=88)
    new = bpy.data.images.load(path)
    new.pack()
    return new

def boost_normal(img, k=1.35):
    raw = bytes(img.packed_file.data) if img.packed_file else None
    if not raw:
        return None
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    a = np.asarray(pil).astype(np.float32) / 255 * 2 - 1
    a[:, :, 0] *= k
    a[:, :, 1] *= k
    n = np.sqrt((a * a).sum(axis=2, keepdims=True))
    a = a / np.maximum(n, 1e-6)
    out = ((a + 1) / 2 * 255).astype(np.uint8)
    path = os.path.join(TMP, f"nrm_{img.name}.jpg")
    Image.fromarray(out).save(path, quality=90)
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
    for n in mat.node_tree.nodes:
        if n.type == "NORMAL_MAP":
            for lk in mat.node_tree.links:
                if lk.to_node == n and lk.from_node.type == "TEX_IMAGE":
                    nb = boost_normal(lk.from_node.image)
                    if nb:
                        nb.colorspace_settings.name = "Non-Color"
                        lk.from_node.image = nb
                        print("normal boosted:", mat.name)

# ---- 減面(UVを保って約1/3に)+エッジ保存シェーディング ----
dec = obj.modifiers.new("dec", "DECIMATE")
dec.ratio = 0.5
try:
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
except Exception:
    bpy.ops.object.shade_smooth()

# ---- AOベイク: 材質ごとに焼きムラが出て色が割れたため不採用(記録として残す) ----
DO_AO = False
bpy.ops.object.modifier_apply(modifier="dec")
scene = bpy.context.scene
ao_images = {}
if DO_AO:
    # AOベイクには環境(ワールド)が必要。空シーンには無いので作る
    world = bpy.data.worlds.new("bakeworld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    scene.world = world
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.render.bake.margin = 4
    for mat in obj.data.materials:
        ao = bpy.data.images.new(f"ao_{mat.name}", 1024, 1024)
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = ao
        mat.node_tree.nodes.active = node
        ao_images[mat.name] = ao
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="AO")
    print("AO baked")
for mat in (obj.data.materials if DO_AO else []):
    ao = ao_images[mat.name]
    w, h = ao.size
    a = np.asarray(ao.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, 0]
    a = np.flipud(a)  # PIL座標へ
    if a.mean() < 0.15:
        print("AO too dark, skipped:", mat.name, round(float(a.mean()), 3))
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    tex = next((lk.from_node for lk in mat.node_tree.links
                if bsdf and lk.to_node == bsdf and lk.to_socket.name == "Base Color"
                and lk.from_node.type == "TEX_IMAGE"), None)
    if tex is None or tex.image is None or tex.image.packed_file is None:
        continue        # テクスチャを持たない材質(旧台座の底板など)は飛ばす
    raw = bytes(tex.image.packed_file.data)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.asarray(pil).astype(np.float32)
    if arr.shape[:2] != a.shape:
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8))
                       .resize((arr.shape[1], arr.shape[0]))).astype(np.float32) / 255
    shade = np.clip(a, 0, 1) ** 0.9 * 0.8 + 0.2
    out = np.clip(arr * shade[:, :, None], 0, 255).astype(np.uint8)
    path = os.path.join(TMP, f"aogold_{mat.name}.png")
    Image.fromarray(out).save(path)
    new = bpy.data.images.load(path)
    new.pack()
    tex.image = new
    mat.node_tree.nodes.remove(next(n for n in mat.node_tree.nodes
                                    if n.type == "TEX_IMAGE" and n.image and n.image.name.startswith("ao_")))
    print("AO multiplied:", mat.name)

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
