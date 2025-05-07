# Discord YouTube Downloader Bot

このプロジェクトは、指定されたYouTube動画をダウンロードし、Cloudflare R2へアップロードするDiscord Botです。動画はユーザーごとに指定名で管理され、30日後に自動削除されます。

---

## ✅ 機能一覧

- `/setname`：アップロード先のユーザー名・ファイル名を設定
- `/upload`：YouTube動画をCloudflare R2に保存し公開URLを取得
- `/myfiles`：アップロード済みの動画一覧とURLを表示
- ⏰ 毎日0時に30日以上前の動画を自動削除

---

## 📁 ディレクトリ構成

```
discord-bot-r2/
├── main.py
├── config.json
├── requirements.txt
├── Dockerfile
├── entrypoint.sh
├── docker-compose.yml
└── bot/
    ├── __init__.py
    ├── core.py
    ├── commands.py
    ├── db.py
    ├── r2.py
    ├── scheduler.py
    ├── utils.py
    └── config.py
```

---

## 🚀 セットアップ手順

### 1. 必要環境

- Python 3.11+
- Docker（推奨）
- Cloudflare R2 アカウント
- Discord Bot Token

### 2. `config.json` を作成

```json
{
  "DISCORD_TOKEN": "your-discord-bot-token",
  "ALLOWED_ROLE": "VideoManager",
  "R2_BUCKET": "your-bucket-name",
  "R2_ENDPOINT": "https://<account_id>.r2.cloudflarestorage.com",
  "R2_ACCESS_KEY": "your-access-key",
  "R2_SECRET_KEY": "your-secret-key",
  "R2_PUBLIC_URL": "https://public.example.com"
}
```

### 3. Dockerで起動

```bash
docker compose up -d --build
```

---

## 📦 使用例

```bash
/setname takumi myvideo
/upload https://www.youtube.com/watch?v=dQw4w9WgXcQ
/myfiles
```

---

## 🔒 注意事項

- ファイル名には `英数字 / _ / -` のみ使用可能
- 公開URLは `R2_PUBLIC_URL` をCloudflare Pagesなどで設定しておく必要があります
- R2料金やトラフィック上限はCloudflareの規約をご確認ください

---

## 📝 ライセンス

MIT License
