"""
ui.py

Discord Bot におけるファイル閲覧・操作用のUIコンポーネントを定義するモジュール。
- ボタンを使ってファイルを削除
- ページ送りで複数ファイルを閲覧
- 削除と一覧表示の切替

対象：/myfiles コマンド
"""

import discord
from bot.r2 import generate_public_url, delete_from_r2
from bot.db import delete_upload
import logging

logger = logging.getLogger(__name__)


class FileListView(discord.ui.View):
    """
    一覧モードのファイル表示ビュー。
    各ファイルに削除ボタンをつけて表示する。
    """

    def __init__(self, user_id: str, entries: list[tuple[str, str, str]]):
        super().__init__(timeout=300)
        self.user_id = user_id
        for filename, path, title in entries:
            button = discord.ui.Button(
                label=f"🗑️ {filename}.mp4",
                style=discord.ButtonStyle.danger
            )
            button.callback = self.make_delete_callback(filename, path)
            self.add_item(button)

    def make_delete_callback(self, filename: str, path: str):
        """
        ボタンが押されたときに呼ばれる削除処理を生成。
        """
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ あなたのファイルではありません。", ephemeral=True)
                logger.warning(f"Unauthorized delete attempt by {interaction.user} for {filename}")
                return
            try:
                delete_from_r2(path)
                delete_upload(self.user_id, filename)
                await interaction.response.send_message(f"🗑️ {filename}.mp4 を削除しました。", ephemeral=True)
                logger.info(f"File deleted (list mode): {path}")
            except Exception as e:
                await interaction.response.send_message(f"⚠️ 削除に失敗しました: {e}", ephemeral=True)
                logger.error(f"Failed to delete {path}: {e}")
        return callback


class PagedFileView(discord.ui.View):
    """
    ページビューによるファイル表示UI。
    前後ボタンや削除、一覧表示への切替ボタンを提供する。
    """

    def __init__(self, user_id: str, entries: list[tuple[str, str, str]]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.entries = entries
        self.index = 0
        self.total = len(entries)
        self.message: discord.Message | None = None  # メッセージ保持（後でview無効化時に使う）
        self.update_buttons()

    def update_buttons(self):
        """
        現在のページに合わせてボタン状態を更新。
        """
        self.clear_items()
        if self.total > 1:
            self.add_item(discord.ui.Button(label="← 前へ", style=discord.ButtonStyle.primary, custom_id="prev"))
            self.add_item(discord.ui.Button(label="次へ →", style=discord.ButtonStyle.primary, custom_id="next"))
        self.add_item(discord.ui.Button(label="🗒️ 一覧に切替", style=discord.ButtonStyle.secondary, custom_id="switch"))
        self.add_item(discord.ui.Button(label="🗑️ 削除", style=discord.ButtonStyle.danger, custom_id="delete"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        ボタン操作が本人によるものであることを確認。
        """
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ このUIはあなた専用です。", ephemeral=True)
            logger.warning(f"UI access denied for {interaction.user}")
            return False
        return True

    def get_current_embed(self):
        """
        現在のページに対応するファイル情報をEmbedに整形して返す。
        """
        filename, path, title = self.entries[self.index]
        embed = discord.Embed(
            title=title or filename,
            description=f"🔗 [動画を見る]({generate_public_url(path)})",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"{self.index+1}/{self.total} | ファイル名: {filename}.mp4")
        return embed

    async def on_timeout(self):
        """
        UIがタイムアウト（操作なし）になったときの処理。
        ボタンを無効化。
        """
        if self.message:
            try:
                await self.message.edit(view=None)
                logger.info("View timed out and disabled")
            except Exception as e:
                logger.warning(f"View timeout edit failed: {e}")

    @discord.ui.button(label="← 前へ", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        ページを前に進める。
        """
        self.index = (self.index - 1) % self.total
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    @discord.ui.button(label="次へ →", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        ページを次に進める。
        """
        self.index = (self.index + 1) % self.total
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    @discord.ui.button(label="🗒️ 一覧に切替", style=discord.ButtonStyle.secondary, custom_id="switch")
    async def switch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        一覧表示モードに切り替える。
        """
        view = FileListView(self.user_id, self.entries)
        await interaction.response.edit_message(content=f"📂 ファイル一覧（{self.total}件）:", embed=None, view=view)

    @discord.ui.button(label="🗑️ 削除", style=discord.ButtonStyle.danger, custom_id="delete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        現在のページのファイルを削除する。
        削除後は自動で次ページへ移動（または終了）。
        """
        filename, path, _ = self.entries[self.index]
        try:
            delete_from_r2(path)
            delete_upload(self.user_id, filename)
            del self.entries[self.index]
            self.total -= 1

            # 削除後の処理：全件削除されたら終了
            if self.total == 0:
                await interaction.response.edit_message(content="🗑️ 全てのファイルを削除しました。", embed=None, view=None)
                return

            # ページ番号調整しボタン更新
            self.index %= self.total
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
            logger.info(f"File deleted: {path}")
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 削除に失敗しました: {e}", ephemeral=True)
            logger.error(f"Failed to delete {path}: {e}")
