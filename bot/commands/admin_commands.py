"""
bot/commands/admin_commands.py

管理者向けコマンドの実装
- setlimit: ユーザーのアップロード上限設定
- changefolder: フォルダ名変更
"""

import discord
from discord import app_commands
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.services import DatabaseService
from bot.models import UserMapping
from bot.errors import PermissionError

logger = logging.getLogger(__name__)

class SetLimitCommand(BaseCommand):
    """アップロード上限設定コマンド"""
    
    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service)
        self.command_name = "setlimit"
        self.set_permission(PermissionLevel.ADMIN)
    
    async def execute_impl(self, interaction: discord.Interaction, user: discord.Member, limit: int):
        # 現在の設定を取得
        mapping = self.db.get_user_mapping(str(user.id))
        if not mapping:
            await interaction.response.send_message("⚠️ 対象ユーザーは設定されていません。", ephemeral=True)
            logger.warning(f"setlimit failed: no mapping found for {user}")
            return
        
        # 上限を更新して保存
        mapping.upload_limit = limit
        self.db.save_user_mapping(mapping)
        
        # 応答
        limit_str = "無制限" if limit <= 0 else str(limit)
        await interaction.response.send_message(
            f"✅ {user.display_name} のアップロード上限を {limit_str} に設定しました。",
            ephemeral=True,
        )
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        @tree.command(name="setlimit", description="指定ユーザーのアップロード上限を設定（管理者のみ）")
        @app_commands.describe(user="対象のユーザー", limit="新しいアップロード上限（0で無制限）")
        async def setlimit(interaction: discord.Interaction, user: discord.Member, limit: int):
            await self.execute_with_framework(interaction, user=user, limit=limit)

class ChangeFolderCommand(BaseCommand):
    """フォルダ名変更コマンド"""
    
    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service)
        self.command_name = "changefolder"
        self.set_permission(PermissionLevel.ADMIN)
        self._default_upload_limit = 5
    
    def set_default_upload_limit(self, limit: int):
        """デフォルトアップロード上限を設定"""
        self._default_upload_limit = limit
    
    async def execute_impl(self, interaction: discord.Interaction, user: discord.Member = None):
        # 対象ユーザー
        target = user or interaction.user
        discord_id = str(target.id)
        new_folder_name = target.name
        
        # 現在の設定を取得
        mapping = self.db.get_user_mapping(discord_id)
        
        if not mapping:
            # 新規作成
            mapping = UserMapping(
                discord_id=discord_id,
                folder_name=new_folder_name,
                filename="",
                upload_limit=self._default_upload_limit
            )
            self.db.save_user_mapping(mapping)
            logger.info(f"Folder mapping created for {target}: {new_folder_name}")
        else:
            # 更新
            mapping.folder_name = new_folder_name
            self.db.save_user_mapping(mapping)
            logger.info(f"Folder mapping updated for {target}: {new_folder_name}")
        
        # 応答
        await interaction.response.send_message(
            f"✅ `{target.display_name}` のフォルダ名を `{new_folder_name}` に設定しました。", 
            ephemeral=True
        )
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        @tree.command(name="changefolder", description="対象フォルダを変更します（管理者のみ）")
        @app_commands.describe(user="対象ユーザー（指定しない場合は自身の名前に戻す）")
        async def changefolder(interaction: discord.Interaction, user: discord.Member = None):
            await self.execute_with_framework(interaction, user=user)

def setup_admin_commands(registry: CommandRegistry, db_service: DatabaseService):
    """
    管理者コマンドをレジストリに登録
    """
    registry.register(SetLimitCommand(db_service))
    registry.register(ChangeFolderCommand(db_service))
    
    logger.debug("Admin commands registered")