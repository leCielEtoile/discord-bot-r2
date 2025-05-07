"""
bot/logging_config.py

ロギング設定を一元管理するモジュール
"""

import logging
import logging.handlers
import os
from datetime import datetime
import sys

def setup_logging(log_level=None):
    """
    アプリケーション全体のロギング設定
    
    Args:
        log_level: ログレベル（未指定時は環境変数またはINFO）
    
    Returns:
        logging.Logger: ルートロガー
    """
    # ログレベル設定
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    level_num = getattr(logging, log_level.upper(), logging.INFO)
    
    # ログディレクトリのパス設定
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(level_num)
    
    # 既存のハンドラをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # フォーマッタ
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # コンソール出力
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level_num)
    root_logger.addHandler(console)
    
    # ファイル出力（日付ごと）
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"bot-{today}.log")
        
        # ファイルハンドラを追加する前に書き込み権限を確認
        if os.access(log_dir, os.W_OK):
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=10485760,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level_num)
            root_logger.addHandler(file_handler)
        else:
            # ログディレクトリに書き込み権限がない場合は警告を出すだけ
            print(f"WARNING: No write permission to log directory: {log_dir}")
            print("Running with console logging only")
    except Exception as e:
        # ファイル出力の設定に失敗した場合はエラーメッセージを出力するだけで続行
        print(f"ERROR: Failed to setup file logging: {e}")
        print("Running with console logging only")
    
    # 外部ライブラリのログレベル調整
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    
    # 初期ログ
    root_logger.info(f"Logging initialized with level {log_level}")
    
    return root_logger