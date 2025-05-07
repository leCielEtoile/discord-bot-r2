"""
bot/impl/sqlite_service.py

SQLiteデータベースを用いたデータベースサービスの実装
"""

import sqlite3
from datetime import datetime
import logging
import os
from typing import List, Optional, Tuple

from bot.services import DatabaseService
from bot.models import UserMapping, UploadEntry
from bot.errors import DatabaseError

logger = logging.getLogger(__name__)

class SQLiteDatabaseService(DatabaseService):
    """SQLiteを使用したデータベースサービス実装"""
    
    def __init__(self, db_path: str = None):
        """
        SQLite接続の初期化
        
        Args:
            db_path: データベースファイルのパス（Noneの場合は環境変数またはデフォルト値を使用）
        """
        try:
            # データベースパスの取得（優先順位: 引数 > 環境変数 > デフォルト値）
            if db_path is None:
                db_path = os.getenv("DB_PATH", "db.sqlite3")
            
            # データベースディレクトリの存在確認と作成試行
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"Created database directory: {db_dir}")
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not create database directory: {e}")
                    # エラーは無視して続行
            
            # ディレクトリが存在しない場合は代替のファイルパスを試みる
            if db_dir and not os.path.exists(db_dir):
                fallback_path = "db.sqlite3"  # カレントディレクトリに保存
                logger.warning(f"Using fallback database path: {fallback_path}")
                db_path = fallback_path
            
            self.conn = sqlite3.connect(
                db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES, 
                check_same_thread=False
            )
            self.cursor = self.conn.cursor()
            self._init_db()
            logger.info(f"SQLiteDatabaseService initialized with db: {db_path}")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"データベース接続に失敗しました: {e}")
    
    def _init_db(self):
        """必要なテーブルを作成"""
        try:
            # file_mapping テーブルを作成（アップロード設定）
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_mapping (
                discord_id TEXT PRIMARY KEY,
                folder_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                upload_limit INTEGER DEFAULT 0
            )
            """)

            # uploads テーブルを作成（アップロード履歴）
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
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Table initialization failed: {e}")
            raise DatabaseError(f"データベーステーブルの初期化に失敗しました: {e}")
    
    def save_user_mapping(self, mapping: UserMapping) -> None:
        """
        ユーザーマッピング情報を保存
        
        Args:
            mapping: 保存するUserMappingオブジェクト
            
        Raises:
            DatabaseError: 保存失敗時
        """
        try:
            self.cursor.execute(
                "REPLACE INTO file_mapping (discord_id, folder_name, filename, upload_limit) VALUES (?, ?, ?, ?)",
                (mapping.discord_id, mapping.folder_name, mapping.filename, mapping.upload_limit),
            )
            self.conn.commit()
            logger.info(f"User mapping saved for {mapping.discord_id}")
        except Exception as e:
            logger.error(f"Save user mapping failed: {e}")
            raise DatabaseError(f"ユーザー設定の保存に失敗しました: {e}")
    
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
    
    def log_upload(self, entry: UploadEntry) -> None:
        """
        アップロード履歴を記録
        
        Args:
            entry: 記録するUploadEntryオブジェクト
            
        Raises:
            DatabaseError: 記録失敗時
        """
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
            logger.info(f"Upload logged: {entry.filename} for {entry.discord_id}")
        except Exception as e:
            logger.error(f"Log upload failed: {e}")
            raise DatabaseError(f"アップロード記録に失敗しました: {e}")
    
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
        try:
            self.cursor.execute(
                """
                SELECT id, folder_name, filename, r2_path, created_at, title 
                FROM uploads 
                WHERE discord_id = ?
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
                    created_at = datetime.utcnow()  # 変換エラー時はUTC現在時刻を使用
                
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
        """
        特定ユーザーの特定ファイルの履歴を削除
        
        Args:
            discord_id: Discord ID
            filename: ファイル名（拡張子なし）
            
        Raises:
            DatabaseError: 削除失敗時
        """
        try:
            self.cursor.execute(
                "DELETE FROM uploads WHERE discord_id = ? AND filename = ?", 
                (discord_id, filename)
            )
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                logger.info(f"Upload deleted: {filename} for {discord_id}")
            else:
                logger.warning(f"No upload found to delete: {filename} for {discord_id}")
        except Exception as e:
            logger.error(f"Delete upload failed: {e}")
            raise DatabaseError(f"アップロード記録の削除に失敗しました: {e}")
    
    def delete_old_uploads(self, before_date: datetime) -> List[str]:
        """
        指定日時より古いアップロードを削除
        
        Args:
            before_date: この日時より前の記録を削除
            
        Returns:
            List[str]: 削除されたファイルのR2パスリスト
            
        Raises:
            DatabaseError: 削除失敗時
        """
        try:
            # 削除前に対象のR2パスを取得
            self.cursor.execute(
                "SELECT r2_path FROM uploads WHERE created_at < ?", 
                (before_date.isoformat(),)
            )
            deleted_paths = [row[0] for row in self.cursor.fetchall()]
            
            # レコード削除
            self.cursor.execute(
                "DELETE FROM uploads WHERE created_at < ?", 
                (before_date.isoformat(),)
            )
            self.conn.commit()
            
            logger.info(f"Deleted {len(deleted_paths)} old uploads before {before_date}")
            return deleted_paths
        except Exception as e:
            logger.error(f"Delete old uploads failed: {e}")
            raise DatabaseError(f"古いアップロード記録の削除に失敗しました: {e}")