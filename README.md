# YouTube Downloader Discord Bot

YouTube動画をダウンロードしてCloudflare R2に保存するDiscord Botです。統合されたフレームワーク設計により、権限管理・エラーハンドリング・ログ出力を一元化しています。

## 主な機能

- **YouTube動画ダウンロード**: H.264/AACコーデック優先でWeb再生に最適化
- **統合ファイル管理**: アップロードした動画の一覧表示・詳細表示・削除機能
- **権限ベース管理**: ロールベースのアクセス制御
- **ユーザー設定管理**: フォルダ名やアップロード上限の個別設定

## 必要条件

- Docker & Docker Compose
- Discordアプリケーション（Bot設定済み）
- Cloudflare R2バケット
- FFmpeg（コンテナに含まれています）

## インストール方法

### 1. リポジトリの準備

```bash
# プロジェクトディレクトリを作成
mkdir discord-ytdl-bot
cd discord-ytdl-bot

# 必要なディレクトリを作成
mkdir -p data logs
```

### 2. 設定ファイルの準備

`config.yaml` を作成します：

```yaml
# Discord設定
DISCORD_TOKEN: "your-discord-bot-token"
ADMIN_ROLE: "Admin"
ALLOWED_ROLE: "Uploader"
ALLOWED_GUILD_ID: 123456789012345678

# Cloudflare R2設定
R2_BUCKET: "your-r2-bucket-name"
R2_ENDPOINT: "https://<account-id>.r2.cloudflarestorage.com"
R2_ACCESS_KEY: "your-access-key"
R2_SECRET_KEY: "your-secret-key"
R2_PUBLIC_URL: "https://files.example.com"

# Bot設定
DEFAULT_UPLOAD_LIMIT: 5

# ログ設定
CONSOLE_LOG_LEVEL: "INFO"
FILE_LOG_LEVEL: "DEBUG"
LOG_DIR: "logs"
```

### 3. Docker環境の設定

`docker-compose.yml`:

```yaml
services:
  discord-bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: discord-ytdl-bot
    restart: unless-stopped
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - CONFIG_PATH=/app/config.yaml
      - DB_PATH=/app/data/db.sqlite3
      - XDG_CACHE_HOME=/app/data/cache
    user: "${UID:-1000}:${GID:-1000}"
```

## 起動方法

```bash
# コンテナをビルドして起動
docker-compose up -d

# ログの確認
docker-compose logs -f

# ステータス確認
docker-compose ps
```

## 使い方

### コマンド一覧

| コマンド | 権限 | 説明 |
|---------|------|------|
| `/upload <url> <filename>` | Uploader | YouTube動画をダウンロードしてR2に保存 |
| `/myfiles [view_type]` | 全員 | 自分のアップロードファイル一覧を表示 |
| `/setlimit <user> <limit>` | Admin | ユーザーのアップロード上限を設定 |
| `/changefolder [user]` | Admin | ユーザーのフォルダ名を変更 |

### 基本的な使い方

1. **初期設定**
   - Discordサーバーでbotを招待
   - 必要なロール（`Admin`, `Uploader`）を設定

2. **動画のアップロード**
   ```
   /upload url:https://www.youtube.com/watch?v=xxxxx filename:video_name
   ```

3. **ファイル管理**
   ```
   /myfiles view_type:リスト表示    # 一覧形式で表示
   /myfiles view_type:詳細表示     # 詳細情報付きで表示
   ```

4. **管理者操作**
   ```
   /setlimit user:@username limit:10        # アップロード上限を10に設定
   /changefolder user:@username             # フォルダ名をユーザー名に変更
   ```

## アーキテクチャ

### フォルダ構成

```
discord-ytdl-bot/
├── main.py                    # エントリーポイント
├── bot/
│   ├── core.py               # 統合Bot起動処理
│   ├── data.py               # データマネージャー（モデル + SQLite実装）
│   ├── errors.py             # エラークラス定義
│   ├── ui.py                 # Discord UI コンポーネント
│   ├── youtube.py            # YouTube処理
│   ├── framework/
│   │   └── command_base.py   # コマンドフレームワーク
│   ├── commands/             # スラッシュコマンド実装
│   │   ├── admin_commands.py
│   │   ├── upload_command.py
│   │   └── file_commands.py
│   └── impl/
│       └── r2_service.py     # R2ストレージサービス
├── config.yaml               # 設定ファイル
├── data/                     # データベース永続化ディレクトリ
├── logs/                     # ログファイル保存ディレクトリ
├── Dockerfile
├── docker-compose.yml
└── entrypoint.sh
```

### 技術スタック

- **言語**: Python 3.11
- **Discord**: discord.py (app_commands)
- **データベース**: SQLite3
- **ストレージ**: Cloudflare R2 (S3互換API)
- **動画処理**: yt-dlp + FFmpeg
- **コンテナ**: Docker

### 設計の特徴

1. **統合フレームワーク**: `DiscordBot`クラスで設定・ログ・サービスを一元管理
2. **コマンドフレームワーク**: `BaseCommand`による統一的な権限チェックとエラーハンドリング
3. **データマネージャー**: モデルとSQLite実装を統合した`DataManager`
4. **UI統合**: リスト表示と詳細表示を切り替え可能な`UnifiedFileView`

## 設定

### 環境変数による設定上書き

config.yamlの値は環境変数で上書きできます：

```bash
# 例：docker-compose.ymlで設定
environment:
  - DISCORD_TOKEN=your-token-here
  - R2_BUCKET=your-bucket
  - CONSOLE_LOG_LEVEL=DEBUG
```

### ログレベル設定

- **CONSOLE_LOG_LEVEL**: コンソール出力レベル (DEBUG/INFO/WARNING/ERROR)
- **FILE_LOG_LEVEL**: ファイル出力レベル (通常はDEBUG推奨)

### データベース設定

- SQLite3を使用（`/app/data/db.sqlite3`）
- 自動的にテーブル作成・初期化
- Dockerボリュームで永続化

## 開発者向け情報

### 直接実行方法（開発用）

```bash
# 必要要件: Python 3.11+, FFmpeg, yt-dlp

# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Linux/macOS

# 依存パッケージのインストール
pip install -r requirements.txt
pip install PyYAML  # 必要に応じて

# yt-dlpのインストール
pip install yt-dlp

# 実行
export PYTHONPATH=/path/to/project
python main.py
```

### 新しいコマンドの追加

1. `bot/commands/`に新しいコマンドファイルを作成
2. `BaseCommand`を継承したクラスを実装
3. `bot/core.py`の`_register_commands()`で登録

```python
from bot.framework.command_base import BaseCommand, PermissionLevel

class MyCommand(BaseCommand):
    def __init__(self, data_manager):
        super().__init__(data_manager)
        self.command_name = "mycommand"
        self.set_permission(PermissionLevel.USER)
    
    async def execute_impl(self, interaction, **kwargs):
        await interaction.response.send_message("Hello!")
    
    def setup_discord_command(self, tree):
        @tree.command(name="mycommand", description="My custom command")
        async def mycommand(interaction):
            await self.execute_with_framework(interaction)
```

## トラブルシューティング

### よくある問題

1. **ダウンロードに失敗する**
   - yt-dlpのバージョンを確認
   - ログで詳細なエラーメッセージを確認

2. **権限エラー**
   - `user: "${UID:-1000}:${GID:-1000}"`が正しく設定されているか確認
   - data/, logs/ディレクトリの権限を確認

3. **Discord接続エラー**
   - DISCORD_TOKENが正しく設定されているか確認
   - Botの権限（Send Messages, Use Slash Commands）を確認

4. **R2接続エラー**
   - エンドポイント、キー、バケット名を確認
   - Cloudflare R2の設定を確認

### ログの確認

```bash
# リアルタイムログ
docker-compose logs -f

# 特定のサービスのログ
docker-compose logs discord-bot

# ファイルログ（詳細）
tail -f logs/bot-$(date +%Y-%m-%d).log
```

## セキュリティ

- 設定ファイルには機密情報が含まれるため、適切に保護してください
- Discord Botトークンは絶対に公開しないでください
- R2のアクセスキーは最小限の権限で設定してください

## ライセンス

MIT License

## 貢献

プルリクエストや課題報告を歓迎します。大きな変更を行う前に、まずissueで議論してください。