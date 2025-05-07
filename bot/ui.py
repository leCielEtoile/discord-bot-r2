"""
bot/ui.py

Discord Bot におけるファイル閲覧・操作用のUIコンポーネント
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
    "prev": "◀️",
    "next": "▶️",
    "info": "ℹ️",
    "link": "🔗",
    "calendar": "📅",
    "name": "📄"
}

# ページあたりの表示件数
FILES_PER_PAGE = 10


class FileListView(discord.ui.View):
    """
    一覧モードのファイル表示ビュー。
    ページング機能付きのリストビュー。
    """

    def __init__(self, user_id: str, entries: List[UploadEntry], 
                 storage_service: StorageService, db_service: DatabaseService):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.storage = storage_service
        self.db = db_service
        self.entries = entries
        self.total_entries = len(entries)
        self.page = 0
        self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
        self.message = None
        
        # ボタンの追加
        self._update_view()

    def _update_view(self):
        """ビューの更新（ボタンの再構成）"""
        self.clear_items()
        
        # 詳細表示ボタン
        details_button = discord.ui.Button(label=f"{ICONS['info']} 詳細表示", style=discord.ButtonStyle.secondary, row=0)
        details_button.callback = self.switch_to_detail_view
        self.add_item(details_button)
        
        # ページネーションボタン
        if self.total_pages > 1:
            # 前のページへ
            prev_button = discord.ui.Button(
                label=ICONS['prev'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == 0),
                row=1
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            
            # ページ情報ラベル
            page_label = discord.ui.Button(
                label=f"{self.page + 1}/{self.total_pages}", 
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=1
            )
            self.add_item(page_label)
            
            # 次のページへ
            next_button = discord.ui.Button(
                label=ICONS['next'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == self.total_pages - 1),
                row=1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # 現在のページの項目へのボタン
        start_idx = self.page * FILES_PER_PAGE
        end_idx = min(start_idx + FILES_PER_PAGE, len(self.entries))
        
        for i in range(start_idx, end_idx):
            entry = self.entries[i]
            row = 2 + (i - start_idx) // 2  # 1行に2つのボタンを配置
            
            # 動画ファイルへのリンクボタン
            play_button = discord.ui.Button(
                label=f"{ICONS['play']} {entry.display_name[:25]}{'...' if len(entry.display_name) > 25 else ''}",
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

    def make_delete_callback(self, filename: str, path: str):
        """
        ボタンが押されたときに呼ばれる削除処理を生成
        """
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ あなたのファイルではありません。", ephemeral=True)
                logger.warning(f"Unauthorized delete attempt by {interaction.user} for {filename}")
                return
            
            # 削除確認ボタン
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
                    # R2からファイル削除
                    self.storage.delete_file(path)
                    
                    # DBから記録削除
                    self.db.delete_upload(self.user_id, filename)
                    
                    # リストから削除
                    self.entries = [e for e in self.entries if e.filename != filename]
                    self.total_entries = len(self.entries)
                    
                    # ページ数再計算
                    self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
                    
                    # 現在のページが範囲外になった場合は調整
                    if self.page >= self.total_pages:
                        self.page = max(0, self.total_pages - 1)
                    
                    # ボタン更新
                    self._update_view()
                    
                    # 応答
                    await confirm_interaction.response.edit_message(
                        content=f"✅ `{filename}.mp4` を削除しました。",
                        view=None
                    )
                    
                    # メインビュー更新
                    if self.message:
                        await self.message.edit(
                            content=self.get_list_content(),
                            view=self
                        )
                    
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
        
        return f"📂 ファイル一覧 ({self.total_entries}件)"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        ボタン操作が本人によるものであることを確認
        """
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ このUIはあなた専用です。", ephemeral=True)
            logger.warning(f"UI access denied for {interaction.user}")
            return False
        return True

    async def on_timeout(self):
        """
        UIがタイムアウト（操作なし）になったときの処理
        ボタンを無効化
        """
        if self.message:
            try:
                await self.message.edit(view=None)
                logger.info("View timed out and disabled")
            except Exception as e:
                logger.warning(f"View timeout edit failed: {e}")

    async def switch_to_detail_view(self, interaction: discord.Interaction):
        """詳細ビューに切り替え"""
        if not self.entries:
            await interaction.response.send_message("📂 表示するファイルがありません。", ephemeral=True)
            return
        
        detail_view = PagedFileView(
            self.user_id, 
            self.entries, 
            self.storage, 
            self.db
        )
        
        embed = detail_view.get_current_embed()
        
        await interaction.response.edit_message(
            content=None,
            embed=embed, 
            view=detail_view
        )
        
        detail_view.message = await interaction.original_response()

    async def prev_page(self, interaction: discord.Interaction):
        """前のページに移動"""
        if self.page > 0:
            self.page -= 1
            self._update_view()
            await interaction.response.edit_message(
                content=self.get_list_content(),
                view=self
            )

    async def next_page(self, interaction: discord.Interaction):
        """次のページに移動"""
        if self.page < self.total_pages - 1:
            self.page += 1
            self._update_view()
            await interaction.response.edit_message(
                content=self.get_list_content(),
                view=self
            )


class PagedFileView(discord.ui.View):
    """
    ページビューによるファイル詳細表示UI。
    前後ボタンや削除、一覧表示への切替ボタンを提供する。
    """

    def __init__(self, user_id: str, entries: List[UploadEntry], 
                 storage_service: StorageService, db_service: DatabaseService):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.entries = entries
        self.storage = storage_service
        self.db = db_service
        self.index = 0
        self.total = len(entries)
        self.message = None  # メッセージ保持（後でview無効化時に使う）
        self.update_buttons()

    def update_buttons(self):
        """
        現在のページに合わせてボタン状態を更新
        """
        self.clear_items()
        
        # 一覧表示切替ボタン
        list_button = discord.ui.Button(
            label=f"{ICONS['list']} 一覧に戻る", 
            style=discord.ButtonStyle.secondary,
            row=0
        )
        list_button.callback = self.switch_to_list
        self.add_item(list_button)
        
        # 公開URLボタン（直接リンク）
        if self.entries:
            entry = self.entries[self.index]
            public_url = self.storage.generate_public_url(entry.r2_path)
            play_button = discord.ui.Button(
                label=f"{ICONS['play']} 再生", 
                style=discord.ButtonStyle.success,
                row=0,
                url=public_url
            )
            self.add_item(play_button)
        
        # 削除ボタン
        delete_button = discord.ui.Button(
            label=f"{ICONS['delete']} 削除", 
            style=discord.ButtonStyle.danger,
            row=0
        )
        delete_button.callback = self.delete_current
        self.add_item(delete_button)
        
        # 複数ファイルがある場合のみページ送りボタン表示
        if self.total > 1:
            # 前のファイルへ
            prev_button = discord.ui.Button(
                label=ICONS['prev'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.index == 0),
                row=1
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            
            # ページ番号
            page_label = discord.ui.Button(
                label=f"{self.index+1}/{self.total}", 
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=1
            )
            self.add_item(page_label)
            
            # 次のファイルへ
            next_button = discord.ui.Button(
                label=ICONS['next'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.index == self.total - 1),
                row=1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        ボタン操作が本人によるものであることを確認
        """
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ このUIはあなた専用です。", ephemeral=True)
            logger.warning(f"UI access denied for {interaction.user}")
            return False
        return True

    def get_current_embed(self):
        """
        現在のページに対応するファイル情報をEmbedに整形して返す
        """
        if not self.entries:
            embed = discord.Embed(
                title="ファイルがありません",
                description="アップロードされたファイルがありません。",
                color=discord.Color.light_grey()
            )
            return embed
        
        entry = self.entries[self.index]
        
        # タイムスタンプを日本時間で表示
        created_at_str = entry.created_at.strftime("%Y年%m月%d日 %H:%M")
        
        embed = discord.Embed(
            title=entry.display_name or entry.filename,
            description=f"{ICONS['link']} [動画を見る]({self.storage.generate_public_url(entry.r2_path)})",
            color=discord.Color.blue()
        )
        
        # 各種情報をフィールドとして追加
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
        
        embed.set_footer(text=f"{self.index+1}/{self.total}")
        return embed

    async def on_timeout(self):
        """
        UIがタイムアウト（操作なし）になったときの処理
        ボタンを無効化
        """
        if self.message:
            try:
                await self.message.edit(view=None)
                logger.info("View timed out and disabled")
            except Exception as e:
                logger.warning(f"View timeout edit failed: {e}")

    async def prev_page(self, interaction: discord.Interaction):
        """前のページに移動"""
        if self.index > 0:
            self.index -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        """次のページに移動"""
        if self.index < self.total - 1:
            self.index += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    async def switch_to_list(self, interaction: discord.Interaction):
        """一覧表示モードに切替"""
        view = FileListView(self.user_id, self.entries, self.storage, self.db)
        await interaction.response.edit_message(
            content=view.get_list_content(), 
            embed=None, 
            view=view
        )
        view.message = await interaction.original_response()

    async def delete_current(self, interaction: discord.Interaction):
        """
        現在のページのファイルを削除
        削除後は自動で次ページへ移動（または終了）
        """
        if not self.entries:
            await interaction.response.send_message("削除するファイルがありません。", ephemeral=True)
            return
        
        entry = self.entries[self.index]
        
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
                # R2からファイル削除
                self.storage.delete_file(entry.r2_path)
                
                # DBから記録削除
                self.db.delete_upload(self.user_id, entry.filename)
                
                # エントリリストから削除
                del self.entries[self.index]
                self.total -= 1
                
                # 削除後の処理：全件削除されたら終了
                if self.total == 0:
                    await confirm_interaction.response.edit_message(
                        content="🗑️ 全てのファイルを削除しました。",
                        embed=None,
                        view=None
                    )
                    logger.info(f"All files deleted by {self.user_id}")
                    return
                
                # ページ番号調整しボタン更新
                if self.index >= self.total:
                    self.index = self.total - 1
                self.update_buttons()
                
                # 確認メッセージを更新
                await confirm_interaction.response.edit_message(
                    content=f"✅ `{entry.filename}.mp4` を削除しました。",
                    view=None
                )
                
                # メインビュー更新
                if self.message:
                    await self.message.edit(
                        embed=self.get_current_embed(), 
                        view=self
                    )
                
                logger.info(f"File deleted: {entry.r2_path}")
                
            except (StorageError, DatabaseError) as e:
                await confirm_interaction.response.edit_message(
                    content=f"⚠️ 削除に失敗しました: {e}",
                    view=None
                )
                logger.error(f"Failed to delete {entry.r2_path}: {e}")
        
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
            f"⚠️ `{entry.filename}.mp4` を削除しますか？この操作は元に戻せません。",
            view=confirm_view,
            ephemeral=True
        )