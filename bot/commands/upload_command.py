"""
bot/commands/upload_command.py

YouTubeの動画をダウンロードしてR2にアップロードするコマンドの実装
H.264/AACコーデックを優先
"""

import discord
from discord import app_commands
import re
import os
import asyncio
from datetime import datetime
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.models import UserMapping, UploadEntry
from bot.services import StorageService, DatabaseService
from bot.youtube import get_video_title, download_video, validate_youtube_url, check_video_codec
from bot.config import DEFAULT_UPLOAD_LIMIT
from bot.errors import UploadError

logger = logging.getLogger(__name__)

def is_valid_filename(name: str) -> bool:
    """ファイル名検証"""
    return re.fullmatch(r"[a-zA-Z0-9_\-]+", name) is not None

class UploadCommand(BaseCommand):
    """YouTubeアップロードコマンド"""
    
    def __init__(self, db_service: DatabaseService, storage_service: StorageService):
        super().__init__(db_service, storage_service)
        self.command_name = "upload"
        self.set_permission(PermissionLevel.USER)
    
    async def execute_impl(self, interaction: discord.Interaction, url: str, filename: str):
        # URLバリデーション
        if not validate_youtube_url(url):
            raise UploadError("有効なYouTubeのURLを入力してください。")
        
        # ファイル名バリデーション
        if not is_valid_filename(filename):
            raise UploadError("ファイル名に不正な文字が含まれています。")
        
        # ユーザー設定取得
        discord_id = str(interaction.user.id)
        user_config = await self._get_or_create_user_config(discord_id, interaction.user.name)
        
        # ファイル一覧取得と上限・重複チェック
        existing_files = await self._get_user_files(discord_id)
        
        # 重複チェック
        if any(entry.filename == filename for entry in existing_files):
            raise UploadError(f"`{filename}.mp4` は既に存在します。別名を指定してください。")
        
        # 上限チェック
        limit = user_config.upload_limit if user_config.upload_limit > 0 else DEFAULT_UPLOAD_LIMIT
        if limit > 0 and len(existing_files) >= limit:
            raise UploadError("アップロード上限に達しました。古いファイルを削除してください。")
        
        # 処理開始通知
        await interaction.response.send_message("📥 ダウンロードを開始します...", ephemeral=True)
        
        # ダウンロード・アップロード処理
        local_path = f"/tmp/{filename}.mp4"
        r2_path = f"{user_config.folder_name}/{filename}.mp4"
        
        try:
            # タイトル取得・ダウンロード・アップロード
            title = await asyncio.to_thread(get_video_title, url)
            
            download_success = await asyncio.to_thread(download_video, url, local_path)
            if not download_success:
                raise UploadError("ダウンロードに失敗しました。")
            
            video_codec, audio_codec = await asyncio.to_thread(check_video_codec, local_path)
            
            await asyncio.to_thread(lambda: self.storage.upload_file(local_path, r2_path))
            
            # DB登録
            entry = UploadEntry(
                id=None,
                discord_id=discord_id,
                folder_name=user_config.folder_name,
                filename=filename,
                r2_path=r2_path,
                created_at=datetime.utcnow(),
                title=title
            )
            await self._log_upload(entry)
            
            # 完了通知
            public_url = self.storage.generate_public_url(r2_path)
            codec_info = f"🎬 動画コーデック: {video_codec}, 🔊 音声コーデック: {audio_codec}"
            
            await interaction.followup.send(
                f"✅ アップロード完了！\n{codec_info}\n🔗 公開URL: {public_url}", 
                ephemeral=True
            )
            
        finally:
            # 一時ファイル削除
            if os.path.exists(local_path):
                os.remove(local_path)
    
    async def _get_or_create_user_config(self, discord_id: str, username: str) -> UserMapping:
        """ユーザー設定を取得または作成"""
        mapping = await asyncio.to_thread(self.db.get_user_mapping, discord_id)
        
        if not mapping:
            mapping = UserMapping(
                discord_id=discord_id,
                folder_name=username,
                filename="",
                upload_limit=DEFAULT_UPLOAD_LIMIT
            )
            await asyncio.to_thread(self.db.save_user_mapping, mapping)
            logger.info(f"Default folder '{username}' registered for user {discord_id}")
        
        return mapping
    
    async def _get_user_files(self, discord_id: str) -> list[UploadEntry]:
        """ユーザーのファイル一覧を取得"""
        return await asyncio.to_thread(self.db.list_user_files, discord_id)
    
    async def _log_upload(self, entry: UploadEntry) -> None:
        """アップロード記録をDBに保存"""
        await asyncio.to_thread(self.db.log_upload, entry)
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        @tree.command(name="upload", description="YouTube動画をダウンロードしてR2に保存します")
        @app_commands.describe(
            url="YouTube動画のURL",
            filename="保存するファイル名（拡張子なし）"
        )
        async def upload(interaction: discord.Interaction, url: str, filename: str):
            await self.execute_with_framework(interaction, url=url, filename=filename)

def setup_upload_command(registry: CommandRegistry, db_service: DatabaseService, storage_service: StorageService):
    """
    アップロードコマンドをレジストリに登録
    """
    registry.register(UploadCommand(db_service, storage_service))
    logger.info("Upload command registered")