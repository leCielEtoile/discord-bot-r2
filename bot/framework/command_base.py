"""
bot/framework/command_base.py

コマンドフレームワークの基盤クラス群
権限管理、エラーハンドリング、コマンド登録を統一化
"""

import discord
from discord import app_commands
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any
from functools import wraps

from bot.errors import PermissionError, handle_bot_error

logger = logging.getLogger(__name__)

class PermissionLevel:
    """
    コマンド実行権限レベルの定数定義
    """
    PUBLIC = "public"        # 全ユーザーが実行可能
    USER = "user"           # 指定ロール保持者のみ実行可能
    ADMIN = "admin"         # 管理者ロール保持者のみ実行可能

class BaseCommand(ABC):
    """
    すべてのBotコマンドの基底クラス
    共通の権限チェック、エラーハンドリング、ログ機能を提供
    """
    
    def __init__(self, db_service, storage_service: Optional = None):
        """
        基底コマンドの初期化
        
        Args:
            db_service: データベースサービスインスタンス
            storage_service: ストレージサービスインスタンス（オプション）
        """
        self.db = db_service
        self.storage = storage_service
        self.permission_level = PermissionLevel.PUBLIC
        self.command_name = ""
        
        # 設定値は後からcore.pyによって注入される
        self._admin_role = None
        self._allowed_role = None
    
    def set_permission(self, level: str) -> 'BaseCommand':
        """
        コマンドの権限レベルを設定
        
        Args:
            level: 権限レベル（PermissionLevelの定数を使用）
            
        Returns:
            BaseCommand: メソッドチェーン用に自身を返す
        """
        self.permission_level = level
        return self
    
    def set_roles(self, admin_role: str, allowed_role: str) -> 'BaseCommand':
        """
        権限チェック用のロール名を設定
        core.pyから設定値が注入される際に呼び出される
        
        Args:
            admin_role: 管理者ロール名
            allowed_role: 一般ユーザーロール名
            
        Returns:
            BaseCommand: メソッドチェーン用に自身を返す
        """
        self._admin_role = admin_role
        self._allowed_role = allowed_role
        return self
    
    def check_permission(self, user: discord.abc.User) -> bool:
        """
        ユーザーがコマンドを実行する権限を持つかチェック
        
        Args:
            user: 権限チェック対象のDiscordユーザー
            
        Returns:
            bool: 権限がある場合True
        """
        if self.permission_level == PermissionLevel.PUBLIC:
            return True
        
        # ロール情報が取得できない場合は権限なし
        if not hasattr(user, 'roles'):
            return False
            
        if self.permission_level == PermissionLevel.ADMIN:
            return any(role.name == self._admin_role for role in user.roles)
        
        if self.permission_level == PermissionLevel.USER:
            return any(role.name == self._allowed_role for role in user.roles)
        
        return False
    
    async def execute_with_framework(self, interaction: discord.Interaction, **kwargs):
        """
        フレームワークによる統一コマンド実行処理
        権限チェック → ログ記録 → 実際の処理 → エラーハンドリングの流れを管理
        
        Args:
            interaction: Discordインタラクション
            **kwargs: コマンド固有の引数
        """
        # コマンド実行開始ログ
        logger.info(f"/{self.command_name} invoked by {interaction.user} with args: {kwargs}")
        
        try:
            # 権限チェック実行
            if not self.check_permission(interaction.user):
                if self.permission_level == PermissionLevel.ADMIN:
                    raise PermissionError("管理者権限がありません。")
                else:
                    raise PermissionError("このコマンドを使用する権限がありません。")
            
            # サブクラスの実装による実際のコマンド処理
            await self.execute_impl(interaction, **kwargs)
            
            # 正常完了ログ
            logger.info(f"/{self.command_name} completed successfully for {interaction.user}")
            
        except Exception as e:
            # 統一エラーハンドリング
            await handle_bot_error(e, interaction, f"{self.command_name} failed: {e}")
    
    @abstractmethod
    async def execute_impl(self, interaction: discord.Interaction, **kwargs):
        """
        コマンドの実際の処理内容
        各サブクラスで実装必須
        
        Args:
            interaction: Discordインタラクション
            **kwargs: コマンド固有の引数
        """
        pass

class CommandRegistry:
    """
    アプリケーション内のすべてのコマンドを管理するレジストリクラス
    コマンドの登録、設定値の注入、Discord APIへの登録を担当
    """
    
    def __init__(self):
        """レジストリの初期化"""
        self.commands: List[BaseCommand] = []
        self._admin_role = "Admin"
        self._allowed_role = "Uploader"
        self._default_upload_limit = 5
    
    def set_config(self, admin_role: str, allowed_role: str, default_upload_limit: int) -> 'CommandRegistry':
        """
        レジストリの設定値を更新
        core.pyから設定ファイルの値が注入される
        
        Args:
            admin_role: 管理者ロール名
            allowed_role: 一般ユーザーロール名
            default_upload_limit: デフォルトアップロード上限
            
        Returns:
            CommandRegistry: メソッドチェーン用に自身を返す
        """
        self._admin_role = admin_role
        self._allowed_role = allowed_role
        self._default_upload_limit = default_upload_limit
        return self
    
    def register(self, command: BaseCommand) -> 'CommandRegistry':
        """
        コマンドをレジストリに登録
        登録時に設定値を各コマンドに注入
        
        Args:
            command: 登録するコマンドインスタンス
            
        Returns:
            CommandRegistry: メソッドチェーン用に自身を返す
        """
        # 設定値をコマンドに注入
        command.set_roles(self._admin_role, self._allowed_role)
        if hasattr(command, 'set_default_upload_limit'):
            command.set_default_upload_limit(self._default_upload_limit)
        self.commands.append(command)
        return self
    
    def setup_all(self, tree: app_commands.CommandTree):
        """
        登録されたすべてのコマンドをDiscord APIに登録
        
        Args:
            tree: Discord.pyのCommandTreeインスタンス
        """
        for command in self.commands:
            command.setup_discord_command(tree)
        logger.debug(f"Registered {len(self.commands)} commands")

def command(name: str, description: str, permission: str = PermissionLevel.PUBLIC):
    """
    クラスベースコマンド作成用のデコレータ
    コマンドクラスに自動的にメタデータを設定
    
    Args:
        name: コマンド名
        description: コマンドの説明
        permission: 権限レベル
        
    Returns:
        デコレータ関数
    """
    def decorator(cls):
        # 元のクラスをラップして自動設定を追加
        class WrappedCommand(cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.command_name = name
                self.description = description
                self.set_permission(permission)
            
            def setup_discord_command(self, tree: app_commands.CommandTree):
                """Discord.pyのCommandTreeにコマンドを登録"""
                @tree.command(name=name, description=description)
                async def discord_command(interaction: discord.Interaction, **kwargs):
                    await self.execute_with_framework(interaction, **kwargs)
                
                # サブクラスでパラメータ設定が定義されている場合は適用
                if hasattr(self, 'setup_parameters'):
                    self.setup_parameters(discord_command)
        
        return WrappedCommand
    return decorator

def create_simple_command(
    name: str, 
    description: str, 
    handler: Callable,
    permission: str = PermissionLevel.PUBLIC,
    parameters: Optional[List] = None
):
    """
    関数ベースでコマンドを作成するヘルパー関数
    単純なコマンドを素早く作成する際に使用
    
    Args:
        name: コマンド名
        description: コマンドの説明
        handler: 実際の処理を行う関数
        permission: 権限レベル
        parameters: コマンドパラメータの定義リスト
        
    Returns:
        BaseCommandを継承したコマンドクラス
    """
    
    class SimpleCommand(BaseCommand):
        def __init__(self, db_service, storage_service=None):
            super().__init__(db_service, storage_service)
            self.command_name = name
            self.description = description
            self.handler = handler
            self.set_permission(permission)
        
        async def execute_impl(self, interaction: discord.Interaction, **kwargs):
            # ハンドラ関数を呼び出し（ストレージサービスの有無で分岐）
            if self.storage:
                await self.handler(interaction, self.db, self.storage, **kwargs)
            else:
                await self.handler(interaction, self.db, **kwargs)
        
        def setup_discord_command(self, tree: app_commands.CommandTree):
            @tree.command(name=name, description=description)
            async def discord_command(interaction: discord.Interaction, **kwargs):
                await self.execute_with_framework(interaction, **kwargs)
            
            # パラメータ設定が指定されている場合は適用
            if parameters:
                for param_name, param_config in parameters:
                    app_commands.describe(**{param_name: param_config})
    
    return SimpleCommand