"""
bot/impl/r2_service.py

Cloudflare R2ストレージサービスの実装
S3互換APIを使用したファイルアップロード・削除・URL生成
"""

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import quote_plus
import logging

from bot.errors import StorageError

logger = logging.getLogger(__name__)

class R2StorageService:
    """
    Cloudflare R2を使用したクラウドストレージサービス
    boto3のS3互換クライアントを使用してR2操作を実装
    """
    
    def __init__(self, bucket, endpoint, access_key, secret_key, public_url):
        """
        R2ストレージクライアントの初期化
        
        Args:
            bucket: R2バケット名
            endpoint: R2エンドポイントURL（アカウント固有）
            access_key: R2 APIアクセスキー
            secret_key: R2 APIシークレットキー
            public_url: ファイル公開用のベースURL
        """
        self.bucket = bucket
        self.public_url = public_url
        
        # boto3でS3互換のR2クライアントを作成
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),  # R2推奨の署名形式
            region_name="auto"                        # R2は自動リージョン選択
        )
        logger.debug(f"R2StorageService initialized for bucket: {bucket}")
    
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        ローカルファイルをR2ストレージにアップロード
        
        Args:
            local_path: アップロード元のローカルファイルパス
            remote_path: R2上の保存先パス
            
        Raises:
            StorageError: アップロード処理が失敗した場合
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
        R2ストレージから指定ファイルを削除
        
        Args:
            remote_path: 削除対象のR2ファイルパス
            
        Raises:
            StorageError: 削除処理が失敗した場合
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
        R2ファイルの公開アクセス用URLを生成
        
        Args:
            remote_path: 公開対象のR2ファイルパス
            
        Returns:
            str: ブラウザでアクセス可能な完全URL
        """
        # URLエンコード（パス区切り文字は保持）
        encoded_path = quote_plus(remote_path, safe='/')
        return f"{self.public_url}/{encoded_path}"