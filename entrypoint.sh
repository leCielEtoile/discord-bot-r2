#!/bin/bash
set -e

echo "==============================================="
echo "YouTube Downloader Discord Bot - Starting Up"
echo "==============================================="

# yt-dlpのキャッシュディレクトリ設定
export XDG_CACHE_HOME=/app/data/cache
mkdir -p $XDG_CACHE_HOME 2>/dev/null || true

# データベースディレクトリの確認と作成
DB_DIR=$(dirname "${DB_PATH:-/app/data/db.sqlite3}")
echo "Database path: ${DB_PATH:-/app/data/db.sqlite3}"

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

# ディレクトリの権限確認
echo "Checking directory permissions..."
if [ ! -w "/app/logs" ]; then
    echo "WARNING: Cannot write to /app/logs directory"
    echo "Attempting to fix permissions..."
    mkdir -p /app/logs
    chmod -R 777 /app/logs 2>/dev/null || true
fi

if [ ! -w "/app/data" ]; then
    echo "WARNING: Cannot write to /app/data directory"
    echo "Attempting to fix permissions..."
    mkdir -p /app/data
    chmod -R 777 /app/data 2>/dev/null || true
fi

# FFmpegの確認
echo "FFmpeg version:"
ffmpeg -version | head -n 1

# yt-dlp のバージョン確認
echo "yt-dlp version:"
yt-dlp --version

# 依存パッケージ確認
echo "Checking for PyYAML..."
if ! pip show PyYAML >/dev/null 2>&1; then
    echo "Installing PyYAML..."
    pip install PyYAML
else
    echo "PyYAML is already installed"
fi

# 開始メッセージ
echo "Starting Discord Bot..."
echo "Configuration file: ${CONFIG_PATH}"
echo "Logs will be available in /app/logs directory"
echo "Database will be stored in ${DB_PATH:-/app/data/db.sqlite3}"
echo "==============================================="

# Pythonパスの設定
export PYTHONPATH=/app

# Botアプリケーションの実行
exec python /app/main.py