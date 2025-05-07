"""
r2.py

Cloudflare R2（S3互換 API）を用いて動画ファイルのアップロード・削除・公開URL生成を行う。
"""

import boto3
from botocore.client import Config
from urllib.parse import quote_plus

from bot.config import (
    R2_BUCKET,         # R2 バケット名（例: 'mybucket'）
    R2_ENDPOINT,       # R2 エンドポイントURL（例: 'https://<account-id>.r2.cloudflarestorage.com'）
    R2_ACCESS_KEY,     # R2 のアクセスキー
    R2_SECRET_KEY,     # R2 のシークレットキー
    R2_PUBLIC_URL,     # 公開URLのベース（例: 'https://files.example.com'）
)

# S3 互換の boto3 クライアントを初期化
# Cloudflare R2 は S3 API に準拠しているため、S3 クライアントでアクセス可能
s3_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),  # Cloudflare 推奨の署名バージョン
    region_name="auto"  # R2は自動リージョン
)

def upload_to_r2(local_path: str, r2_path: str) -> None:
    """
    ローカルファイルを R2 にアップロードする。

    Args:
        local_path: ローカルファイルのフルパス
        r2_path: R2 上の保存パス（例: username/filename.mp4）
    """
    with open(local_path, "rb") as file:
        s3_client.upload_fileobj(file, R2_BUCKET, r2_path)

def delete_from_r2(r2_path: str) -> None:
    """
    指定されたパスのファイルを R2 から削除する。

    Args:
        r2_path: 削除対象の R2 ファイルパス
    Raises:
        RuntimeError: 削除に失敗した場合
    """
    try:
        s3_client.delete_object(Bucket=R2_BUCKET, Key=r2_path)
        logger.info(f"Delete success: {r2_path}")
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Delete from R2 failed: {e}")
        raise RuntimeError(f"R2からの削除に失敗しました: {e}")


def generate_public_url(r2_path: str) -> str:
    """
    指定された R2 パスに基づいて公開URLを生成する。

    Args:
        r2_path: 公開対象のファイルパス（例: 'username/filename.mp4'）

    Returns:
        完全な公開URL（例: https://files.example.com/username/filename.mp4）
    """
    # / はパス区切りとして扱いたいのでエンコードしない
    return f"{R2_PUBLIC_URL}/{quote_plus(r2_path, safe='/')}"
