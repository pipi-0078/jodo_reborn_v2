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

def make_paving(size=512, tiles=8):
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
        draw.line([(0, p), (size, p)], fill=(120, 92, 40), width=3)
        draw.line([(p, 0), (p, size)], fill=(120, 92, 40), width=3)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(os.path.join(OUT, "paving.png"))


# ---------------------------------------------------------------- 碼碯(めのう)の縞

def make_agate(size=512):
    """基壇装飾用。朱・橙・褐色のゆらぐ縞模様。"""
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    palette = [(178, 74, 40), (206, 118, 52), (150, 84, 48), (222, 150, 84), (128, 62, 36)]
    y = 0
    k = 0
    while y < size:
        band = rng.randint(7, 26)
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


# ---------------------------------------------------------------- 法線マップ共通

def height_to_normal(height, strength=2.4):
    gy, gx = np.gradient(height.astype(np.float32))
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(height)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([(nx / norm + 1) / 2, (ny / norm + 1) / 2, (nz / norm + 1) / 2], axis=-1)
    return Image.fromarray((normal * 255).astype(np.uint8))


# ---------------------------------------------------------------- 七宝繋ぎ文様(金の壁板)

def make_shippo_panel(size=512):
    """重なる円環の伝統文様「七宝繋ぎ」。金の浮彫り+法線マップ。"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = size // 6
    height = np.zeros((size, size), dtype=np.float32)
    sigma = size * 0.006
    centers = []
    for cx in range(0, size + 1, r * 2):
        for cy in range(0, size + 1, r * 2):
            centers += [(cx, cy), (cx + r, cy + r)]
    for cx, cy in centers:
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        ring = np.exp(-((d - r * 0.98) ** 2) / (2 * sigma ** 2))
        # 外環のすぐ内側に細い副環を沿わせる(二重の彫り)
        ring2 = np.exp(-((d - r * 0.80) ** 2) / (2 * (sigma * 0.7) ** 2)) * 0.55
        # 中心に小さな珠
        dot = np.exp(-(d ** 2) / (2 * (r * 0.10) ** 2)) * 0.85
        height = np.maximum.reduce([height, ring, ring2, dot])
    base = np.array([188, 146, 66], dtype=float)
    lit = np.array([236, 202, 120], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "shippo.png"))
    height_to_normal(height, 3.0).save(os.path.join(OUT, "shippo_normal.png"))


# ---------------------------------------------------------------- 丸瓦の列(瑠璃の屋根)

def make_roof_tiles(size=512, rows=11):
    """丸瓦が重なって葺かれた屋根面。深い瑠璃+法線マップ。"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rh = size / rows
    tw = size / 14
    height = np.zeros((size, size), dtype=np.float32)
    for row in range(rows + 1):
        edge_y = row * rh  # この行の瓦の裾(下端)
        offset = (row % 2) * tw / 2
        for k in range(-1, 15):
            cx = k * tw + offset
            d = np.sqrt((xx - cx) ** 2 + ((yy - edge_y) * 1.6) ** 2)
            bump = np.clip(1 - d / (tw * 0.62), 0, 1) ** 1.4
            mask = (yy <= edge_y + rh * 0.12)
            height = np.maximum(height, np.where(mask, bump, 0))
    base = np.array([22, 44, 116], dtype=float)
    lit = np.array([96, 132, 214], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "roof_tiles.png"))
    height_to_normal(height, 2.6).save(os.path.join(OUT, "roof_tiles_normal.png"))


# ---------------------------------------------------------------- 金の柱(縦の筋)

def make_column_gold(size=512):
    """金の柱身。浅い縦筋と磨きむら。"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    flutes = (np.sin(xx / size * math.pi * 28) * 0.5 + 0.5) ** 1.8
    fine = (np.sin(xx / size * math.pi * 112) * 0.5 + 0.5) * 0.12
    grain = smooth_noise(size, octaves=6, seed=31) * 0.30
    height = np.clip(flutes * 0.66 + fine + grain, 0, 1)
    base = np.array([176, 132, 54], dtype=float)
    lit = np.array([232, 194, 108], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "column_gold.png"))
    height_to_normal(height, 1.6).save(os.path.join(OUT, "column_gold_normal.png"))




# ---------------------------------------------------------------- 唐草文様(黄金楼の壁)

def make_karakusa(size=1024):
    """蔓が波打ち、渦を巻く唐草文様。金の浮彫り+法線マップ。横に完全に繋がる。"""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    band = size // 4
    per = size // 4

    def spiral(cx, cy, r0, sgn, phase):
        pts = []
        for k in range(110):
            t = k / 109
            r = r0 * (1 - 0.90 * t)
            a = sgn * (t * 2.6 * 2 * math.pi) + phase
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        draw.line(pts, fill=255, width=9)
        # 渦の芯に珠
        ex, ey = pts[-1]
        draw.ellipse([ex - 7, ey - 7, ex + 7, ey + 7], fill=255)

    for row in range(4):
        cy = row * band + band // 2
        amp = band * 0.16
        ph = row * math.pi / 2
        # 波打つ蔓(横にループが繋がるようにsin一周期×4)
        pts = [(x, cy + amp * math.sin(2 * math.pi * x / per + ph)) for x in range(-8, size + 9, 4)]
        draw.line(pts, fill=255, width=10)
        for k in range(4):
            # 山と谷から渦が伸びる
            xc1 = (k * per + per * 0.25 - ph / (2 * math.pi) * per) % size
            xc2 = (k * per + per * 0.75 - ph / (2 * math.pi) * per) % size
            spiral(xc1, cy - band * 0.27, band * 0.235, -1, math.pi / 2)
            spiral(xc2, cy + band * 0.27, band * 0.235, 1, -math.pi / 2)
        # 蔓に沿う小さな葉
        for k in range(16):
            x = (k * size / 16 + per / 8) % size
            y = cy + amp * math.sin(2 * math.pi * x / per + ph)
            draw.ellipse([x - 6, y - 13, x + 6, y + 13], outline=255, width=4)
    img = img.filter(ImageFilter.GaussianBlur(2.2))
    height = np.asarray(img).astype(np.float32) / 255
    base = np.array([148, 106, 40], dtype=float)
    lit = np.array([255, 226, 150], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "karakusa.png"))
    height_to_normal(height, 3.2).save(os.path.join(OUT, "karakusa_normal.png"))


# ---------------------------------------------------------------- 花菱格子(基壇・軒裏)

def make_hanabishi(size=1024, cells=8):
    """斜め格子に四弁の花菱を打った文様。完全に繋がる。"""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    p = size // cells
    for k in range(-cells, cells * 2 + 1):
        draw.line([(k * p, 0), (k * p + size, size)], fill=210, width=5)
        draw.line([(k * p, size), (k * p + size, 0)], fill=210, width=5)
    # 菱の中心に四弁花
    for i in range(cells):
        for j in range(cells):
            cx, cy = i * p + p // 2, j * p + p // 2
            r = p * 0.16
            for ang in (0, 90, 180, 270):
                a = math.radians(ang)
                px, py = cx + r * math.cos(a), cy + r * math.sin(a)
                draw.ellipse([px - p * 0.085, py - p * 0.085, px + p * 0.085, py + p * 0.085], fill=255)
            draw.ellipse([cx - p * 0.06, cy - p * 0.06, cx + p * 0.06, cy + p * 0.06], fill=140)
    img = img.filter(ImageFilter.GaussianBlur(1.8))
    height = np.asarray(img).astype(np.float32) / 255
    base = np.array([155, 112, 44], dtype=float)
    lit = np.array([252, 220, 138], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "hanabishi.png"))
    height_to_normal(height, 2.8).save(os.path.join(OUT, "hanabishi_normal.png"))


# ---------------------------------------------------------------- 蓮弁の帯(基壇の縁)

def make_renben(size=1024):
    """基壇を巡る蓮の花弁の帯。二重の弁が重なる。横に繋がる。"""
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    n = 8
    w = size // n
    # 奥の弁(半つ割りずらし)
    for k in range(n + 1):
        cx = k * w - w // 2
        draw.pieslice([cx - w * 0.46, size * 0.30, cx + w * 0.46, size * 1.45], 180, 360, fill=110)
        draw.arc([cx - w * 0.46, size * 0.30, cx + w * 0.46, size * 1.45], 180, 360, fill=170, width=8)
    # 手前の弁
    for k in range(n):
        cx = k * w + w // 2
        draw.pieslice([cx - w * 0.47, size * 0.12, cx + w * 0.47, size * 1.55], 180, 360, fill=200)
        draw.arc([cx - w * 0.47, size * 0.12, cx + w * 0.47, size * 1.55], 180, 360, fill=255, width=10)
        # 弁の中の脈
        draw.arc([cx - w * 0.28, size * 0.30, cx + w * 0.28, size * 1.40], 200, 340, fill=255, width=5)
    img = img.filter(ImageFilter.GaussianBlur(2.0))
    height = np.asarray(img).astype(np.float32) / 255
    base = np.array([150, 108, 42], dtype=float)
    lit = np.array([255, 228, 152], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "renben.png"))
    height_to_normal(height, 3.0).save(os.path.join(OUT, "renben_normal.png"))


# ---------------------------------------------------------------- 金瓦(黄金楼の屋根)

def make_gold_tiles(size=1024, rows=13):
    """金の丸瓦。青瓦と同じ葺きで、色だけ黄金。"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rh = size / rows
    tw = size / 16
    height = np.zeros((size, size), dtype=np.float32)
    for row in range(rows + 1):
        edge_y = row * rh
        offset = (row % 2) * tw / 2
        for k in range(-1, 18):
            cx = k * tw + offset
            d = np.sqrt((xx - cx) ** 2 + ((yy - edge_y) * 1.6) ** 2)
            bump = np.clip(1 - d / (tw * 0.62), 0, 1) ** 1.4
            mask = (yy <= edge_y + rh * 0.12)
            height = np.maximum(height, np.where(mask, bump, 0))
    base = np.array([112, 74, 22], dtype=float)
    lit = np.array([226, 178, 92], dtype=float)
    rgb = (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)
    Image.fromarray(rgb).save(os.path.join(OUT, "gold_tiles.png"))
    height_to_normal(height, 2.6).save(os.path.join(OUT, "gold_tiles_normal.png"))


# ================================================================ 材質そのものの表情
# (文様ではなく、金という素材の細かな描写。箔足・皺・鎚目・磨き傷)

def tileable_noise(size, octaves=5, seed=0):
    """継ぎ目が出にくいノイズ(端が巻き付くように格子を作ってから拡大)。"""
    r = np.random.default_rng(seed)
    acc = np.zeros((size, size))
    for o in range(octaves):
        n = 2 ** (o + 2)
        layer = r.random((n, n))
        layer = np.pad(layer, ((0, 1), (0, 1)), mode="wrap")
        img = Image.fromarray((layer * 255).astype(np.uint8)).resize((size + 1, size + 1), Image.BICUBIC)
        acc += (np.asarray(img)[:size, :size] / 255.0) * (0.5 ** o)
    acc -= acc.min()
    return acc / acc.max()


def _wrap_draw(draw, size, fn):
    """要素を9方向に複製して描き、タイルの継ぎ目で切れないようにする。"""
    for dy in (-size, 0, size):
        for dx in (-size, 0, size):
            fn(dx, dy)


def _gold_shade(height, base, lit):
    base = np.array(base, dtype=float)
    lit = np.array(lit, dtype=float)
    return (base[None, None, :] + (lit - base)[None, None, :] * height[:, :, None]).astype(np.uint8)


def make_kinpaku(size=1024, sheets=5):
    """金箔押しの面。箔足(箔の継ぎ目)、箔ごとの濃淡、細かな皺と擦れ。"""
    r = random.Random(101)
    cloud = tileable_noise(size, octaves=6, seed=201)
    grain = tileable_noise(size, octaves=8, seed=202)

    # 箔ごとのわずかな濃淡(規則的に見えないよう、行ごとに継ぎ目をずらす)
    tone = np.zeros((size, size), dtype=np.float32)
    step = size / sheets
    offs = [r.uniform(-0.22, 0.22) * step for _ in range(sheets)]
    for i in range(sheets):
        y0, y1 = int(i * step), int((i + 1) * step)
        for j in range(-1, sheets + 1):
            x0 = int(j * step + offs[i])
            x1 = int((j + 1) * step + offs[i])
            v = r.uniform(-1.0, 1.0)
            xa, xb = max(0, x0), min(size, x1)
            if xb > xa:
                tone[y0:y1, xa:xb] = v

    # 箔足: わずかに盛り上がる継ぎ目。切れ切れにして格子に見せない
    seam_img = Image.new("L", (size, size), 0)
    sd = ImageDraw.Draw(seam_img)

    def wobble(p0, p1, amp=2.6, n=26):
        pts = []
        for k in range(n + 1):
            t = k / n
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            pts.append((x + r.uniform(-amp, amp), y + r.uniform(-amp, amp)))
        return pts

    for i in range(sheets + 1):
        y = i * step
        for j in range(-1, sheets + 1):
            if r.random() < 0.18:      # ところどころ継ぎ目が見えない
                continue
            x0 = j * step + offs[i % sheets]
            _wrap_draw(sd, size, lambda dx, dy, x0=x0, y=y:
                       sd.line([(px + dx, py + dy) for px, py in
                                wobble((x0, y), (x0 + step, y))],
                               fill=r.randint(90, 190), width=r.choice([2, 3])))
    for i in range(sheets):
        for j in range(-1, sheets + 1):
            if r.random() < 0.22:
                continue
            x = j * step + offs[i]
            y0 = i * step
            _wrap_draw(sd, size, lambda dx, dy, x=x, y0=y0:
                       sd.line([(px + dx, py + dy) for px, py in
                                wobble((x, y0), (x, y0 + step))],
                               fill=r.randint(90, 190), width=r.choice([2, 3])))
    seam = np.asarray(seam_img.filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32) / 255

    # 箔の皺: 細いノイズの尾根を拾う
    fine = tileable_noise(size, octaves=7, seed=203)
    gy, gx = np.gradient(fine)
    wrinkle = np.clip(np.sqrt(gx * gx + gy * gy) * 26 - 0.55, 0, 1) ** 1.5

    # 擦れ傷
    scr_img = Image.new("L", (size, size), 0)
    cd = ImageDraw.Draw(scr_img)
    for _ in range(520):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = r.uniform(0, math.pi)
        L = r.uniform(size * 0.01, size * 0.09)
        _wrap_draw(cd, size, lambda dx, dy, x=x, y=y, a=a, L=L:
                   cd.line([(x - L * math.cos(a) / 2 + dx, y - L * math.sin(a) / 2 + dy),
                            (x + L * math.cos(a) / 2 + dx, y + L * math.sin(a) / 2 + dy)],
                           fill=r.randint(40, 120), width=1))
    scratch = np.asarray(scr_img.filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 255

    height = np.clip(0.42 + seam * 0.30 + wrinkle * 0.26 + grain * 0.10 - scratch * 0.16, 0, 1)
    shade = np.clip(0.60 + (cloud - 0.5) * 0.16 + tone * 0.05 + seam * 0.13
                    + wrinkle * 0.16 - scratch * 0.11, 0, 1)
    Image.fromarray(_gold_shade(shade, (152, 108, 38), (255, 236, 176))).save(
        os.path.join(OUT, "kinpaku.png"))
    height_to_normal(height, 1.6).save(os.path.join(OUT, "kinpaku_normal.png"))


def make_tsuchime(size=1024, dimples=520):
    """鎚目(つちめ)。金鎚で打ち出した無数のくぼみが重なる面。"""
    r = random.Random(303)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    height = np.zeros((size, size), dtype=np.float32)
    for _ in range(dimples):
        cx, cy = r.uniform(0, size), r.uniform(0, size)
        rad = r.uniform(size * 0.032, size * 0.062)
        depth = r.uniform(0.55, 1.0)
        for dx in (-size, 0, size):
            for dy in (-size, 0, size):
                if abs(cx + dx - size / 2) > size / 2 + rad or abs(cy + dy - size / 2) > size / 2 + rad:
                    continue
                d = np.sqrt((xx - cx - dx) ** 2 + (yy - cy - dy) ** 2)
                bowl = np.clip(1 - (d / rad) ** 2, 0, 1)
                height = np.minimum(height, -bowl * depth * 0.5) if False else \
                    np.where(bowl > 0, np.minimum(height, -bowl * depth), height)
    height = height - height.min()
    height = height / max(height.max(), 1e-6)
    # 打ち跡の縁をなめらかにして、金物らしい柔らかな起伏にする
    height = np.asarray(Image.fromarray((height * 255).astype(np.uint8))
                        .filter(ImageFilter.GaussianBlur(size / 220))).astype(np.float32) / 255
    grain = tileable_noise(size, octaves=7, seed=304)
    height = np.clip(height * 0.88 + grain * 0.12, 0, 1)
    shade = np.clip(0.68 + (height - 0.5) * 0.15 + (grain - 0.5) * 0.05, 0, 1)
    Image.fromarray(_gold_shade(shade, (140, 98, 32), (255, 230, 160))).save(
        os.path.join(OUT, "tsuchime.png"))
    height_to_normal(height, 3.0).save(os.path.join(OUT, "tsuchime_normal.png"))


def make_migaki(size=1024):
    """磨き金。縦方向の細かな研ぎ目と、うっすらした曇り。ほぼ平滑。"""
    r = random.Random(505)
    rr = np.random.default_rng(506)
    # 縦の研ぎ目: 1次元ノイズを縦に引き伸ばす
    line = rr.random(size)
    brush = np.tile(line, (size, 1))
    brush = np.asarray(Image.fromarray((brush * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
    cloud = tileable_noise(size, octaves=5, seed=507)
    scr_img = Image.new("L", (size, size), 0)
    cd = ImageDraw.Draw(scr_img)
    for _ in range(260):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = math.pi / 2 + r.uniform(-0.10, 0.10)
        L = r.uniform(size * 0.05, size * 0.35)
        _wrap_draw(cd, size, lambda dx, dy, x=x, y=y, a=a, L=L:
                   cd.line([(x - L * math.cos(a) / 2 + dx, y - L * math.sin(a) / 2 + dy),
                            (x + L * math.cos(a) / 2 + dx, y + L * math.sin(a) / 2 + dy)],
                           fill=r.randint(30, 110), width=1))
    scratch = np.asarray(scr_img.filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
    height = np.clip(0.5 + (brush - 0.5) * 0.22 - scratch * 0.20, 0, 1)
    shade = np.clip(0.56 + (brush - 0.5) * 0.14 + (cloud - 0.5) * 0.20 - scratch * 0.10, 0, 1)
    Image.fromarray(_gold_shade(shade, (132, 92, 30), (255, 230, 158))).save(
        os.path.join(OUT, "migaki.png"))
    height_to_normal(height, 0.9).save(os.path.join(OUT, "migaki_normal.png"))


def make_hameita(size=2048, planks=12):
    """金の羽目板張り。板の継ぎ目(目地)と面取り、板ごとの濃淡、板端の継ぎ、
    そのうえに金箔の箔足と皺と擦れ。壁が「ただの面」にならないための主材。"""
    r = random.Random(707)
    cloud = tileable_noise(size, octaves=6, seed=701)
    grain = tileable_noise(size, octaves=8, seed=702)

    pw = size / planks
    xs = np.arange(size, dtype=np.float32)[None, :]

    # 板ごとの濃淡
    tone = np.zeros((size, size), dtype=np.float32)
    for j in range(planks):
        tone[:, int(j * pw):int((j + 1) * pw)] = r.uniform(-1.0, 1.0)

    # 目地(彫り込み)と面取り(左右の稜)
    groove = np.zeros((size, size), dtype=np.float32)
    bevel = np.zeros((size, size), dtype=np.float32)
    gw = max(2.0, size * 0.0022)      # 目地の幅
    bw = max(3.0, size * 0.0050)      # 面取りの幅
    for j in range(planks + 1):
        cx = j * pw
        d = np.abs(((xs - cx + size / 2) % size) - size / 2)
        groove = np.maximum(groove, np.clip(1 - d / gw, 0, 1))
        edge = np.clip(1 - np.abs(d - (gw + bw * 0.5)) / (bw * 0.5), 0, 1)
        side = np.sign(((xs - cx + size / 2) % size) - size / 2)
        bevel = bevel + edge * side * 0.5
    groove = np.repeat(groove, size, axis=0) if groove.shape[0] == 1 else groove
    bevel = np.repeat(bevel, size, axis=0) if bevel.shape[0] == 1 else bevel

    # 板端の継ぎ(横目地)。板ごとに高さを変えて規則性を消す
    butt_img = Image.new("L", (size, size), 0)
    bd = ImageDraw.Draw(butt_img)
    for j in range(planks):
        for _ in range(r.choice([0, 1, 1, 2])):
            y = r.uniform(size * 0.12, size * 0.88)
            x0, x1 = j * pw + gw, (j + 1) * pw - gw
            bd.line([(x0, y), (x1, y)], fill=255, width=int(gw) + 1)
    butt = np.asarray(butt_img.filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255

    # 金箔の表情(箔足・皺・擦れ)を板の上に重ねる
    fine = tileable_noise(size, octaves=7, seed=703)
    gy, gx = np.gradient(fine)
    wrinkle = np.clip(np.sqrt(gx * gx + gy * gy) * 30 - 0.6, 0, 1) ** 1.5
    scr_img = Image.new("L", (size, size), 0)
    cd = ImageDraw.Draw(scr_img)
    for _ in range(900):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = r.uniform(0, math.pi)
        L = r.uniform(size * 0.006, size * 0.05)
        _wrap_draw(cd, size, lambda dx, dy, x=x, y=y, a=a, L=L:
                   cd.line([(x - L * math.cos(a) / 2 + dx, y - L * math.sin(a) / 2 + dy),
                            (x + L * math.cos(a) / 2 + dx, y + L * math.sin(a) / 2 + dy)],
                           fill=r.randint(35, 110), width=1))
    scratch = np.asarray(scr_img.filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 255

    cut = np.maximum(groove, butt)
    height = np.clip(0.56 - cut * 0.50 + bevel * 0.10
                     + wrinkle * 0.13 + (grain - 0.5) * 0.09 - scratch * 0.10, 0, 1)
    shade = np.clip(0.64 - cut * 0.42 + bevel * 0.13 + tone * 0.045
                    + (cloud - 0.5) * 0.13 + wrinkle * 0.12 - scratch * 0.09, 0, 1)
    Image.fromarray(_gold_shade(shade, (146, 102, 34), (255, 234, 170))).save(
        os.path.join(OUT, "hameita.png"))
    height_to_normal(height, 2.6).save(os.path.join(OUT, "hameita_normal.png"))


if __name__ == "__main__":
    make_ginkgo()
    make_needle()
    make_bark()
    make_petal()
    make_paving()
    make_agate()
    make_shippo_panel()
    make_roof_tiles()
    make_column_gold()
    make_karakusa()
    make_hanabishi()
    make_renben()
    make_gold_tiles()
    make_kinpaku()
    make_tsuchime()
    make_migaki()
    make_hameita()
    print("textures ->", OUT)
