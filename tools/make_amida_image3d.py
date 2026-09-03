#!/usr/bin/env python3
"""キャラクターシート(正面・左側面・背面)から阿弥陀如来坐像を image-to-3D で起こす。

fal.ai の三面対応エンジンを叩く。LESSONS.md 2-1「有機的な造形はゼロから作らない」
および 4-6「キャラクターシートから image-to-3D」の続き。

エンジン(--engine):
    trellis  fal-ai/trellis/multi          螺髪・白毫・宝珠が形になる。顔も彫れる(9/3 採用)
    rodin    fal-ai/hyper3d/rodin          顔が最も整う。螺髪は模様止まり。9万tris
    hunyuan  fal-ai/hunyuan3d/v2/multi-view 4万tris で頭打ち。顔が崩れる

使い方:
    export FAL_KEY=...
    python3 tools/make_amida_image3d.py --engine trellis \
        --front refs/amida_front.png --left refs/amida_left.png --back refs/amida_back.png \
        --out public/assets/amida_trellis.glb

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
import urllib.error
import urllib.request

ENGINES = {
    "trellis": "fal-ai/trellis/multi",
    "rodin": "fal-ai/hyper3d/rodin",
    "hunyuan": "fal-ai/hunyuan3d/v2/multi-view",
}
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
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:  # 422 は本文に理由が入る。握り潰さない
        sys.exit(f"{e.code} {e.reason}\n{e.read().decode(errors='replace')[:800]}")


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


def submit(engine, payload):
    job = _req("https://queue.fal.run/" + ENGINES[engine], payload)
    print(f"  request_id: {job['request_id']}")
    last = None
    for _ in range(360):  # 最大 30 分
        st = _req(job["status_url"])["status"]  # URL は応答のものを使う(自分で組むと 404 する)
        if st != last:
            print(f"  {st}")
            last = st
        if st == "COMPLETED":
            return _req(job["response_url"])
        time.sleep(5)
    sys.exit("タイムアウト")


def find_glb(obj):
    """応答のどこかにある .glb の URL を拾う(エンジンごとにキーが違う)。"""
    if isinstance(obj, dict):
        if str(obj.get("url", "")).endswith(".glb"):
            return obj["url"]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            u = find_glb(v)
            if u:
                return u
    return None


def build_payload(engine, a, front, left, back):
    if engine == "hunyuan":
        p = {"front_image_url": front, "left_image_url": left, "back_image_url": back,
             "textured_mesh": not a.no_texture, "octree_resolution": a.octree,
             "num_inference_steps": a.steps, "guidance_scale": a.guidance}
    elif engine == "rodin":
        # addons は配列ではなく文字列 "HighPack"(配列だと 422)
        p = {"input_image_urls": [front, left, back], "condition_mode": "concat",
             "quality": "high", "addons": "HighPack", "material": "PBR",
             "geometry_file_format": "glb", "tier": "Regular"}
    else:  # trellis: mesh_simplify は 0.9 以上しか受けない
        p = {"image_urls": [front, left, back], "mesh_simplify": 0.9, "texture_size": 2048,
             "multiimage_algo": "multidiffusion", "ss_sampling_steps": 20, "slat_sampling_steps": 20}
    if a.seed is not None:
        p["seed"] = a.seed
    return p


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
    ap.add_argument("--engine", choices=list(ENGINES), default="trellis")
    ap.add_argument("--out", default="public/assets/amida_trellis.glb")
    ap.add_argument("--mirror-left", action="store_true", help="--left が右側面のとき反転する")
    ap.add_argument("--no-texture", action="store_true", help="[hunyuan] 形だけ生成")
    ap.add_argument("--octree", type=int, default=512, help="[hunyuan] オクツリー解像度(1-1024)")
    ap.add_argument("--steps", type=int, default=50, help="[hunyuan] 推論ステップ(1-50。超えると422)")
    ap.add_argument("--guidance", type=float, default=7.5, help="[hunyuan] ガイダンス(0-20)")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.engine == "hunyuan":  # アップロード前に範囲を確かめる(422 は本文を読むまで分からない)
        for name, val, lo, hi in (("--octree", a.octree, 1, 1024), ("--steps", a.steps, 1, 50),
                                  ("--guidance", a.guidance, 0, 20)):
            if not lo <= val <= hi:
                sys.exit(f"{name} は {lo}〜{hi} の範囲(指定: {val})")
    left = a.left
    if a.mirror_left:
        left = mirror(left, os.path.join(os.path.dirname(a.out) or ".", "_left_mirrored.png"))

    print("画像を fal へ:")
    payload = build_payload(a.engine, a, upload(a.front), upload(left), upload(a.back))

    print(f"{ENGINES[a.engine]}:")
    res = submit(a.engine, payload)
    url = find_glb(res)
    if not url:
        sys.exit("応答に glb が無い: " + json.dumps(res)[:500])
    if "seed" in res:
        print(f"  seed: {res['seed']}")

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
