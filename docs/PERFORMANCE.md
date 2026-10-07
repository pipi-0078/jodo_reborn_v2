# 2026-10-08 軽量化の確認

承認済みの形状・顔画像・配置・影の解像度は変更していない。

| 項目 | 変更前 | 変更後 |
| --- | ---: | ---: |
| 圧縮対象のGLB 19個 | 97,853,692 bytes | 54,528,150 bytes |
| メイン空間のモデル・画像の転送量 | 185,336,522 bytes | 142,010,980 bytes |
| BGM MP3 | 7,495,110 bytes | 4,800,044 bytes |
| renderer.info.memory.total（入場中） | 2,154,684,290 bytes | 2,015,444,452 bytes |
| renderer.info.memory.textures | 160 | 153 |
| renderer.info.memory.geometries | 396 | 387 |

- GLBはビルド前にgzipを生成。全19ファイルを展開して元データとバイト単位で照合する。元GLBはギャラリー用に残す。
- 水底の同じ画像を使うTextureを共有し、宝樹の同じGLBの解析・結合も一度にする。
- BGMは128 kbps / 48 kHz / stereoへ変換し、カバー画像とメタデータを除去。音量18%、入場4秒・退出2秒のフェード、ループは維持。
- 入場待ちの描画は最大10fps。入場中は従来どおり各画面更新で描く。意図的に省略したフレームの時間を蓄積し、入場中の長い停止に対する0.05秒の上限は維持。
- 入場画面とBGMの連携は`src/experience/entrance.ts`、描画間隔は`frameScheduler.ts`、GLBの展開処理は`src/assets/loadGltf.ts`に分離。

## 計測条件と限界

同じMacのheadless Chrome、1100×760、入場位置、各6秒間で計測。GPU用メモリはThree.jsが追跡する推定値で、OS全体のGPU使用量ではない。転送量にはBGMやJavaScriptを含めない。

入場中のFPSは15.9→14.6、ブラウザのCPU処理時間は6秒あたり5.71→4.64秒だった。GPU負荷や実行時の状態に揺れがあるため、一般的なFPS改善率は主張しない。確実な改善は配信量、重複リソース、待機中の描画回数。

## 再確認

```sh
npm run build
node --experimental-strip-types tools/verify_frame_scheduler.mjs
npm run dev -- --host 127.0.0.1 --port 8965
WORLD_BASE=http://127.0.0.1:8965/jodo_reborn_v2/ PROFILE_OUT=/tmp/jodo-world-profile.json node tools/profile_world.cjs
BGM_BASE=http://127.0.0.1:8965/jodo_reborn_v2/ node tools/verify_bgm.cjs
```

ブラウザ計測は順番に実行し、計測中にビルドやソース変更をしない。開発サーバーの自動再読み込みや、同時に起動した別ブラウザの負荷を結果に混ぜない。

BGM変換: `ffmpeg -i INPUT.mp3 -map 0:a:0 -map_metadata -1 -c:a libmp3lame -b:a 128k -ar 48000 -ac 2 -write_xing 1 OUTPUT.mp3`
