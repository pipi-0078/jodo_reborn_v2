#!/usr/bin/env python3
"""宝樹用のテクスチャを描く。

- ginkgo.png      金の銀杏の葉(扇形・葉脈・アルファ)
- needle.png      針葉の小枝(茎から左右に細い針・アルファ)
- bark.png        樹皮(縦の筋・色むら)
- bark_normal.png 樹皮の法線マップ(高さから生成)

出力先: tools/textures/
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "textures")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(7)


def smooth_noise(size, octaves=4, seed=0):
    r = np.random.default_rng(seed)
    acc = np.zeros((size, size))
    for o in range(octaves):
        n = 2 ** (o + 2)
        layer = r.random((n, n))
        img = Image.fromarray((layer * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        acc += (np.asarray(img) / 255.0) * (0.5 ** o)
    acc -= acc.min()
    return acc / acc.max()


# ---------------------------------------------------------------- 銀杏の葉

def make_ginkgo(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, int(size * 0.94)  # 扇の要(葉柄の付け根)を下端に
    radius = size * 0.82
    a0, a1 = math.radians(-90 - 38), math.radians(-90 + 38)

    # 扇の輪郭(外縁は波打ち、中央に切れ込み)
    outline = [(cx, cy)]
    steps = 90
    for i in range(steps + 1):
        t = i / steps
        angle = a0 + (a1 - a0) * t
        wave = 1 + 0.045 * math.sin(t * math.pi * 7) - 0.02 * math.cos(t * math.pi * 13)
        notch = 1 - 0.20 * math.exp(-((t - 0.5) ** 2) / 0.004)  # 中央の切れ込み
        r = radius * wave * notch
        outline.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(outline, fill=(212, 168, 60, 255))

    # 放射状のグラデーション(中心は淡く明るい金)
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for i in range(40):
        t = i / 39
        r = radius * (1 - t)
        color = (int(212 + 40 * t), int(168 + 52 * t), int(60 + 70 * t), 12)
        gdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    img = Image.alpha_composite(img, grad)

    # 葉脈(要から放射状に)
    vein = ImageDraw.Draw(img)
    for i in range(26):
        t = i / 25
        angle = a0 + (a1 - a0) * t
        r = radius * (0.98 - 0.18 * math.exp(-((t - 0.5) ** 2) / 0.004))
        x1 = cx + r * math.cos(angle) + rng.uniform(-2, 2)
        y1 = cy + r * math.sin(angle)
        vein.line([(cx, cy), (x1, y1)], fill=(255, 232, 150, 110), width=1)

    # 葉柄
    vein.line([(cx, cy), (cx, size - 2)], fill=(180, 135, 40, 255), width=3)

    # 葉の形でアルファを切り直す(グラデのはみ出しを消す)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(outline, fill=255)
    ImageDraw.Draw(mask).line([(cx, cy), (cx, size - 2)], fill=255, width=3)
    img.putalpha(mask)
    img.save(os.path.join(OUT, "ginkgo.png"))


# ---------------------------------------------------------------- 針葉の小枝

def make_needle(size=256):
    """針葉の小枝。ミップマップで痩せて消えないよう、太く密に描く。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = size // 2
    top, bottom = int(size * 0.02), int(size * 0.98)

    # 針を2層(奥は暗く、手前は明るく)で密に重ねる
    for layer, (width, alpha, bright) in enumerate([(7, 235, -30), (5, 255, 8)]):
        count = 46
        for i in range(count):
            t = i / (count - 1)
            y = top + (bottom - top) * t
            length = size * 0.46 * (0.25 + 0.75 * min(1, t * 2.2)) * (1 - 0.25 * t)
            for side in (-1, 1):
                for sub in range(2):
                    x1 = cx + side * length * rng.uniform(0.75, 1.0)
                    y1 = y + length * 0.36 + rng.uniform(-4, 4)
                    shade = rng.randint(-14, 14) + bright
                    color = (min(255, 226 + shade), min(255, 222 + shade), min(255, 206 + shade), alpha)
                    draw.line([(cx, y - layer * 2), (x1, y1)], fill=color, width=width - sub * 2)

    # 茎
    draw.line([(cx, top), (cx, bottom)], fill=(210, 200, 180, 255), width=5)
    img.save(os.path.join(OUT, "needle.png"))


# ---------------------------------------------------------------- 樹皮

def make_bark(size=512):
    height = smooth_noise(size, octaves=6, seed=3) * 0.35 + 0.5

    # 縦に走る割れ目を彫る(うねりながら下る溝)
    groove = Image.new("L", (size, size), 0)
    gdraw = ImageDraw.Draw(groove)
    for i in range(22):
        x = (i / 22) * size + rng.uniform(-8, 8)
        drift = rng.uniform(-0.25, 0.25)
        width = rng.choice([2, 2, 3, 4])
        points = []
        for y in range(0, size + 8, 8):
            x += math.sin(y * 0.02 + i) * 1.6 + drift
            points.append(((x + size) % size, y))
        gdraw.line(points, fill=rng.randint(140, 230), width=width)
    groove = groove.filter(ImageFilter.GaussianBlur(1.2))
    height = np.clip(height - (np.asarray(groove) / 255.0) * 0.55, 0, 1)

    # 節くれの隆起を少し
    knots = smooth_noise(size, octaves=3, seed=17)
    height = np.clip(height + (knots - 0.5) * 0.25, 0, 1)

    base = np.array([96, 68, 26], dtype=float)
    light = np.array([182, 140, 66], dtype=float)
    rgb = (base[None, None, :] + (light - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "bark.png"))

    # 高さ→法線マップ
    gy, gx = np.gradient(height.astype(np.float32))
    strength = 2.6
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(height)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([(nx / norm + 1) / 2, (ny / norm + 1) / 2, (nz / norm + 1) / 2], axis=-1)
    Image.fromarray((normal * 255).astype(np.uint8)).save(os.path.join(OUT, "bark_normal.png"))


# ---------------------------------------------------------------- 蓮の花びら

def make_petal(size=512):
    """蓮の花びら。UVは縦=花びらの根元(下)→先端(上)。
    白っぽい地に縦の葉脈、先端へ向けてわずかに濃くなる。実行時に四宝の色を乗算する。"""
    img = Image.new("RGB", (size, size), (250, 248, 244))
    draw = ImageDraw.Draw(img)

    # 先端(上)へ向けた濃淡グラデーション
    for y in range(size):
        t = y / size  # 0=先端, 1=根元
        # 根元は明るく、先端は少し濃い(乗算で色が深く出る)
        value = int(255 - 52 * (1 - t) ** 1.6)
        draw.line([(0, y), (size, y)], fill=(value, value - 3, max(0, value - 8)))

    # 縦の葉脈(中央から扇形にわずかに開く)
    cx = size // 2
    for i in range(22):
        offset = (i - 10.5) / 10.5  # -1..1
        x0 = cx + offset * size * 0.36
        x1 = cx + offset * size * 0.48
        shade = rng.randint(6, 20)
        points = []
        for y in range(0, size + 16, 16):
            t = y / size
            x = x0 + (x1 - x0) * (1 - t) + math.sin(y * 0.02 + i) * 1.5
            points.append((x, y))
        draw.line(points, fill=(255 - shade * 3, 252 - shade * 3, 246 - shade * 3), width=2)

    img = img.filter(ImageFilter.GaussianBlur(0.7))
    img.save(os.path.join(OUT, "petal.png"))


# ---------------------------------------------------------------- 金の敷石(橋・道用)

def make_paving(size=512, tiles=6):
    """金の敷石。目地の溝と、タイルごとのわずかな色むら。"""
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    tile = size // tiles
    for ty in range(tiles):
        for tx in range(tiles):
            v = rng.randint(-14, 14)
            base = (196 + v, 158 + v, 84 + v // 2)
            draw.rectangle([tx * tile, ty * tile, (tx + 1) * tile - 1, (ty + 1) * tile - 1], fill=base)
    # ノイズを重ねる
    noise = smooth_noise(size, octaves=5, seed=21)
    arr = np.asarray(img).astype(float)
    arr *= (0.92 + noise[:, :, None] * 0.16)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    # 目地
    draw = ImageDraw.Draw(img)
    for k in range(tiles + 1):
        p = min(k * tile, size - 1)
        draw.line([(0, p), (size, p)], fill=(120, 92, 40), width=4)
        draw.line([(p, 0), (p, size)], fill=(120, 92, 40), width=4)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(os.path.join(OUT, "paving.png"))


# ---------------------------------------------------------------- 碼碯(めのう)の縞

def make_agate(size=256):
    """基壇装飾用。朱・橙・褐色のゆらぐ縞模様。"""
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    palette = [(178, 74, 40), (206, 118, 52), (150, 84, 48), (222, 150, 84), (128, 62, 36)]
    y = 0
    k = 0
    while y < size:
        band = rng.randint(6, 22)
        color = palette[k % len(palette)]
        for yy in range(y, min(y + band, size)):
            # 縞を横方向にゆらす
            shift = int(6 * math.sin(yy * 0.05 + k))
            for x in range(size):
                v = rng.randint(-10, 10)
                img.putpixel(((x + shift) % size, yy),
                             (max(0, color[0] + v), max(0, color[1] + v), max(0, color[2] + v)))
        y += band
        k += 1
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    img.save(os.path.join(OUT, "agate.png"))


if __name__ == "__main__":
    make_ginkgo()
    make_needle()
    make_bark()
    make_petal()
    make_paving()
    make_agate()
    print("textures ->", OUT)
