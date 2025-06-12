"""
bot/framework/bot_core.py

統合されたBot初期化フレームワーク
設定読み込み、ログ設定、サービス初期化を一元管理
"""

import discord
from discord import app_commands
import asyncio
import signal
import logging
import logging.handlers
import os
import yaml
from datetime import datetime
from typing import Dict, Any, Optional

from bot.framework.command_base import CommandRegistry
from bot.commands.admin_commands import setup_admin_commands
from bot.commands.upload_command import setup_upload_command
from bot.commands.file_commands import setup_file_commands
from bot.impl.r2_service import R2StorageService
from bot.impl.sqlite_service import SQLiteDatabaseService

class BotFramework:
    """
    統合されたBotフレームワーク
    設定・ログ・サービス・コマンドを一元管理
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = {}
        self.logger = None
        
        # 初期化シーケンス
        self._load_config()
        self._setup_logging()
        self._init_services()
        self._setup_discord_client()
        self._setup_command_registry()
        
    def _load_config(self) -> None:
        """設定ファイル読み込み（環境変数で上書き可能）"""
        # デフォルト設定
        self.config = {
            "DISCORD_TOKEN": "",
            "ADMIN_ROLE": "Admin",
            "ALLOWED_ROLE": "Uploader",
            "ALLOWED_GUILD_ID": 0,
            "R2_BUCKET": "",
            "R2_ENDPOINT": "",
            "R2_ACCESS_KEY": "",
            "R2_SECRET_KEY": "",
            "R2_PUBLIC_URL": "",
            "DEFAULT_UPLOAD_LIMIT": 5,
            "CONSOLE_LOG_LEVEL": "INFO",
            "FILE_LOG_LEVEL": "DEBUG",
            "LOG_DIR": "logs",
        }
        
        # 設定ファイルから読み込み
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        self.config.update(yaml_config)
                print(f"Configuration loaded from {self.config_path}")
            else:
                print(f"Configuration file {self.config_path} not found, using defaults")
        except Exception as e:
            print(f"Failed to load configuration file: {e}")
        
        # 環境変数で上書き
        env_overrides = 0
        for key in self.config:
            env_value = os.getenv(key)
            if env_value:
                # 型変換
                if isinstance(self.config[key], int) and env_value.isdigit():
                    self.config[key] = int(env_value)
                else:
                    self.config[key] = env_value
                env_overrides += 1
        
        if env_overrides > 0:
            print(f"Configuration overridden by {env_overrides} environment variables")
        
        # 必須設定のバリデーション
        required_keys = ["DISCORD_TOKEN", "R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY"]
        missing_keys = [key for key in required_keys if not self.config[key]]
        
        if missing_keys:
            missing_str = ", ".join(missing_keys)
            raise ValueError(f"Missing required configuration: {missing_str}")
    
    def _setup_logging(self) -> None:
        """ログ設定（コンソールとファイルで別レベル対応）"""
        # ログレベル取得
        console_level = getattr(logging, self.config["CONSOLE_LOG_LEVEL"].upper(), logging.INFO)
        file_level = getattr(logging, self.config["FILE_LOG_LEVEL"].upper(), logging.DEBUG)
        
        # ログディレクトリ作成
        log_dir = self.config["LOG_DIR"]
        os.makedirs(log_dir, exist_ok=True)
        
        # ルートロガー設定
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 最も詳細なレベルに設定
        
        # 既存のハンドラをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # フォーマッタ
        detailed_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        simple_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s]: %(message)s",
            datefmt="%H:%M:%S"
        )
        
        # コンソール出力（設定可能レベル）
        console = logging.StreamHandler()
        console.setFormatter(simple_formatter if console_level >= logging.INFO else detailed_formatter)
        console.setLevel(console_level)
        root_logger.addHandler(console)
        
        # ファイル出力（詳細ログ）
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            log_path = os.path.join(log_dir, f"bot-{today}.log")
            
            if os.access(log_dir, os.W_OK):
                file_handler = logging.handlers.RotatingFileHandler(
                    log_path,
                    maxBytes=10485760,  # 10MB
                    backupCount=5,
                    encoding="utf-8"
                )
                file_handler.setFormatter(detailed_formatter)
                file_handler.setLevel(file_level)
                root_logger.addHandler(file_handler)
            else:
                print(f"WARNING: No write permission to log directory: {log_dir}")
        except Exception as e:
            print(f"ERROR: Failed to setup file logging: {e}")
        
        # 外部ライブラリのログレベル調整
        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized - Console: {self.config['CONSOLE_LOG_LEVEL']}, File: {self.config['FILE_LOG_LEVEL']}")
    
    def _init_services(self) -> None:
        """各種サービスの初期化"""
        # データベースパス
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite3")
        
        # データベースサービス
        self.db_service = SQLiteDatabaseService(db_path=db_path)
        self.logger.debug("Database service initialized")
        
        # ストレージサービス
        self.storage_service = R2StorageService(
            bucket=self.config["R2_BUCKET"],
            endpoint=self.config["R2_ENDPOINT"],
            access_key=self.config["R2_ACCESS_KEY"],
            secret_key=self.config["R2_SECRET_KEY"],
            public_url=self.config["R2_PUBLIC_URL"]
        )
        self.logger.debug("Storage service initialized")
    
    def _setup_discord_client(self) -> None:
        """Discordクライアントの設定"""
        # インテント設定
        intents = discord.Intents.default()
        intents.members = True
        
        # クライアント初期化
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # イベント登録
        @self.client.event
        async def on_ready():
            # コマンド登録とDiscord同期
            self._register_commands()
            self.command_registry.setup_all(self.tree)
            await self.tree.sync()
            
            self.logger.info(f"Bot logged in as {self.client.user}")
        
        self.logger.debug("Discord client configured")
    
    def _setup_command_registry(self) -> None:
        """コマンドレジストリの初期化"""
        self.command_registry = CommandRegistry()
        self.logger.debug("Command registry initialized")
    
    def _register_commands(self) -> None:
        """全コマンドをレジストリに登録"""
        # 各コマンドモジュールから登録
        setup_admin_commands(self.command_registry, self.db_service)
        setup_upload_command(self.command_registry, self.db_service, self.storage_service)
        setup_file_commands(self.command_registry, self.db_service, self.storage_service)
        
        self.logger.info("All commands registered to framework")
    
    async def _shutdown(self) -> None:
        """シャットダウン処理"""
        self.logger.info("Shutting down bot...")
        await self.client.close()
        self.logger.info("Bot shutdown complete")
    
    def _handle_exit(self, *_) -> None:
        """シグナルハンドラ"""
        asyncio.create_task(self._shutdown())
    
    def run(self) -> int:
        """Botを起動"""
        try:
            # シグナルハンドラ登録
            signal.signal(signal.SIGTERM, self._handle_exit)
            signal.signal(signal.SIGINT, self._handle_exit)
            
            self.logger.info("Starting Discord bot with integrated framework...")
            self.client.run(self.config["DISCORD_TOKEN"])
            
        except Exception as e:
            self.logger.critical(f"Critical error: {e}", exc_info=True)
            return 1
        
        return 0
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        return self.config.get(key, default)