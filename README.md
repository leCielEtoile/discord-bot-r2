# YouTube Downloader Discord Bot

YouTube動画をダウンロードしてCloudflare R2に保存するDiscord Botです。スラッシュコマンドで簡単に操作できます。

## 主な機能

- YouTube動画を手軽にダウンロード（H.264/AACコーデック優先）
- アップロードした動画をブラウザで閲覧可能
- ファイル一覧表示と削除機能
- ユーザーごとのアップロード上限管理
- 30日以上経過した古いファイルを自動削除

## 必要条件

- Docker
- Discordアプリケーション（Bot設定済み）
- Cloudflare R2バケット

## インストール方法

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/youtube-dl-discord-bot.git
cd youtube-dl-discord-bot

# データディレクトリを作成
mkdir -p data logs
```

### 設定ファイルの準備

```bash
cp config.example.json config.json
```

設定ファイル `config.json` に以下の情報を設定します:

```json
{
  "DISCORD_TOKEN": "your-discord-bot-token",
  "ADMIN_ROLE": "Admin",
  "ALLOWED_ROLE": "Uploader",
  "ALLOWED_GUILD_ID": 123456789012345678,
  "R2_BUCKET": "your-r2-bucket-name",
  "R2_ENDPOINT": "https://<account-id>.r2.cloudflarestorage.com",
  "R2_ACCESS_KEY": "your-access-key",
  "R2_SECRET_KEY": "your-secret-key",
  "R2_PUBLIC_URL": "https://files.example.com",
  "DEFAULT_UPLOAD_LIMIT": 5
}
```

## 起動方法

```bash
# ビルドして起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

## 使い方

### コマンド一覧

- `/upload <url> <filename>` - YouTube動画をダウンロードしてR2に保存
- `/myfiles [view_type]` - アップロードしたファイル一覧を表示
- `/setlimit <user> <limit>` - （管理者のみ）ユーザーのアップロード上限を設定
- `/changefolder <user>` - （管理者のみ）ユーザーのフォルダ名を変更

### 基本的な使い方

1. Discordサーバーでbotを招待
2. `Uploader`ロールを持つユーザーは`/upload`コマンドを使用可能
3. YouTubeのURLとファイル名を指定して動画を保存
4. `/myfiles`コマンドでアップロード済みファイルを確認・削除

## 開発・カスタマイズ

### フォルダ構成

```
discord-ytdl-bot/
├── bot/
│   ├── commands/      # スラッシュコマンド実装
│   ├── impl/          # サービス実装
│   ├── models.py      # データモデル
│   ├── services.py    # サービスインターフェース
│   ├── ui.py          # Discord UI
│   └── ...
├── data/              # データベース保存ディレクトリ
├── logs/              # ログ保存ディレクトリ
├── config.json        # 設定ファイル
├── Dockerfile         # Dockerイメージ定義
├── docker-compose.yml # Dockerコンテナ設定
├── entrypoint.sh      # 起動スクリプト
├── main.py            # メインエントリポイント
└── requirements.txt   # 依存パッケージリスト
```

### 環境変数

`docker-compose.yml`で設定できる環境変数は以下の通りです：

- `DISCORD_TOKEN` - Discord Botトークン（config.jsonの値を上書き）
- `ADMIN_ROLE` - 管理者ロール名（config.jsonの値を上書き）
- `ALLOWED_ROLE` - 許可ロール名（config.jsonの値を上書き）
- `ALLOWED_GUILD_ID` - 許可サーバーID（config.jsonの値を上書き）
- `R2_BUCKET` - R2バケット名（config.jsonの値を上書き）
- `R2_ENDPOINT` - R2エンドポイント（config.jsonの値を上書き）
- `R2_ACCESS_KEY` - R2アクセスキー（config.jsonの値を上書き）
- `R2_SECRET_KEY` - R2シークレットキー（config.jsonの値を上書き）
- `R2_PUBLIC_URL` - 公開URL（config.jsonの値を上書き）
- `DEFAULT_UPLOAD_LIMIT` - デフォルトアップロード上限（config.jsonの値を上書き）
- `DB_PATH` - データベースファイルのパス（デフォルト: `/app/data/db.sqlite3`）
- `LOG_LEVEL` - ログレベル（INFO, DEBUG, など）
- `CONFIG_PATH` - 設定ファイルのパス（デフォルト: `/app/config.json`）

## 開発者向け情報

### 直接実行方法（開発用）

```bash
# Python 3.9+が必要
# FFmpegのインストールが必要

# 仮想環境の作成と有効化
python -m venv venv
source venv/bin/activate  # Linux/macOS
# または
venv\Scripts\activate     # Windows

# 依存パッケージのインストール
pip install -r requirements.txt

# 実行
python main.py
```

## トラブルシューティング

- **ダウンロードに失敗する**: コンテナが正常に起動しているか確認
- **コーデック変換エラー**: ログを確認し、十分なシステムリソースがあるか確認
- **Discordエラー**: Botのトークンと権限を確認
- **R2接続エラー**: バケット設定とアクセスキーを確認

## ライセンス

[MIT License](LICENSE)

## 貢献方法

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/improvement`)
3. 変更をコミット (`git commit -m 'Add improvement'`)
4. ブランチをプッシュ (`git push origin feature/improvement`)
5. プルリクエストを作成
