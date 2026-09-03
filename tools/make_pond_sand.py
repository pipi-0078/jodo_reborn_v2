#!/usr/bin/env python3
"""七宝池の底砂テクスチャを描く。

「池底純以金沙布地」+ 四宝(金・銀・瑠璃・玻璃)の砂が
流れに寄せられて吹き溜まりを作っている様子。
- 粒: 1粒=数ピクセルの砂粒。粒ごとに四宝いずれかの色と明度を持つ
- 吹き溜まり: 域を波打つノイズで分け、境界では粒が確率的に混ざる(9/3: 塊を 1/64 タイルまで細かく)
- 砂紋: 水流が刻む低い畝を法線マップに焼き込む
出力: public/textures/pond_sand.png / pond_sand_normal.png (2048px、砂紋あり=池底用)
      public/textures/pond_sand_flat.png / pond_sand_flat_normal.png(砂紋なし=斜面用)
"""
import math
import os

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public/textures")
os.makedirs(OUT, exist_ok=True)


def tileable_noise(size, octaves=5, seed=0, base=4):
    """base: 最低周波数のセル数(大きいほど模様が細かい)。"""
    r = np.random.default_rng(seed)
    acc = np.zeros((size, size))
    for o in range(octaves):
        n = base * 2 ** o
        layer = r.random((n, n))
        layer = np.pad(layer, ((0, 1), (0, 1)), mode="wrap")
        img = Image.fromarray((layer * 255).astype(np.uint8)).resize(
            (size + 1, size + 1), Image.BICUBIC)
        acc += (np.asarray(img)[:size, :size] / 255.0) * (0.5 ** o)
    acc -= acc.min()
    return acc / acc.max()


def height_to_normal(height, strength=2.4):
    gy, gx = np.gradient(height.astype(np.float32))
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(height)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([(nx / norm + 1) / 2, (ny / norm + 1) / 2, (nz / norm + 1) / 2], axis=-1)
    return Image.fromarray((normal * 255).astype(np.uint8))


def make_pond_sand(size=2048, grain_px=2):
    rng = np.random.default_rng(41)
    g = size // grain_px                      # 粒格子(1セル=1粒)

    # --- 吹き溜まり: ドメインワープしたノイズで四宝の領域を分ける ---
    # 吹き溜まりは 1 タイルの 1/64 程度の大きさ(据え付け時のタイル 1.6〜2.5m → 3〜4cm の粒立ち。大きいと迷彩に見える)
    warp_x = tileable_noise(g, octaves=4, seed=11, base=8)
    warp_y = tileable_noise(g, octaves=4, seed=12, base=8)
    yy, xx = np.mgrid[0:g, 0:g].astype(np.float32) / g
    fx = (xx + (warp_x - 0.5) * 0.18) % 1.0
    fy = (yy + (warp_y - 0.5) * 0.18) % 1.0
    # 四宝それぞれの「勢い」を独立したノイズで立て、勝った宝の吹き溜まりになる。
    # 金は経典どおり主役(池底純以金沙布地)。他の三宝が島状に寄る
    bias = [1.30, 0.97, 0.94, 0.97]           # 金 / 銀 / 瑠璃 / 玻璃
    stacks = []
    ix, iy = (fx * (g - 1)).astype(int), (fy * (g - 1)).astype(int)
    for i, b in enumerate(bias):
        f = tileable_noise(g, octaves=3, seed=30 + i, base=64)[iy, ix]
        f = np.asarray(Image.fromarray((f * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32) / 255
        stacks.append(f * b)
    stack = np.stack(stacks)
    types = np.argmax(stack, axis=0)

    # 境界で粒を確率的に混ぜる(一位と二位が拮抗する帯)
    part = np.sort(stack, axis=0)
    band = (part[-1] - part[-2]) < 0.09
    second = np.argsort(stack, axis=0)[-2]
    jitter = rng.random((g, g))
    swap = band & (jitter < 0.5)
    types[swap] = second[swap]
    # まばらな異色粒(どの砂にも他の宝の粒がわずかに紛れる)
    stray = rng.random((g, g)) < 0.14
    types[stray] = rng.integers(0, 4, stray.sum())

    # --- 粒ごとの色と明度 ---
    palette = np.array([
        [214, 168, 66],    # 金沙
        [222, 226, 233],   # 銀沙
        [46, 78, 190],     # 瑠璃沙
        [238, 246, 252],   # 玻璃沙
    ], dtype=np.float32)
    bright = 0.72 + rng.random((g, g)).astype(np.float32) * 0.55   # 粒の明度むら
    sparkle = rng.random((g, g)) < 0.030                            # きらりと返す粒
    bright[sparkle] = 1.9
    color_g = palette[types] * bright[:, :, None]

    # 粒の高さ(法線用)と、粒面のわずかな丸み
    h_g = rng.random((g, g)).astype(np.float32)

    # --- 粒格子をピクセルへ拡大(最近傍=粒がタイルとして残る) ---
    up = lambda a: np.asarray(Image.fromarray(a).resize((size, size), Image.NEAREST))
    color = np.stack([up(color_g[:, :, c].astype(np.float32)) for c in range(3)], axis=-1)
    h = up(h_g)

    # 粒の縁を少し落として丸粒に見せる
    cell = np.tile(np.linspace(-1, 1, grain_px), size // grain_px)
    dome = 1 - 0.35 * (cell[None, :] ** 2 + cell[:, None] ** 2)
    h = h * dome
    color = color * (0.86 + 0.14 * dome[:, :, None])

    # --- 砂紋: 流れが刻む畝(ゆるく波打つ縞)。池底(平場)用
    #     斜面に貼ると「地層の横線」に見えるので、斜面用には砂紋なしの版(_flat)を別に出す(9/3)
    w1 = tileable_noise(size, octaves=4, seed=21)
    ripple = np.sin(np.mgrid[0:size, 0:size][0].astype(np.float32) / size
                    * math.pi * 2 * 26 + (w1 - 0.5) * 9.0)
    ripple = (ripple * 0.5 + 0.5) ** 1.3
    height = np.clip(h * 0.55 + ripple * 0.45, 0, 1)
    color_r = color * (0.90 + ripple[:, :, None] * 0.18)
    Image.fromarray(np.clip(color_r, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, "pond_sand.png"))
    height_to_normal(height, 2.0).save(os.path.join(OUT, "pond_sand_normal.png"))

    # 斜面用: 砂紋の代わりに方向性のないゆるい起伏だけ
    mound = tileable_noise(size, octaves=3, seed=22, base=6)
    height_flat = np.clip(h * 0.6 + mound * 0.4, 0, 1)
    color_f = color * (0.94 + (mound[:, :, None] - 0.5) * 0.12)
    Image.fromarray(np.clip(color_f, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, "pond_sand_flat.png"))
    height_to_normal(height_flat, 1.6).save(os.path.join(OUT, "pond_sand_flat_normal.png"))
    counts = [(types == i).mean() for i in range(4)]
    print("pond_sand 2048px  金/銀/瑠璃/玻璃 =", [round(c, 2) for c in counts])


if __name__ == "__main__":
    make_pond_sand()
