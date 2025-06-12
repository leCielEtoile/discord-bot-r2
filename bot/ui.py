"""
bot/ui.py

Discord UIコンポーネントの実装
ファイル一覧表示、詳細表示、操作ボタンを提供
"""

import discord
import logging
from typing import List
from datetime import datetime
import math

from bot.data import UploadEntry
from bot.errors import StorageError, DatabaseError

logger = logging.getLogger(__name__)

# UI表示用の絵文字アイコン定義
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

# Discordの制限に合わせたページング設定
FILES_PER_PAGE = 4  # 1行に2ボタン配置で4ファイル表示可能

class UnifiedFileView(discord.ui.View):
    """
    ファイル一覧の統合表示ビュー
    リスト表示と詳細表示の切り替え、ページング、ファイル操作を提供
    """

    def __init__(self, user_id: str, entries: List[UploadEntry], 
                 storage_service, db_service, view_mode: str = "list"):
        """
        ビューの初期化
        
        Args:
            user_id: 操作ユーザーのDiscord ID
            entries: 表示するファイルエントリのリスト
            storage_service: ストレージサービスインスタンス
            db_service: データベースサービスインスタンス
            view_mode: 初期表示モード（"list" または "detail"）
        """
        super().__init__(timeout=600)  # 10分でタイムアウト
        self.user_id = user_id
        self.storage = storage_service
        self.db = db_service
        self.entries = entries
        self.total_entries = len(entries)
        self.page = 0
        self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
        self.view_mode = view_mode
        self.message = None  # メッセージインスタンスの参照保持
        
        self._update_view()

    def _update_view(self):
        """
        現在の状態に基づいてUIコンポーネントを再構築
        表示モードとページ情報に応じてボタンレイアウトを更新
        """
        self.clear_items()
        
        if not self.entries:
            return
        
        # 表示モードに応じたページング計算
        if self.view_mode == "detail":
            # 詳細表示：1ファイルずつ表示
            self.total_pages = len(self.entries)
            if self.page >= self.total_pages:
                self.page = self.total_pages - 1
        else:
            # リスト表示：複数ファイルを一度に表示
            self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
            if self.page >= self.total_pages:
                self.page = self.total_pages - 1
        
        # 表示モード切替ボタン（最上段）
        mode_button = discord.ui.Button(
            label=f"{ICONS['detail'] if self.view_mode == 'list' else ICONS['list']} {'詳細表示' if self.view_mode == 'list' else 'リスト表示'}", 
            style=discord.ButtonStyle.secondary, 
            row=0
        )
        mode_button.callback = self.switch_view_mode
        self.add_item(mode_button)
        
        # ページネーションボタン（複数ページある場合のみ表示）
        if self.total_pages > 1:
            # 前ページボタン
            prev_button = discord.ui.Button(
                label=ICONS['prev'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == 0),
                row=0
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            
            # 現在ページ表示ラベル
            page_label = discord.ui.Button(
                label=f"{self.page + 1}/{self.total_pages}", 
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=0
            )
            self.add_item(page_label)
            
            # 次ページボタン
            next_button = discord.ui.Button(
                label=ICONS['next'], 
                style=discord.ButtonStyle.primary, 
                disabled=(self.page == self.total_pages - 1),
                row=0
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        if self.view_mode == "list":
            # リスト表示：ファイル一覧とアクションボタン
            start_idx = self.page * FILES_PER_PAGE
            end_idx = min(start_idx + FILES_PER_PAGE, len(self.entries))
            
            # 各ファイルに対して再生ボタンと削除ボタンを1行に配置
            for i in range(start_idx, end_idx):
                entry = self.entries[i]
                row = 1 + (i - start_idx)  # row 1, 2, 3, 4
                
                # 動画再生ボタン（左側）
                play_button = discord.ui.Button(
                    label=f"{ICONS['play']} {entry.display_name[:25]}{'...' if len(entry.display_name) > 25 else ''}",
                    style=discord.ButtonStyle.primary,
                    row=row,
                    url=self.storage.generate_public_url(entry.r2_path)
                )
                self.add_item(play_button)
                
                # 削除ボタン（右側）
                delete_button = discord.ui.Button(
                    label=f"{ICONS['delete']} 削除",
                    style=discord.ButtonStyle.danger,
                    row=row,
                    custom_id=f"delete_{entry.filename}"
                )
                delete_button.callback = self.make_delete_callback(entry.filename, entry.r2_path)
                self.add_item(delete_button)
        
        elif self.view_mode == "detail" and self.entries:
            # 詳細表示：現在のファイルの操作ボタン
            current_entry = self.entries[self.page]
            
            # 再生ボタン
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
        """
        ファイル削除ボタンのコールバック関数を生成
        確認ダイアログ表示と実際の削除処理を行う
        
        Args:
            filename: 削除対象のファイル名
            path: R2上のファイルパス
            
        Returns:
            削除処理を行う非同期関数
        """
        async def callback(interaction: discord.Interaction):
            # 権限チェック：操作ユーザーが本人かどうか確認
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ あなたのファイルではありません。", ephemeral=True)
                return
            
            # 削除確認用のUIビュー作成
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
                """削除確定時の処理"""
                try:
                    # R2ストレージとデータベースから削除
                    self.storage.delete_file(path)
                    self.db.delete_upload(self.user_id, filename)
                    
                    # メモリ上のエントリリストからも削除
                    self.entries = [e for e in self.entries if e.filename != filename]
                    self.total_entries = len(self.entries)
                    self.total_pages = max(1, math.ceil(self.total_entries / FILES_PER_PAGE))
                    
                    # ページ位置の調整
                    if self.page >= self.total_pages:
                        self.page = max(0, self.total_pages - 1)
                    
                    await confirm_interaction.response.edit_message(
                        content=f"✅ `{filename}.mp4` を削除しました。",
                        view=None
                    )
                    
                    # メインビューの更新
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
                """削除キャンセル時の処理"""
                await cancel_interaction.response.edit_message(
                    content="❌ 削除をキャンセルしました。",
                    view=None
                )
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            # 確認ダイアログの表示
            await interaction.response.send_message(
                f"⚠️ `{filename}.mp4` を削除しますか？この操作は元に戻せません。",
                view=confirm_view,
                ephemeral=True
            )
            
        return callback

    def get_list_content(self):
        """
        リスト表示モード用のメッセージテキストを生成
        
        Returns:
            str: 表示用テキスト
        """
        if not self.entries:
            return "📂 アップロード履歴がありません。"
        return f"📂 ファイル一覧 ({self.total_entries}件) - ページ {self.page + 1}/{self.total_pages}"

    def get_current_embed(self):
        """
        詳細表示モード用のEmbedオブジェクトを生成
        現在のページに対応するファイルの詳細情報を表示
        
        Returns:
            discord.Embed: ファイル詳細情報のEmbed
        """
        if not self.entries:
            return discord.Embed(
                title="ファイルがありません",
                description="アップロードされたファイルがありません。",
                color=discord.Color.light_grey()
            )
        
        # 現在表示中のファイル情報
        current_index = self.page
        entry = self.entries[current_index]
        
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
        
        embed.set_footer(text=f"ファイル {current_index + 1}/{len(self.entries)}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        UIボタン操作の権限チェック
        操作者が当該UIの所有者であることを確認
        
        Args:
            interaction: Discord インタラクション
            
        Returns:
            bool: 権限がある場合True
        """
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ このUIはあなた専用です。", ephemeral=True)
            logger.warning(f"UI access denied for {interaction.user}")
            return False
        return True

    async def on_timeout(self):
        """
        UIタイムアウト時の処理
        タイムアウト後はボタンを無効化してインタラクションを防ぐ
        """
        if self.message:
            try:
                await self.message.edit(view=None)
                logger.info("View timed out and disabled")
            except Exception as e:
                logger.warning(f"View timeout edit failed: {e}")

    async def switch_view_mode(self, interaction: discord.Interaction):
        """
        表示モード切替処理（リスト⇔詳細）
        """
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


# 後方互換性のためのエイリアス（既存コードとの互換性維持）
FileListView = UnifiedFileView
PagedFileView = UnifiedFileView