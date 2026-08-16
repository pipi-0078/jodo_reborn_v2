# 浄土再現プロジェクト 設計書(v0.1)

『仏説阿弥陀経』に説かれる極楽浄土を、ブラウザ上の3D空間として再現する。
一人称視点で歩き回れるメタバース的空間の中央に阿弥陀如来坐像を安置し、
空を極楽鳥(迦陵頻伽など)が群れ飛ぶ世界を目指す。

---

## 1. 技術選定

### 推奨構成

| 領域 | 採用技術 | 理由 |
|---|---|---|
| レンダリング | **Three.js `WebGPURenderer`**(WebGL 2自動フォールバック付き) | 2026年現在、WebGPUは全主要ブラウザ対応(約95%)。非対応環境へはThree.jsが自動でWebGL 2にフォールバックするため、**最初からWebGPURendererで書けば「将来のWebGPU拡張」が不要になる**(移行コストゼロ) |
| シェーダ | **TSL(Three.js Shading Language)** | WGSL(WebGPU)とGLSL(WebGL)の両方にコンパイルされるノードベース記法。水面・光背・宝樹の煌めき等のカスタム表現をWebGPU/WebGL両対応で書ける |
| ビルド | Vite + TypeScript | 高速な開発サーバ、静的サイトとしてGitHub Pagesへ即デプロイ可能 |
| 操作系 | PointerLockControls + WASD(デスクトップ)/ 仮想スティック(モバイル) | Three.js標準。追加ライブラリ不要 |
| 鳥の群れ | Boidsアルゴリズム(まずCPU実装 → 必要ならTSL Computeでフル GPU化) | Three.js公式の `webgpu_compute_birds` / `webgl_gpgpu_birds` サンプルが実績あり |
| アセット | glTF 2.0(.glb)+ Draco/meshopt圧縮 + KTX2テクスチャ | Web配信の標準。転送量を1/5〜1/10に圧縮 |
| 音響 | Web Audio API(Three.js `Audio` / `PositionalAudio`) | 天楽・鳥の声・風鐸の空間音響 |

> **元リクエストへの提案**: 「Three.js + WebGL中心で、将来WebGPUへ拡張」ではなく、
> **最初からWebGPURendererで開発する**方式を推奨する。フォールバックが自動なので
> 現行環境も切り捨てず、書き直しも発生しない。

### 参考にする既存プロジェクト(GitHub調査結果)

| プロジェクト | 借りる知見 |
|---|---|
| [MengTo/kage](https://github.com/MengTo/kage)([mirror](https://github.com/herdiansah/kage-threejs)) | 京都の山寺を歩くThree.js作品。**和風建築の雰囲気づくり・章立て演出**の手本 |
| [three.js公式 GPGPU birds](https://threejs.org/examples/webgl_gpgpu_birds.html) | **GPU上で数千羽の鳥群を計算**する実装。極楽鳥の群れの土台 |
| [juanuys/boids](https://github.com/juanuys/boids) / [dannygelman1/Wings](https://github.com/dannygelman1/Wings) | CPU Boidsのシンプル実装、**止まり木にとまる挙動**(鳥が宝樹に留まる演出に流用) |
| [forthtemple/openworldthreejs](https://github.com/forthtemple/openworldthreejs) | ワールドモデルから床・壁を検出して歩行させる**衝突判定の設計** |
| [VerseEngine/verse-three](https://github.com/VerseEngine/verse-three) | 将来マルチユーザー化する場合のP2Pメタバースエンジン候補 |

### 阿弥陀如来坐像のアセット戦略 【確保済み ✅】

**採用アセット**: `public/assets/amida_gold.glb`(クレジットは [ATTRIBUTION.md](./ATTRIBUTION.md) 参照)

- 原典: Sketchfab「阿弥陀如来坐像 / Wooden Amitabha sitting statue」(Atsushi Nakabayashi氏、CC-BY-SA-4.0、ライセンス確認済み)
- 弥陀の定印を結んだ正統な阿弥陀如来坐像のフォトグラメトリスキャン。蓮華座付き
- 最適化済み: 37.3万 → 8.2万トライアングル、29.3MB → 4.5MB
- 木造の質感 → **金色のPBRメタリックマテリアル**に変換済み(baseColor: 金、metallic 1.0、roughness 0.38)。彫りの精細さはノーマルマップ(1024px)で維持
- プレビュー: [preview_amida_gold.png](./preview_amida_gold.png)
- Phase 2 での残作業: シーンの照明(西日+HDR環境)に合わせた金色の調整、光背シェーダの追加、スケール調整(現状 実寸約1m → シーン内で拡大配置)

---

## 1.5 アートディレクション(完成イメージ)

施主から提供された完成イメージ: [reference_concept.png](./reference_concept.png)
(2026-08-16受領。施主コメント:「少しキラキラすぎるけど、完成イメージとしてはこんな感じ」)

この画から採る設計言語:

- **パレット**: 金と白金を基調に、瑠璃(サファイアブルー)の差し色。空は柔らかな紫〜桃金のグラデーション、水は淡い水色
- **蓮華**: 車輪大の蓮華は**宝石のような半透明の花弁**(クリスタル質)。青・黄・赤・白がそれぞれの色で内側から発光
- **楼閣**: 金の骨組み+瑠璃色のガラス/水晶の柱、多層の屋根、頂に宝珠。細身の塔として遠景に複数配置
- **光背**: 阿弥陀如来の光背は**曼荼羅状の精緻な円環**(単純な円盤ではなく、同心の文様リング)
- **羅網**: 空から宝珠を綴った飾り紐が無数に垂れる(=七重羅網の表現)
- **天楽**: 楽器(箜篌など)が空に浮かんで自ずから鳴っている(「常作天楽」の視覚化)
- **道**: 金の敷石の道に欄干と灯籠が添う。灯籠は階道への追加候補

**抑制の方針**(施主の「キラキラすぎる」への応答):
発光・粒子・装飾の密度はこの画の6〜7割に抑える。今の「夕暮れの静けさ」の空気は保ち、
賑やかさより荘厳さを優先する。判断に迷ったら「光らせる数を減らして、ひとつを丁寧に光らせる」。

## 2. 経典からの情景抽出 → 3D要素マッピング

『仏説阿弥陀経』本文から浄土の描写を抜き出し、シーン要素に対応させる。

| # | 経文 | 意味 | 3D空間での表現 |
|---|---|---|---|
| 1 | 従是西方過十万億仏土…有世界名曰極楽 | 西方十万億土の彼方にある極楽 | 太陽を常に**西の低い位置**に置き、世界全体を金色の夕光で包む。来訪者は東から西(阿弥陀仏)へ向かって歩く |
| 2 | 七重欄楯 七重羅網 七重行樹 皆是四宝周匝囲繞 | 七重の欄干・宝の網・並木が四宝(金銀瑠璃玻璃)で囲む | 空間を**七重の同心円**で設計。欄干リング・頭上の宝網(半透明の煌めくメッシュ)・宝樹の並木リングが中心を囲む |
| 3 | 七宝池 八功徳水充満其中 池底純以金沙布地 | 七宝の池に八功徳水が満ち、池底は金砂 | 中央部に大きな池。**透明度の高い水面シェーダ(TSL)**+池底に金砂テクスチャ(屈折で揺らめく) |
| 4 | 四辺階道 金銀瑠璃玻璃合成 | 池の四辺に四宝の階段 | 池の東西南北に金銀瑠璃玻璃4種のマテリアルの階段。歩行で昇降可能 |
| 5 | 上有楼閣 亦以金銀瑠璃玻璃硨磲赤珠碼碯而厳飾之 | 七宝で飾られた楼閣 | 池畔・並木の間に**七宝装飾の楼閣**(和様建築+宝石エミッシブ)。遠景のランドマーク |
| 6 | 池中蓮華大如車輪 青色青光 黄色黄光 赤色赤光 白色白光 微妙香潔 | 車輪ほどの蓮華が青黄赤白に光る | 池面に**直径1m級の巨大蓮華**を群生させ、花色ごとに同色のエミッシブ+Bloomで発光 |
| 7 | 常作天楽 黄金為地 | 天の音楽が常に流れ、大地は黄金 | 地面は金色マテリアル(ラフネス高めで上品に)。環境BGMとして雅楽的アンビエント |
| 8 | 昼夜六時而雨曼陀羅華 | 昼夜六時に曼陀羅華が降る | **花弁パーティクル**が空からゆっくり舞い降りる(六時=約4分周期で降り方が強まる演出) |
| 9 | 種種奇妙雑色之鳥 白鵠孔雀鸚鵡舎利迦陵頻伽共命之鳥 昼夜六時出和雅音 | 白鵠・孔雀・鸚鵡・舎利・迦陵頻伽・共命鳥が美声で鳴く | **Boids群飛**。色とりどりの鳥(将来的に種類別モデル)。PositionalAudioで鳥声を空間配置 |
| 10 | 是諸衆鳥皆是阿弥陀仏…変化所作 | 鳥は阿弥陀仏の化作 | 鳥にほのかな発光・微粒子の軌跡を与え「化鳥」らしさを演出 |
| 11 | 微風吹動諸宝行樹及宝羅網 出微妙音 譬如百千種楽 | 微風が宝樹と羅網を鳴らし妙音を出す | 宝樹の**風揺れ頂点アニメーション(TSL)**+風に連動して鳴る生成的な鈴音・和音 |
| 12 | 有仏号阿弥陀 今現在説法 | 阿弥陀仏が今まさに説法している | 空間の**中心、池の中島の蓮華座上に阿弥陀如来坐像**。光背をシェーダで表現し、近づくと微かな読経・説法の環境音 |

### 空間レイアウト(平面図)

```
        (最外周)七重目の行樹・欄楯リング
   ・・・・・・・・・・・・・・・・・・・・・
  ・   楼閣    宝樹並木(七重)   楼閣   ・
  ・      ┌─────────────┐      ・
  ・      │   七宝池(八功徳水)  │      ・
  ・  階道→│  蓮華群  ◎中島    │←階道  ・
  ・      │     阿弥陀如来坐像  │      ・
  ・      └─────────────┘      ・
  ・   スポーン地点(東端・仏に向き合う)    ・
   ・・・・・・・・・・・・・・・・・・・・・
        頭上:七重の宝羅網 / 空:極楽鳥の群れ
```

---

## 3. 開発工程(フェーズ計画)

一気に作らず、**各フェーズ完了ごとに動くものをデプロイして確認**しながら進める。

### Phase 0 — 基盤(歩ける金色の大地)
- Vite + TypeScript + Three.js(WebGPURenderer)プロジェクト初期化
- 一人称移動(PointerLock + WASD、視点操作)、簡易衝突(地面高さ追従)
- 黄金の大地・空(グラデーション)・西日ライティングの仮置き
- GitHub Pages への自動デプロイ(GitHub Actions)
- **完了条件**: URLを開くと金色の平原を歩き回れる

### Phase 1 — 空間骨格(七重の結界と七宝池)
- 七重の同心円レイアウト実装(欄楯・行樹リングをプロシージャル配置)
- 中央の七宝池:TSL水面シェーダ(反射・屈折・金砂の池底)
- 四辺階道(4種マテリアル)、池への昇降
- **完了条件**: 池の周囲を歩き、階段から水辺に降りられる

### Phase 2 — 阿弥陀如来坐像の安置
- 仏像アセット取得(§1のアセット戦略)→ 減面・glb圧縮パイプライン確立
- 中島+蓮華座+坐像の配置、光背(放射光シェーダ)
- 仏前に近づくと環境音が変わる演出
- **完了条件**: 池の中心に光背を負った阿弥陀如来坐像が安置されている

### Phase 3 — 極楽鳥
- Boids(CPU実装、〜200羽)で群飛。宝樹への止まり・飛び立ち
- 鳥声のPositionalAudio(六時周期で「和雅音」が強まる)
- パフォーマンス不足ならTSL Computeで GPU Boids化(数千羽)
- **完了条件**: 空を鳥群が自由に舞い、木々にとまり、声が空間から聞こえる

### Phase 4 — 荘厳(しょうごん)ディテール
- 四色に発光する車輪大の蓮華群+Bloomポストプロセス
- 曼陀羅華の降下パーティクル
- 頭上の宝羅網(煌めきシェーダ)、楼閣モデル、宝樹の風揺れ+妙音
- 天楽アンビエントBGM
- **完了条件**: 経典の主要描写(§2の表)が一通り体験できる

### Phase 5 — 仕上げ・拡張
- モバイル対応(仮想スティック・画質自動調整)、ロード画面(経文の引用演出)
- アクセシビリティ(酔い対策の視野角設定等)
- 任意拡張: WebXR(VR歩行)/ マルチユーザー化(VerseEngine等)/ 説法テキストの字幕演出
- **完了条件**: スマホでも快適に動き、公開URLとして人に案内できる

---

## 4. アセット生成用プロンプト集

コンセプトアート・スカイボックス・3Dモデル生成(Meshy等)・テクスチャ生成に使う。
経文の描写を直訳ではなく視覚語彙に変換してある。

### 世界観・スカイボックス
> **EN**: A vast serene Buddhist Pure Land paradise at eternal golden hour, sun low in the west, sky of soft amber and rose gradients, distant jeweled pavilions on the horizon, seven concentric rows of jeweled trees, tranquil sacred atmosphere, painterly yet photoreal, equirectangular panorama
>
> **JP**: 永遠の夕暮れに包まれた広大で静謐な極楽浄土。西に低い太陽、琥珀と薔薇色の空、地平線に宝石で飾られた楼閣、七重に連なる宝樹の並木。神聖で安らかな空気。

### 七宝池と蓮華
> **EN**: A crystal-clear lotus pond with golden sand shimmering on the bottom, giant lotus flowers as large as chariot wheels, glowing softly in blue, yellow, red and white — each color radiating light of its own hue, gentle ripples, staircases of gold, silver, lapis lazuli and crystal descending into the water
>
> **JP**: 池底の金砂が揺らめく澄み切った蓮池。車輪ほどの巨大な蓮華が青・黄・赤・白に、それぞれの色の光を放って咲く。金・銀・瑠璃・玻璃の階段が水辺へ降りる。

### 阿弥陀如来坐像
> **EN**: A serene seated Amida Buddha statue in meditation mudra (Amida jōin), gentle half-closed eyes, seated on a giant lotus pedestal, radiant halo (kōhai) of soft golden light rays behind, bronze with subtle gold leaf, Kamakura-period Japanese Buddhist sculpture style, highly detailed, reverent atmosphere
>
> **JP**: 弥陀の定印を結び半眼で瞑想する阿弥陀如来坐像。巨大な蓮華座に坐し、背後に金色の光線を放つ光背。鎌倉期の日本仏像様式、青銅にかすかな金箔。

### 極楽鳥(迦陵頻伽・共命鳥など)
> **EN**: Mystical paradise birds of the Pure Land — white swans, peacocks, parrots, and the mythical kalavinka with iridescent multicolored plumage, faintly glowing as if made of light, graceful flight, stylized low-poly-friendly silhouettes suitable for real-time rendering
>
> **JP**: 極楽の霊鳥たち――白鵠・孔雀・鸚鵡、そして虹色の羽をもつ伝説の迦陵頻伽。光でできているかのように淡く発光し、優雅に舞う。リアルタイム描画向けの簡潔なシルエット。

### 宝樹と羅網
> **EN**: Rows of sacred jeweled trees with trunks of gold and leaves of lapis lazuli and crystal, glittering softly in the breeze; above, seven layers of translucent jeweled nets strung with tiny bells and gems, catching the golden light
>
> **JP**: 金の幹に瑠璃と玻璃の葉をもつ宝樹の並木が微風にきらめく。頭上には小さな鈴と宝珠を綴った半透明の宝網が七重にかかり、金色の光を受けて輝く。

### 曼陀羅華の花の雨
> **EN**: Soft rain of glowing mandarava blossoms — pale coral-white celestial flowers drifting down slowly from the sky like snow, catching golden light, dreamy particle effect
>
> **JP**: 淡い珊瑚色の天華・曼陀羅華が、雪のようにゆっくりと空から舞い降り、金色の光を受けて輝く。

---

## 5. リポジトリ構成(予定)

```
jodo_reborn_v2/
├── docs/DESIGN.md          # 本書
├── index.html
├── src/
│   ├── main.ts             # エントリ(レンダラ・ループ)
│   ├── world/              # 大地・池・宝樹・楼閣などシーン構築
│   ├── controls/           # 一人称操作
│   ├── birds/              # Boids
│   ├── shaders/            # TSLマテリアル(水面・光背・羅網)
│   └── audio/              # 天楽・鳥声
├── public/assets/          # glb・KTX2・音源
└── .github/workflows/      # Pages デプロイ
```
