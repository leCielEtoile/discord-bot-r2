"""
bot/errors.py

アプリケーション固有の例外クラスとエラー処理ユーティリティ
統一されたエラーハンドリングを提供
"""

import discord
import logging

logger = logging.getLogger(__name__)

class BotError(Exception):
    """
    Botアプリケーションの基底例外クラス
    すべてのBot固有エラーはこのクラスを継承する
    """
    pass

class UploadError(BotError):
    """
    YouTube動画のアップロード処理に関連するエラー
    ダウンロード失敗、変換エラー、容量制限等で発生
    """
    pass

class StorageError(BotError):
    """
    R2ストレージ操作に関連するエラー
    アップロード失敗、削除失敗、認証エラー等で発生
    """
    pass

class DatabaseError(BotError):
    """
    データベース操作に関連するエラー
    SQLite操作の失敗時に発生
    """
    pass

class PermissionError(BotError):
    """
    権限チェックに関連するエラー
    コマンド実行権限がない場合に発生
    """
    pass

async def handle_bot_error(error, interaction, log_message="エラーが発生しました"):
    """
    統一されたエラーハンドリング関数
    例外をログに記録し、ユーザーに適切なエラーメッセージを表示
    
    Args:
        error: 発生した例外
        interaction: Discord インタラクション
        log_message: ログに記録するメッセージ
    """
    error_message = f"⚠️ {str(error)}"
    logger.error(f"{log_message}: {error}")
    
    # インタラクションの応答状態に応じて適切な方法でメッセージを送信
    if interaction.response.is_done():
        return await interaction.followup.send(error_message, ephemeral=True)
    else:
        return await interaction.response.send_message(error_message, ephemeral=True)