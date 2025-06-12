#!/bin/bash
set -e

echo "==============================================="
echo "YouTube Downloader Discord Bot - Starting Up"
echo "==============================================="

# yt-dlpのキャッシュディレクトリ設定
export XDG_CACHE_HOME=/app/data/cache
mkdir -p $XDG_CACHE_HOME 2>/dev/null || true
# 権限変更が失敗しても処理を継続（docker-compose.ymlのuser設定に依存）
chmod 777 $XDG_CACHE_HOME 2>/dev/null || echo "Note: Unable to chmod cache directory, using current permissions"

# データベースファイル用ディレクトリの準備
DB_DIR=$(dirname "${DB_PATH:-/app/data/db.sqlite3}")
echo "Database path: ${DB_PATH:-/app/data/db.sqlite3}"
mkdir -p "$DB_DIR" 2>/dev/null || true
chmod 777 "$DB_DIR" 2>/dev/null || echo "Note: Unable to chmod database directory, using current permissions"

# 設定ファイルの存在確認
if [ ! -f "${CONFIG_PATH}" ]; then
    echo "ERROR: Configuration file not found at ${CONFIG_PATH}"
    echo "Please mount a valid configuration file to this location."
    exit 1
fi

# 重要な環境変数の存在チェック（警告レベル）
if [ -z "${DISCORD_TOKEN}" ] && ! grep -q "DISCORD_TOKEN" "${CONFIG_PATH}"; then
    echo "WARNING: DISCORD_TOKEN not found in environment or config file"
fi

if [ -z "${R2_BUCKET}" ] && ! grep -q "R2_BUCKET" "${CONFIG_PATH}"; then
    echo "WARNING: R2_BUCKET not found in environment or config file"
fi

# ディレクトリの書き込み権限確認と修正試行
echo "Checking directory permissions..."
if [ ! -w "/app/logs" ]; then
    echo "WARNING: Cannot write to /app/logs directory"
    echo "Attempting to fix permissions..."
    mkdir -p /app/logs
    chmod -R 777 /app/logs
fi

if [ ! -w "/app/data" ]; then
    echo "WARNING: Cannot write to /app/data directory"
    echo "Attempting to fix permissions..."
    mkdir -p /app/data
    chmod -R 777 /app/data
fi

# システムツールのバージョン確認
echo "FFmpeg version:"
ffmpeg -version | head -n 1

echo "yt-dlp version:"
yt-dlp --version

# Python依存関係の確認（PyYAMLが重要）
echo "Checking for PyYAML..."
if ! pip list | grep -q "PyYAML"; then
    echo "Installing PyYAML..."
    pip install PyYAML
fi

# 起動情報の表示
echo "Starting Discord Bot..."
echo "Configuration file: ${CONFIG_PATH}"
echo "Logs will be available in /app/logs directory"
echo "Database will be stored in ${DB_PATH:-/app/data/db.sqlite3}"
echo "==============================================="

# Pythonパスを明示的に設定
export PYTHONPATH=/app

# Botアプリケーションの実行
exec python /app/main.py