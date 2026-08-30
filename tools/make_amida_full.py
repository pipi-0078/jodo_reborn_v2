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


def blur(a, r):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255


def blur_signed(a, r):
    """負の値も扱えるぼかし(0.5を中心に置いてから戻す)。"""
    return blur(np.clip(a * 2 + 0.5, 0, 1), r) * 0.5 - 0.25


def to_gold(img, normal_img=None):
    raw = bytes(img.packed_file.data) if img.packed_file else None
    if not raw:
        return None
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255
    lum = arr[:, :, 0] * 0.30 + arr[:, :, 1] * 0.59 + arr[:, :, 2] * 0.11
    # バンドパス: ムラ(低周波)も粒状ノイズ(超高周波)も捨て、輪郭の帯だけ残す
    lum = (lum - lum.mean()) / max(lum.std(), 1e-6) * 0.20 + 0.5
    lum = np.clip(lum, 0, 1)
    size = lum.shape[0]

    coarse = blur(lum, size / 40)      # 細い線だけ通す(染みは大きいので捨てる)
    fine = blur(lum, 1.2)              # 粒状ノイズを均した版
    band = fine - coarse               # 輪郭の帯だけ
    # 帯の中の弱い成分(残ったムラ)を切り捨て、強い線だけ通す
    band = np.sign(band) * np.clip(np.abs(band) - 0.010, 0, None)
    # 面で広がる濃淡(染み)を打ち消す。細線は小さなぼかしで消えるが染みは残る性質を利用
    for r in (5.0, 12.0):
        band = band - blur_signed(band, r)
    # 彫ってある場所だけ濃淡を通す(平らな面は均一な金のまま)
    if normal_img is not None:
        nraw = bytes(normal_img.packed_file.data) if normal_img.packed_file else None
        if nraw:
            npil = Image.open(io.BytesIO(nraw)).convert("RGB").resize(lum.shape[::-1])
            na = np.asarray(npil).astype(np.float32) / 255 * 2 - 1
            relief = np.sqrt(na[:, :, 0] ** 2 + na[:, :, 1] ** 2)   # 傾きの大きさ=彫り
            relief = blur(relief / max(relief.max(), 1e-6), 2.0)
            mask = np.clip((relief - 0.14) / 0.26, 0, 1) ** 1.3
            print(f"    relief mask: mean={mask.mean():.3f} (彫り部だけ通す)")
            band = band * mask
    lum = np.clip(0.66 + band * 7.0, 0, 1)
    # 仕上げに細線をもう一段立てる
    lum = np.clip(lum + (lum - blur(lum, 1.5)) * 0.7, 0, 1)
    print(f"    tex {img.name}: std={lum.std():.3f} band_std={band.std():.3f}")
    # 影の底も磨いた金。金箔のムラは粗さ側(rough map)で表現する
    base = np.array([176, 128, 56], dtype=np.float32)
    lit = np.array([255, 226, 156], dtype=np.float32)
    out = (base[None, None] + (lit - base)[None, None] * lum[:, :, None]).astype(np.uint8)
    path = os.path.join(TMP, f"full_gold_{img.name}.jpg")
    Image.fromarray(out).filter(
        ImageFilter.UnsharpMask(radius=2.2, percent=110, threshold=2)).save(path, quality=88)
    new = bpy.data.images.load(path)
    new.pack()
    return new


def boost_normal(img, k=3.0, detail=1.1):
    """彫りの凹凸を強める。傾きの増幅に加え、細部の起伏を上乗せして
    目・鼻・口・耳の稜線をはっきり出す(色には一切触れない)。"""
    raw = bytes(img.packed_file.data) if img.packed_file else None
    if not raw:
        return None
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    a = np.asarray(pil).astype(np.float32) / 255 * 2 - 1
    # スキャンのざらつきを先に均してから、細部の起伏を上乗せする
    for ch in (0, 1):
        v = blur(np.clip(a[:, :, ch] * 0.5 + 0.5, 0, 1), 1.1) * 2 - 1
        lo = blur(np.clip(v * 0.5 + 0.5, 0, 1), 4.0) * 2 - 1
        a[:, :, ch] = v + (v - lo) * detail
    a[:, :, 0] *= k
    a[:, :, 1] *= k
    a[:, :, 2] = np.maximum(a[:, :, 2], 0.25)
    n = np.sqrt((a * a).sum(axis=2, keepdims=True))
    a = a / np.maximum(n, 1e-6)
    out = ((a + 1) / 2 * 255).astype(np.uint8)
    path = os.path.join(TMP, f"full_nrm_{img.name}.jpg")
    Image.fromarray(out).save(path, quality=95)
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
    rough = (0.33 + acc * 0.04) * 255       # 0.33〜0.37 のごく控えめなムラ
    path = os.path.join(TMP, "full_rough.png")
    Image.fromarray(rough.astype(np.uint8)).save(path)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    return img


# 台座(rengeza)とまったく同じ金の単色。写真テクスチャは使わない。
# 彫りの陰影は法線マップ(凹凸)だけで出す ＝ ムラも汚れも原理的に発生しない
PED_GOLD = (0.85, 0.62, 0.20)          # make_pavilion.py の "gold" と同値
PED_METAL, PED_ROUGH = 0.90, 0.30
PED_EMIT, PED_EMIT_STR = (0.45, 0.30, 0.08), 0.18

for mat in body.data.materials:
    if not mat or not mat.use_nodes:
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        continue
    # ベースカラーの画像リンクを外して単色に
    for lk in list(mat.node_tree.links):
        if lk.to_node == bsdf and lk.to_socket.name in ("Base Color", "Roughness"):
            mat.node_tree.links.remove(lk)
    bsdf.inputs["Base Color"].default_value = (*PED_GOLD, 1.0)
    bsdf.inputs["Metallic"].default_value = PED_METAL
    bsdf.inputs["Roughness"].default_value = PED_ROUGH
    bsdf.inputs["Emission Color"].default_value = (*PED_EMIT, 1.0)
    bsdf.inputs["Emission Strength"].default_value = PED_EMIT_STR
    # 法線マップは残す(彫りの陰影の担い手)
    for n in mat.node_tree.nodes:
        if n.type == "NORMAL_MAP":
            for lk in mat.node_tree.links:
                if lk.to_node == n and lk.from_node.type == "TEX_IMAGE":
                    nb = boost_normal(lk.from_node.image)
                    if nb:
                        nb.colorspace_settings.name = "Non-Color"
                        lk.from_node.image = nb
    print("solid gold:", mat.name)

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

# ---- キャビティ(凹みの陰)を頂点色へ焼き込む ----
# 目の窪み・口の線・螺髪の谷など、形状の谷を暗くして顔立ちを立てる。
# 写真由来ではないのでムラにならない(Blender定番の Dirty Vertex Colors)
BAKE_CAVITY = False   # 減面後の粗い頂点では斑になるため既定で無効
if BAKE_CAVITY and not body.data.color_attributes:
    body.data.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
if BAKE_CAVITY:
    bpy.ops.paint.vertex_color_dirt(blur_strength=1.0, blur_iterations=2,
                                    clean_angle=math.pi, dirt_angle=0.0,
                                    dirt_only=True, normalize=True)
for col in (body.data.color_attributes[0],) if BAKE_CAVITY else ():
    vals = np.empty(len(col.data) * 4, dtype=np.float32)
    col.data.foreach_get("color", vals)
    vals = vals.reshape(-1, 4)
    vals[:, :3] = 0.42 + np.clip(vals[:, :3], 0, 1) * 0.58
    col.data.foreach_set("color", vals.reshape(-1))
    print("cavity shading baked (min", round(float(vals[:, :3].min()), 3), ")")

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
try:
    bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True,
                              export_vertex_color="ACTIVE")
except TypeError:
    bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
           for o in (body, pedestal))
print(f"exported amida_full.glb ({tris} tris)")
