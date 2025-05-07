"""
db.py

Discord Bot 用の SQLite データベース操作モジュール。
ユーザーごとの保存先フォルダ設定、アップロード履歴の登録・取得・削除などを担当。
"""

import sqlite3
from typing import Optional

# SQLite接続（スレッドセーフ設定付き）
conn = sqlite3.connect("db.sqlite3", detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    """
    初回起動時に必要なテーブルを作成する。
    - file_mapping: 各ユーザーの保存フォルダ名、初期ファイル名、アップロード上限
    - uploads: アップロード履歴
    """
    # file_mapping テーブルを作成（アップロード設定）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_mapping (
        discord_id TEXT PRIMARY KEY,
        folder_name TEXT NOT NULL,
        filename TEXT NOT NULL,
        upload_limit INTEGER DEFAULT 0
    )
    """)

    # uploads テーブルを作成（アップロード履歴）
    cursor.execute("""
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

    conn.commit()

def save_mapping(discord_id: str, folder_name: str, filename: str, upload_limit: int = 0):
    """
    指定ユーザーの保存設定を保存（新規または上書き）。

    Args:
        discord_id: DiscordユーザーID
        folder_name: 保存先フォルダ名
        filename: 初期ファイル名（現在未使用）
        upload_limit: アップロード上限（0は無制限）
    """
    cursor.execute(
        "REPLACE INTO file_mapping (discord_id, folder_name, filename, upload_limit) VALUES (?, ?, ?, ?)",
        (discord_id, folder_name, filename, upload_limit),
    )
    conn.commit()

def get_mapping(discord_id: str) -> Optional[tuple[str, str, int]]:
    """
    指定ユーザーの保存設定を取得。

    Returns:
        (folder_name, filename, upload_limit) のタプル または None
    """
    cursor.execute("SELECT folder_name, filename, upload_limit FROM file_mapping WHERE discord_id = ?", (discord_id,))
    return cursor.fetchone()

def log_upload(discord_id: str, folder_name: str, filename: str, r2_path: str, created_at, title: str):
    """
    アップロード履歴を記録する。

    Args:
        discord_id: ユーザーID
        folder_name: 保存先フォルダ名
        filename: ファイル名（拡張子なし）
        r2_path: R2に保存されたパス
        created_at: アップロード日時
        title: YouTubeタイトル
    """
    cursor.execute(
        """
        INSERT INTO uploads (discord_id, folder_name, filename, r2_path, created_at, title)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (discord_id, folder_name, filename, r2_path, created_at, title),
    )
    conn.commit()

def list_user_files(discord_id: str):
    """
    指定ユーザーがアップロードしたファイルを一覧取得。

    Returns:
        (filename, r2_path, title) のリスト
    """
    cursor.execute("SELECT filename, r2_path, title FROM uploads WHERE discord_id = ?", (discord_id,))
    return cursor.fetchall()

def delete_upload(discord_id: str, filename: str):
    """
    特定ユーザーのファイルを履歴から削除する。

    Args:
        discord_id: ユーザーID
        filename: ファイル名（拡張子なし）
    """
    cursor.execute("DELETE FROM uploads WHERE discord_id = ? AND filename = ?", (discord_id, filename))
    conn.commit()

def delete_old_uploads(before_timestamp):
    """
    指定日時より古いファイル記録を削除。

    Args:
        before_timestamp: ISO8601形式の日付文字列
    """
    cursor.execute("DELETE FROM uploads WHERE created_at < ?", (before_timestamp,))
    conn.commit()
