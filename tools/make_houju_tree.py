#!/usr/bin/env python3
"""宝樹(ほうじゅ): 承認済みの木の glb に宝飾を施した宝樹を出力する。

「七重行樹 皆是四宝」— 幹と枝は金(名前で空間側の純金処理に載せる)、
枝先から真珠と水晶の鎖が垂れ、先に桜色・水色・藤色の淡い宝石の雫。枝には金の萼付きの宝石の実。
9/4 施主の指示: 一本目(名木)で「淡くて優しい色」が承認 → 全種類の木に施す。

手順(各木共通):
  1. 元の glb を読み込み、幹・枝のマテリアルを gold_* に(無地の金にする)
  2. 幹以外の頂点から枝先らしい点(外側・中〜上段)を選び、瓔珞の鎖と宝石の実を吊るす
  3. 飾りの大きさは空間での配置スケールを打ち消して、どの木でもほぼ同じ実寸になるよう K で補正
出力: public/assets/houju_*.glb(houju_tree.glb は名木の宝樹、互換のため名前据え置き)
"""
import json
import math
import os
import random
import struct
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_bridge import GOLD  # noqa: E402
from make_ramou import Batch, gem_material, tube  # noqa: E402

TRUNK_NAMES = ("bark", "material")  # 幹・太枝(takara_tree は "material" が幹)
TWIG_NAMES = ("twig",)

# 木ごとの設定: (元ファイル, 出力, 吊り下げ点の数, 点の間隔, 空間での配置スケール)
# 外周の軽量宝樹は本数が多い(約180本)ので飾りを軽く
TREES = [
    ("tree_meiboku.glb", "houju_tree.glb", 180, 0.42, 1.0),
    ("takara_tree.glb", "houju_takara.glb", 180, 0.8, 0.55),
    ("tree_yanagi.glb", "houju_yanagi.glb", 150, 0.42, 1.3),
    ("tree_conifer.glb", "houju_conifer.glb", 120, 0.42, 1.1),
    ("tree_broadleaf.glb", "houju_broadleaf.glb", 120, 0.42, 1.3),
    ("tree_weeping.glb", "houju_weeping.glb", 120, 0.42, 1.4),
    ("tree_lod.glb", "houju_lod.glb", 40, 0.6, 1.1),
]


def goldify(material, name, roughness):
    """既存マテリアルを金に: 名前を gold_* にし、無地の金属にする"""
    material.name = name
    if material.use_nodes:
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # 樹皮テクスチャは外す(暗い樹皮色が金に乗って黒ずむ 9/4)。承認済みの一本目と同じ無地の金に
            for link in list(bsdf.inputs["Base Color"].links):
                material.node_tree.links.remove(link)
            bsdf.inputs["Base Color"].default_value = (*GOLD, 1.0)
            bsdf.inputs["Metallic"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = roughness


def alpha_modes(path):
    """glb の葉マテリアルの alphaMode を読む(再出力で失われていないかの確認用)"""
    with open(path, "rb") as f:
        f.read(12)
        n, _ = struct.unpack("<II", f.read(8))
        gltf = json.loads(f.read(n))
    return {m.get("name"): m.get("alphaMode", "OPAQUE") for m in gltf.get("materials", [])}


def build(src, dst, count, spacing, place_scale):
    rand = random.Random(31)
    reset_scene()
    src_path = os.path.join(OUT_DIR, src)
    bpy.ops.import_scene.gltf(filepath=src_path)
    K = 1.0 / place_scale  # 飾りの実寸をそろえる補正

    gold = plain_material("gold_polished", GOLD, 1.0, 0.22)
    pearl = plain_material("pearl", (0.97, 0.95, 0.91), 0.0, 0.22, (0.30, 0.28, 0.25), 0.3)
    # 淡く優しい色の宝石(9/4): 桜色・水色・藤色。空間側の *_gem プリセットで透けさせる
    hari = gem_material("hari_gem", (0.92, 0.96, 1.0), 1.95, (0.6, 0.7, 0.9), 0.12)
    sakura = gem_material("sakura_gem", (0.98, 0.80, 0.84), 1.55, (0.5, 0.3, 0.33), 0.1)
    mizu = gem_material("mizu_gem", (0.80, 0.93, 0.98), 1.55, (0.35, 0.48, 0.55), 0.1)
    fuji = gem_material("fuji_gem", (0.88, 0.82, 0.97), 1.55, (0.42, 0.36, 0.55), 0.1)

    # --- 幹と枝を金に ---
    top = 0.0
    candidates = []
    done = set()
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        trunk = False
        for slot in obj.material_slots:
            m = slot.material
            if m is None:
                continue
            base = m.name.split(".")[0]
            if base in TRUNK_NAMES or m.name.startswith("gold_trunk"):
                trunk = True
                if m.name not in done:
                    goldify(m, "gold_trunk", 0.4)
            elif base in TWIG_NAMES or m.name.startswith("gold_twig"):
                trunk = True
                if m.name not in done:
                    goldify(m, "gold_twig", 0.35)
            done.add(m.name)
        for v in obj.data.vertices:
            p = obj.matrix_world @ v.co
            top = max(top, p.z)
            if not trunk:
                candidates.append(p)

    # --- 吊り下げ点: 幹以外(葉・既存の宝石)の頂点から、外側で高さ 30〜96% の範囲 ---
    points = [p for p in candidates if 0.3 * top < p.z < 0.96 * top and math.hypot(p.x, p.y) > 0.6 * K]
    rand.shuffle(points)
    chosen = []
    for p in points:
        if all((p - q).length > spacing for q in chosen):
            chosen.append(p)
        if len(chosen) >= count:
            break

    wire = Batch("gold_wire", gold)
    fitting = Batch("gold_fitting", gold, smooth=False)
    pearls = Batch("pearl_batch", pearl)
    gems = {"hari": Batch("hari_batch", hari, smooth=False), "sakura": Batch("sakura_batch", sakura, smooth=False),
            "mizu": Batch("mizu_batch", mizu, smooth=False), "fuji": Batch("fuji_batch", fuji, smooth=False)}
    colored = [gems["sakura"], gems["mizu"], gems["fuji"]]

    # --- 瓔珞の鎖: 真珠と水晶を連ね、先に色石の雫 ---
    n_strings = int(len(chosen) * 0.6)  # 6 割を鎖、4 割を実に
    for i, p in enumerate(chosen[:n_strings]):
        length = rand.uniform(0.7, 1.8) * K
        wire.add(*tube([p, p + Vector((0, 0, -length))], 0.012 * K, sides=4))
        n = int(length / (0.14 * K))
        for k in range(n):
            q = p + Vector((0, 0, -(0.08 + k * 0.14) * K))
            if k % 3 == 2:
                gems["hari"].gem(q, 0.05 * K, elong=1.3, facets=8)
            else:
                pearls.sphere(q, 0.042 * K)
        fitting.petal_disc(p + Vector((0, 0, -length + 0.06 * K)), 0.07 * K, 6, tilt=-0.7, width=0.5)
        colored[i % 3].gem(p + Vector((0, 0, -length - 0.07 * K)), 0.09 * K, elong=1.7, facets=8)

    # --- 宝石の実: 枝に直接、金の萼(がく)付きの大きな宝石 ---
    for i, p in enumerate(chosen[n_strings:]):
        q = p + Vector((0, 0, -0.12 * K))
        fitting.petal_disc(q + Vector((0, 0, 0.05 * K)), 0.09 * K, 6, tilt=-0.6, width=0.5)
        colored[(i + 1) % 3].gem(q, 0.12 * K, elong=1.3, facets=8)

    for b in (wire, fitting, pearls, *gems.values()):
        b.finish()
    print(f"{src}: 吊り下げ点 {len(chosen)} / 樹高 {top:.1f}m", file=sys.stderr)
    export(os.path.join(OUT_DIR, dst))
    before, after = alpha_modes(src_path), alpha_modes(os.path.join(OUT_DIR, dst))
    lost = [n for n, mode in before.items() if mode == "MASK" and after.get(n) != "MASK"]
    if lost:
        print(f"  警告: 葉の alphaMode が失われた {lost}", file=sys.stderr)


if __name__ == "__main__":
    only = sys.argv[1:]
    for src, dst, count, spacing, place_scale in TREES:
        if only and dst not in only:
            continue
        build(src, dst, count, spacing, place_scale)
    print("done", file=sys.stderr)
