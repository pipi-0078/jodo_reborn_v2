"""ヘッドレスの bpy モジュールで MPFB2(MakeHuman Plugin For Blender)を使えるようにする。

MPFB2 は GPL-3.0 のアドオン(ベースメッシュとターゲットは CC0)。
    git clone --depth 1 https://github.com/makehumancommunity/mpfb2 <どこか>
してから、環境変数 MPFB_SRC にその <どこか>/src/mpfb を渡す(既定はスクラッチパッド)。

bpy のアドオン機構は拡張(bl_ext.<repo>.<name>)としての読み込みを要求するので、
ユーザー拡張ディレクトリへシンボリックリンクを張り、preferences への登録を先に済ませてから register() する。
"""
import importlib
import logging
import os
import sys

import bpy  # noqa: F401  (addon_utils は bpy の後でないと見つからない)
import addon_utils  # noqa: E402

MPFB_SRC = os.environ.get(
    "MPFB_SRC",
    "/tmp/claude-0/-home-user-jodo-reborn-v2/99555b29-dbc6-57ef-840e-5178dab97e8a/scratchpad/mpfb2/src/mpfb",
)
MODULE = "bl_ext.user_default.mpfb"


def bootstrap():
    """MPFB を登録し、サービス群(HumanService など)を返す。"""
    logging.disable(logging.CRITICAL)
    ext_dir = bpy.utils.user_resource("EXTENSIONS", path="user_default", create=True)
    link = os.path.join(ext_dir, "mpfb")
    if not os.path.exists(link):
        os.symlink(MPFB_SRC, link)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils._addon_ensure(MODULE)
    addon_utils.modules(refresh=True)
    mod = importlib.import_module(MODULE)
    mod.register()
    services = {}
    for name in ("humanservice.HumanService", "targetservice.TargetService", "rigservice.RigService",
                 "objectservice.ObjectService", "locationservice.LocationService"):
        file, cls = name.split(".")
        services[cls] = getattr(importlib.import_module(f"{MODULE}.services.{file}"), cls)
    return services


if __name__ == "__main__":
    s = bootstrap()
    print("MPFB ready:", sorted(s.keys()), file=sys.stderr)
