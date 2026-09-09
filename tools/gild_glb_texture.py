#!/usr/bin/env python3
"""glb の基礎色テクスチャを「金一色」に染め直す(色だけ。陰影の明暗・法線・形は触らない)。

Hitem3D の坐像は螺髪・目のまわり・衣の陰が茶〜黒で焼き込まれていて、倍率を掛けても暗いまま(9/9「顔まわりが黒い」)。
各画素の明るさ L(0〜1)を取り出し、金の色 × (floor + (1-floor) × L^gamma) に置き換える。

使い方: python3 tools/gild_glb_texture.py in.glb out.glb [floor=0.45] [gamma=0.8]
"""
import io
import json
import struct
import sys

from PIL import Image

GOLD = (255, 208, 118)  # sRGB。壇の金(PURE_GOLD)に合わせた明るい金


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    floor = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
    gamma = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
    data = open(src, 'rb').read()
    json_len = struct.unpack('<I', data[12:16])[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    binary = data[bin_start:]

    base_index = gltf['materials'][0]['pbrMetallicRoughness']['baseColorTexture']['index']
    image_index = gltf['textures'][base_index]['source']
    base_view = gltf['images'][image_index]['bufferView']

    chunks = []
    for view_index, view in enumerate(gltf['bufferViews']):
        chunk = binary[view['byteOffset']:view['byteOffset'] + view['byteLength']]
        if view_index == base_view:
            image = Image.open(io.BytesIO(chunk)).convert('L')
            lut = [int(round(GOLD[c] * (floor + (1 - floor) * (v / 255) ** gamma))) for c in range(3) for v in range(256)]
            gilded = Image.merge('RGB', [image.point(lut[c * 256:(c + 1) * 256]) for c in range(3)])
            out = io.BytesIO()
            gilded.save(out, format='JPEG', quality=92, subsampling=0)
            chunk = out.getvalue()
            px = list(gilded.resize((128, 128)).getdata())
            print('gilded mean sRGB', [round(sum(p[c] for p in px) / len(px)) for c in range(3)], len(chunk), 'bytes')
        chunks.append(chunk)

    offset = 0
    out_bin = bytearray()
    for view, chunk in zip(gltf['bufferViews'], chunks):
        view['byteOffset'] = offset
        view['byteLength'] = len(chunk)
        out_bin += chunk
        padding = (-len(chunk)) % 4
        out_bin += b'\0' * padding
        offset += len(chunk) + padding
    gltf['buffers'][0]['byteLength'] = len(out_bin)
    json_bytes = json.dumps(gltf, separators=(',', ':')).encode()
    json_bytes += b' ' * ((-len(json_bytes)) % 4)
    total = 12 + 8 + len(json_bytes) + 8 + len(out_bin)
    with open(dst, 'wb') as f:
        f.write(b'glTF' + struct.pack('<II', 2, total))
        f.write(struct.pack('<I', len(json_bytes)) + b'JSON' + json_bytes)
        f.write(struct.pack('<I', len(out_bin)) + b'BIN\0' + out_bin)
    print(dst, total, 'bytes')


if __name__ == '__main__':
    main()
