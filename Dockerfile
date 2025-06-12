# マルチステージビルドでイメージサイズを最適化
FROM python:3.11-slim AS base

# Python依存関係のビルドステージ
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install
COPY requirements.txt .

# PyYAMLを明示的に追加（設定ファイル読み込みに必要）
RUN echo "PyYAML>=6.0" >> requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 実行環境の構築ステージ
FROM base
# システムレベルの必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonライブラリを前ステージからコピー
COPY --from=builder /install /usr/local

# yt-dlpの最新版を直接ダウンロードしてインストール
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# タイムゾーンを日本時間に設定
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# アプリケーションファイルをコピー
WORKDIR /app
COPY . .

# エントリーポイントスクリプトに実行権限を付与
RUN chmod +x entrypoint.sh

# 環境変数の設定（docker-compose.ymlで上書き可能）
ENV CONFIG_PATH=/app/config.yaml
ENV PYTHONPATH=/app

# 必要なディレクトリを事前作成
# 実際の権限設定はdocker-compose.ymlのuserディレクティブで制御
RUN mkdir -p /app/logs /app/data /app/data/cache

ENTRYPOINT ["./entrypoint.sh"]