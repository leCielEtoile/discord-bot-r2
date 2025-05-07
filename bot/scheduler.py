"""
bot/scheduler.py

毎日古いファイルを削除する定期タスクを提供するスケジューラモジュール
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
import asyncio
import logging

from bot.services import DatabaseService, StorageService

logger = logging.getLogger(__name__)

class Scheduler:
    """定期タスク実行のためのスケジューラクラス"""
    
    def __init__(self, db_service: DatabaseService, storage_service: StorageService, retention_days: int = 30):
        """
        スケジューラの初期化
        
        Args:
            db_service: データベースサービス
            storage_service: ストレージサービス
            retention_days: ファイル保持日数
        """
        self.db_service = db_service
        self.storage_service = storage_service
        self.retention_days = retention_days
        self.scheduler = AsyncIOScheduler()
        self._running = False
    
    def start(self):
        """スケジューラを開始"""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        # 毎日 JST 0 時に cleanup_task を実行
        self.scheduler.add_job(
            self._cleanup_task, 
            trigger="cron", 
            hour=0, 
            timezone="Asia/Tokyo",
            id="cleanup_task"
        )
        
        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started - cleanup task scheduled at midnight JST")
    
    def stop(self):
        """スケジューラを停止"""
        if not self._running:
            return
            
        self.scheduler.shutdown()
        self._running = False
        logger.info("Scheduler stopped")
    
    async def _cleanup_task(self):
        """
        古いファイルを削除する定期タスク
        JST タイムゾーンにおける現在時刻を基準に retention_days 日前のファイルを削除
        """
        logger.info(f"Running cleanup task - removing files older than {self.retention_days} days")
        
        # 削除基準日時の計算
        jst = pytz.timezone("Asia/Tokyo")
        cutoff_time = datetime.now(jst) - timedelta(days=self.retention_days)
        
        try:
            # 非同期でDB操作を実行
            loop = asyncio.get_event_loop()
            expired_paths = await loop.run_in_executor(
                None, 
                lambda: self.db_service.delete_old_uploads(cutoff_time)
            )
            
            logger.info(f"Found {len(expired_paths)} files to delete")
            
            # 各ファイルをR2から削除
            deleted_count = 0
            for r2_path in expired_paths:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda path=r2_path: self.storage_service.delete_file(path)
                    )
                    deleted_count += 1
                    logger.info(f"🗑️ Deleted: {r2_path}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to delete {r2_path}: {e}")
            
            logger.info(f"Cleanup task complete - deleted {deleted_count}/{len(expired_paths)} files")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
    
    def run_now(self):
        """すぐに削除処理を実行（テスト用）"""
        if not self._running:
            logger.warning("Scheduler is not running, starting cleanup task anyway")
        
        asyncio.create_task(self._cleanup_task())
        logger.info("Cleanup task triggered manually")