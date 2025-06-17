"""
bot/commands/upload_command.py

YouTube動画アップロード機能の実装（URL正規化対応）
動画ダウンロード、変換、ストレージアップロード、データベース記録を統合
プレイリストURL対策を含む
"""

import discord
from discord import app_commands
import re
import os
import asyncio
from datetime import datetime
import logging

from bot.framework.command_base import BaseCommand, PermissionLevel, CommandRegistry
from bot.data import DataManager, UserMapping, UploadEntry
from bot.youtube import get_video_title, download_video, validate_youtube_url, check_video_codec, normalize_youtube_url, extract_video_id
from bot.errors import UploadError

logger = logging.getLogger(__name__)

def is_valid_filename(name: str) -> bool:
    """
    ファイル名の妥当性をチェック
    英数字、アンダースコア、ハイフンのみ許可
    
    Args:
        name: チェック対象のファイル名
        
    Returns:
        bool: 有効なファイル名の場合True
    """
    return re.fullmatch(r"[a-zA-Z0-9_\-]+", name) is not None

class UploadCommand(BaseCommand):
    """
    YouTube動画をダウンロードしてR2ストレージにアップロードするコマンド
    プレイリストURL正規化対応済み
    """
    
    def __init__(self, data_manager: DataManager, storage_service):
        """
        コマンドの初期化
        
        Args:
            data_manager: データベース管理インスタンス
            storage_service: ストレージサービスインスタンス
        """
        super().__init__(data_manager, storage_service)
        self.command_name = "upload"
        self.set_permission(PermissionLevel.USER)
        self._default_upload_limit = 5
    
    def set_default_upload_limit(self, limit: int):
        """
        新規ユーザーのデフォルトアップロード上限を設定
        
        Args:
            limit: デフォルト上限値
        """
        self._default_upload_limit = limit
    
    async def execute_impl(self, interaction: discord.Interaction, url: str, filename: str):
        """
        アップロード処理の実行
        
        Args:
            interaction: Discordインタラクション
            url: YouTube動画のURL
            filename: 保存するファイル名（拡張子なし）
        """
        # 入力値の検証
        if not validate_youtube_url(url):
            raise UploadError("有効なYouTubeのURLを入力してください。")
        
        if not is_valid_filename(filename):
            raise UploadError("ファイル名に不正な文字が含まれています。")
        
        # URLを正規化してプレイリスト情報を除去
        normalized_url = normalize_youtube_url(url)
        video_id = extract_video_id(normalized_url)
        
        # URLが正規化されたかログに記録
        if normalized_url != url:
            logger.info(f"URL normalized: {url} -> {normalized_url} (video_id: {video_id})")
        
        # ユーザー設定の取得または作成
        discord_id = str(interaction.user.id)
        user_config = await self._get_or_create_user_config(discord_id, interaction.user.name)
        
        # 既存ファイルの取得と制限チェック
        existing_files = await self._get_user_files(discord_id)
        
        # ファイル名の重複チェック
        if any(entry.filename == filename for entry in existing_files):
            raise UploadError(f"`{filename}.mp4` は既に存在します。別名を指定してください。")
        
        # アップロード上限のチェック
        limit = user_config.upload_limit if user_config.upload_limit > 0 else self._default_upload_limit
        if limit > 0 and len(existing_files) >= limit:
            raise UploadError("アップロード上限に達しました。古いファイルを削除してください。")
        
        # 処理開始の通知（正規化された情報を含む）
        status_message = "📥 ダウンロードを開始します..."
        if normalized_url != url:
            status_message += f"\n🔗 URL正規化済み（動画ID: {video_id}）"
        
        await interaction.response.send_message(status_message, ephemeral=True)
        
        # ファイルパスの準備
        local_path = f"/tmp/{filename}.mp4"
        r2_path = f"{user_config.folder_name}/{filename}.mp4"
        
        try:
            # YouTube動画のタイトル取得（正規化されたURLを使用）
            title = await asyncio.to_thread(get_video_title, normalized_url)
            
            # 動画のダウンロード（正規化されたURLを使用）
            download_success = await asyncio.to_thread(download_video, normalized_url, local_path)
            if not download_success:
                raise UploadError("ダウンロードに失敗しました。")
            
            # ダウンロードしたファイルのコーデック確認
            video_codec, audio_codec = await asyncio.to_thread(check_video_codec, local_path)
            
            # R2ストレージへのアップロード
            await asyncio.to_thread(lambda: self.storage.upload_file(local_path, r2_path))
            
            # データベースへの記録
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
            
            # 完了通知の送信
            public_url = self.storage.generate_public_url(r2_path)
            codec_info = f"🎬 動画コーデック: {video_codec}, 🔊 音声コーデック: {audio_codec}"
            
            completion_message = f"✅ アップロード完了！\n{codec_info}\n🔗 公開URL: {public_url}"
            if normalized_url != url:
                completion_message += f"\n📹 動画ID: {video_id}"
            
            await interaction.followup.send(completion_message, ephemeral=True)
            
        finally:
            # 一時ファイルのクリーンアップ
            if os.path.exists(local_path):
                os.remove(local_path)
    
    async def _get_or_create_user_config(self, discord_id: str, username: str) -> UserMapping:
        """
        ユーザー設定を取得、存在しない場合は新規作成
        
        Args:
            discord_id: ユーザーのDiscord ID
            username: ユーザー名（フォルダ名のデフォルト値として使用）
            
        Returns:
            UserMapping: ユーザー設定
        """
        mapping = await asyncio.to_thread(self.db.get_user_mapping, discord_id)
        
        if not mapping:
            # 新規ユーザーの場合はデフォルト設定で作成
            mapping = UserMapping(
                discord_id=discord_id,
                folder_name=username,
                filename="",
                upload_limit=self._default_upload_limit
            )
            await asyncio.to_thread(self.db.save_user_mapping, mapping)
            logger.info(f"Default folder '{username}' registered for user {discord_id}")
        
        return mapping
    
    async def _get_user_files(self, discord_id: str) -> list[UploadEntry]:
        """
        ユーザーの既存ファイル一覧を取得
        
        Args:
            discord_id: ユーザーのDiscord ID
            
        Returns:
            List[UploadEntry]: ファイルエントリのリスト
        """
        return await asyncio.to_thread(self.db.list_user_files, discord_id)
    
    async def _log_upload(self, entry: UploadEntry) -> None:
        """
        アップロード記録をデータベースに保存
        
        Args:
            entry: 保存するアップロードエントリ
        """
        await asyncio.to_thread(self.db.log_upload, entry)
    
    def setup_discord_command(self, tree: app_commands.CommandTree):
        """Discord APIにコマンドを登録"""
        @tree.command(name="upload", description="YouTube動画をダウンロードしてR2に保存します")
        @app_commands.describe(
            url="YouTube動画のURL（プレイリストURLも自動で単一動画に変換されます）",
            filename="保存するファイル名（拡張子なし）"
        )
        async def upload(interaction: discord.Interaction, url: str, filename: str):
            await self.execute_with_framework(interaction, url=url, filename=filename)

def setup_upload_command(registry: CommandRegistry, data_manager: DataManager, storage_service):
    """
    アップロードコマンドをコマンドレジストリに登録
    
    Args:
        registry: コマンドレジストリインスタンス
        data_manager: データベース管理インスタンス
        storage_service: ストレージサービスインスタンス
    """
    registry.register(UploadCommand(data_manager, storage_service))
    logger.debug("Upload command registered to framework")