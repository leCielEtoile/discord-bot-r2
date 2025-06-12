"""
bot/commands/file_commands.py

ファイル一覧表示や操作用コマンドの実装（統合UI対応版）
"""

import discord
from discord import app_commands
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.services import DatabaseService, StorageService
from bot.ui import UnifiedFileView

logger = logging.getLogger(__name__)

class MyFilesCommand(BaseCommand):
    """ファイル一覧表示コマンド"""
    
    def __init__(self, db_service: DatabaseService, storage_service: StorageService):
        super().__init__(db_service, storage_service)
        self.command_name = "myfiles"
        self.set_permission(PermissionLevel.PUBLIC)  # 自分のファイルは誰でも見れる
    
    async def execute_impl(self, interaction: discord.Interaction, view_type: str = "list"):
        # ユーザーID取得
        user_id = str(interaction.user.id)
        
        # 処理開始通知
        await interaction.response.defer(ephemeral=True)
        
        # ファイル一覧をDBから取得
        entries = self.db.list_user_files(user_id)
        
        # ファイルが存在しない場合の応答
        if not entries:
            await interaction.followup.send("📂 アップロード履歴がありません。", ephemeral=True)
            logger.info(f"No files found for {interaction.user}")
            return
        
        # 統合ビューを作成
        view = UnifiedFileView(user_id, entries, self.storage, self.db, view_type)
        
        if view_type == "detail":
            # 詳細表示モード
            embed = view.get_current_embed()
            response = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # リスト表示モード（デフォルト）
            content = view.get_list_content()
            response = await interaction.followup.send(content=content, view=view, ephemeral=True)
        
        # メッセージ参照を保存
        view.message = response
        logger.info(f"Displayed file list to {interaction.user} - {len(entries)} files in {view_type} view")
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        @tree.command(name="myfiles", description="アップロード済みの動画ファイル一覧を表示します")
        @app_commands.describe(view_type="表示形式（リスト表示または詳細表示）")
        @app_commands.choices(view_type=[
            discord.app_commands.Choice(name="リスト表示（デフォルト）", value="list"),
            discord.app_commands.Choice(name="詳細表示", value="detail")
        ])
        async def myfiles(interaction: discord.Interaction, view_type: str = "list"):
            await self.execute_with_framework(interaction, view_type=view_type)

def setup_file_commands(registry: CommandRegistry, db_service: DatabaseService, storage_service: StorageService):
    """
    ファイル操作コマンドをレジストリに登録
    """
    registry.register(MyFilesCommand(db_service, storage_service))
    logger.info("File commands registered")