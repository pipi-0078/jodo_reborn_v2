# 舎利の飛翔アセット

採用済みの `shari-flight-v6.glb` を、形状・テクスチャ・骨格・モーフ・アニメーションを維持して追加。
生成元は fal.ai の `tripo3d/h3.1/multiview-to-3d`。

- ギャラリー: `gallery.html?asset=shari`
- 単体展示: `shari.html`（全身・正面・背面・目元・一時停止・GLB保存）
- 空間: `index.html?view=shari`（東の橋から飛行範囲を見上げる初期視点）
- アセット: `public/assets/shari/shari-flight.glb.gz`
- 来歴・SHA-256・容量: `public/assets/shari/manifest.json`

## 動作

`Living flight` は12秒。2.4秒の滑らかな羽ばたきを5回繰り返し、1.8秒・5.9秒・9.5秒に瞬きする。
翼の上下軸と水平姿勢は承認済みの設定を維持し、尾羽の付け根から先へ波を伝える。

空間での移動はアニメーション階層の外側で行う。七宝池の上空を巡る経路に、周期の異なる半径・高さ・速度変化を加える。
頭は経路の接線へ向け、胴体を水平に保つ。寸法は `src/world/layout.ts` の `SHARI_SCALE` と `SHARI_FLIGHT_AREA`。
単一の固定円を繰り返す動きではないが、飛行範囲は定めた池上空に限定している。

羅網の取り付け高さだけでなく、GLBの最低点を確認した。長い羅網は約15m下まで垂れるため、
舎利は外側の低い垂れ飾りを避け、池中心から約19.4〜21.8m、高さ約7.44〜9.68mを飛ぶ。
元モデルの約0.99mの翼幅は空間では約2.35m。羅網の実寸に基づく内側境界からも翼端の余裕を取っている。

## 検証

`npm run build` で型検査と本番ビルド。
`node tools/verify_shari.cjs` はローカルの8946番ポートを既定として使用し、ギャラリーの表示、瞬き、
ダウンロードのSHA-256、スマートフォン幅の表示、本体での移動と600秒分の経路を確認する。
`SHARI_BASE` と `OUTPUT_DIR` でURLと検証結果の保存先を変更できる。

## アニメーションの再生成

`tools/shari/` のスクリプトを以下の順で実行する。PythonとNumPyが必要。
生成原本 `shari-multiview-v1.glb` は `pipi-0078/jodo_diary` の `output/shari/` に保存。

1. `build-articulated-flight.py`: 原本 → 肩・肘・手首の骨格を持つGLB
2. `refine-flight-posture.py`: 頭と脚の飛行姿勢
3. `orient-level-flight.py`: 体を水平にする
4. `build-vertical-flight.py`: 垂直・滑らかな羽ばたき
5. `build-living-flight.py`: 瞬きと尾羽

配信ファイルはgzipによる可逆圧縮。ブラウザーで展開し、保存リンクは通常のGLBを返す。
