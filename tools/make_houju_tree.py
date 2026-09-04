#!/usr/bin/env python3
"""宝樹(ほうじゅ): 承認済みの名木(tree_meiboku.glb)に宝飾を施した木をglb出力する。

「七重行樹 皆是四宝」— 幹と枝は金、葉は金(空間側で四宝の色に染める)、
枝先から真珠と水晶の鎖が垂れ、先に桜色・水色・藤色の淡い宝石の雫。枝には宝石の実。
参考図(9/4)の、枝から瓔珞が下がる宝樹に寄せる。

手順:
  1. tree_meiboku.glb を読み込む(幹 bark / 小枝 twig / 葉 foliage)
  2. 幹・小枝のマテリアル名を gold_trunk / gold_twig に(空間側で純金の反射になる)
  3. 葉の頂点から枝先らしい点(外側・中〜上段)を選び、瓔珞の鎖と宝石の実を吊るす
出力: public/assets/houju_tree.glb
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public/assets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from make_trees import export, plain_material, reset_scene  # noqa: E402
from make_bridge import GOLD  # noqa: E402
from make_ramou import Batch, gem_material, tube  # noqa: E402

rand = random.Random(31)
STRINGS = 110      # 瓔珞の鎖の本数
FRUITS = 70        # 宝石の実の数


def build(path):
    reset_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(OUT_DIR, "tree_meiboku.glb"))

    gold = plain_material("gold_polished", GOLD, 1.0, 0.22)
    pearl = plain_material("pearl", (0.97, 0.95, 0.91), 0.0, 0.22, (0.30, 0.28, 0.25), 0.3)
    # 淡く優しい色の宝石(9/4 施主の指示「もっとおとなしい色」): 桜色・水色・藤色。空間側の *_gem プリセットで透けさせる
    hari = gem_material("hari_gem", (0.92, 0.96, 1.0), 1.95, (0.6, 0.7, 0.9), 0.12)
    sakura = gem_material("sakura_gem", (0.98, 0.80, 0.84), 1.55, (0.5, 0.3, 0.33), 0.1)
    mizu = gem_material("mizu_gem", (0.80, 0.93, 0.98), 1.55, (0.35, 0.48, 0.55), 0.1)
    fuji = gem_material("fuji_gem", (0.88, 0.82, 0.97), 1.55, (0.42, 0.36, 0.55), 0.1)

    # --- 幹と枝を金に(名前で空間側の純金処理に載せる) ---
    foliage = None
    top = 0.0
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            name = slot.material.name
            if name.startswith("bark"):
                slot.material = plain_material("gold_trunk", GOLD, 1.0, 0.4)
            elif name.startswith("twig"):
                slot.material = plain_material("gold_twig", GOLD, 1.0, 0.35)
            elif name.startswith("foliage"):
                foliage = obj
        for v in obj.data.vertices:
            top = max(top, (obj.matrix_world @ v.co).z)
    assert foliage is not None, "foliage が見つからない"

    # --- 葉の頂点から吊り下げ点を選ぶ: 外側で、高さ 35〜95% の範囲 ---
    points = []
    for v in foliage.data.vertices:
        p = foliage.matrix_world @ v.co
        r = math.hypot(p.x, p.y)
        if 0.3 * top < p.z < 0.96 * top and r > 0.6:
            points.append(p)
    rand.shuffle(points)
    # 近すぎる点を間引く(0.6m)
    chosen = []
    for p in points:
        if all((p - q).length > 0.42 for q in chosen):
            chosen.append(p)
        if len(chosen) >= STRINGS + FRUITS:
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
        length = rand.uniform(0.7, 1.8)
        wire.add(*tube([p, p + Vector((0, 0, -length))], 0.012, sides=4))
        n = int(length / 0.14)
        for k in range(n):
            q = p + Vector((0, 0, -0.08 - k * 0.14))
            if k % 3 == 2:
                gems["hari"].gem(q, 0.05, elong=1.3, facets=8)
            else:
                pearls.sphere(q, 0.042)
        fitting.petal_disc(p + Vector((0, 0, -length + 0.06)), 0.07, 6, tilt=-0.7, width=0.5)
        colored[i % 3].gem(p + Vector((0, 0, -length - 0.07)), 0.09, elong=1.7, facets=8)

    # --- 宝石の実: 枝に直接、金の萼(がく)付きの大きな宝石 ---
    for i, p in enumerate(chosen[n_strings:]):
        q = p + Vector((0, 0, -0.12))
        fitting.petal_disc(q + Vector((0, 0, 0.05)), 0.09, 6, tilt=-0.6, width=0.5)
        colored[(i + 1) % 3].gem(q, 0.12, elong=1.3, facets=8)

    for b in (wire, fitting, pearls, *gems.values()):
        b.finish()
    print(f"  吊り下げ点 {len(chosen)} / 樹高 {top:.1f}m", file=sys.stderr)
    export(path)


if __name__ == "__main__":
    build(os.path.join(OUT_DIR, "houju_tree.glb"))
    print("done", file=sys.stderr)
