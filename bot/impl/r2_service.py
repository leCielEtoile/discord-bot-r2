"""
bot/impl/r2_service.py

Cloudflare R2（S3互換API）を用いたストレージサービスの実装
"""

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import quote_plus
import logging

from bot.services import StorageService
from bot.errors import StorageError

logger = logging.getLogger(__name__)

class R2StorageService(StorageService):
    """Cloudflare R2を使用したストレージサービス実装"""
    
    def __init__(self, bucket, endpoint, access_key, secret_key, public_url):
        """
        R2接続の初期化
        
        Args:
            bucket: R2バケット名
            endpoint: R2エンドポイントURL
            access_key: R2アクセスキー
            secret_key: R2シークレットキー
            public_url: 公開URLのベース
        """
        self.bucket = bucket
        self.public_url = public_url
        
        # S3互換のboto3クライアントを初期化
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),  # Cloudflare推奨の署名バージョン
            region_name="auto"  # R2は自動リージョン
        )
        logger.info(f"R2StorageService initialized for bucket: {bucket}")
    
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        ローカルファイルをR2にアップロード
        
        Args:
            local_path: ローカルファイルのフルパス
            remote_path: R2上の保存パス
            
        Raises:
            StorageError: アップロード失敗時
        """
        try:
            with open(local_path, "rb") as file:
                self.s3_client.upload_fileobj(file, self.bucket, remote_path)
            logger.info(f"File uploaded: {local_path} -> {remote_path}")
        except (BotoCoreError, ClientError) as e:
            logger.error(f"R2 upload failed: {e}")
            raise StorageError(f"R2へのアップロードに失敗しました: {e}")
        except Exception as e:
            logger.error(f"Unexpected upload error: {e}")
            raise StorageError(f"ファイルアップロード中にエラーが発生しました: {e}")
    
    def delete_file(self, remote_path: str) -> None:
        """
        指定されたパスのファイルをR2から削除
        
        Args:
            remote_path: 削除対象のR2ファイルパス
            
        Raises:
            StorageError: 削除失敗時
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=remote_path)
            logger.info(f"File deleted from R2: {remote_path}")
        except (BotoCoreError, ClientError) as e:
            logger.error(f"R2 delete failed: {e}")
            raise StorageError(f"R2からの削除に失敗しました: {e}")
        except Exception as e:
            logger.error(f"Unexpected delete error: {e}")
            raise StorageError(f"ファイル削除中にエラーが発生しました: {e}")
    
    def generate_public_url(self, remote_path: str) -> str:
        """
        指定されたR2パスに基づいて公開URLを生成
        
        Args:
            remote_path: 公開対象のファイルパス
            
        Returns:
            str: 完全な公開URL
        """
        # /はパス区切りとして扱いたいのでエンコードしない
        return f"{self.public_url}/{quote_plus(remote_path, safe='/')}"