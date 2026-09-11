# 浄土再現プロジェクト 作業規約(Codex 用。CLAUDE.md と同内容)

## 最初に読む
- **`docs/HANDOVER_CODEX.md`**: Claude からの引き継ぎ書。進捗・構成・ブランチ運用・未解決事項
- **`docs/LESSONS.md`**: これまでの失敗・エラー・できなかったことのまとめ。
  アセット制作・空間配置・仏像の作業に取りかかる前に該当する節を読み、同じ失敗を繰り返さない。
  新しい失敗が出たら、その日のうちに追記する

## 施主の信頼に関わる規約
- アセットは必ず「作る → ギャラリーで見せる → 承認 → 空間へ」。承認前に main.ts / props.ts へ置かない
- 編集後は grep か数値で反映を確認してから報告する
- できないことは早い段階で「できない」と言う。施主の言葉を足し算で解釈しない
- 見立てが外れたときに「たぶん」で二度目のプッシュをしない。再現してから直す

## トークン節約
- 検品する画像は必ず `tools/inspect.sh <png>` で 640px 幅に縮小してから見る。施主へ渡す画像は縮小しない
- 撮影は必要な枚数だけ。同じ角度を撮り直さない
- GitHub Actions のログ一覧を API で丸ごと取らない。デプロイ確認はプッシュ成功と `npm run build` の通過で足れりとする
- ファイルは全読みせず `sed -n` / `grep -n` で必要箇所だけ。一度読んだファイルを再読しない
- アセットの接合確認は、スクショより Blender 内でワールド座標を出力して数値で判定する
- 報告は要点のみ。コード編集は差分最小

## プロジェクト構成
- `src/` メイン空間(main.ts)とギャラリー(gallery.ts)。寸法はすべて `src/world/layout.ts` から導く
- `tools/make_*.py` Blender(bpy、ヘッドレス)によるアセット生成
- `public/assets/` 完成アセット + gallery.json(陳列台帳)
- 日記は別リポジトリ `pipi-0078/jodo_diary`。手順は `.claude/skills/x-worklog/SKILL.md`。本体に日記を置かない

## デプロイ
- デプロイ元ブランチは `claude/pure-land-3d-visualization-eltvnb`(`.github/workflows/deploy.yml`)。名前を変えない
- プッシュ前に `npm ci` 相当で依存が解決し `npm run build` が通ることを確認する

## 環境復元(コンテナは使い捨て)
    pip install bpy pillow numpy
    npm ci
