"""
bot/commands/admin_files_command.py

管理者専用のファイル一覧表示コマンド
全ユーザーのファイル、または指定ユーザーのファイルを表示可能
"""

import discord
from discord import app_commands
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.data import DataManager
from bot.ui import UnifiedFileView

logger = logging.getLogger(__name__)

class AdminFilesCommand(BaseCommand):
    """
    管理者専用でユーザーのファイル一覧を表示するコマンド
    任意のユーザーのファイルを確認・管理可能
    """
    
    def __init__(self, data_manager: DataManager, storage_service):
        """
        コマンドの初期化
        
        Args:
            data_manager: データベース管理インスタンス
            storage_service: ストレージサービスインスタンス
        """
        super().__init__(data_manager, storage_service)
        self.command_name = "adminfiles"
        self.set_permission(PermissionLevel.ADMIN)  # 管理者限定
    
    async def execute_impl(self, interaction: discord.Interaction, user: discord.Member = None, view_type: str = "list"):
        """
        管理者用ファイル一覧表示の実行処理
        
        Args:
            interaction: Discordインタラクション
            user: 表示対象のユーザー（未指定時は実行者自身）
            view_type: 表示形式（"list": リスト表示, "detail": 詳細表示）
        """
        # 対象ユーザーの決定
        target_user = user or interaction.user
        user_id = str(target_user.id)
        
        # 処理時間を考慮して先に応答を遅延設定
        await interaction.response.defer(ephemeral=True)
        
        # データベースからユーザーのファイル一覧を取得
        entries = self.db.list_user_files(user_id)
        
        # ファイルが存在しない場合の処理
        if not entries:
            target_name = target_user.display_name if user else "あなた"
            await interaction.followup.send(
                f"📂 {target_name}のアップロード履歴がありません。", 
                ephemeral=True
            )
            logger.info(f"No files found for user {target_user} (checked by admin {interaction.user})")
            return
        
        # 管理者なので対象ユーザーのファイルを操作可能なビューを作成
        # 注意: ここでは管理者のIDではなく、対象ユーザーのIDを使用
        view = UnifiedFileView(user_id, entries, self.storage, self.db, view_type)
        
        # 管理者用のヘッダー情報を追加
        target_info = f"👤 対象ユーザー: {target_user.display_name}"
        
        if view_type == "detail":
            # 詳細表示モード：Embedで1ファイルずつ詳細表示
            embed = view.get_current_embed()
            # Embedにユーザー情報を追加
            embed.add_field(name="👑 管理者表示", value=target_info, inline=False)
            response = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # リスト表示モード：テキストでファイル一覧表示
            content = f"{target_info}\n{view.get_list_content()}"
            response = await interaction.followup.send(content=content, view=view, ephemeral=True)
        
        # ビューにメッセージ参照を保存
        view.message = response
        logger.info(f"Admin {interaction.user} displayed files for {target_user} - {len(entries)} files in {view_type} view")
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        """Discord APIにコマンドを登録"""
        @tree.command(
            name="adminfiles", 
            description="管理者限定: 指定ユーザーのファイル一覧を表示します"
        )
        @app_commands.describe(
            user="表示対象のユーザー（未指定時は自分のファイル）",
            view_type="表示形式（リスト表示または詳細表示）"
        )
        @app_commands.choices(view_type=[
            discord.app_commands.Choice(name="リスト表示（デフォルト）", value="list"),
            discord.app_commands.Choice(name="詳細表示", value="detail")
        ])
        async def adminfiles(
            interaction: discord.Interaction, 
            user: discord.Member = None, 
            view_type: str = "list"
        ):
            await self.execute_with_framework(interaction, user=user, view_type=view_type)

def setup_admin_files_command(registry: CommandRegistry, data_manager: DataManager, storage_service):
    """
    管理者ファイル一覧コマンドをコマンドレジストリに登録
    
    Args:
        registry: コマンドレジストリインスタンス
        data_manager: データベース管理インスタンス
        storage_service: ストレージサービスインスタンス
    """
    registry.register(AdminFilesCommand(data_manager, storage_service))
    logger.debug("Admin files command registered to framework")