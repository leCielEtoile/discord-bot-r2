"""
bot/models.py

データモデルを定義するモジュール。
SQLiteのデータ構造をPythonのデータクラスとしてマッピング。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class UserMapping:
    """
    ユーザーの保存設定
    file_mappingテーブルに対応
    """
    discord_id: str
    folder_name: str
    filename: str = ""
    upload_limit: int = 0
    
    def is_unlimited(self) -> bool:
        """アップロード上限が無制限かどうか"""
        return self.upload_limit <= 0

@dataclass
class UploadEntry:
    """
    アップロード履歴エントリ
    uploadsテーブルに対応
    """
    id: Optional[int]
    discord_id: str
    folder_name: str
    filename: str
    r2_path: str
    created_at: datetime
    title: str = ""
    
    @property
    def display_name(self) -> str:
        """表示用名称を返す（タイトルがない場合はファイル名）"""
        return self.title or self.filename
    
    @property
    def file_with_extension(self) -> str:
        """拡張子付きのファイル名を返す"""
        return f"{self.filename}.mp4"