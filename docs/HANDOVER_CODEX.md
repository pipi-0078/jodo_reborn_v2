# 浄土再現プロジェクト 引き継ぎ書(Claude → Codex)

作成日: 2026-09-11。作成時点の最新コミットは `10dd873`(阿弥陀像の輪郭を戻す)。
この文書は、これまで Claude Code が担当してきた開発を OpenAI Codex に引き継ぐためのもの。
**まずこの文書を読み、次に `docs/LESSONS.md` を通読してから作業に入ること。**

---

## 1. プロジェクトの目的と現在地

『仏説阿弥陀経』の描写をもとに極楽浄土をブラウザ上の 3D 空間として再現する。
一人称視点で歩ける空間の中央(池の中島)に阿弥陀如来坐像を安置し、七重の宝樹・七宝池・楼閣・羅網・蓮華で荘厳する。

- 施主(発注者): ヨシボウさん(GitHub: `pipi-0078`)。日本語でやり取りする
- 公開ページ: https://pipi-0078.github.io/jodo_reborn_v2/(メイン空間)、`/gallery.html`(アセット陳列室)
- 設計書: `docs/DESIGN.md`(技術選定・経文と 3D 要素の対応表・フェーズ計画・生成用プロンプト集)
- 完成イメージ: `docs/reference_concept.png`(施主提供。「少しキラキラすぎる」の 6〜7 割に抑える方針)

### フェーズ進捗(`docs/DESIGN.md` §3 の計画に対して)

| フェーズ | 状態 | 備考 |
|---|---|---|
| Phase 0 基盤(歩ける金の大地・Pages デプロイ) | 完了 | |
| Phase 1 空間骨格(七重の同心円・七宝池・四辺の橋) | 完了 | 水面は `reflector` 反射、金砂の池底、外岸の斜面 |
| Phase 2 阿弥陀如来坐像の安置 | ほぼ完了 | Hitem3D 生成像を中島の壇の上段中央に安置済み。**光背は施主が却下(付けない)**。直近は像の見え方(黒ずみ・影・輪郭)の調整を繰り返しており、`10dd873` の結果は施主の確認待ち |
| Phase 3 極楽鳥(Boids・鳥声) | 未着手 | `src/birds/` `src/audio/` はまだ存在しない |
| Phase 4 荘厳ディテール | 大半完了 | 四色に光る蓮華+発光ブルーム、曼陀羅華の降下、七重羅網、楼閣 2 種、宝樹 7 周、紫雲は実装済み。**天楽 BGM・宝樹の風揺れ・鈴音は未実装** |
| Phase 5 仕上げ(モバイル・ロード画面・XR) | 未着手 | |

### 直近の未解決事項(2026-09-10 時点)

1. 阿弥陀像の見え方。施主の指摘の連鎖: 真っ黒 → 黒みがかっている → 顔まわりが黒い → 口の周りがヒゲのように黒い → 顎下の影がひどい → 影は消えたが輪郭まで薄い。
   最終手段として「像専用の環境マップに上下の勾配を残し、東上方からの絞った SpotLight で像だけ照らす」を入れてプッシュ済み。**施主の返事を待って次の手を決める**。
   経緯の全文は `docs/LESSONS.md` §4 の 10 番。次に触るときの規則も同節末尾にある(顔の形状は絶対にいじらない、無理なら無理と言う)
2. `jodo_diary`(日記リポジトリ)は一時的に Public にした可能性があり、Private に戻せているか未確認(`docs/LESSONS.md` §5)

---

## 2. リポジトリ構成

```
jodo_reborn_v2/
├── AGENTS.md                 # Codex が自動で読む作業規約(CLAUDE.md と同内容)
├── CLAUDE.md                 # Claude Code 用の作業規約(参考として残す)
├── index.html / gallery.html # メイン空間 / 陳列室のエントリ
├── src/
│   ├── main.ts               # メイン空間: WebGPURenderer・後処理(発光だけのブルーム)・ループ
│   ├── gallery.ts            # 陳列室: gallery.json を読んで 1 品ずつ OrbitControls で見せる
│   ├── controls/firstPerson.ts # PointerLock + WASD、足元高さは layout.sampleGround に従う
│   └── world/
│       ├── layout.ts         # 空間の寸法定数と歩行判定(すべての寸法の出どころ。ここから導く)
│       ├── sky.ts            # 勾配ドームの空と PMREM 環境、太陽方向
│       ├── gold.ts           # 金・銀の専用環境マップ、applyPureGold(材質名で判定)、像専用環境
│       ├── ground.ts / pond.ts # 金の大地、七宝池(反射水面・金砂・岸)
│       ├── props.ts          # glb の据え付け(橋・壇・如来・楼閣・宝樹・蓮・羅網)
│       ├── rings.ts / trees.ts # 七重の欄楯・行樹の配置
│       ├── glow.ts / petals.ts / clouds.ts # 蓮の光・降る花・紫雲
├── public/assets/            # 完成 glb(合計 約125MB)と gallery.json(陳列台帳)
├── tools/
│   ├── make_*.py             # Blender(bpy)ヘッドレスでのアセット生成スクリプト
│   ├── gild_glb_texture.py   # glb の基礎色を金一色に染める(pillow のみ)
│   ├── shrink_glb_textures.py# glb 内の画像を縮小(pillow のみ)
│   ├── inspect.sh            # 検品用スクショを 640px に縮小
│   ├── textures/             # make_textures.py の出力(金箔・槌目・樹皮など)
│   └── vendor/ch_trees       # tree-gen(GPL-3.0)の同梱
├── docs/
│   ├── DESIGN.md             # 設計書
│   ├── LESSONS.md            # 失敗と教訓(最重要。作業前に必読)
│   ├── ATTRIBUTION.md        # 外部アセットのクレジット(CC-BY-SA の遵守事項)
│   ├── OBSIDIAN_SYNC.md      # 旧手順(日記が本体リポジトリにあった頃のもの。現行は §7 を参照)
│   └── *.png                 # 各フェーズのスクショ、完成イメージ
├── .claude/skills/x-worklog/ # 日記(X 投稿用記事)作成の手順書。Codex でも SKILL.md を読んで手動で従う
└── .github/workflows/deploy.yml # GitHub Pages への自動デプロイ
```

### 技術スタック
- Three.js `r185` の **WebGPURenderer**(WebGL 2 へ自動フォールバック)+ TSL。`three/webgpu` と `three/tsl` から import する
- Vite 8 + TypeScript 7(`strict`、`noUnusedLocals`)。`npm run build` は `tsc --noEmit && vite build`
- アセット生成は Blender を **pip の `bpy`** でヘッドレス実行(GUI もレンダも不可)
- 外部ポストエフェクト系ライブラリは入れない(N8AO で peer dep が衝突し CI が落ちた前歴)

---

## 3. 環境の復元(コンテナは使い捨て)

```bash
pip install bpy pillow numpy
npm ci
npm run build        # 型検査込み。プッシュ前に必ず通す
```

- コンテナに GPU はない。Blender の render は不可、Cycles のベイクも実質不可
- 外部の 3D 生成 API(Meshy / Tripo / fal.ai / huggingface)へは出られない。**image-to-3D は施主が生成し、glb を受け取る**
- 見た目の確認は `vite build` → `python3 -m http.server` → Playwright(`playwright-core` 同梱、Chromium は環境に既設)で撮影する
  - 撮影スクリプトの例は `.claude/skills/x-worklog/scripts/thumbnail.mjs`(`--use-angle=swiftshader`、ポート 8933)
  - メイン空間は水面反射で 2 回描くため 1 枚 3〜5 分。`timeout` は 600000ms。並列に撮るときは chromium を 5 秒ずつずらす
  - **公開ページの見え方は WebGPU 経路で確かめる**: `--enable-unsafe-webgpu --use-vulkan=swiftshader` を渡し、`GPUTexture.createView` の `swizzle` を落とす initScript を入れると再現する(LESSONS §4-10)
  - `http.server` を `pkill` しない(自分のシェルまで落ちる)。`curl` で生存確認して無ければ起動
- `window.__camera` `window.__scene`(メイン)、`window.__controls`(ギャラリー)がヘッドレス検証用フック

---

## 4. ブランチとデプロイ

- リポジトリの既定ブランチ兼 **デプロイ元ブランチ**: `claude/pure-land-3d-visualization-eltvnb`
  (`.github/workflows/deploy.yml` の `on.push.branches`)。ここへプッシュすると Pages が更新される
- Pull Request は使っていない。作業ブランチで作業し、施主の承認後にデプロイ元ブランチへ fast-forward でプッシュしてきた
- 作業ブランチは `claude/<セッション名>` 形式で作られていた。Codex では任意の名前でよいが、**デプロイ元ブランチ名は変えない**(変えるなら deploy.yml も同時に直す)
- 直近の作業ブランチ `claude/amida-central-pedestal-3lzynz` はデプロイ元と同じ `10dd873` を指している
- Actions の結果を API で取りにいかない(1 回で数万〜数十万文字返る)。プッシュ成功 + `npm run build` が通っていればデプロイ済みとみなす
- `public/assets/` の glb は Git に直接入っている(LFS ではない)。1 ファイル 13MB 程度まで

---

## 5. 作業規約(施主の信頼に関わる。必ず守る)

`AGENTS.md` にも同じ内容を置く。根拠と経緯は `docs/LESSONS.md` §0。

1. **アセットは「作る → ギャラリーで見せる → 施主が承認 → 空間(main.ts / props.ts)へ」**。承認前に空間へ置かない
2. **編集後は grep か数値で反映を確認してから報告する**。「変わってないよ」を言わせない
3. できないことは早い段階で「できない」と言う。指示のたびに別の手段を足していかない
4. 施主の言葉を足し算で解釈しない。「一色にして」は「全部剥がして」の意味
5. 見立てが外れたときに「たぶん」で二度目のプッシュをしない。再現してから直す
6. 報告は要点のみ。作業ログの実況をしない。コード編集は差分最小
7. 施主は数値より見た目の一言で判断する(「浮いてない??」「厚化粧」)。その一言は正確なので、疑わず原因を数値で探す
8. 「正直に答えてね?」と聞かれたら、出典や限界をそのまま言う

### 施主の美的な好み(繰り返し言われたこと。LESSONS §2-5 の要約)
- 最初から最大の作り込みで出す(「もう少し細かく」は必ず来る)
- 幾何学模様のテクスチャは NG。金箔・槌目・磨きなど**材質感**で
- 繰り返しの規則性を一目で見つける。タイルは角度・縮尺違いで重ね貼り
- 宝石は淡くて優しい色(桜色・水色・藤色)。青のラインや派手な赤青は嫌う
- 光は最初から強めに(「淡く」と言われても結局 3 回上げた)
- 蓮は車輪大(直径 1〜1.2m)。大きさより**ばらつき**(倍率 2 倍以上の幅)が効く
- 仏像の顔・手は手続き生成しない。材質は台座と同じ金一色

---

## 6. アセットの現状(`public/assets/gallery.json` が台帳)

メイン空間で使用中(props.ts が読む): `bridge_long`, `island_dais`, `amida_hitem3d_eighth`, `pavilion`, `pavilion_b`, `houju_tree`, `houju_takara`, `houju_yanagi`, `houju_conifer`, `houju_broadleaf`, `houju_lod`, `lotus`, `lotus_bud`, `ramou`, `ramou_short`

ギャラリーのみ(未採用・旧版・保留): `amida_gold`, `amida_polish`, `amida_full`, `amida_wip`(旧仏像 4 種。経緯は LESSONS §4)、`rengeza`(蓮華座。Hitem3D 像が蓮華座つきなので現在は不使用)、`houdou`(宝幢。壇の四隅に立てる案、未配置)、`bridge`(短橋)、`takara_tree` と `tree_*`(宝飾前の木)

### 生成スクリプトと成果物の対応
| スクリプト | 成果物 | 注意 |
|---|---|---|
| `make_dais.py` | island_dais, houdou | 寸法は `layout.ts` の `DAIS_*` と揃える |
| `make_bridge.py` | bridge, bridge_long | 池を変えたら橋・水位線・歩行判定も追従 |
| `make_pavilion.py` / `make_pavilion_b.py` | pavilion / pavilion_b | 部材数が多いと生成 25 分。`bpy.ops` の連打を避け一つのメッシュに詰める |
| `make_lotus.py` | lotus, lotus_bud | 花弁の発光マップ下限 0.22(外面が真っ黒になる対策) |
| `make_ramou.py` | ramou, ramou_short | 懸垂線の垂れは間隔の 30〜46%。宝石は透過+吸収で色付け |
| `make_houju_tree.py` + `make_tree_treegen.py` | houju_* | tree-gen の木に宝飾を追加。幹は無地の金 |
| `make_rengeza.py` | rengeza | |
| `make_amida_*.py` / `mpfb_bootstrap.py` | 旧仏像 | **もう使わない**。仏像は施主の image-to-3D 生成物を受け取る |
| `make_textures.py` | tools/textures/*.png | 金箔・槌目・樹皮など |

### 外部素材のライセンス
`docs/ATTRIBUTION.md` を維持する。Sketchfab 由来の 2 点(CC-BY-SA-4.0 / CC-BY-4.0)はアプリ内クレジット表示が必要(ロード画面またはクレジット画面。**まだ実装していない**。Phase 5 で入れる)。tree-gen は GPL-3.0。

---

## 7. 日記(X 投稿用記事)の運用

- 作業した日は、その日の終わりに **X 投稿用の記事を 1 本**書くところまでが仕事。施主から頼まれなくても、区切りやプッシュのタイミングで書く
- 手順書は `.claude/skills/x-worklog/SKILL.md`。文体の規準は同フォルダ `references/exemplar-2026-08-17.md`、検査は `scripts/check_style.py`
- 置き場所は **別リポジトリ `pipi-0078/jodo_diary` の直下**(`YYYY-MM-DD-X投稿用.md`)。このリポジトリが施主の Obsidian Vault 本体
- **本体リポジトリに日記を置かない**(過去に同期事故でアセットが消えた)
- 記事内では AI を「Fable」という登場人物として書いてきた。Codex に引き継いだことは施主と相談して、名前をどうするか決める
- 記事はコミット後にチャットにも添付する(施主はスマホで受け取って投稿する)
- Claude の環境では `jodo_diary` への書き込み権限が既定で無く、施主に「jodo_diary を追加して」と言ってもらう必要があった。Codex の環境で権限がどうなるかは最初に確認する

---

## 8. Claude 固有だったもの(Codex で読み替える)

| Claude での運用 | Codex での対応 |
|---|---|
| `CLAUDE.md` を自動で読む | `AGENTS.md` を自動で読む(同内容を置いた) |
| `.claude/skills/x-worklog` をスキルとして呼ぶ | SKILL.md を手順書として読み、手動で従う |
| `SendUserFile` で画像・記事を施主に渡す(コンテキスト消費なし) | 相当する手段で添付する。無ければパスを示す |
| 画像は `tools/inspect.sh` で 640px に縮小して見る | 同じ。画像トークンの節約は Codex でも有効 |
| GitHub は MCP 経由。`actions_list` は呼ばない | どの経路でも Actions のログを丸ごと取らない |
| 別リポジトリは `add_repo` で追加 | Codex の権限設定に従う。最初に `jodo_diary` へ push できるか試す |
| コミット末尾に Claude の署名行 | 不要。モデル名を成果物に書かない |

---

## 9. 次にやることの候補(優先順)

1. 阿弥陀像の見え方について施主の返事を受けて対応する(§1 の未解決事項)。像の材質は `props.ts` の `placeAmida`、環境は `gold.ts` の `getStatueEnvironment`
2. Phase 3 極楽鳥: CPU Boids(〜200 羽)から。参考は `docs/DESIGN.md` §1 の GPGPU birds。鳥のモデルは手続き生成しない(有機的な造形は施主の期待に届かない)
3. 天楽 BGM・鳥声の PositionalAudio(音源の入手先は施主と相談)
4. 宝樹の風揺れ(TSL 頂点アニメーション)と羅網の鈴音
5. Phase 5: モバイル操作、ロード画面(経文の引用+クレジット表示)、画質の自動調整

着手前に、その分野の節を `docs/LESSONS.md` で読むこと。新しい失敗が出たら、その日のうちに `docs/LESSONS.md` へ追記する。
