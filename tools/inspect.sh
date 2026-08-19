#!/usr/bin/env bash
# 検品用スクショを縮小して出力する(私が目視する画像のトークンを1/4に)。
# 使い方: tools/inspect.sh <入力png> [幅=640]
# 施主に送る画像は縮小しないこと(SendUserFileの画像はコンテキストを消費しない)。
set -euo pipefail
src="$1"; width="${2:-640}"
out="${src%.png}_s.png"
python3 -c "
from PIL import Image; import sys
im=Image.open('$src'); w,h=im.size
im.resize(($width, int(h*$width/w)), Image.LANCZOS).save('$out')
print('$out', f'{$width}x{int(h*$width/w)}', f'~{$width*int(h*$width/w)//750} tokens')
"
