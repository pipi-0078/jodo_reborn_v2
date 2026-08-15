# アセットのクレジット表記

## 阿弥陀如来坐像(`public/assets/amida_gold.glb`)

- **原作品**: 「阿弥陀如来坐像 / Wooden Amitabha sitting statue」
- **作者**: [Atsushi Nakabayashi](https://sketchfab.com/nakabayashi)
- **出典**: [Sketchfab](https://sketchfab.com/3d-models/wooden-amitabha-sitting-statue-dfbce4dd8c374376b7fcd3a1dae3a8f3)
- **ライセンス**: [CC-BY-SA-4.0](http://creativecommons.org/licenses/by-sa/4.0/)
- **改変内容**(本プロジェクトによる):
  - メッシュ簡略化: 372,870 → 82,021 トライアングル(meshopt simplifier, ratio 0.22)
  - マテリアル変更: 木造(フォトグラメトリのカラーテクスチャ)→ 金色のPBRメタリックマテリアル
  - カラーテクスチャ除去、ノーマルマップを1024pxに縮小、頂点量子化
  - ファイルサイズ: 29.3MB → 4.5MB

ライセンス情報は glb ファイル内の `asset.extras` にも埋め込み済み。

**CC-BY-SA-4.0 の遵守事項**:
- アプリ内(クレジット画面またはロード画面)と本リポジトリで上記クレジットを表示すること
- 改変版のモデルデータも同ライセンス(CC-BY-SA-4.0)で提供されること

## 宝樹(最内周の大樹)(`public/assets/takara_tree.glb`)

- **原作品**: 「tesuto tree」
- **作者**: [toshiki3782](https://sketchfab.com/toshiki3782)
- **出典**: [Sketchfab](https://sketchfab.com/3d-models/tesuto-tree-68eff483c589466e8b65e9268b0eb16a)
- **ライセンス**: [CC-BY-4.0](http://creativecommons.org/licenses/by/4.0/)
- **改変内容**(本プロジェクトによる):
  - メッシュ簡略化: 229,344 → 75,853 トライアングル(幹15%・葉50%)
  - 葉のカラーテクスチャをグレースケール化・明度調整(実行時に四宝の色を乗算するため)
  - ノーマルマップ・タンジェント除去、テクスチャ512px化
  - ファイルサイズ: 19.3MB → 7.1MB
- ライセンス情報は glb ファイル内の `asset.extras` にも埋め込み済み

**CC-BY-4.0 の遵守事項**: アプリ内(クレジット画面またはロード画面)と本リポジトリで上記クレジットを表示すること
