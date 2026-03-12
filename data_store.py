"""
資料儲存模組 - 使用 SQLite 儲存所有分析結果
"""
import sqlite3
import json
import os
from datetime import datetime
from config import DB_PATH, DATA_DIR, DATA_RETENTION_DAYS, DEFAULT_STOCK_TICKERS


def get_db():
    """取得資料庫連線"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化資料庫表格"""
    conn = get_db()
    cursor = conn.cursor()

    # 即時分析評分表（四大面向每分鐘輪替）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realtime_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            dimension_id TEXT NOT NULL,
            dimension_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            summary TEXT,
            key_factors TEXT,
            raw_news TEXT,
            raw_response TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 股票深度估值表（每天台灣時間5點）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_valuations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            overall_score INTEGER NOT NULL,
            fundamental_score INTEGER,
            technical_score INTEGER,
            sentiment_score INTEGER,
            political_score INTEGER,
            recommendation TEXT,
            target_price_range TEXT,
            key_risks TEXT,
            key_catalysts TEXT,
            analysis_summary TEXT,
            raw_response TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 爬蟲原始資料快照表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 自訂股票代號表（動態新增/刪除）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            added_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1
        )
    """)

    # 初始化預設股票代號
    for ticker in DEFAULT_STOCK_TICKERS:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO custom_tickers (ticker) VALUES (?)",
                (ticker.upper(),)
            )
        except:
            pass

    conn.commit()
    conn.close()


# ===== 股票代號管理 =====

def get_active_tickers():
    """取得目前所有啟用的股票代號"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM custom_tickers WHERE is_active = 1 ORDER BY added_at")
    tickers = [row["ticker"] for row in cursor.fetchall()]
    conn.close()
    return tickers if tickers else DEFAULT_STOCK_TICKERS


def add_ticker(ticker):
    """新增股票代號"""
    ticker = ticker.strip().upper()
    if not ticker:
        return False, "股票代號不可為空"
    if len(ticker) > 10:
        return False, "股票代號過長"

    conn = get_db()
    cursor = conn.cursor()
    try:
        # 檢查是否已存在（包括停用的）
        cursor.execute("SELECT id, is_active FROM custom_tickers WHERE ticker = ?", (ticker,))
        existing = cursor.fetchone()
        if existing:
            if existing["is_active"]:
                conn.close()
                return False, f"{ticker} 已在追蹤列表中"
            else:
                # 重新啟用
                cursor.execute("UPDATE custom_tickers SET is_active = 1 WHERE ticker = ?", (ticker,))
                conn.commit()
                conn.close()
                return True, f"已重新啟用 {ticker}"
        else:
            cursor.execute("INSERT INTO custom_tickers (ticker) VALUES (?)", (ticker,))
            conn.commit()
            conn.close()
            return True, f"已新增 {ticker}"
    except Exception as e:
        conn.close()
        return False, f"新增失敗: {e}"


def remove_ticker(ticker):
    """移除股票代號（軟刪除）"""
    ticker = ticker.strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE custom_tickers SET is_active = 0 WHERE ticker = ?", (ticker,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected > 0:
        return True, f"已移除 {ticker}"
    return False, f"{ticker} 不在追蹤列表中"


# ===== 即時分析評分 =====

def save_realtime_score(dimension_id, dimension_name, score, summary, key_factors, raw_news, raw_response):
    """儲存即時分析評分"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO realtime_scores (timestamp, dimension_id, dimension_name, score, summary, key_factors, raw_news, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, dimension_id, dimension_name, score, summary,
          json.dumps(key_factors, ensure_ascii=False) if isinstance(key_factors, list) else key_factors,
          raw_news, raw_response))
    conn.commit()
    conn.close()


def save_stock_valuation(ticker, overall_score, fundamental_score, technical_score,
                         sentiment_score, political_score, recommendation,
                         target_price_range, key_risks, key_catalysts, analysis_summary, raw_response):
    """儲存股票估值分析"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO stock_valuations (timestamp, ticker, overall_score, fundamental_score, technical_score,
            sentiment_score, political_score, recommendation, target_price_range,
            key_risks, key_catalysts, analysis_summary, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, ticker, overall_score, fundamental_score, technical_score,
          sentiment_score, political_score, recommendation, target_price_range,
          json.dumps(key_risks, ensure_ascii=False) if isinstance(key_risks, list) else key_risks,
          json.dumps(key_catalysts, ensure_ascii=False) if isinstance(key_catalysts, list) else key_catalysts,
          analysis_summary, raw_response))
    conn.commit()
    conn.close()


def save_news_snapshot(source, content):
    """儲存爬蟲快照"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO news_snapshots (timestamp, source, content)
        VALUES (?, ?, ?)
    """, (now, source, content))
    conn.commit()
    conn.close()


# ===== 查詢函數 =====

def get_recent_scores(limit=100):
    """取得最近的即時評分"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM realtime_scores ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_recent_scores_by_dimension(dimension_id, limit=60):
    """取得特定面向的最近評分"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM realtime_scores WHERE dimension_id = ? ORDER BY timestamp DESC LIMIT ?
    """, (dimension_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_latest_scores_all_dimensions():
    """取得每個面向最新的一筆評分"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM realtime_scores
        WHERE id IN (
            SELECT MAX(id) FROM realtime_scores GROUP BY dimension_id
        )
        ORDER BY dimension_id
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_stock_valuations(ticker=None, limit=30):
    """取得股票估值資料"""
    conn = get_db()
    cursor = conn.cursor()
    if ticker:
        cursor.execute("""
            SELECT * FROM stock_valuations WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?
        """, (ticker, limit))
    else:
        cursor.execute("""
            SELECT * FROM stock_valuations ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_latest_stock_valuations():
    """取得每支股票最新的估值"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM stock_valuations
        WHERE id IN (
            SELECT MAX(id) FROM stock_valuations GROUP BY ticker
        )
        ORDER BY ticker
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def cleanup_old_data():
    """清理超過保留天數的舊資料"""
    conn = get_db()
    cursor = conn.cursor()
    cutoff = f"datetime('now', '-{DATA_RETENTION_DAYS} days')"

    tables = ["realtime_scores", "stock_valuations", "news_snapshots"]
    total_deleted = 0

    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE timestamp < {cutoff}")
            deleted = cursor.rowcount
            total_deleted += deleted
            if deleted > 0:
                import logging
                logging.getLogger(__name__).info(f"[資料清理] {table}: 刪除 {deleted} 筆過期資料")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[資料清理] {table} 清理失敗: {e}")

    if total_deleted > 0:
        cursor.execute("VACUUM")  # 壓縮資料庫檔案

    conn.commit()
    conn.close()
    return total_deleted
