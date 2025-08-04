# syntax=docker/dockerfile:1
# GitHub Container Registry最適化版Dockerfile
FROM python:3.11-slim AS base

# GitHub Container Registryメタデータ
LABEL org.opencontainers.image.source="https://github.com/leCielEtoile/discord-bot-r2"
LABEL org.opencontainers.image.description="YouTube Downloader Discord Bot"
LABEL org.opencontainers.image.licenses="MIT"

# 依存関係ステージ（最もキャッシュ効果が高い部分）
FROM base AS dependencies
LABEL stage=dependencies

# ビルドに必要な最小限のシステムパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /install

# pipの動作最適化設定
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=100
ENV PYTHONUNBUFFERED=1

# requirements.txtを先にコピー（依存関係変更時のみこのレイヤーが再ビルド）
COPY requirements.txt .

# pipとsetuptoolsを最新版にアップグレード（キャッシュマウント使用）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Pythonパッケージをインストール（GitHub Actionsキャッシュ対応）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install \
    --prefer-binary \
    --no-warn-script-location \
    --find-links https://wheel-index.org \
    -r requirements.txt

# yt-dlpの最新版を直接ダウンロード
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /install/bin/yt-dlp \
    && chmod a+rx /install/bin/yt-dlp

# 実行環境ステージ
FROM base AS runtime

# 実行時に必要な最小限のパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 依存関係ステージからPythonライブラリとyt-dlpをコピー
COPY --from=dependencies /install /usr/local

# 環境設定
ENV TZ=Asia/Tokyo
ENV CONFIG_PATH=/app/config.yaml
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# アプリケーションディレクトリの準備
WORKDIR /app
RUN mkdir -p /app/logs /app/data /app/data/cache

# アプリケーションコードのコピー
COPY . .
RUN chmod +x entrypoint.sh

# ビルド情報をラベルに追加（GitHub Actionsで設定される）
ARG BUILD_DATE
ARG VCS_REF
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.revision=$VCS_REF

ENTRYPOINT ["./entrypoint.sh"]