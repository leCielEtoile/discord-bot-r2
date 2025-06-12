"""
bot/ui.py

Discord Bot におけるファイル閲覧・操作用のUIコンポーネント（統合版）
"""

import discord
import logging
from typing import List
from datetime import datetime
import math

from bot.models import UploadEntry
from bot.services import StorageService, DatabaseService
from bot.errors import StorageError, DatabaseError

logger = logging.getLogger(__name__)

# アイコン定義（絵文字）
ICONS = {
    "video": "🎬",
    "play": "▶️",
    "delete": "🗑️",
    "list": "📋",
    "detail": "📄",
    "prev": "◀️",
    "next": "▶️",
    "info": "ℹ️",
    "link": "🔗",
    "calendar": "📅",
    "name": "📄"
}

# ページあたりの表示件数
FILES_PER_PAGE = 5

class UnifiedFileView(discord.ui.View):
    """
    統合ファイル表示ビュー。
    リスト表示と詳細表示を切り替え可能。
    """

    def __init__(self, user_id: str, entries: List[UploadEntry], 
                 storage_service: StorageService, db_service: DatabaseService, 
                 view_mode: str = "list"):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.storage = storage_service
        self.db = db_service
        self.entries = entries
        self.total_entries = len(entries)
        self.page = 0
        self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
        self.view_mode = view_mode  # "list" or "detail"
        self.message = None
        
        self._update_view()

    def _update_view(self):
        """ビューの更新（ボタンの再構成）"""
        self.clear_items()
        
        if not self.entries:
            return
        
        # 表示モード切替ボタン
        mode_button = discord.ui.Button(
            label=f"{ICONS['detail'] if self.view_mode == 'list' else ICONS['list']} {'詳細表示' if self.view_mode == 'list' else 'リスト表示'}", 
            style=discord.ButtonStyle.secondary, 
            row=0
        )
        mode_button.callback = self.switch_view_mode
        self.add_item(mode_button)
        
        # ページネーションボタン（複数ページある場合のみ）
        if self.total_pages > 1:
            # 前のページへ
            prev_button = discord.ui.Button(
                label=ICONS['prev'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == 0),
                row=0
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            
            # ページ情報ラベル
            page_label = discord.ui.Button(
                label=f"{self.page + 1}/{self.total_pages}", 
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=0
            )
            self.add_item(page_label)
            
            # 次のページへ
            next_button = discord.ui.Button(
                label=ICONS['next'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == self.total_pages - 1),
                row=0
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # 現在のページの項目
        start_idx = self.page * FILES_PER_PAGE
        end_idx = min(start_idx + FILES_PER_PAGE, len(self.entries))
        
        if self.view_mode == "list":
            # リスト表示：各ファイルに再生・削除ボタン
            for i in range(start_idx, end_idx):
                entry = self.entries[i]
                row = 1 + (i - start_idx)
                
                # 動画ファイルへのリンクボタン
                play_button = discord.ui.Button(
                    label=f"{ICONS['play']} {entry.display_name[:30]}{'...' if len(entry.display_name) > 30 else ''}",
                    style=discord.ButtonStyle.primary,
                    row=row,
                    url=self.storage.generate_public_url(entry.r2_path)
                )
                self.add_item(play_button)
                
                # 削除ボタン
                delete_button = discord.ui.Button(
                    label=f"{ICONS['delete']}",
                    style=discord.ButtonStyle.danger,
                    row=row,
                    custom_id=f"delete_{entry.filename}"
                )
                delete_button.callback = self.make_delete_callback(entry.filename, entry.r2_path)
                self.add_item(delete_button)
        
        elif self.view_mode == "detail" and self.entries:
            # 詳細表示：現在のファイルのアクションボタン
            current_entry = self.entries[start_idx]
            
            # 公開URLボタン
            play_button = discord.ui.Button(
                label=f"{ICONS['play']} 再生", 
                style=discord.ButtonStyle.success,
                row=1,
                url=self.storage.generate_public_url(current_entry.r2_path)
            )
            self.add_item(play_button)
            
            # 削除ボタン
            delete_button = discord.ui.Button(
                label=f"{ICONS['delete']} 削除", 
                style=discord.ButtonStyle.danger,
                row=1
            )
            delete_button.callback = self.make_delete_callback(current_entry.filename, current_entry.r2_path)
            self.add_item(delete_button)

    def make_delete_callback(self, filename: str, path: str):
        """削除ボタンのコールバック関数を生成"""
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ あなたのファイルではありません。", ephemeral=True)
                return
            
            # 削除確認ビュー
            confirm_view = discord.ui.View()
            confirm_button = discord.ui.Button(
                label=f"{ICONS['delete']} 削除する", 
                style=discord.ButtonStyle.danger
            )
            cancel_button = discord.ui.Button(
                label="キャンセル", 
                style=discord.ButtonStyle.secondary
            )
            
            async def confirm_callback(confirm_interaction: discord.Interaction):
                try:
                    # R2とDBから削除
                    self.storage.delete_file(path)
                    self.db.delete_upload(self.user_id, filename)
                    
                    # エントリリストから削除
                    self.entries = [e for e in self.entries if e.filename != filename]
                    self.total_entries = len(self.entries)
                    self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
                    
                    # ページ調整
                    if self.page >= self.total_pages:
                        self.page = max(0, self.total_pages - 1)
                    
                    await confirm_interaction.response.edit_message(
                        content=f"✅ `{filename}.mp4` を削除しました。",
                        view=None
                    )
                    
                    # メインビュー更新
                    if self.message:
                        if self.total_entries == 0:
                            await self.message.edit(
                                content="📂 アップロード履歴がありません。",
                                embed=None,
                                view=None
                            )
                        else:
                            self._update_view()
                            if self.view_mode == "detail":
                                embed = self.get_current_embed()
                                await self.message.edit(embed=embed, view=self)
                            else:
                                content = self.get_list_content()
                                await self.message.edit(content=content, view=self)
                    
                    logger.info(f"File deleted: {path}")
                    
                except (StorageError, DatabaseError) as e:
                    await confirm_interaction.response.edit_message(
                        content=f"⚠️ 削除に失敗しました: {e}",
                        view=None
                    )
                    logger.error(f"Failed to delete {path}: {e}")
            
            async def cancel_callback(cancel_interaction: discord.Interaction):
                await cancel_interaction.response.edit_message(
                    content="❌ 削除をキャンセルしました。",
                    view=None
                )
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            await interaction.response.send_message(
                f"⚠️ `{filename}.mp4` を削除しますか？この操作は元に戻せません。",
                view=confirm_view,
                ephemeral=True
            )
            
        return callback

    def get_list_content(self):
        """リストビューのコンテンツを生成"""
        if not self.entries:
            return "📂 アップロード履歴がありません。"
        return f"📂 ファイル一覧 ({self.total_entries}件) - ページ {self.page + 1}/{self.total_pages}"

    def get_current_embed(self):
        """詳細ビューの現在のページに対応するEmbedを生成"""
        if not self.entries:
            return discord.Embed(
                title="ファイルがありません",
                description="アップロードされたファイルがありません。",
                color=discord.Color.light_grey()
            )
        
        start_idx = self.page * FILES_PER_PAGE
        entry = self.entries[start_idx]
        
        created_at_str = entry.created_at.strftime("%Y年%m月%d日 %H:%M")
        
        embed = discord.Embed(
            title=entry.display_name or entry.filename,
            description=f"{ICONS['link']} [動画を見る]({self.storage.generate_public_url(entry.r2_path)})",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"{ICONS['name']} ファイル名", 
            value=f"`{entry.filename}.mp4`", 
            inline=True
        )
        embed.add_field(
            name=f"{ICONS['calendar']} アップロード日時", 
            value=created_at_str, 
            inline=True
        )
        
        embed.set_footer(text=f"ページ {self.page + 1}/{self.total_pages} | ファイル {start_idx + 1}/{self.total_entries}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """ボタン操作が本人によるものであることを確認"""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ このUIはあなた専用です。", ephemeral=True)
            logger.warning(f"UI access denied for {interaction.user}")
            return False
        return True

    async def on_timeout(self):
        """UIタイムアウト時の処理"""
        if self.message:
            try:
                await self.message.edit(view=None)
                logger.info("View timed out and disabled")
            except Exception as e:
                logger.warning(f"View timeout edit failed: {e}")

    async def switch_view_mode(self, interaction: discord.Interaction):
        """表示モードを切り替え"""
        self.view_mode = "detail" if self.view_mode == "list" else "list"
        self._update_view()
        
        if self.view_mode == "detail":
            embed = self.get_current_embed()
            await interaction.response.edit_message(
                content=None,
                embed=embed, 
                view=self
            )
        else:
            content = self.get_list_content()
            await interaction.response.edit_message(
                content=content,
                embed=None, 
                view=self
            )

    async def prev_page(self, interaction: discord.Interaction):
        """前のページに移動"""
        if self.page > 0:
            self.page -= 1
            self._update_view()
            
            if self.view_mode == "detail":
                embed = self.get_current_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                content = self.get_list_content()
                await interaction.response.edit_message(content=content, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """次のページに移動"""
        if self.page < self.total_pages - 1:
            self.page += 1
            self._update_view()
            
            if self.view_mode == "detail":
                embed = self.get_current_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                content = self.get_list_content()
                await interaction.response.edit_message(content=content, view=self)


# 後方互換性のためのエイリアス
FileListView = UnifiedFileView
PagedFileView = UnifiedFileView