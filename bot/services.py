"""
bot/services.py

各種サービスの抽象クラスを定義するモジュール。
依存性注入パターンを実現するためのインターフェース。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from bot.models import UserMapping, UploadEntry

class StorageService(ABC):
    """ストレージサービスの抽象クラス (R2操作)"""
    
    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        ローカルファイルをリモートストレージにアップロード
        
        Args:
            local_path: ローカルファイルパス
            remote_path: リモート保存先パス
            
        Raises:
            StorageError: アップロード失敗時
        """
        pass
        
    @abstractmethod
    def delete_file(self, remote_path: str) -> None:
        """
        リモートストレージからファイルを削除
        
        Args:
            remote_path: 削除対象ファイルパス
            
        Raises:
            StorageError: 削除失敗時
        """
        pass
        
    @abstractmethod
    def generate_public_url(self, remote_path: str) -> str:
        """
        リモートパスに対応する公開URLを生成
        
        Args:
            remote_path: リモートファイルパス
            
        Returns:
            str: 完全な公開URL
        """
        pass

class DatabaseService(ABC):
    """データベースサービスの抽象クラス (SQLite操作)"""
    
    @abstractmethod
    def save_user_mapping(self, mapping: UserMapping) -> None:
        """
        ユーザーマッピング情報を保存
        
        Args:
            mapping: 保存するUserMappingオブジェクト
            
        Raises:
            DatabaseError: 保存失敗時
        """
        pass
        
    @abstractmethod
    def get_user_mapping(self, discord_id: str) -> Optional[UserMapping]:
        """
        ユーザーIDに紐づくマッピング情報を取得
        
        Args:
            discord_id: Discord ID
            
        Returns:
            Optional[UserMapping]: 見つかった場合はUserMapping、なければNone
            
        Raises:
            DatabaseError: データベースエラー発生時
        """
        pass
        
    @abstractmethod
    def log_upload(self, entry: UploadEntry) -> None:
        """
        アップロード履歴を記録
        
        Args:
            entry: 記録するUploadEntryオブジェクト
            
        Raises:
            DatabaseError: 記録失敗時
        """
        pass
        
    @abstractmethod
    def list_user_files(self, discord_id: str) -> List[UploadEntry]:
        """
        ユーザーのアップロードファイル一覧を取得
        
        Args:
            discord_id: Discord ID
            
        Returns:
            List[UploadEntry]: アップロードエントリのリスト
            
        Raises:
            DatabaseError: 取得失敗時
        """
        pass
        
    @abstractmethod
    def delete_upload(self, discord_id: str, filename: str) -> None:
        """
        特定ユーザーの特定ファイルの履歴を削除
        
        Args:
            discord_id: Discord ID
            filename: ファイル名（拡張子なし）
            
        Raises:
            DatabaseError: 削除失敗時
        """
        pass
        