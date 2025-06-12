"""
bot/data.py

統合データマネージャー
モデル、サービス、SQLite実装を一元化
"""

import sqlite3
from datetime import datetime
import logging
import os
from typing import List, Optional, NamedTuple
from dataclasses import dataclass

from bot.errors import DatabaseError

logger = logging.getLogger(__name__)

# データモデル定義
@dataclass
class UserMapping:
    """ユーザーの保存設定"""
    discord_id: str
    folder_name: str
    filename: str = ""
    upload_limit: int = 0
    
    def is_unlimited(self) -> bool:
        """アップロード上限が無制限かどうか"""
        return self.upload_limit <= 0

@dataclass
class UploadEntry:
    """アップロード履歴エントリ"""
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

class DataManager:
    """
    統合データマネージャー
    SQLite操作とモデル管理を一元化
    """
    
    def __init__(self, db_path: str = None):
        """
        DataManagerの初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        try:
            # データベースパスの取得
            if db_path is None:
                db_path = os.getenv("DB_PATH", "db.sqlite3")
            
            # データベースディレクトリ作成
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.debug(f"Created database directory: {db_dir}")
            
            # SQLite接続
            self.conn = sqlite3.connect(
                db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES, 
                check_same_thread=False
            )
            self.cursor = self.conn.cursor()
            self._init_tables()
            logger.debug(f"DataManager initialized with db: {db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"データベース接続に失敗しました: {e}")
    
    def _init_tables(self):
        """必要なテーブルを作成"""
        try:
            # file_mapping テーブル
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_mapping (
                discord_id TEXT PRIMARY KEY,
                folder_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                upload_limit INTEGER DEFAULT 0
            )
            """)

            # uploads テーブル
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                r2_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                title TEXT DEFAULT ''
            )
            """)

            self.conn.commit()
            logger.debug("Database tables initialized")
            
        except Exception as e:
            logger.error(f"Table initialization failed: {e}")
            raise DatabaseError(f"データベーステーブルの初期化に失敗しました: {e}")
    
    # ユーザーマッピング操作
    def save_user_mapping(self, mapping: UserMapping) -> None:
        """ユーザーマッピング情報を保存"""
        try:
            self.cursor.execute(
                "REPLACE INTO file_mapping (discord_id, folder_name, filename, upload_limit) VALUES (?, ?, ?, ?)",
                (mapping.discord_id, mapping.folder_name, mapping.filename, mapping.upload_limit),
            )
            self.conn.commit()
            logger.debug(f"User mapping saved for {mapping.discord_id}")
            
        except Exception as e:
            logger.error(f"Save user mapping failed: {e}")
            raise DatabaseError(f"ユーザー設定の保存に失敗しました: {e}")
    
    def get_user_mapping(self, discord_id: str) -> Optional[UserMapping]:
        """ユーザーIDに紐づくマッピング情報を取得"""
        try:
            self.cursor.execute(
                "SELECT folder_name, filename, upload_limit FROM file_mapping WHERE discord_id = ?", 
                (discord_id,)
            )
            result = self.cursor.fetchone()
            
            if result:
                folder_name, filename, upload_limit = result
                return UserMapping(
                    discord_id=discord_id,
                    folder_name=folder_name,
                    filename=filename,
                    upload_limit=upload_limit
                )
            return None
            
        except Exception as e:
            logger.error(f"Get user mapping failed: {e}")
            raise DatabaseError(f"ユーザー設定の取得に失敗しました: {e}")
    
    # アップロード履歴操作
    def log_upload(self, entry: UploadEntry) -> None:
        """アップロード履歴を記録"""
        try:
            self.cursor.execute(
                """
                INSERT INTO uploads (discord_id, folder_name, filename, r2_path, created_at, title)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.discord_id, 
                    entry.folder_name, 
                    entry.filename, 
                    entry.r2_path, 
                    entry.created_at.isoformat(), 
                    entry.title
                ),
            )
            self.conn.commit()
            logger.debug(f"Upload logged: {entry.filename} for {entry.discord_id}")
            
        except Exception as e:
            logger.error(f"Log upload failed: {e}")
            raise DatabaseError(f"アップロード記録に失敗しました: {e}")
    
    def list_user_files(self, discord_id: str) -> List[UploadEntry]:
        """ユーザーのアップロードファイル一覧を取得"""
        try:
            self.cursor.execute(
                """
                SELECT id, folder_name, filename, r2_path, created_at, title 
                FROM uploads 
                WHERE discord_id = ?
                ORDER BY created_at DESC
                """, 
                (discord_id,)
            )
            
            entries = []
            for row in self.cursor.fetchall():
                id, folder_name, filename, r2_path, created_at_str, title = row
                
                # ISO形式の日時文字列をdatetimeに変換
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except ValueError:
                    created_at = datetime.utcnow()  # 変換エラー時は現在時刻
                
                entries.append(UploadEntry(
                    id=id,
                    discord_id=discord_id,
                    folder_name=folder_name,
                    filename=filename,
                    r2_path=r2_path,
                    created_at=created_at,
                    title=title
                ))
            
            return entries
            
        except Exception as e:
            logger.error(f"List user files failed: {e}")
            raise DatabaseError(f"ファイル一覧の取得に失敗しました: {e}")
    
    def delete_upload(self, discord_id: str, filename: str) -> None:
        """特定ユーザーの特定ファイルの履歴を削除"""
        try:
            self.cursor.execute(
                "DELETE FROM uploads WHERE discord_id = ? AND filename = ?", 
                (discord_id, filename)
            )
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                logger.debug(f"Upload deleted: {filename} for {discord_id}")
            else:
                logger.warning(f"No upload found to delete: {filename} for {discord_id}")
                
        except Exception as e:
            logger.error(f"Delete upload failed: {e}")
            raise DatabaseError(f"アップロード記録の削除に失敗しました: {e}")
    
    # ユーティリティメソッド
    def get_user_file_count(self, discord_id: str) -> int:
        """ユーザーのファイル数を取得"""
        try:
            self.cursor.execute(
                "SELECT COUNT(*) FROM uploads WHERE discord_id = ?", 
                (discord_id,)
            )
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Get user file count failed: {e}")
            raise DatabaseError(f"ファイル数の取得に失敗しました: {e}")
    
    def get_total_file_count(self) -> int:
        """全ファイル数を取得"""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM uploads")
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Get total file count failed: {e}")
            raise DatabaseError(f"総ファイル数の取得に失敗しました: {e}")
    
    def close(self):
        """データベース接続を閉じる"""
        if hasattr(self, 'conn'):
            self.conn.close()
            logger.debug("Database connection closed")