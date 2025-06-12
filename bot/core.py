"""
core.py

Discord Bot の初期化・起動処理
依存性注入パターンを用いてサービスを初期化
"""

import discord
from discord import app_commands
import asyncio
import signal
import logging
import os

from bot.commands.admin_commands import setup_admin_commands
from bot.commands.upload_command import UploadCommand
from bot.commands.file_commands import setup_file_commands
from bot.impl.r2_service import R2StorageService
from bot.impl.sqlite_service import SQLiteDatabaseService
from bot.logging_config import setup_logging
from bot.config import (
    TOKEN, R2_BUCKET, R2_ENDPOINT, 
    R2_ACCESS_KEY, R2_SECRET_KEY, R2_PUBLIC_URL
)

# ロガー設定
logger = logging.getLogger(__name__)

class DiscordBot:
    """Discord Botのメインクラス"""
    
    def __init__(self):
        """Botと各サービスを初期化"""
        # メンバー情報取得のためのインテント設定
        intents = discord.Intents.default()
        intents.members = True
        
        # クライアントインスタンス生成
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # データベースパスを環境変数から取得（デフォルトは/app/data/db.sqlite3）
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite3")
        
        # サービス初期化
        self.db_service = SQLiteDatabaseService(db_path=db_path)
        self.storage_service = R2StorageService(
            bucket=R2_BUCKET,
            endpoint=R2_ENDPOINT,
            access_key=R2_ACCESS_KEY,
            secret_key=R2_SECRET_KEY,
            public_url=R2_PUBLIC_URL
        )
        
        # クライアントイベント登録
        self._register_events()
        
    def _register_events(self):
        """クライアントのイベントハンドラを登録"""
        @self.client.event
        async def on_ready():
            # コマンド登録
            await self._register_commands()
            
            # コマンドツリー同期
            await self.tree.sync()
            logger.info(f"Bot logged in as {self.client.user}")
    
    async def _register_commands(self):
        """全コマンドを登録（非同期）"""
        # 管理者コマンド
        setup_admin_commands(self.tree, self.db_service)
        
        # アップロードコマンド
        upload_cmd = UploadCommand(self.storage_service, self.db_service)
        await upload_cmd.register(self.tree)
        
        # ファイル操作コマンド
        setup_file_commands(self.tree, self.db_service, self.storage_service)
        
        logger.info("All commands registered")
    
    async def _shutdown(self):
        """シャットダウン処理"""
        logger.info("シャットダウン処理中...")
        await self.client.close()
        logger.info("Bot切断完了")
    
    def _handle_exit(self, *_):
        """シグナルハンドラ"""
        asyncio.create_task(self._shutdown())
    
    def run(self):
        """Botを起動"""
        # シグナルハンドラ登録
        signal.signal(signal.SIGTERM, self._handle_exit)
        signal.signal(signal.SIGINT, self._handle_exit)
        
        logger.info("Starting Discord bot...")
        self.client.run(TOKEN)

def run_bot():
    """
    Botを初期化して実行
    """
    # ロギング設定
    setup_logging()
    
    try:
        # Bot初期化と実行
        bot = DiscordBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
        return 1
    
    return 0