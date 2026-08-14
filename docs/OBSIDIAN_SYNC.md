# 作業日記をObsidianに自動同期する手順

このリポジトリの `diary/` フォルダを、Macの Obsidian Vault(Araya_shiiki)内の
「浄土再現v2」フォルダへ Obsidian Git プラグインで同期するための手順。

仕組み: Claude が日記を `diary/YYYY-MM-DD.md` としてコミット&プッシュ →
Mac 側の Obsidian Git が定期的に `git pull` → Vault に日記が現れる。

## 1. 事前確認(1回だけ)

Vault 自体がすでに Git 管理されていないかを確認する。ターミナルで:

```bash
ls -a "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Araya_shiiki" | grep .git
```

- 何も表示されなければそのまま手順2へ
- `.git` が表示された場合は、Obsidian Git はすでに Vault 全体を管理している。
  その場合はこの手順を中断して相談すること(別の同期方法を使う)

## 2. リポジトリをVault内へクローン(1回だけ)

ターミナルに以下を1ブロックずつ貼り付けて実行:

```bash
cd "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Araya_shiiki"
git clone --filter=blob:none --sparse https://github.com/pipi-0078/jodo_reborn_v2.git 浄土再現v2
```

```bash
cd "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Araya_shiiki/浄土再現v2"
git sparse-checkout set diary
ls diary
```

`ls diary` で `2026-08-14.md` などが表示されれば成功。

補足:

- `--sparse` + `sparse-checkout set diary` により、コードや3Dアセットは落とさず
  **日記フォルダだけ**が Vault に展開される(Vault が重くならない)
- すでに「浄土再現v2」フォルダが存在してファイルが入っている場合は、
  先に別名に退避してからクローンする
- ユーザー名とパスワードを聞かれた場合、パスワード欄には GitHub の
  Personal Access Token を入れる(github.com → Settings → Developer settings →
  Personal access tokens で作成)。GitHub Desktop 等で認証済みなら聞かれない

## 3. Obsidian Git プラグインの設定

Obsidian の 設定 → コミュニティプラグイン → Obsidian Git のオプションを開き:

1. **Advanced → Custom base path (Git repository path)** に `浄土再現v2` と入力
   (Vault ルートからの相対パス)
2. **Automatic** セクション:
   - Auto pull interval: `10`(10分ごとに自動でpull)
   - Auto commit-and-sync interval: `0`(自動コミット・プッシュは無効のまま)
3. Obsidian を再起動するか、コマンドパレット(Cmd+P)で
   **「Obsidian Git: Pull」** を実行して動作確認

以後、日記がプッシュされるたび、最大10分以内に
`浄土再現v2/diary/` フォルダへ自動で反映される。

## 4. 日記の場所

- Vault 内のパス: `Araya_shiiki/浄土再現v2/diary/YYYY-MM-DD.md`
- Mac 側で日記を編集した場合、そのままでは GitHub に戻らない(pull専用運用)。
  編集を戻したくなったら、コマンドパレットの
  「Obsidian Git: Commit-and-sync」を手動実行すればプッシュされる
