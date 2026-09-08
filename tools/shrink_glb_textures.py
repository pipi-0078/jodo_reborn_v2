#!/usr/bin/env python3
"""glb に埋め込まれた画像を縮小して書き戻す(bpy 不要、pillow だけ)。形・法線・マテリアルの値は触らない。

8192² のテクスチャ 2 枚(RGBA + ミップで約 700MB)は、ギャラリー単体では映るが、メイン空間では
他のテクスチャと合わせて GPU メモリを超えて生成に失敗し、像が真っ黒になる(9/8)。

使い方: python3 tools/shrink_glb_textures.py in.glb out.glb <最大辺> [画像index=最大辺 ...]
  例: python3 tools/shrink_glb_textures.py a.glb b.glb 4096 1=2048   (画像1 だけ 2048)
"""
import io
import json
import struct
import sys

from PIL import Image


def main() -> None:
    src, dst, default_max = sys.argv[1], sys.argv[2], int(sys.argv[3])
    per_image = {int(k): int(v) for k, v in (a.split('=') for a in sys.argv[4:])}
    data = open(src, 'rb').read()
    json_len = struct.unpack('<I', data[12:16])[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    binary = data[bin_start:]

    image_views = {img['bufferView']: i for i, img in enumerate(gltf.get('images', []))}
    new_chunks = []
    for view_index, view in enumerate(gltf['bufferViews']):
        chunk = binary[view['byteOffset']:view['byteOffset'] + view['byteLength']]
        if view_index in image_views:
            image_index = image_views[view_index]
            limit = per_image.get(image_index, default_max)
            image = Image.open(io.BytesIO(chunk))
            width, height = image.size
            if max(width, height) > limit:
                scale = limit / max(width, height)
                image = image.convert('RGB').resize((round(width * scale), round(height * scale)), Image.LANCZOS)
                out = io.BytesIO()
                image.save(out, format='JPEG', quality=92, subsampling=0)
                chunk = out.getvalue()
                gltf['images'][image_index]['mimeType'] = 'image/jpeg'
            print(f'image {image_index}: {width}x{height} -> {image.size[0]}x{image.size[1]}, {view["byteLength"]} -> {len(chunk)} bytes')
        new_chunks.append(chunk)

    offset = 0
    out_bin = bytearray()
    for view, chunk in zip(gltf['bufferViews'], new_chunks):
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
