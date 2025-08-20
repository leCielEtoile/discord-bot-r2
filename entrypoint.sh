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

# yt-dlp自動更新処理
YT_DLP_PATH="/app/data/yt-dlp"
YT_DLP_VERSION_FILE="/app/data/yt-dlp-version"

echo "Checking yt-dlp version..."

# GitHubリリースAPIから最新バージョンを取得
get_latest_version() {
    curl -s "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest" | \
    grep '"tag_name":' | \
    sed -E 's/.*"tag_name": "([^"]+)".*/\1/' || echo "unknown"
}

# 現在インストールされているバージョンを確認
get_current_version() {
    if [ -f "$YT_DLP_VERSION_FILE" ]; then
        cat "$YT_DLP_VERSION_FILE"
    else
        echo "none"
    fi
}

# yt-dlpのダウンロードと配置
download_ytdlp() {
    local version=$1
    echo "Downloading yt-dlp version $version..."
    
    # 一時ダウンロード先
    local temp_path="/tmp/yt-dlp-download"
    
    # ダウンロード試行（3回まで）
    local download_success=false
    for i in {1..3}; do
        if curl -L --connect-timeout 30 --max-time 300 \
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" \
            -o "$temp_path"; then
            download_success=true
            break
        else
            echo "Download attempt $i failed, retrying..."
            sleep 2
        fi
    done
    
    if [ "$download_success" = false ]; then
        echo "ERROR: Failed to download yt-dlp after 3 attempts"
        return 1
    fi
    
    # ダウンロードしたファイルの検証
    if [ ! -s "$temp_path" ]; then
        echo "ERROR: Downloaded yt-dlp file is empty"
        rm -f "$temp_path"
        return 1
    fi
    
    # ファイルの配置と権限設定
    mv "$temp_path" "$YT_DLP_PATH"
    chmod +x "$YT_DLP_PATH"
    
    # バージョン情報を保存
    echo "$version" > "$YT_DLP_VERSION_FILE"
    
    echo "yt-dlp version $version installed successfully"
    return 0
}

# yt-dlpのバージョンチェックとアップデート
check_and_update_ytdlp() {
    echo "Fetching latest yt-dlp version information..."
    
    # 最新バージョンを取得（タイムアウト付き）
    local latest_version
    latest_version=$(timeout 30 get_latest_version)
    
    if [ "$latest_version" = "unknown" ] || [ -z "$latest_version" ]; then
        echo "WARNING: Could not fetch latest yt-dlp version from GitHub"
        
        # 既存のyt-dlpが存在するかチェック
        if [ -f "$YT_DLP_PATH" ] && [ -x "$YT_DLP_PATH" ]; then
            echo "Using existing yt-dlp binary"
            return 0
        else
            echo "ERROR: No yt-dlp binary found and cannot fetch latest version"
            echo "Attempting to download anyway..."
            if download_ytdlp "latest"; then
                return 0
            else
                return 1
            fi
        fi
    fi
    
    local current_version
    current_version=$(get_current_version)
    
    echo "Current yt-dlp version: $current_version"
    echo "Latest yt-dlp version: $latest_version"
    
    # バージョン比較とダウンロード判定
    if [ "$current_version" != "$latest_version" ] || [ ! -f "$YT_DLP_PATH" ] || [ ! -x "$YT_DLP_PATH" ]; then
        echo "Updating yt-dlp..."
        if download_ytdlp "$latest_version"; then
            echo "yt-dlp updated successfully"
        else
            echo "ERROR: Failed to update yt-dlp"
            
            # フォールバック: 既存のyt-dlpがあるかチェック
            if [ -f "$YT_DLP_PATH" ] && [ -x "$YT_DLP_PATH" ]; then
                echo "WARNING: Using existing yt-dlp binary"
                return 0
            else
                return 1
            fi
        fi
    else
        echo "yt-dlp is already up to date"
    fi
    
    return 0
}

# yt-dlpの更新チェック実行
if ! check_and_update_ytdlp; then
    echo "CRITICAL: Could not ensure yt-dlp is available"
    exit 1
fi

# PATHにyt-dlpを追加
export PATH="/app/data:$PATH"

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
if "$YT_DLP_PATH" --version; then
    echo "yt-dlp is working correctly"
else
    echo "ERROR: yt-dlp is not working properly"
    exit 1
fi

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
echo "yt-dlp binary location: ${YT_DLP_PATH}"
echo "==============================================="

# Pythonパスの設定
export PYTHONPATH=/app

# Botアプリケーションの実行
exec python /app/main.py