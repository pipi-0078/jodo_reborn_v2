#!/usr/bin/env python3
"""キャラクターシート(正面・左側面・背面)から阿弥陀如来坐像を image-to-3D で起こす。

fal.ai の Hunyuan3D v2 multi-view を叩く。LESSONS.md 2-1「有機的な造形はゼロから作らない」
および 4-6「キャラクターシートから image-to-3D」の続き。

使い方:
    export FAL_KEY=...
    python3 tools/make_amida_hunyuan.py \
        --front refs/amida_front.png --left refs/amida_left.png --back refs/amida_back.png \
        --out public/assets/amida_hunyuan.glb

引数はローカルパスでも http(s) URL でもよい。ローカルなら fal のストレージへ上げてから使う。
--mirror-left は「像が画面左を向いた写真」(=右側面)しかないときに左右反転して左側面に仕立てる。
出力後にワールド寸法を数値で表示する(スクショで確かめない。LESSONS.md 2-4)。
"""
import argparse
import json
import mimetypes
import os
import struct
import sys
import time
import urllib.request

QUEUE = "https://queue.fal.run/fal-ai/hunyuan3d/v2/multi-view"
INITIATE = "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3"


def _key():
    key = os.environ.get("FAL_KEY")
    if not key:
        sys.exit("FAL_KEY が未設定")
    return key


def _req(url, data=None, method=None, headers=None, raw=False):
    body = None
    hdrs = {"Authorization": "Key " + _key()}
    if data is not None:
        body = data if raw else json.dumps(data).encode()
        hdrs["Content-Type"] = headers["Content-Type"] if headers else "application/json"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=300) as res:
        return json.loads(res.read())


def upload(path):
    """ローカル画像を fal ストレージへ上げて公開 URL を返す。"""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    ctype = mimetypes.guess_type(path)[0] or "image/png"
    init = _req(INITIATE, {"content_type": ctype, "file_name": os.path.basename(path)})
    with open(path, "rb") as f:
        blob = f.read()
    req = urllib.request.Request(
        init["upload_url"], data=blob, headers={"Content-Type": ctype}, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=300):
        pass
    print(f"  upload {os.path.basename(path)} ({len(blob)//1024}KB) -> {init['file_url']}")
    return init["file_url"]


def mirror(path, out):
    """左右反転(右側面しかないときに左側面を作る)。"""
    from PIL import Image

    Image.open(path).transpose(Image.FLIP_LEFT_RIGHT).save(out)
    print(f"  mirror {os.path.basename(path)} -> {out}")
    return out


def submit(payload):
    job = _req(QUEUE, payload)
    rid = job["request_id"]
    print(f"  request_id: {rid}")
    base = f"https://queue.fal.run/fal-ai/hunyuan3d/requests/{rid}"
    last = None
    for _ in range(360):  # 最大 30 分
        st = _req(base + "/status")["status"]
        if st != last:
            print(f"  {st}")
            last = st
        if st == "COMPLETED":
            return _req(base)
        time.sleep(5)
    sys.exit("タイムアウト")


def glb_bounds(path):
    """glb の全 POSITION アクセサの min/max からワールド寸法を出す(数値で検品)。"""
    with open(path, "rb") as f:
        buf = f.read()
    off, jsn = 12, None
    while off < len(buf):
        clen, ctype = struct.unpack_from("<I4s", buf, off)
        if ctype == b"JSON":
            jsn = json.loads(buf[off + 8 : off + 8 + clen])
            break
        off += 8 + clen + (-clen % 4)
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    tris = 0
    for mesh in jsn.get("meshes", []):
        for prim in mesh.get("primitives", []):
            acc = jsn["accessors"][prim["attributes"]["POSITION"]]
            for i in range(3):
                lo[i] = min(lo[i], acc["min"][i])
                hi[i] = max(hi[i], acc["max"][i])
            if "indices" in prim:
                tris += jsn["accessors"][prim["indices"]]["count"] // 3
    return lo, hi, tris, len(jsn.get("materials", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", required=True)
    ap.add_argument("--left", required=True)
    ap.add_argument("--back", required=True)
    ap.add_argument("--out", default="public/assets/amida_hunyuan.glb")
    ap.add_argument("--mirror-left", action="store_true", help="--left が右側面のとき反転する")
    ap.add_argument("--no-texture", action="store_true", help="形だけ生成(金一色は後で当てる)")
    ap.add_argument("--octree", type=int, default=256, help="オクツリー解像度(彫りの細かさ)")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--guidance", type=float, default=7.5)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()

    left = a.left
    if a.mirror_left:
        left = mirror(left, os.path.join(os.path.dirname(a.out) or ".", "_left_mirrored.png"))

    print("画像を fal へ:")
    payload = {
        "front_image_url": upload(a.front),
        "left_image_url": upload(left),
        "back_image_url": upload(a.back),
        "textured_mesh": not a.no_texture,
        "octree_resolution": a.octree,
        "num_inference_steps": a.steps,
        "guidance_scale": a.guidance,
    }
    if a.seed is not None:
        payload["seed"] = a.seed

    print("Hunyuan3D v2 multi-view:")
    res = submit(payload)
    url = res["model_mesh"]["url"]
    print(f"  seed: {res.get('seed')}")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    urllib.request.urlretrieve(url, a.out)
    size = os.path.getsize(a.out)

    lo, hi, tris, mats = glb_bounds(a.out)
    dim = [hi[i] - lo[i] for i in range(3)]
    print(f"\n{a.out}  {size/1e6:.1f}MB  {tris}tris  materials={mats}")
    print(f"  bounds min ({lo[0]:.3f}, {lo[1]:.3f}, {lo[2]:.3f})")
    print(f"         max ({hi[0]:.3f}, {hi[1]:.3f}, {hi[2]:.3f})")
    print(f"  size W{dim[0]:.3f} H{dim[1]:.3f} D{dim[2]:.3f}")
    print("  ※ 配置前にスケールを合わせる。マテリアルは台座と同一(LESSONS.md 2-3)")


if __name__ == "__main__":
    main()
