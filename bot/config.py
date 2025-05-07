"""
bot/config.py

環境変数または設定ファイルから各種定数を読み込むモジュール
"""

import yaml
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 環境変数からYAMLパスを取得、指定がなければデフォルト使用
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")

# 設定の優先順位: 環境変数 > 設定ファイル > デフォルト値
def _get_config() -> Dict[str, Any]:
    """設定を環境変数またはYAMLファイルから読み込む"""
    # デフォルト設定
    config = {
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
    }
    
    # 設定ファイルからの読み込み
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config.update(yaml_config)
                logger.info(f"Configuration loaded from {CONFIG_PATH}")
        else:
            logger.warning(f"Configuration file {CONFIG_PATH} not found")
    except Exception as e:
        logger.error(f"Failed to load configuration file: {e}")
    
    # 環境変数で上書き
    env_overrides = 0
    for key in config:
        env_value = os.getenv(key)
        if env_value:
            # 型変換（数値の場合）
            if isinstance(config[key], int) and env_value.isdigit():
                config[key] = int(env_value)
            else:
                config[key] = env_value
            env_overrides += 1
    
    if env_overrides > 0:
        logger.info(f"Configuration overridden by {env_overrides} environment variables")
    
    # 必須設定のバリデーション
    required_keys = ["DISCORD_TOKEN", "R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY"]
    missing_keys = [key for key in required_keys if not config[key]]
    
    if missing_keys:
        missing_str = ", ".join(missing_keys)
        logger.error(f"Missing required configuration: {missing_str}")
    
    return config

# 設定を読み込み
_config = _get_config()

# 設定値を変数としてエクスポート
TOKEN: str = _config["DISCORD_TOKEN"]
ADMIN_ROLE: str = _config["ADMIN_ROLE"]
ALLOWED_ROLE: str = _config["ALLOWED_ROLE"]
ALLOWED_GUILD_ID: int = _config["ALLOWED_GUILD_ID"]

R2_BUCKET: str = _config["R2_BUCKET"]
R2_ENDPOINT: str = _config["R2_ENDPOINT"]
R2_ACCESS_KEY: str = _config["R2_ACCESS_KEY"]
R2_SECRET_KEY: str = _config["R2_SECRET_KEY"]
R2_PUBLIC_URL: str = _config["R2_PUBLIC_URL"]

DEFAULT_UPLOAD_LIMIT: int = _config["DEFAULT_UPLOAD_LIMIT"]

# ログレベルの設定
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()