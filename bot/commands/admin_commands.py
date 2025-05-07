"""
bot/commands/admin_commands.py

管理者向けコマンドの実装
- setlimit: ユーザーのアップロード上限設定
- changefolder: フォルダ名変更
"""

import discord
from discord import app_commands
import logging

from bot.services import DatabaseService
from bot.models import UserMapping
from bot.utils import is_admin
from bot.errors import PermissionError, handle_bot_error
from bot.config import DEFAULT_UPLOAD_LIMIT

logger = logging.getLogger(__name__)

def setup_admin_commands(tree: app_commands.CommandTree, db_service: DatabaseService):
    """
    管理者コマンドをコマンドツリーに登録
    
    Args:
        tree: コマンドツリー
        db_service: データベースサービス
    """
    
    @tree.command(name="setlimit", description="指定ユーザーのアップロード上限を設定（管理者のみ）")
    @app_commands.describe(user="対象のユーザー", limit="新しいアップロード上限（0で無制限）")
    async def setlimit(interaction: discord.Interaction, user: discord.Member, limit: int):
        """
        管理者が対象ユーザーのアップロード可能数（上限）を設定する。
        0 を指定した場合は無制限として扱う。
        """
        logger.info(f"/setlimit invoked by {interaction.user} for {user} with limit={limit}")
        
        try:
            # 管理者権限チェック
            if not is_admin(interaction.user):
                raise PermissionError("管理者権限がありません。")
            
            # 現在の設定を取得
            mapping = db_service.get_user_mapping(str(user.id))
            if not mapping:
                await interaction.response.send_message("⚠️ 対象ユーザーは設定されていません。", ephemeral=True)
                logger.warning(f"setlimit failed: no mapping found for {user}")
                return
            
            # 上限を更新して保存
            mapping.upload_limit = limit
            db_service.save_user_mapping(mapping)
            
            # 応答
            limit_str = "無制限" if limit <= 0 else str(limit)
            await interaction.response.send_message(
                f"✅ {user.display_name} のアップロード上限を {limit_str} に設定しました。",
                ephemeral=True,
            )
            
            logger.info(f"Upload limit updated: {user} = {limit}")
            
        except Exception as e:
            await handle_bot_error(e, interaction, f"setlimit failed: {e}")
    
    @tree.command(name="changefolder", description="対象フォルダを変更します（管理者のみ）")
    @app_commands.describe(user="対象ユーザー（指定しない場合は自身の名前に戻す）")
    async def changefolder(interaction: discord.Interaction, user: discord.Member = None):
        """
        管理者が現在のアップロード先フォルダ名（folder_name）を変更できるコマンド。
        引数なしで実行した場合、自分自身のユーザー名に戻す。
        """
        logger.info(f"/changefolder invoked by {interaction.user} for {user or interaction.user}")
        
        try:
            # 管理者権限チェック
            if not is_admin(interaction.user):
                raise PermissionError("管理者権限がありません。")
            
            # 対象ユーザー
            target = user or interaction.user
            discord_id = str(target.id)
            new_folder_name = target.name
            
            # 現在の設定を取得
            mapping = db_service.get_user_mapping(discord_id)
            
            if not mapping:
                # 新規作成
                mapping = UserMapping(
                    discord_id=discord_id,
                    folder_name=new_folder_name,
                    filename="",
                    upload_limit=DEFAULT_UPLOAD_LIMIT
                )
                db_service.save_user_mapping(mapping)
                logger.info(f"Folder mapping created for {target}: {new_folder_name}")
            else:
                # 更新
                mapping.folder_name = new_folder_name
                db_service.save_user_mapping(mapping)
                logger.info(f"Folder mapping updated for {target}: {new_folder_name}")
            
            # 応答
            await interaction.response.send_message(
                f"✅ `{target.display_name}` のフォルダ名を `{new_folder_name}` に設定しました。", 
                ephemeral=True
            )
            
        except Exception as e:
            await handle_bot_error(e, interaction, f"changefolder failed: {e}")