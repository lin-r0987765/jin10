"""
Dashboard 後端 - Flask Web 應用
提供 API 端點與網頁渲染
"""
import json
import logging
import threading
from flask import Flask, render_template, jsonify, request
from data_store import (
    get_recent_scores, get_recent_scores_by_dimension,
    get_latest_scores_all_dimensions, get_stock_valuations,
    get_latest_stock_valuations
)
from scheduler import get_scheduler_status
from analyzer import run_realtime_analysis, run_stock_valuation
from config import DASHBOARD_HOST, DASHBOARD_PORT, DIMENSIONS, STOCK_TICKERS

logger = logging.getLogger(__name__)

app = Flask(__name__)

# 背景任務狀態追蹤
_task_status = {
    "realtime": {"running": False, "last_error": None},
    "valuation": {"running": False, "last_error": None},
}
_status_lock = threading.Lock()


def _run_in_background(task_key, func):
    """在背景線程中執行任務"""
    def wrapper():
        try:
            func()
        except Exception as e:
            logger.error(f"[背景任務] {task_key} 執行失敗: {e}", exc_info=True)
            with _status_lock:
                _task_status[task_key]["last_error"] = str(e)
        finally:
            with _status_lock:
                _task_status[task_key]["running"] = False

    with _status_lock:
        if _task_status[task_key]["running"]:
            return False  # 已在執行中
        _task_status[task_key]["running"] = True
        _task_status[task_key]["last_error"] = None

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return True


# ===== 頁面路由 =====

@app.route("/")
def index():
    """主頁面 - Dashboard"""
    return render_template("dashboard.html",
                           dimensions=DIMENSIONS,
                           tickers=STOCK_TICKERS)


# ===== API 端點 =====

@app.route("/api/realtime/latest")
def api_realtime_latest():
    """取得每個面向最新的評分"""
    try:
        data = get_latest_scores_all_dimensions()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"success": False, "data": [], "error": str(e)})


@app.route("/api/realtime/history")
def api_realtime_history():
    """取得即時評分歷史"""
    try:
        dimension_id = request.args.get("dimension_id", None)
        limit = int(request.args.get("limit", 60))
        if dimension_id:
            data = get_recent_scores_by_dimension(dimension_id, limit)
        else:
            data = get_recent_scores(limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"success": False, "data": [], "error": str(e)})


@app.route("/api/valuation/latest")
def api_valuation_latest():
    """取得每支股票最新的估值"""
    try:
        data = get_latest_stock_valuations()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"success": False, "data": [], "error": str(e)})


@app.route("/api/valuation/history")
def api_valuation_history():
    """取得股票估值歷史"""
    try:
        ticker = request.args.get("ticker", None)
        limit = int(request.args.get("limit", 30))
        data = get_stock_valuations(ticker, limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({"success": False, "data": [], "error": str(e)})


@app.route("/api/scheduler/status")
def api_scheduler_status():
    """取得排程狀態"""
    status = get_scheduler_status()
    with _status_lock:
        status["tasks"] = {k: dict(v) for k, v in _task_status.items()}
    return jsonify({"success": True, "data": status})


@app.route("/api/trigger/realtime", methods=["POST"])
def api_trigger_realtime():
    """手動觸發一次即時分析（背景執行）"""
    started = _run_in_background("realtime", run_realtime_analysis)
    if started:
        return jsonify({"success": True, "message": "即時分析已在背景啟動"})
    else:
        return jsonify({"success": False, "message": "即時分析正在執行中，請稍候"})


@app.route("/api/trigger/valuation", methods=["POST"])
def api_trigger_valuation():
    """手動觸發一次股票估值（背景執行）"""
    started = _run_in_background("valuation", run_stock_valuation)
    if started:
        return jsonify({"success": True, "message": "股票估值已在背景啟動，約需2-3分鐘"})
    else:
        return jsonify({"success": False, "message": "股票估值正在執行中，請稍候"})


@app.route("/api/task/status")
def api_task_status():
    """查詢背景任務狀態"""
    with _status_lock:
        return jsonify({"success": True, "data": {k: dict(v) for k, v in _task_status.items()}})


@app.route("/api/debug")
def api_debug():
    """除錯端點 - 顯示資料庫和系統狀態"""
    import os
    import sqlite3
    from config import DB_PATH, DATA_DIR
    info = {
        "db_path": DB_PATH,
        "data_dir": DATA_DIR,
        "db_exists": os.path.exists(DB_PATH),
    }
    try:
        info["db_size"] = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM realtime_scores")
        info["realtime_count"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stock_valuations")
        info["valuation_count"] = cursor.fetchone()[0]

        cursor.execute("SELECT dimension_id, score, summary, timestamp FROM realtime_scores ORDER BY id DESC LIMIT 5")
        info["recent_realtime"] = [{"dim": r[0], "score": r[1], "summary": r[2], "time": r[3]} for r in cursor.fetchall()]

        cursor.execute("SELECT ticker, overall_score, recommendation, timestamp FROM stock_valuations ORDER BY id DESC LIMIT 10")
        info["recent_valuation"] = [{"ticker": r[0], "score": r[1], "rec": r[2], "time": r[3]} for r in cursor.fetchall()]

        conn.close()
    except Exception as e:
        info["error"] = str(e)

    return jsonify(info)
