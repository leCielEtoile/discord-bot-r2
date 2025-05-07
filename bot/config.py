"""
config.py

設定ファイルから各種定数を読み込む
"""

import json
import os

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _config = json.load(f)

# Discord Bot設定
TOKEN: str = _config["DISCORD_TOKEN"]
ADMIN_ROLE: str = _config["ADMIN_ROLE"]
ALLOWED_ROLE: str = _config["ALLOWED_ROLE"]
ALLOWED_GUILD_ID: int = _config["ALLOWED_GUILD_ID"]

# R2接続設定
R2_BUCKET: str = _config["R2_BUCKET"]
R2_ENDPOINT: str = _config["R2_ENDPOINT"]
R2_ACCESS_KEY: str = _config["R2_ACCESS_KEY"]
R2_SECRET_KEY: str = _config["R2_SECRET_KEY"]
R2_PUBLIC_URL: str = _config["R2_PUBLIC_URL"]

# アップロード上限のデフォルト値（ユーザー設定なし時に使用）
DEFAULT_UPLOAD_LIMIT: int = _config.get("DEFAULT_UPLOAD_LIMIT", 5)
