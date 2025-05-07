"""
bot/errors.py

ボット全体で使用する例外クラスとエラーハンドリング関数
"""

import discord
import logging

logger = logging.getLogger(__name__)

class BotError(Exception):
    """ボット固有のエラー基底クラス"""
    pass

class UploadError(BotError):
    """アップロード関連のエラー"""
    pass

class StorageError(BotError):
    """R2ストレージ関連のエラー"""
    pass

class DatabaseError(BotError):
    """データベース関連のエラー"""
    pass

class PermissionError(BotError):
    """権限関連のエラー"""
    pass

async def handle_bot_error(error, interaction, log_message="エラーが発生しました"):
    """統一されたエラーハンドリング関数"""
    error_message = f"⚠️ {str(error)}"
    logger.error(f"{log_message}: {error}")
    
    if interaction.response.is_done():
        return await interaction.followup.send(error_message, ephemeral=True)
    else:
        return await interaction.response.send_message(error_message, ephemeral=True)