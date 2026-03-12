"""
網頁爬蟲模組 - 爬取金十數據即時快訊、Yahoo Finance 新聞、Finviz 新聞
"""
import requests
import re
import json
import time
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ===== 通用 Session 設定 =====
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})


def _safe_request(url, headers=None, params=None, timeout=20, retries=2):
    """帶重試機制的安全請求"""
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 403:
                logger.warning(f"[爬蟲] {url} 返回 403，嘗試 {attempt + 1}/{retries + 1}")
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    _session.cookies.clear()
                    continue
            else:
                logger.warning(f"[爬蟲] {url} 返回 HTTP {resp.status_code}")
                return resp
        except Exception as e:
            logger.warning(f"[爬蟲] {url} 請求失敗 (嘗試 {attempt + 1}): {e}")
            if attempt < retries:
                time.sleep(2)
    return None


# ===== 金十數據即時快訊 =====

def scrape_jin10():
    """
    爬取金十數據的即時快訊（7x24 Flash News）
    使用金十的公開 API
    """
    items = []
    try:
        api_url = "https://flash-api.jin10.com/get_flash_list"
        headers = {
            "x-app-id": "bVBF4FyRTn5NJF5n",
            "x-version": "1.0.0",
            "Referer": "https://www.jin10.com/",
            "Origin": "https://www.jin10.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        params = {
            "channel": "-8200",
            "vip": "1",
            "max_time": "",
        }
        resp = _safe_request(api_url, headers=headers, params=params, timeout=15)
        if resp and resp.status_code == 200:
            data = resp.json()
            flash_list = data.get("data", [])
            if isinstance(flash_list, list):
                for item in flash_list:
                    # 金十的 data 欄位結構
                    content = ""
                    if isinstance(item.get("data"), dict):
                        content = item["data"].get("content", "") or item["data"].get("title", "")
                    elif isinstance(item.get("data"), str):
                        content = item["data"]

                    # 清理 HTML 標籤
                    if content:
                        content = BeautifulSoup(content, "html.parser").get_text(strip=True)

                    time_str = item.get("time", "")
                    if time_str:
                        try:
                            # 只取 HH:MM
                            time_str = time_str[11:16] if len(time_str) > 16 else time_str
                        except:
                            pass

                    if content and len(content) > 3:
                        items.append({
                            "time": time_str,
                            "content": content[:500],
                            "source": "jin10"
                        })

                if items:
                    logger.info(f"[金十數據] 成功獲取 {len(items)} 條即時快訊")
                    return items

    except Exception as e:
        logger.error(f"[金十數據] 爬取失敗: {e}")

    # 備用：使用金十的另一個 API
    if not items:
        try:
            resp2 = _safe_request(
                "https://flash-api.jin10.com/get_flash_list",
                headers={
                    "x-app-id": "bVBF4FyRTn5NJF5n",
                    "Referer": "https://www.jin10.com/",
                },
                params={"channel": "-8200", "vip": "1", "max_time": "", "t": str(int(time.time() * 1000))},
                timeout=15
            )
            if resp2 and resp2.status_code == 200:
                data2 = resp2.json()
                for item in data2.get("data", []):
                    content = ""
                    if isinstance(item.get("data"), dict):
                        content = item["data"].get("content", "") or item["data"].get("title", "")
                    elif isinstance(item.get("data"), str):
                        content = item["data"]
                    if content:
                        content = BeautifulSoup(content, "html.parser").get_text(strip=True)
                    if content and len(content) > 3:
                        items.append({
                            "time": item.get("time", "")[:16] if item.get("time") else "",
                            "content": content[:500],
                            "source": "jin10_v2"
                        })
                if items:
                    logger.info(f"[金十數據v2] 成功獲取 {len(items)} 條快訊")
                    return items
        except Exception as e:
            logger.warning(f"[金十數據v2] 備用 API 也失敗: {e}")

    if not items:
        logger.warning("[金十數據] 所有方式均失敗")
    return items


# ===== Yahoo Finance 新聞 =====

def scrape_yahoo_finance():
    """
    爬取 Yahoo Finance 的市場新聞
    使用 RSS feed（最穩定的免費方式）+ 頁面爬取
    """
    items = []

    # 方法1: Yahoo Finance RSS Feed（最穩定）
    rss_urls = [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=QQQ,GOOG,MSFT,NVDA,TSLA&region=US&lang=en-US",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
    ]
    for rss_url in rss_urls:
        try:
            resp = _safe_request(rss_url, timeout=12)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "xml")
                rss_items = soup.find_all("item")
                for rss_item in rss_items[:25]:
                    title = rss_item.find("title")
                    desc = rss_item.find("description")
                    pub_date = rss_item.find("pubDate")
                    if title:
                        title_text = title.get_text(strip=True)
                        desc_text = desc.get_text(strip=True)[:300] if desc else ""
                        items.append({
                            "title": title_text,
                            "content": desc_text if desc_text else title_text,
                            "time": pub_date.get_text(strip=True)[:16] if pub_date else "",
                            "source": "yahoo_finance"
                        })
                if items:
                    logger.info(f"[Yahoo Finance RSS] 成功獲取 {len(items)} 條新聞")
                    return items
        except Exception as e:
            logger.debug(f"[Yahoo Finance RSS] {rss_url} 失敗: {e}")

    # 方法2: 直接爬取 finance.yahoo.com 頁面
    try:
        page_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = _safe_request("https://finance.yahoo.com/", headers=page_headers, timeout=15)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # 嘗試提取 SSR JSON 資料
            scripts = soup.find_all("script")
            for script in scripts:
                text = script.string or ""
                if "root.App.main" in text or '"newsStream"' in text:
                    json_match = re.search(r'root\.App\.main\s*=\s*(\{.*?\});', text, re.DOTALL)
                    if json_match:
                        try:
                            state = json.loads(json_match.group(1))
                            _extract_yahoo_news(state, items)
                        except:
                            pass

            # HTML 選擇器
            if not items:
                selectors = [
                    "h3 a", "[data-testid='storyitem'] a",
                    "a[href*='/news/']", ".stream-item a",
                ]
                for sel in selectors:
                    links = soup.select(sel)
                    for link in links:
                        title = link.get_text(strip=True)
                        if title and 8 < len(title) < 200:
                            items.append({
                                "title": title,
                                "content": title,
                                "time": datetime.now().strftime("%H:%M"),
                                "source": "yahoo_page"
                            })
                    if len(items) >= 10:
                        break

            if items:
                # 去重
                seen = set()
                unique = []
                for item in items:
                    key = item.get("title", "") or item.get("content", "")
                    if key not in seen:
                        seen.add(key)
                        unique.append(item)
                items = unique[:25]
                logger.info(f"[Yahoo Finance 頁面] 成功獲取 {len(items)} 條新聞")
                return items

    except Exception as e:
        logger.warning(f"[Yahoo Finance 頁面] 爬取失敗: {e}")

    if not items:
        logger.warning("[Yahoo Finance] 所有方式均失敗")
    return items


def _extract_yahoo_news(obj, results, depth=0):
    """遞迴從 Yahoo 的 SSR state 中提取新聞"""
    if depth > 5 or len(results) >= 25:
        return
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and ("title" in item or "headline" in item):
                title = item.get("title", "") or item.get("headline", "")
                if title and len(title) > 8:
                    results.append({
                        "title": title,
                        "content": item.get("summary", "") or item.get("description", "") or title,
                        "time": item.get("pubDate", "") or item.get("publishedAt", ""),
                        "source": "yahoo_ssr"
                    })
            elif isinstance(item, (dict, list)):
                _extract_yahoo_news(item, results, depth + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _extract_yahoo_news(v, results, depth + 1)


# ===== Finviz 新聞 =====

def scrape_finviz():
    """
    爬取 Finviz 的市場新聞
    URL: https://finviz.com/news.ashx
    """
    items = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://finviz.com/",
        }
        # Finviz 需要獨立請求（不使用共享 session，避免 cookie/header 干擾）
        resp = requests.get("https://finviz.com/news.ashx", headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # 方法1: 使用 nn-tab-link class（Finviz 新聞連結的主要 class）
            news_links = soup.select("a.nn-tab-link")
            if news_links:
                for link in news_links:
                    title = link.get_text(strip=True)
                    if title and len(title) > 5:
                        # 從同行的 td 中取得時間
                        row = link.find_parent("tr")
                        time_display = ""
                        if row:
                            cells = row.find_all("td")
                            for cell in cells:
                                cell_text = cell.get_text(strip=True)
                                if re.match(r'\d{1,2}:\d{2}[AP]M', cell_text):
                                    time_display = cell_text
                                    break
                                elif re.match(r'\w{3}-\d{1,2}', cell_text):
                                    time_display = cell_text
                                    break
                        if not time_display:
                            time_display = datetime.now().strftime("%H:%M")

                        items.append({
                            "title": title,
                            "content": title,
                            "time": time_display,
                            "source": "finviz"
                        })

            # 方法2: 使用 styled-table-new（備用）
            if not items:
                tables = soup.find_all("table", class_="styled-table-new")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        link = row.find("a")
                        if link:
                            title = link.get_text(strip=True)
                            if title and len(title) > 8:
                                cells = row.find_all("td")
                                time_display = ""
                                for cell in cells:
                                    t = cell.get_text(strip=True)
                                    if re.match(r'\d{1,2}:\d{2}[AP]M', t) or re.match(r'\w{3}-\d{1,2}', t):
                                        time_display = t
                                        break
                                items.append({
                                    "title": title,
                                    "content": title,
                                    "time": time_display or datetime.now().strftime("%H:%M"),
                                    "source": "finviz_table"
                                })

            if items:
                # 去重
                seen = set()
                unique = []
                for item in items:
                    key = item.get("title", "")
                    if key and key not in seen:
                        seen.add(key)
                        unique.append(item)
                items = unique[:30]
                logger.info(f"[Finviz] 成功獲取 {len(items)} 條新聞")

    except Exception as e:
        logger.error(f"[Finviz] 爬取失敗: {e}")

    if not items:
        logger.warning("[Finviz] 未能獲取新聞")
    return items


# ===== 備用新聞來源（當主要來源都失敗時）=====

def _fallback_news():
    """備用新聞來源 - Google News RSS"""
    items = []
    try:
        resp = _safe_request(
            "https://news.google.com/rss/search?q=stock+market+US&hl=en-US&gl=US&ceid=US:en",
            timeout=10
        )
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            rss_items = soup.find_all("item")
            for rss_item in rss_items[:15]:
                title = rss_item.find("title")
                pub_date = rss_item.find("pubDate")
                if title:
                    items.append({
                        "title": title.get_text(strip=True),
                        "content": title.get_text(strip=True),
                        "time": pub_date.get_text(strip=True)[:16] if pub_date else "",
                        "source": "google_news_rss"
                    })
            if items:
                logger.info(f"[Google News RSS] 成功獲取 {len(items)} 條新聞")
    except Exception as e:
        logger.debug(f"[Google News RSS] 失敗: {e}")

    if not items:
        items.append({
            "title": "新聞來源暫時無法獲取，請依據最近已知的市場資訊進行分析",
            "content": "新聞來源暫時無法獲取",
            "time": datetime.now().strftime("%H:%M"),
            "source": "fallback"
        })
    return items


# ===== 彙總所有來源的新聞 =====

def get_all_news():
    """
    彙總所有來源的新聞，格式化為文字供 MiniMax 分析
    來源：金十數據（即時快訊）+ Yahoo Finance + Finviz
    """
    jin10_data = scrape_jin10()
    yahoo_data = scrape_yahoo_finance()
    finviz_data = scrape_finviz()

    # 如果所有主要來源都失敗，使用備用
    if not jin10_data and not yahoo_data and not finviz_data:
        yahoo_data = _fallback_news()

    formatted_parts = []

    # 金十數據即時快訊
    if jin10_data:
        formatted_parts.append("=" * 50)
        formatted_parts.append("【金十數據 - 即時快訊】")
        formatted_parts.append("=" * 50)
        for i, item in enumerate(jin10_data[:30], 1):
            time_str = item.get("time", "")
            content = item.get("content", "")
            formatted_parts.append(f"{i}. [{time_str}] {content}")

    # Yahoo Finance 新聞
    if yahoo_data:
        formatted_parts.append("")
        formatted_parts.append("=" * 50)
        formatted_parts.append("【Yahoo Finance - 國際財經新聞】")
        formatted_parts.append("=" * 50)
        for i, item in enumerate(yahoo_data[:20], 1):
            time_str = item.get("time", "")
            title = item.get("title", "")
            content = item.get("content", "")
            display = title if title else content
            if content and content != title:
                display += f" | {content[:150]}"
            formatted_parts.append(f"{i}. [{time_str}] {display}")

    # Finviz 新聞
    if finviz_data:
        formatted_parts.append("")
        formatted_parts.append("=" * 50)
        formatted_parts.append("【Finviz - 美股市場新聞】")
        formatted_parts.append("=" * 50)
        for i, item in enumerate(finviz_data[:20], 1):
            time_str = item.get("time", "")
            title = item.get("title", "")
            formatted_parts.append(f"{i}. [{time_str}] {title}")

    result = "\n".join(formatted_parts)
    if not result.strip():
        result = "目前暫無新聞來源可用，請基於你已知的最新市場資訊進行分析。"

    return result


# ===== 即時股價（使用 yfinance）=====

def fetch_stock_prices(tickers):
    """
    使用 yfinance 獲取即時股價資訊
    回傳格式: { ticker: { price, change_pct, high_52w, low_52w, market_cap, pe_ratio, volume } }
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[股價] yfinance 未安裝，無法獲取即時股價")
        return {}

    results = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if not info or "currentPrice" not in info:
                # 嘗試從 fast_info 或 history 取得
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = round(float(hist["Close"].iloc[-1]), 2)
                    results[ticker] = {
                        "price": current_price,
                        "change_pct": "N/A",
                        "high_52w": "N/A",
                        "low_52w": "N/A",
                        "market_cap": "N/A",
                        "pe_ratio": "N/A",
                        "volume": "N/A",
                    }
                    logger.info(f"[股價] {ticker}: ${current_price} (from history)")
                continue

            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev_close = info.get("regularMarketPreviousClose", 0)
            change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close else 0

            results[ticker] = {
                "price": round(float(current_price), 2),
                "change_pct": f"{'+' if change_pct >= 0 else ''}{change_pct}%",
                "high_52w": round(float(info.get("fiftyTwoWeekHigh", 0)), 2),
                "low_52w": round(float(info.get("fiftyTwoWeekLow", 0)), 2),
                "market_cap": info.get("marketCap", "N/A"),
                "pe_ratio": round(float(info.get("trailingPE", 0)), 2) if info.get("trailingPE") else "N/A",
                "volume": info.get("regularMarketVolume", "N/A"),
            }
            logger.info(f"[股價] {ticker}: ${current_price} ({change_pct:+.2f}%)")

        except Exception as e:
            logger.warning(f"[股價] {ticker} 獲取失敗: {e}")
            results[ticker] = None

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("===== 測試金十數據爬蟲 =====")
    jin10 = scrape_jin10()
    print(f"金十: {len(jin10)} 條")
    for item in jin10[:5]:
        print(f"  [{item['time']}] {item['content'][:80]}")

    print("\n===== 測試 Yahoo Finance =====")
    yahoo = scrape_yahoo_finance()
    print(f"Yahoo: {len(yahoo)} 條")
    for item in yahoo[:5]:
        print(f"  [{item['time']}] {item.get('title', item['content'])[:80]}")

    print("\n===== 測試 Finviz =====")
    finviz = scrape_finviz()
    print(f"Finviz: {len(finviz)} 條")
    for item in finviz[:5]:
        print(f"  [{item['time']}] {item.get('title', item['content'])[:80]}")

    print("\n===== 彙總新聞 =====")
    all_news = get_all_news()
    print(f"總字數: {len(all_news)}")
    print(all_news[:1000])

    print("\n===== 測試即時股價 =====")
    prices = fetch_stock_prices(["QQQ", "GOOG", "NVDA"])
    for t, p in prices.items():
        print(f"  {t}: {p}")
