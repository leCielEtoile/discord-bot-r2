"""
core.py

Discord Bot の初期化・起動処理（discord.Client ベース）
"""

import discord
from discord import app_commands
import asyncio
import signal
import logging

from bot.commands import register_commands
from bot.scheduler import start_scheduler
from bot.db import init_db
from bot.config import TOKEN

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# メンバー情報取得のためのインテント設定
intents = discord.Intents.default()
intents.members = True

# クライアントインスタンス生成（Bot用）
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def run_bot():
    """
    Bot を初期化して実行します（discord.Client ベース）。
    - DB 初期化
    - スラッシュコマンド登録
    - イベントハンドラ登録
    - スケジューラ起動
    """
    init_db()
    register_commands(tree)

    @client.event
    async def on_ready():
        await tree.sync()
        logger.info(f"Bot logged in as {client.user}")
        start_scheduler()

    async def shutdown():
        logger.info("シャットダウン処理中...")
        await client.close()
        logger.info("Bot切断完了")

    def handle_exit(*_):
        asyncio.create_task(shutdown())

    # SIGTERM/SIGINT をトラップ
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    client.run(TOKEN)
