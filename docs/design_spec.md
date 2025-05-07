# Discord YouTube Downloader Bot - 詳細設計書

## 📘 概要

このBotは、Discord上でスラッシュコマンドを使ってYouTube動画をダウンロードし、Cloudflare R2へ保存・公開するシステムです。保存された動画は30日後に自動削除されます。

---

## 🧩 機能一覧

| 機能 | 説明 |
|------|------|
| `/setname` | 保存先のユーザー名とファイル名を登録 |
| `/upload` | 指定URLの動画をDLしてCloudflare R2にアップロード |
| `/myfiles` | ユーザー自身のアップロード済みファイル一覧を表示 |
| ⏰ 自動削除 | 毎日0時に30日以上前のファイルを削除 |

---

## 📁 ディレクトリ構成

```
discord-bot-r2/
├── main.py                      # エントリーポイント
├── config.json                  # 機密情報（.gitignore推奨）
├── requirements.txt             # 必要ライブラリ
├── Dockerfile                   # Dockerイメージ定義
├── docker-compose.yml           # 起動構成
├── entrypoint.sh                # 起動スクリプト
├── README.md                    # 利用手順
└── bot/
    ├── __init__.py
    ├── core.py                  # Bot初期化、イベント登録
    ├── commands.py              # スラッシュコマンド群
    ├── db.py                    # SQLiteによるDB操作
    ├── r2.py                    # Cloudflare R2操作
    ├── scheduler.py             # 自動削除処理
    ├── utils.py                 # バリデーション・権限チェック
    └── config.py                # 設定読込
```

---

## ⚙️ コマンド詳細

### `/setname`

- 保存ファイル名を決めるためのコマンド
- バリデーション：`[a-zA-Z0-9_-]+`

### `/upload`

- yt-dlpでmp4をDL
- `R2にアップロード`
- 成功時：パブリックURLを返却

### `/myfiles`

- 自分のアップロード履歴を表示
- DBから `filename, r2_path` を取得し、公開URLを生成

---

## 🗃️ データベース構造

### `file_mapping`

| カラム名 | 型 | 説明 |
|----------|----|------|
| discord_id | TEXT | ユーザーのDiscord ID（主キー） |
| username   | TEXT | 保存先ユーザー名 |
| filename   | TEXT | 保存ファイル名 |

### `uploads`

| カラム名 | 型 | 説明 |
|----------|----|------|
| discord_id | TEXT | Discord ID |
| username   | TEXT | 保存ユーザー名 |
| filename   | TEXT | ファイル名（拡張子なし） |
| r2_path    | TEXT | R2保存パス |
| created_at | TEXT | アップロード日時（ISO形式） |

---

## ⏰ 自動削除仕様

- 実装：`apscheduler`
- 実行タイミング：毎日 JST 0時
- 処理：
  - `uploads.created_at <= 今日 - 30日` のファイル取得
  - R2 から削除
  - uploads テーブルから削除

---

## 🧪 テスト構成（未実装）

- `tests/` ディレクトリを作成予定
- pytest + mock を使って `db.py`, `r2.py`, `utils.py` を単体テスト可能にする予定

---

## 🧰 今後の拡張予定

| 機能 | 優先度 | 補足 |
|------|--------|------|
| Web UI | ★★★ | FastAPI + Cloudflare Pagesで履歴閲覧 |
| ファイルサイズ制限 | ★☆☆ | yt-dlpオプション調整 |

---

## 🔐 セキュリティ/注意点

- `config.json` は `.gitignore` に含め、Gitに上げない
- Cloudflare R2の `公開URL` は誰でもアクセス可能なので注意
- Botトークンはリーク厳禁（envファイル化も検討）

---

## 📝 ライセンス

MIT License
