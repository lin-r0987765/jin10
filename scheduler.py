"""
排程模組 - 管理定時任務
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz
from config import REALTIME_INTERVAL_SECONDS, VALUATION_HOUR_TW, VALUATION_MINUTE_TW
from analyzer import run_realtime_analysis, run_stock_valuation
from data_store import cleanup_old_data

logger = logging.getLogger(__name__)

TW_TZ = pytz.timezone("Asia/Taipei")

scheduler = BackgroundScheduler(timezone=TW_TZ)


def start_scheduler():
    """啟動所有排程任務"""

    # 任務1: 每分鐘即時分析（四面向輪替）
    scheduler.add_job(
        run_realtime_analysis,
        trigger=IntervalTrigger(seconds=REALTIME_INTERVAL_SECONDS),
        id="realtime_analysis",
        name="即時市場面向分析（每分鐘輪替）",
        replace_existing=True,
        max_instances=1,  # 確保上一次執行完才開始下一次
        misfire_grace_time=30
    )
    logger.info(f"[排程] 即時分析已啟動，每 {REALTIME_INTERVAL_SECONDS} 秒執行一次")

    # 任務2: 每天台灣時間 5:00 股票深度估值
    scheduler.add_job(
        run_stock_valuation,
        trigger=CronTrigger(
            hour=VALUATION_HOUR_TW,
            minute=VALUATION_MINUTE_TW,
            timezone=TW_TZ
        ),
        id="stock_valuation",
        name="每日股票深度估值分析（台灣時間05:00）",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300  # 5分鐘容忍時間
    )
    logger.info(f"[排程] 股票估值已啟動，每天台灣時間 {VALUATION_HOUR_TW:02d}:{VALUATION_MINUTE_TW:02d} 執行")

    # 任務3: 每天凌晨4點清理過期資料
    scheduler.add_job(
        cleanup_old_data,
        trigger=CronTrigger(hour=4, minute=0, timezone=TW_TZ),
        id="data_cleanup",
        name="每日資料清理（台灣時間04:00）",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600
    )
    logger.info("[排程] 資料清理已啟動，每天台灣時間 04:00 執行")

    scheduler.start()
    logger.info("[排程] 排程器已啟動")


def stop_scheduler():
    """停止排程器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[排程] 排程器已停止")


def get_scheduler_status():
    """取得排程狀態"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
            "trigger": str(job.trigger)
        })
    return {
        "running": scheduler.running,
        "jobs": jobs
    }
