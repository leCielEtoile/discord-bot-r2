# ベースイメージ
FROM python:3.11-slim AS base

# 依存関係インストール用ステージ
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install
COPY requirements.txt .

# PyYAMLを明示的に追加
RUN echo "PyYAML>=6.0" >> requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 最終イメージ
FROM base
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 依存関係をコピー
COPY --from=builder /install /usr/local

# yt-dlpのインストール
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# タイムゾーン設定
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# アプリケーションのコピー
WORKDIR /app
COPY . .

# 実行権限付与
RUN chmod +x entrypoint.sh

# 設定ファイルパス指定（環境変数でオーバーライド可能）
ENV CONFIG_PATH=/app/config.yaml
ENV PYTHONPATH=/app

# ログディレクトリとデータディレクトリを作成
# 権限設定はdocker-compose.ymlのuserディレクティブで行う
# これにより、ホスト側のユーザー権限で作成される
RUN mkdir -p /app/logs /app/data /app/data/cache

ENTRYPOINT ["./entrypoint.sh"]