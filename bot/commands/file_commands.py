"""
bot/commands/file_commands.py

ファイル操作関連コマンドの実装
ユーザーのアップロード履歴表示、ファイル管理機能を提供
"""

import discord
from discord import app_commands
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.data import DataManager
from bot.ui import UnifiedFileView

logger = logging.getLogger(__name__)

class MyFilesCommand(BaseCommand):
    """
    ユーザーのアップロード済みファイル一覧を表示するコマンド
    """
    
    def __init__(self, data_manager: DataManager, storage_service):
        """
        コマンドの初期化
        
        Args:
            data_manager: データベース管理インスタンス
            storage_service: ストレージサービスインスタンス
        """
        super().__init__(data_manager, storage_service)
        self.command_name = "myfiles"
        self.set_permission(PermissionLevel.PUBLIC)  # 自分のファイルは誰でも閲覧可能
    
    async def execute_impl(self, interaction: discord.Interaction, view_type: str = "list"):
        """
        ファイル一覧表示の実行処理
        
        Args:
            interaction: Discordインタラクション
            view_type: 表示形式（"list": リスト表示, "detail": 詳細表示）
        """
        # 実行ユーザーのIDを取得
        user_id = str(interaction.user.id)
        
        # 処理時間を考慮して先に応答を遅延設定
        await interaction.response.defer(ephemeral=True)
        
        # データベースからユーザーのファイル一覧を取得
        entries = self.db.list_user_files(user_id)
        
        # ファイルが存在しない場合の処理
        if not entries:
            await interaction.followup.send("📂 アップロード履歴がありません。", ephemeral=True)
            logger.info(f"No files found for {interaction.user}")
            return
        
        # 統合ファイルビューを作成
        view = UnifiedFileView(user_id, entries, self.storage, self.db, view_type)
        
        if view_type == "detail":
            # 詳細表示モード：Embedで1ファイルずつ詳細表示
            embed = view.get_current_embed()
            response = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # リスト表示モード：テキストでファイル一覧表示
            content = view.get_list_content()
            response = await interaction.followup.send(content=content, view=view, ephemeral=True)
        
        # ビューにメッセージ参照を保存（削除時の更新処理で使用）
        view.message = response
        logger.info(f"Displayed file list to {interaction.user} - {len(entries)} files in {view_type} view")
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        """Discord APIにコマンドを登録"""
        @tree.command(name="myfiles", description="アップロード済みの動画ファイル一覧を表示します")
        @app_commands.describe(view_type="表示形式（リスト表示または詳細表示）")
        @app_commands.choices(view_type=[
            discord.app_commands.Choice(name="リスト表示（デフォルト）", value="list"),
            discord.app_commands.Choice(name="詳細表示", value="detail")
        ])
        async def myfiles(interaction: discord.Interaction, view_type: str = "list"):
            await self.execute_with_framework(interaction, view_type=view_type)

def setup_file_commands(registry: CommandRegistry, data_manager: DataManager, storage_service):
    """
    ファイル操作コマンドをコマンドレジストリに登録
    
    Args:
        registry: コマンドレジストリインスタンス
        data_manager: データベース管理インスタンス
        storage_service: ストレージサービスインスタンス
    """
    registry.register(MyFilesCommand(data_manager, storage_service))
    logger.debug("File commands registered to framework")