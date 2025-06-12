"""
bot/commands/file_commands.py

ファイル一覧表示や操作用コマンドの実装（統合UI対応版）
"""

import discord
from discord import app_commands
import logging

from bot.services import DatabaseService, StorageService
from bot.ui import UnifiedFileView
from bot.errors import handle_bot_error

logger = logging.getLogger(__name__)

def setup_file_commands(
    tree: app_commands.CommandTree, 
    db_service: DatabaseService, 
    storage_service: StorageService
):
    """
    ファイル操作コマンドをコマンドツリーに登録
    
    Args:
        tree: コマンドツリー
        db_service: データベースサービス
        storage_service: ストレージサービス
    """
    
    @tree.command(name="myfiles", description="アップロード済みの動画ファイル一覧を表示します")
    @app_commands.describe(view_type="表示形式（リスト表示または詳細表示）")
    @app_commands.choices(view_type=[
        discord.app_commands.Choice(name="リスト表示（デフォルト）", value="list"),
        discord.app_commands.Choice(name="詳細表示", value="detail")
    ])
    async def myfiles(interaction: discord.Interaction, view_type: str = "list"):
        """
        自分の保存フォルダにアップロードされた動画を一覧表示する。
        統合UIでページネーションと削除機能が含まれる。
        
        Args:
            interaction: Discordインタラクション
            view_type: 表示形式（"list"または"detail"）
        """
        logger.info(f"/myfiles invoked by {interaction.user} with view_type={view_type}")
        
        try:
            # ユーザーID取得
            user_id = str(interaction.user.id)
            
            # 処理開始通知
            await interaction.response.defer(ephemeral=True)
            
            # ファイル一覧をDBから取得
            entries = db_service.list_user_files(user_id)
            
            # ファイルが存在しない場合の応答
            if not entries:
                await interaction.followup.send("📂 アップロード履歴がありません。", ephemeral=True)
                logger.info(f"No files found for {interaction.user}")
                return
            
            # 統合ビューを作成
            try:
                view = UnifiedFileView(user_id, entries, storage_service, db_service, view_type)
                
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
                
            except Exception as e:
                logger.error(f"/myfiles UI generation error: {e}")
                await interaction.followup.send("⚠️ 表示に失敗しました。", ephemeral=True)
                
        except Exception as e:
            await handle_bot_error(e, interaction, f"myfiles failed: {e}")