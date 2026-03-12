"""
股票估值分析系統 - 主入口
啟動方式: python main.py

系統流程:
1. 爬取金十數據 + Yahoo國際新聞
2. 每分鐘傳給 MiniMax 做四面向輪替評分（基本面→技術面→市場情緒→政治政策）
3. 收到回傳後統整存入資料庫 → 自動更新 Dashboard
4. 每天台灣時間 05:00 對 QQQ, GOOG, MSFT, NVDA, TSLA 做深度估值分析
"""
import logging
import sys
import os

# 確保工作目錄正確
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 先建立日誌目錄（必須在 logging 初始化之前）
_log_dir = os.path.join(os.path.expanduser("~"), ".stock_valuation_data")
os.makedirs(_log_dir, exist_ok=True)

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(_log_dir, "system.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("   股票估值分析系統啟動")
    logger.info("=" * 60)

    # 1. 初始化資料庫
    from data_store import init_db
    init_db()
    logger.info("[啟動] 資料庫初始化完成")

    # 2. 啟動排程器
    from scheduler import start_scheduler
    start_scheduler()
    logger.info("[啟動] 排程器啟動完成")

    # 3. 啟動 Dashboard
    from dashboard import app
    from config import DASHBOARD_HOST, DASHBOARD_PORT
    logger.info(f"[啟動] Dashboard 啟動中: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    logger.info(f"[啟動] 本機瀏覽: http://localhost:{DASHBOARD_PORT}")
    logger.info("=" * 60)

    app.run(
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=False,
        threaded=True,       # 啟用多線程，避免長時間任務阻塞 Dashboard
        use_reloader=False   # 避免排程器重複啟動
    )


if __name__ == "__main__":
    main()
