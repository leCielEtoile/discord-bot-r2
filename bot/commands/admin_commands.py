"""
bot/commands/admin_commands.py

管理者専用コマンドの実装
ユーザー設定の変更、権限管理を提供
"""

import discord
from discord import app_commands
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.data import DataManager, UserMapping
from bot.errors import PermissionError

logger = logging.getLogger(__name__)

class SetLimitCommand(BaseCommand):
    """
    ユーザーのアップロード上限を設定する管理者コマンド
    """
    
    def __init__(self, data_manager: DataManager):
        """
        コマンドの初期化
        
        Args:
            data_manager: データベース管理インスタンス
        """
        super().__init__(data_manager)
        self.command_name = "setlimit"
        self.set_permission(PermissionLevel.ADMIN)
    
    async def execute_impl(self, interaction: discord.Interaction, user: discord.Member, limit: int):
        """
        アップロード上限設定の実行処理
        
        Args:
            interaction: Discordインタラクション
            user: 設定対象のユーザー
            limit: 新しいアップロード上限（0で無制限）
        """
        # 対象ユーザーの現在設定を取得
        mapping = self.db.get_user_mapping(str(user.id))
        if not mapping:
            await interaction.response.send_message("⚠️ 対象ユーザーは設定されていません。", ephemeral=True)
            logger.warning(f"setlimit failed: no mapping found for {user}")
            return
        
        # アップロード上限を更新してデータベースに保存
        mapping.upload_limit = limit
        self.db.save_user_mapping(mapping)
        
        # 実行結果をユーザーに通知
        limit_str = "無制限" if limit <= 0 else str(limit)
        await interaction.response.send_message(
            f"✅ {user.display_name} のアップロード上限を {limit_str} に設定しました。",
            ephemeral=True,
        )
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        """Discord APIにコマンドを登録"""
        @tree.command(name="setlimit", description="指定ユーザーのアップロード上限を設定（管理者のみ）")
        @app_commands.describe(user="対象のユーザー", limit="新しいアップロード上限（0で無制限）")
        async def setlimit(interaction: discord.Interaction, user: discord.Member, limit: int):
            await self.execute_with_framework(interaction, user=user, limit=limit)

class ChangeFolderCommand(BaseCommand):
    """
    ユーザーのストレージフォルダ名を変更する管理者コマンド
    """
    
    def __init__(self, data_manager: DataManager):
        """
        コマンドの初期化
        
        Args:
            data_manager: データベース管理インスタンス
        """
        super().__init__(data_manager)
        self.command_name = "changefolder"
        self.set_permission(PermissionLevel.ADMIN)
        self._default_upload_limit = 5
    
    def set_default_upload_limit(self, limit: int):
        """
        新規ユーザー作成時のデフォルトアップロード上限を設定
        
        Args:
            limit: デフォルト上限値
        """
        self._default_upload_limit = limit
    
    async def execute_impl(self, interaction: discord.Interaction, user: discord.Member = None):
        """
        フォルダ名変更の実行処理
        
        Args:
            interaction: Discordインタラクション
            user: 対象ユーザー（未指定時は実行者のフォルダをリセット）
        """
        # 対象ユーザーの決定（未指定時は実行者自身）
        target = user or interaction.user
        discord_id = str(target.id)
        new_folder_name = target.name
        
        # 現在の設定を取得
        mapping = self.db.get_user_mapping(discord_id)
        
        if not mapping:
            # 設定が存在しない場合は新規作成
            mapping = UserMapping(
                discord_id=discord_id,
                folder_name=new_folder_name,
                filename="",
                upload_limit=self._default_upload_limit
            )
            self.db.save_user_mapping(mapping)
            logger.info(f"Folder mapping created for {target}: {new_folder_name}")
        else:
            # 既存設定のフォルダ名を更新
            mapping.folder_name = new_folder_name
            self.db.save_user_mapping(mapping)
            logger.info(f"Folder mapping updated for {target}: {new_folder_name}")
        
        # 実行結果をユーザーに通知
        await interaction.response.send_message(
            f"✅ `{target.display_name}` のフォルダ名を `{new_folder_name}` に設定しました。", 
            ephemeral=True
        )
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        """Discord APIにコマンドを登録"""
        @tree.command(name="changefolder", description="対象フォルダを変更します（管理者のみ）")
        @app_commands.describe(user="対象ユーザー（指定しない場合は自身の名前に戻す）")
        async def changefolder(interaction: discord.Interaction, user: discord.Member = None):
            await self.execute_with_framework(interaction, user=user)

def setup_admin_commands(registry: CommandRegistry, data_manager: DataManager):
    """
    管理者コマンドをコマンドレジストリに登録
    
    Args:
        registry: コマンドレジストリインスタンス
        data_manager: データベース管理インスタンス
    """
    registry.register(SetLimitCommand(data_manager))
    registry.register(ChangeFolderCommand(data_manager))
    
    logger.debug("Admin commands registered to framework")