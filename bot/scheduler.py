"""
scheduler.py

毎日 0 時に Cloudflare R2 上の 30 日以上経過したファイルを削除する定期タスクを提供する。
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz

from bot.db import delete_old_uploads
from bot.r2 import delete_from_r2

def start_scheduler() -> None:
    """
    APScheduler を用いて毎日 JST 0 時に古いファイル削除タスクを実行する。
    削除対象：30 日以上前にアップロードされたファイル。
    """
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(event_loop=loop)

    def cleanup_task():
        """
        JST タイムゾーンにおける現在時刻を基準に 30 日前のファイルを削除。
        DB 上の記録と R2 上の実体ファイルを両方削除。
        """
        jst = pytz.timezone("Asia/Tokyo")
        cutoff_time = datetime.now(jst) - timedelta(days=30)
        expired_files = delete_old_uploads(cutoff_time.isoformat())

        for (r2_path,) in expired_files:
            try:
                delete_from_r2(r2_path)
                print(f"🗑️ 削除成功: {r2_path}")
            except Exception as error:
                print(f"⚠️ 削除失敗: {r2_path} - {error}")

    # 毎日 JST 0 時に cleanup_task を実行
    scheduler.add_job(cleanup_task, trigger="cron", hour=0, timezone="Asia/Tokyo")
    scheduler.start()
