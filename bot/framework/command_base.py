"""
bot/framework/command_base.py

統一されたコマンドフレームワーク
権限チェック、エラーハンドリング、ログ出力を統一
"""

import discord
from discord import app_commands
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any
from functools import wraps

from bot.services import DatabaseService, StorageService
from bot.errors import PermissionError, handle_bot_error
from bot.config import ADMIN_ROLE, ALLOWED_ROLE

logger = logging.getLogger(__name__)

class PermissionLevel:
    """権限レベル定数"""
    PUBLIC = "public"        # 全員
    USER = "user"           # 許可ロール保持者
    ADMIN = "admin"         # 管理者のみ

class BaseCommand(ABC):
    """
    コマンドの基底クラス
    共通の権限チェック、エラーハンドリング、ログを提供
    """
    
    def __init__(self, db_service: DatabaseService, storage_service: Optional[StorageService] = None):
        self.db = db_service
        self.storage = storage_service
        self.permission_level = PermissionLevel.PUBLIC
        self.command_name = ""
    
    def set_permission(self, level: str) -> 'BaseCommand':
        """権限レベルを設定"""
        self.permission_level = level
        return self
    
    def check_permission(self, user: discord.abc.User) -> bool:
        """権限チェック"""
        if self.permission_level == PermissionLevel.PUBLIC:
            return True
        
        if not hasattr(user, 'roles'):
            return False
            
        if self.permission_level == PermissionLevel.ADMIN:
            return any(role.name == ADMIN_ROLE for role in user.roles)
        
        if self.permission_level == PermissionLevel.USER:
            return any(role.name == ALLOWED_ROLE for role in user.roles)
        
        return False
    
    async def execute_with_framework(self, interaction: discord.Interaction, **kwargs):
        """
        フレームワークによる統一実行処理
        権限チェック → ログ → 実行 → エラーハンドリング
        """
        # コマンド開始ログ
        logger.info(f"/{self.command_name} invoked by {interaction.user} with args: {kwargs}")
        
        try:
            # 権限チェック
            if not self.check_permission(interaction.user):
                if self.permission_level == PermissionLevel.ADMIN:
                    raise PermissionError("管理者権限がありません。")
                else:
                    raise PermissionError("このコマンドを使用する権限がありません。")
            
            # 実際のコマンド実行
            await self.execute_impl(interaction, **kwargs)
            
            # 成功ログ
            logger.info(f"/{self.command_name} completed successfully for {interaction.user}")
            
        except Exception as e:
            # エラーハンドリング
            await handle_bot_error(e, interaction, f"{self.command_name} failed: {e}")
    
    @abstractmethod
    async def execute_impl(self, interaction: discord.Interaction, **kwargs):
        """実際のコマンド処理（サブクラスで実装）"""
        pass

class CommandRegistry:
    """
    コマンド登録を管理するレジストリクラス
    """
    
    def __init__(self):
        self.commands: List[BaseCommand] = []
    
    def register(self, command: BaseCommand) -> 'CommandRegistry':
        """コマンドを登録"""
        self.commands.append(command)
        return self
    
    def setup_all(self, tree: app_commands.CommandTree):
        """すべてのコマンドをDiscordに登録"""
        for command in self.commands:
            command.setup_discord_command(tree)
        logger.info(f"Registered {len(self.commands)} commands")

def command(name: str, description: str, permission: str = PermissionLevel.PUBLIC):
    """
    コマンドデコレータ
    クラスベースコマンドを簡単に作成
    """
    def decorator(cls):
        # 元のクラスをラップして自動設定
        class WrappedCommand(cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.command_name = name
                self.description = description
                self.set_permission(permission)
            
            def setup_discord_command(self, tree: app_commands.CommandTree):
                """Discordコマンドとして登録"""
                @tree.command(name=name, description=description)
                async def discord_command(interaction: discord.Interaction, **kwargs):
                    await self.execute_with_framework(interaction, **kwargs)
                
                # パラメータ情報をコピー（実装により追加可能）
                if hasattr(self, 'setup_parameters'):
                    self.setup_parameters(discord_command)
        
        return WrappedCommand
    return decorator

# 簡単なコマンド作成用のヘルパー関数
def create_simple_command(
    name: str, 
    description: str, 
    handler: Callable,
    permission: str = PermissionLevel.PUBLIC,
    parameters: Optional[List] = None
):
    """
    シンプルなコマンドを作成するヘルパー
    関数ベースでコマンドを定義可能
    """
    
    class SimpleCommand(BaseCommand):
        def __init__(self, db_service, storage_service=None):
            super().__init__(db_service, storage_service)
            self.command_name = name
            self.description = description
            self.handler = handler
            self.set_permission(permission)
        
        async def execute_impl(self, interaction: discord.Interaction, **kwargs):
            # ハンドラ関数を呼び出し
            if self.storage:
                await self.handler(interaction, self.db, self.storage, **kwargs)
            else:
                await self.handler(interaction, self.db, **kwargs)
        
        def setup_discord_command(self, tree: app_commands.CommandTree):
            @tree.command(name=name, description=description)
            async def discord_command(interaction: discord.Interaction, **kwargs):
                await self.execute_with_framework(interaction, **kwargs)
            
            # パラメータ設定
            if parameters:
                for param_name, param_config in parameters:
                    app_commands.describe(**{param_name: param_config})
    
    return SimpleCommand