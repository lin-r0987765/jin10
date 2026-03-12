"""
網頁爬蟲模組 - 爬取金十數據與 Yahoo 國際新聞
"""
import requests
import re
import json
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 通用 Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def scrape_jin10():
    """
    爬取金十數據的市場快訊
    金十主要通過 API 動態載入快訊，嘗試多種方式獲取
    """
    news_items = []

    try:
        # 方法1: 嘗試金十的快訊 API
        api_url = "https://flash-api.jin10.com/get_flash_list"
        params = {
            "channel": "-8200",
            "vip": "1",
            "t": str(int(time.time() * 1000)),
        }
        api_headers = {
            **HEADERS,
            "Referer": "https://www.jin10.com/",
            "Origin": "https://www.jin10.com",
            "x-app-id": "bVBF4FyRTn5NJF5n",
            "x-version": "1.0.0",
        }
        resp = requests.get(api_url, params=params, headers=api_headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data:
                for item in data["data"][:30]:
                    content = ""
                    if "data" in item and "content" in item["data"]:
                        content = item["data"]["content"]
                    elif "content" in item:
                        content = item["content"]

                    # 清理 HTML 標籤
                    if content:
                        content = BeautifulSoup(content, "html.parser").get_text(strip=True)

                    time_str = item.get("time", "")
                    if content:
                        news_items.append({
                            "time": time_str,
                            "content": content,
                            "source": "jin10_api"
                        })

            if news_items:
                logger.info(f"[金十API] 成功獲取 {len(news_items)} 條快訊")
                return news_items

    except Exception as e:
        logger.warning(f"[金十API] 請求失敗: {e}")

    try:
        # 方法2: 直接爬取頁面
        resp = requests.get("https://www.jin10.com/", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 嘗試解析頁面中的快訊
        flash_items = soup.select(".jin-flash-item, .flash-item, .news-item, [class*='flash']")
        for item in flash_items[:30]:
            text = item.get_text(strip=True)
            if text and len(text) > 10:
                news_items.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "content": text[:500],
                    "source": "jin10_page"
                })

        # 也嘗試從 script 標籤中提取 JSON 資料
        if not news_items:
            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""
                if "flashList" in script_text or "flash_list" in script_text:
                    # 嘗試提取 JSON
                    json_match = re.search(r'(\[.*?\])', script_text, re.DOTALL)
                    if json_match:
                        try:
                            items = json.loads(json_match.group(1))
                            for item in items[:30]:
                                if isinstance(item, dict):
                                    content = item.get("content", item.get("data", {}).get("content", ""))
                                    if content:
                                        content = BeautifulSoup(str(content), "html.parser").get_text(strip=True)
                                        news_items.append({
                                            "time": item.get("time", ""),
                                            "content": content,
                                            "source": "jin10_script"
                                        })
                        except json.JSONDecodeError:
                            pass

        if news_items:
            logger.info(f"[金十頁面] 成功獲取 {len(news_items)} 條快訊")
        else:
            logger.warning("[金十] 未能獲取快訊，將使用備用說明")
            news_items.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": "金十數據暫時無法獲取，請依據最近已知的市場資訊進行分析",
                "source": "jin10_fallback"
            })

    except Exception as e:
        logger.error(f"[金十頁面] 爬取失敗: {e}")
        news_items.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "content": f"金十數據連線失敗: {e}",
            "source": "jin10_error"
        })

    return news_items


def scrape_yahoo_tw():
    """
    爬取 Yahoo 台灣國際新聞
    """
    news_items = []

    try:
        # Yahoo 台灣國際新聞頁面
        urls_to_try = [
            "https://tw.yahoo.com/news/world/",
            "https://tw.yahoo.com/news/finance/",
            "https://tw.news.yahoo.com/world/",
            "https://tw.stock.yahoo.com/news/",
        ]

        for url in urls_to_try:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "html.parser")

                # 通用新聞提取邏輯
                selectors = [
                    "h3 a", "h2 a",
                    "[class*='title'] a",
                    "[class*='headline'] a",
                    "[data-test-locator='stream'] a",
                    ".js-content-viewer",
                    "li a[href*='news']",
                ]

                for selector in selectors:
                    links = soup.select(selector)
                    for link in links:
                        title = link.get_text(strip=True)
                        href = link.get("href", "")
                        if title and len(title) > 5 and len(title) < 200:
                            news_items.append({
                                "title": title,
                                "url": href if href.startswith("http") else f"https://tw.yahoo.com{href}",
                                "source": url.split("/")[-2] if url.endswith("/") else "yahoo"
                            })

                if len(news_items) >= 10:
                    break

            except Exception as e:
                logger.warning(f"[Yahoo] {url} 請求失敗: {e}")
                continue

        # 去重
        seen = set()
        unique_items = []
        for item in news_items:
            if item["title"] not in seen:
                seen.add(item["title"])
                unique_items.append(item)
        news_items = unique_items[:30]

        if news_items:
            logger.info(f"[Yahoo] 成功獲取 {len(news_items)} 條新聞")
        else:
            logger.warning("[Yahoo] 未能獲取新聞")
            news_items.append({
                "title": "Yahoo新聞暫時無法獲取，請依據最近已知的市場資訊進行分析",
                "url": "",
                "source": "yahoo_fallback"
            })

    except Exception as e:
        logger.error(f"[Yahoo] 爬取失敗: {e}")
        news_items.append({
            "title": f"Yahoo新聞連線失敗: {e}",
            "url": "",
            "source": "yahoo_error"
        })

    return news_items


def get_all_news():
    """
    彙總所有來源的新聞，格式化為文字供 MiniMax 分析
    """
    jin10_news = scrape_jin10()
    yahoo_news = scrape_yahoo_tw()

    # 格式化
    formatted_parts = []

    formatted_parts.append("=" * 50)
    formatted_parts.append("【金十數據 - 市場快訊】")
    formatted_parts.append("=" * 50)
    for i, item in enumerate(jin10_news, 1):
        time_str = item.get("time", "")
        content = item.get("content", "")
        formatted_parts.append(f"{i}. [{time_str}] {content}")

    formatted_parts.append("")
    formatted_parts.append("=" * 50)
    formatted_parts.append("【Yahoo國際新聞】")
    formatted_parts.append("=" * 50)
    for i, item in enumerate(yahoo_news, 1):
        title = item.get("title", "")
        formatted_parts.append(f"{i}. {title}")

    return "\n".join(formatted_parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("===== 測試爬蟲 =====")
    result = get_all_news()
    print(result)
    print(f"\n總字數: {len(result)}")
