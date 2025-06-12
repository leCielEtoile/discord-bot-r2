"""
bot/data.py

データ管理の統合モジュール
モデル定義、データベース操作、ビジネスロジックを一元化
"""

import sqlite3
from datetime import datetime
import logging
import os
from typing import List, Optional, NamedTuple
from dataclasses import dataclass

from bot.errors import DatabaseError

logger = logging.getLogger(__name__)

# データクラス定義
@dataclass
class UserMapping:
    """
    ユーザーの保存設定を表すデータクラス
    Discord IDとファイル保存設定の関連付けを管理
    """
    discord_id: str          # Discord ユーザーID
    folder_name: str         # R2上のフォルダ名
    filename: str            # 基本ファイル名（現在は未使用）
    upload_limit: int        # アップロード上限数（0=無制限）
    
    def is_unlimited(self) -> bool:
        """
        アップロード上限が無制限かどうかを判定
        
        Returns:
            bool: 無制限の場合True
        """
        return self.upload_limit <= 0

@dataclass
class UploadEntry:
    """
    アップロード履歴の単一エントリを表すデータクラス
    """
    id: Optional[int]        # データベース内のユニークID
    discord_id: str          # アップロードしたユーザーのDiscord ID
    folder_name: str         # R2上のフォルダ名
    filename: str            # ファイル名（拡張子なし）
    r2_path: str             # R2上の完全パス
    created_at: datetime     # アップロード日時
    title: str = ""          # 動画タイトル（YouTube等から取得）
    
    @property
    def display_name(self) -> str:
        """
        UI表示用の名称を取得
        タイトルが設定されている場合はタイトル、なければファイル名を返す
        """
        return self.title or self.filename
    
    @property
    def file_with_extension(self) -> str:
        """
        拡張子付きのファイル名を取得
        
        Returns:
            str: .mp4拡張子付きファイル名
        """
        return f"{self.filename}.mp4"

class DataManager:
    """
    データベース操作とビジネスロジックを管理するクラス
    SQLiteを使用したデータ永続化を提供
    """
    
    def __init__(self, db_path: str = None):
        """
        DataManagerの初期化
        
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        try:
            # データベースファイルパスの決定
            if db_path is None:
                db_path = os.getenv("DB_PATH", "db.sqlite3")
            
            # データベースディレクトリの作成
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.debug(f"Created database directory: {db_dir}")
            
            # SQLite接続の確立
            self.conn = sqlite3.connect(
                db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES,  # datetime型の自動変換
                check_same_thread=False                # マルチスレッド対応
            )
            self.cursor = self.conn.cursor()
            self._init_tables()
            logger.debug(f"DataManager initialized with db: {db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"データベース接続に失敗しました: {e}")
    
    def _init_tables(self):
        """
        必要なデータベーステーブルの作成
        アプリケーション起動時に実行される
        """
        try:
            # ユーザー設定テーブル
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_mapping (
                discord_id TEXT PRIMARY KEY,
                folder_name TEXT NOT NULL,
                filename TEXT NOT NULL,
                upload_limit INTEGER DEFAULT 0
            )
            """)

            # アップロード履歴テーブル
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
    
    # ユーザー設定操作メソッド
    def save_user_mapping(self, mapping: UserMapping) -> None:
        """
        ユーザーマッピング情報をデータベースに保存
        既存データがある場合は上書きされる
        
        Args:
            mapping: 保存するユーザーマッピング情報
        """
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
        """
        指定されたユーザーIDのマッピング情報を取得
        
        Args:
            discord_id: 取得対象のDiscord ユーザーID
            
        Returns:
            UserMapping: マッピング情報（存在しない場合はNone）
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
    
    # アップロード履歴操作メソッド
    def log_upload(self, entry: UploadEntry) -> None:
        """
        アップロード完了時の履歴をデータベースに記録
        
        Args:
            entry: 記録するアップロードエントリ
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
            logger.debug(f"Upload logged: {entry.filename} for {entry.discord_id}")
            
        except Exception as e:
            logger.error(f"Log upload failed: {e}")
            raise DatabaseError(f"アップロード記録に失敗しました: {e}")
    
    def list_user_files(self, discord_id: str) -> List[UploadEntry]:
        """
        指定ユーザーのアップロードファイル一覧を新しい順で取得
        
        Args:
            discord_id: 取得対象のDiscord ユーザーID
            
        Returns:
            List[UploadEntry]: アップロードエントリのリスト
        """
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
                
                # ISO形式の日時文字列をdatetimeオブジェクトに変換
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except ValueError:
                    # 変換に失敗した場合は現在時刻を使用
                    created_at = datetime.utcnow()
                
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
        指定ユーザーの指定ファイルのアップロード履歴を削除
        
        Args:
            discord_id: ユーザーのDiscord ID
            filename: 削除対象のファイル名
        """
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
    
    # 統計情報取得メソッド
    def get_user_file_count(self, discord_id: str) -> int:
        """
        指定ユーザーのアップロードファイル総数を取得
        
        Args:
            discord_id: ユーザーのDiscord ID
            
        Returns:
            int: ファイル数
        """
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
        """
        システム全体のアップロードファイル総数を取得
        
        Returns:
            int: 全ファイル数
        """
        try:
            self.cursor.execute("SELECT COUNT(*) FROM uploads")
            return self.cursor.fetchone()[0]
            
        except Exception as e:
            logger.error(f"Get total file count failed: {e}")
            raise DatabaseError(f"総ファイル数の取得に失敗しました: {e}")
    
    def close(self):
        """
        データベース接続のクリーンアップ
        アプリケーション終了時に呼び出される
        """
        if hasattr(self, 'conn'):
            self.conn.close()
            logger.debug("Database connection closed")