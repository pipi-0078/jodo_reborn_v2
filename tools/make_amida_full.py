#!/usr/bin/env python3
"""黄金の阿弥陀如来坐像(定印・蓮華座付き)— 案件定義(2026-08-28)準拠。

High Poly原型(37万trisスキャン, CC-BY-SA-4.0)から本体を仕上げ、
検品済みの黄金蓮華座と古典比率(膝張=蓮肉径)で合成する。
- 本体: 台座切除→溶接→クリーンアップ→減面。細部は原型の法線マップ+CLAHE金箔
- 金箔: 深みのある金、ノイズで粗さにムラ(完全鏡面にしない)
- 構成: Amida_Body / Lotus_Pedestal の2オブジェクト
- 総高約2.7m、蓮華座の底がZ=0、正面+X

使い方: python3 tools/make_amida_full.py
出力: public/assets/amida_full.glb
"""
import io
import math
import os

import bpy
import bmesh
import mathutils
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "/root/.claude/uploads/99555b29-dbc6-57ef-840e-5178dab97e8a/871873a0-wooden_amitabha_sitting_statue.glb"
RENGEZA = os.path.join(ROOT, "public/assets/rengeza.glb")
OUT = os.path.join(ROOT, "public/assets/amida_full.glb")
TMP = "/tmp/claude-0/-home-user-jodo-reborn-v2/99555b29-dbc6-57ef-840e-5178dab97e8a/scratchpad"

PED_SCALE = 0.75     # 蓮華座の縮尺
BODY_SCALE = 1.82    # 本体の縮尺(膝が蓮肉から蓮弁へ少しかかる古典の納まり)
DAIS_TOP = 1.45      # 蓮肉の天端(rengeza座標)

bpy.ops.wm.read_factory_settings(use_empty=True)

# ================= 蓮華座 =================
bpy.ops.import_scene.gltf(filepath=RENGEZA)
ped_parts = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in ped_parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = ped_parts[0]
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.join()
pedestal = bpy.context.active_object
pedestal.name = "Lotus_Pedestal"
pedestal.scale = (PED_SCALE,) * 3
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ================= 本体 =================
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=SRC)
body_parts = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in body_parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = body_parts[0]
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.join()
body = bpy.context.active_object
body.name = "Amida_Body"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bm = bmesh.new()
bm.from_mesh(body.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
cut = [v for v in bm.verts if v.co.z < 0.37]
bmesh.ops.delete(bm, geom=cut, context="VERTS")
# 浮きゴミ(孤立した小さな破片)を除去: 連結成分の小さいものを消す
bm.verts.ensure_lookup_table()
parent = list(range(len(bm.verts)))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a
for e in bm.edges:
    a, b = find(e.verts[0].index), find(e.verts[1].index)
    if a != b:
        parent[a] = b
from collections import Counter
sizes = Counter(find(i) for i in range(len(bm.verts)))
main = sizes.most_common(1)[0][0]
junk = [v for v in bm.verts if find(v.index) != main]
if junk:
    bmesh.ops.delete(bm, geom=junk, context="VERTS")
    print("removed junk islands:", len(sizes) - 1, "(", len(junk), "verts )")
bm.to_mesh(body.data)
bm.free()
print("body verts:", len(body.data.vertices))

# ---- 金箔テクスチャ(深みのある金・CLAHE・露出正規化) ----
def clahe(lum, tiles=8, clip=2.4):
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
    t1 = np.minimum(y0 + 1, tiles - 1)
    t2 = np.minimum(x0 + 1, tiles - 1)
    v = (luts[y0, x0, idx] * (1 - wy) * (1 - wx) + luts[t1, x0, idx] * wy * (1 - wx)
         + luts[y0, t2, idx] * (1 - wy) * wx + luts[t1, t2, idx] * wy * wx)
    return v.astype(np.float32)


def to_gold(img):
    raw = bytes(img.packed_file.data) if img.packed_file else None
    if not raw:
        return None
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255
    lum = arr[:, :, 0] * 0.30 + arr[:, :, 1] * 0.59 + arr[:, :, 2] * 0.11
    lum = (lum - lum.mean()) / max(lum.std(), 1e-6) * 0.07 + 0.66
    lum = np.clip(lum, 0, 1)
    lum = clahe(lum, clip=1.3) ** 0.85   # 局所差は最小限に(ムラを出さない)
    # 影の底も磨いた金。金箔のムラは粗さ側(rough map)で表現する
    base = np.array([206, 158, 72], dtype=np.float32)
    lit = np.array([255, 238, 172], dtype=np.float32)
    out = (base[None, None] + (lit - base)[None, None] * lum[:, :, None]).astype(np.uint8)
    path = os.path.join(TMP, f"full_gold_{img.name}.jpg")
    Image.fromarray(out).filter(
        ImageFilter.UnsharpMask(radius=2.2, percent=110, threshold=2)).save(path, quality=88)
    new = bpy.data.images.load(path)
    new.pack()
    return new


def boost_normal(img, k=1.45):
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
    path = os.path.join(TMP, f"full_nrm_{img.name}.jpg")
    Image.fromarray(out).save(path, quality=90)
    new = bpy.data.images.load(path)
    new.pack()
    return new


# 金箔のムラ: 粗さにノイズの揺らぎ(§6「完全な鏡面にしない」)
def make_rough_map():
    r = np.random.default_rng(77)
    acc = np.zeros((512, 512), dtype=np.float32)
    for o in range(5):
        n = 2 ** (o + 3)
        layer = np.pad(r.random((n, n)), ((0, 1), (0, 1)), mode="wrap")
        acc += np.asarray(Image.fromarray((layer * 255).astype(np.uint8))
                          .resize((513, 513), Image.BICUBIC))[:512, :512] / 255 * 0.5 ** o
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    rough = (0.32 + acc * 0.07) * 255       # 0.32〜0.39 の控えめなムラ
    path = os.path.join(TMP, "full_rough.png")
    Image.fromarray(rough.astype(np.uint8)).save(path)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    return img


rough_img = make_rough_map()
for mat in body.data.materials:
    if not mat or not mat.use_nodes:
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        continue
    bsdf.inputs["Metallic"].default_value = 0.95
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.76, 0.32, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.08
    rnode = mat.node_tree.nodes.new("ShaderNodeTexImage")
    rnode.image = rough_img
    mat.node_tree.links.new(rnode.outputs["Color"], bsdf.inputs["Roughness"])
    for link in list(mat.node_tree.links):
        if link.to_node == bsdf and link.to_socket.name == "Base Color" \
                and link.from_node.type == "TEX_IMAGE":
            g = to_gold(link.from_node.image)
            if g:
                link.from_node.image = g
                print("gilded:", mat.name)
    for n in mat.node_tree.nodes:
        if n.type == "NORMAL_MAP":
            for lk in mat.node_tree.links:
                if lk.to_node == n and lk.from_node.type == "TEX_IMAGE":
                    nb = boost_normal(lk.from_node.image)
                    if nb:
                        nb.colorspace_settings.name = "Non-Color"
                        lk.from_node.image = nb

# ---- 減面してWeb向けに ----
dec = body.modifiers.new("dec", "DECIMATE")
dec.ratio = 0.45
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier="dec")
try:
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
except Exception:
    bpy.ops.object.shade_smooth()

# ---- 配置: 膝張=蓮肉径、蓮肉の天端に着座、正面+X ----
lo = mathutils.Vector((1e9,) * 3)
hi = mathutils.Vector((-1e9,) * 3)
for v in body.data.vertices:
    lo = mathutils.Vector(map(min, lo, v.co))
    hi = mathutils.Vector(map(max, hi, v.co))
body.scale = (BODY_SCALE,) * 3
body.location = (-(lo.x + hi.x) / 2 * BODY_SCALE,
                 -(lo.y + hi.y) / 2 * BODY_SCALE,
                 DAIS_TOP * PED_SCALE - lo.z * BODY_SCALE - 0.02)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
top = max(v.co.z for v in body.data.vertices)
print(f"total height: {top:.2f} m (knee span {(hi.y - lo.y) * BODY_SCALE:.2f})")

body["credit"] = ("Base: Amitabha statue scan by Atsushi Nakabayashi (Sketchfab, "
                  "CC-BY-SA-4.0). Modified: pedestal removed, gold-leaf retexture, "
                  "decimated, composed with procedural lotus pedestal.")
bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
           for o in (body, pedestal))
print(f"exported amida_full.glb ({tris} tris)")
