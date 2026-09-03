#!/usr/bin/env python3
"""スキャン原型から「金箔押しの阿弥陀如来坐像(台座なし)」を作る。

方針(docs/LESSONS.md 2-2, 2-3, 4 の教訓):
  ・形は触らない。写真テクスチャ(色ムラの原因)は完全に剥がし、ベースカラーは台座と同じ金一色
  ・彫りはスキャン自身の法線マップで出す(増幅もAOも焼き込まない)
  ・「材質感」は色ではなく、金箔の細かな皺(ごく弱い法線)と箔ごとの艶の差(粗さの微差)で出す
  ・マテリアル値は蓮華座の金と同じ系統: base (0.83,0.59,0.18), metallic 0.75, roughness 0.48, 弱い発光

使い方: python3 tools/make_amida_goldleaf.py
出力: public/assets/amida_polish.glb(ギャラリー「阿弥陀如来坐像(磨き・台座なし)」を置き換える)
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
TEX = os.path.join(ROOT, "tools/textures")
TMP = "/tmp/claude-0/-home-user-jodo-reborn-v2/99555b29-dbc6-57ef-840e-5178dab97e8a/scratchpad"

GOLD = (0.83, 0.59, 0.18)          # 蓮華座の金の系統(空の映り込みで白っぽくならないよう少し深く)
METALLIC = 0.75                    # 鏡面すぎると空の青緑が顔に映る(LESSONS 2-3)
ROUGHNESS = 0.48
EMISSION = (0.45, 0.30, 0.08)
EMISSION_STRENGTH = 0.15
NORMAL_STRENGTH = 0.85             # スキャン法線(彫り)の強さ
LEAF_TILE = 6                      # 金箔の皺をUV一枚あたり何回繰り返すか
LEAF_NORMAL_MIX = 0.12             # 皺の法線をどれだけ混ぜるか(ごく弱く。粒に見えるとムラになる)
ROUGH_RANGE = (0.45, 0.52)         # 箔ごとの艶の差
DECIMATE = 0.7                     # 減面率(彫りを残すため軽め)


def log(*a):
    print(*a, file=sys.stderr)


def tiled(path, size, reps):
    """タイル化画像を reps 回繰り返して size 角にする。"""
    im = Image.open(path).convert("RGB")
    cell = max(1, size // reps)
    im = im.resize((cell, cell), Image.LANCZOS)
    canvas = Image.new("RGB", (cell * reps, cell * reps))
    for y in range(reps):
        for x in range(reps):
            canvas.paste(im, (x * cell, y * cell))
    return canvas.resize((size, size), Image.LANCZOS)


def blend_normal(scan_img):
    """スキャンの法線に金箔の皺の法線を弱く混ぜる(UDN 合成: xy を足し、z はそのまま)。"""
    raw = bytes(scan_img.packed_file.data) if scan_img.packed_file else None
    if not raw:
        return None
    scan = Image.open(io.BytesIO(raw)).convert("RGB")
    size = scan.size[0]
    a = np.asarray(scan).astype(np.float32) / 255 * 2 - 1
    leaf = np.asarray(tiled(os.path.join(TEX, "kinpaku_normal.png"), size, LEAF_TILE)).astype(np.float32) / 255 * 2 - 1
    out = a.copy()
    out[:, :, 0] += leaf[:, :, 0] * LEAF_NORMAL_MIX
    out[:, :, 1] += leaf[:, :, 1] * LEAF_NORMAL_MIX
    n = np.sqrt((out * out).sum(axis=2, keepdims=True))
    out = out / np.maximum(n, 1e-6)
    path = os.path.join(TMP, f"leafnrm_{scan_img.name}.png")
    Image.fromarray(((out + 1) / 2 * 255).astype(np.uint8)).save(path)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    return img


def roughness_image(size=1024):
    """箔の一枚一枚で艶がわずかに違う: kinpaku.png の明暗を粗さの微差にする(G=粗さ, B=金属)。"""
    lum = np.asarray(tiled(os.path.join(TEX, "kinpaku.png"), size, LEAF_TILE).convert("L")).astype(np.float32) / 255
    lum = (lum - lum.min()) / max(1e-6, lum.max() - lum.min())
    rough = ROUGH_RANGE[0] + (1 - lum) * (ROUGH_RANGE[1] - ROUGH_RANGE[0])
    orm = np.zeros((size, size, 3), dtype=np.uint8)
    orm[:, :, 0] = 255
    orm[:, :, 1] = (rough * 255).astype(np.uint8)
    orm[:, :, 2] = int(METALLIC * 255)
    path = os.path.join(TMP, "leaf_orm.png")
    Image.fromarray(orm).save(path)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    return img


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)

    # ---- 結合・溶接・台座切除(make_amida_polish.py と同じ手順) ----
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
    log("after cut verts:", len(obj.data.vertices))

    # ---- 材質: 写真テクスチャを剥がし、金一色+スキャン法線+金箔の皺 ----
    orm = roughness_image()
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        # ベースカラーへの画像リンクを切る(画像ノードは残しても書き出されないが消しておく)
        for lk in list(tree.links):
            if lk.to_node == bsdf and lk.to_socket.name in ("Base Color", "Metallic", "Roughness"):
                tree.links.remove(lk)
        for n in [n for n in tree.nodes if n.type == "TEX_IMAGE" and n.image
                  and not any(lk.from_node == n for lk in tree.links)]:
            tree.nodes.remove(n)
        bsdf.inputs["Base Color"].default_value = (*GOLD, 1.0)
        bsdf.inputs["Metallic"].default_value = METALLIC
        bsdf.inputs["Roughness"].default_value = ROUGHNESS
        bsdf.inputs["Emission Color"].default_value = (*EMISSION, 1.0)
        bsdf.inputs["Emission Strength"].default_value = EMISSION_STRENGTH
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.5
        # 粗さの微差(glTF の metallicRoughness テクスチャとして書き出される定型: 画像→Separate→G/B)
        tex = tree.nodes.new("ShaderNodeTexImage")
        tex.image = orm
        sep = tree.nodes.new("ShaderNodeSeparateColor")
        tree.links.new(tex.outputs["Color"], sep.inputs["Color"])
        tree.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        tree.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        # 法線: スキャンの彫り+箔の皺
        for n in tree.nodes:
            if n.type == "NORMAL_MAP":
                n.inputs["Strength"].default_value = NORMAL_STRENGTH
                for lk in tree.links:
                    if lk.to_node == n and lk.from_node.type == "TEX_IMAGE":
                        blended = blend_normal(lk.from_node.image)
                        if blended:
                            lk.from_node.image = blended
                            log("normal blended:", mat.name)
        log("gilded:", mat.name)

    # ---- 減面(UVを保つ)+エッジ保存シェーディング ----
    dec = obj.modifiers.new("dec", "DECIMATE")
    dec.ratio = DECIMATE
    bpy.ops.object.modifier_apply(modifier="dec")
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
    log("statue size:", [round(hi[i] - lo[i], 2) for i in range(3)])

    obj["credit"] = ("Base: Amitabha statue scan by Atsushi Nakabayashi (Sketchfab, "
                     "CC-BY-SA-4.0). Modified: pedestal removed, photo textures replaced by a "
                     "uniform gold-leaf PBR material, decimated.")
    bpy.ops.export_scene.gltf(filepath=OUT, export_apply=True, export_extras=True,
                              export_image_format="JPEG", export_jpeg_quality=88)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    log(f"exported {os.path.relpath(OUT, ROOT)} tris={tris}")


if __name__ == "__main__":
    main()
