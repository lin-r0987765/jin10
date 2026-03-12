"""
分析模組 - 四大面向評分 + 股票深度估值
"""
import json
import logging
from datetime import datetime
from config import DIMENSIONS, STOCK_TICKERS, MODEL_REALTIME, MODEL_VALUATION
from minimax_client import call_minimax, parse_json_response
from scraper import get_all_news, fetch_stock_prices
from data_store import save_realtime_score, save_stock_valuation, save_news_snapshot, get_recent_scores_by_dimension

logger = logging.getLogger(__name__)

# 全域計數器，追蹤目前輪到哪個面向
_dimension_counter = 0


def get_next_dimension():
    """取得下一個要分析的面向（四個面向輪替）"""
    global _dimension_counter
    dim = DIMENSIONS[_dimension_counter % len(DIMENSIONS)]
    _dimension_counter += 1
    return dim


def build_realtime_prompt(dimension, news_text, previous_scores=None):
    """
    建構即時分析的 prompt，要求固定 JSON 格式回傳
    previous_scores: 該面向最近幾次的歷史評分記錄 (list of dict)
    """
    # 建構歷史評分參考區塊
    history_block = ""
    if previous_scores:
        history_lines = []
        for i, ps in enumerate(previous_scores, 1):
            history_lines.append(
                f"  {i}. 評分: {ps.get('score', '?')} | "
                f"摘要: {ps.get('summary', 'N/A')} | "
                f"時間: {ps.get('timestamp', 'N/A')}"
            )
        history_block = f"""\n【歷史評分參考（同面向最近 {len(previous_scores)} 次分析結果）】
以下是你先前對此面向的評分記錄，請作為本次評分的參考基準。
除非有明確的重大新聞或數據變化，否則分數變動幅度不應超過 10-15 分，以確保評分的連續性和穩定性。
{chr(10).join(history_lines)}
"""

    return f"""你是一位資深金融市場分析師。現在請根據以下最新市場快訊，針對「{dimension['name']}」這個面向進行評分分析。

【分析面向說明】
{dimension['description']}
{history_block}
【最新市場快訊】
{news_text}

【回傳格式要求】
請嚴格以下列 JSON 格式回傳，不要加入任何其他文字：
{{
    "dimension_id": "{dimension['id']}",
    "dimension_name": "{dimension['name']}",
    "score": <0到100的整數分數>,
    "summary": "<50字以內的一句話總結目前此面向的狀態>",
    "key_factors": [
        "<影響因子1>",
        "<影響因子2>",
        "<影響因子3>"
    ],
    "trend": "<up|down|neutral 表示趨勢方向>",
    "confidence": <0到100的整數，表示你對這個評分的信心程度>
}}

【評分標準】
- 0-20 分：極度悲觀/極度負面
- 21-40 分：偏空/負面因素居多
- 41-60 分：中性/多空交織
- 61-80 分：偏多/正面因素居多
- 81-100 分：極度樂觀/極度正面

【重要提醒】
- 你的評分應該具有連續性，基於上次的評分進行微調，而非每次獨立重新評估。
- 只有當出現重大新聞、重要經濟數據公布、或市場情緒明顯轉變時，才應該有較大幅度的分數變動。
- 如果新聞內容與上次類似且無重大變化，分數應保持穩定或僅有小幅調整（±5分以內）。

請務必只回傳 JSON，不要有其他說明文字。"""


def build_valuation_prompt(ticker, price_data=None):
    """
    建構股票深度估值的 prompt
    price_data: 即時股價資訊 dict，包含 price, change_pct, high_52w, low_52w 等
    """
    # 建構即時市場數據區塊
    market_data_block = ""
    if price_data:
        market_data_block = f"""\n【即時市場數據 - 截至 {datetime.now().strftime('%Y-%m-%d %H:%M')}】
- 目前股價: ${price_data.get('price', 'N/A')}
- 今日漲跌: {price_data.get('change_pct', 'N/A')}
- 52週最高: ${price_data.get('high_52w', 'N/A')}
- 52週最低: ${price_data.get('low_52w', 'N/A')}
- 本益比(P/E): {price_data.get('pe_ratio', 'N/A')}
- 市值: {_format_market_cap(price_data.get('market_cap', 'N/A'))}
- 成交量: {price_data.get('volume', 'N/A')}

重要：上面的即時市場數據是透過 Yahoo Finance API 取得的最新真實數據，請以此為基準進行估值分析。
你的 current_price_estimate 必須使用上面提供的「目前股價」，不要使用你訓練資料中的舊價格。
"""

    return f"""你是一位頂級的股票研究分析師。請對股票代號 {ticker} 進行全面深度估值分析。
{market_data_block}
請運用你所有的知識，包含但不限於：
1. 基本面：最新財報數據、營收成長趨勢、EPS、本益比、產業前景
2. 技術面：近期價格走勢、關鍵支撐壓力位、技術指標訊號
3. 市場情緒：市場對該股票的共識、分析師評級、新聞熱度
4. 外部因素：相關政策、地緣政治風險、產業監管變化

你可以引用任何你知道的最新公開資訊來進行分析。

【回傳格式要求】
請嚴格以下列 JSON 格式回傳，不要加入任何其他文字：
{{
    "ticker": "{ticker}",
    "company_name": "<公司全名>",
    "analysis_date": "<分析日期 YYYY-MM-DD>",
    "overall_score": <0到100的整數，綜合評分>,
    "fundamental_score": <0到100的整數>,
    "technical_score": <0到100的整數>,
    "sentiment_score": <0到100的整數>,
    "political_score": <0到100的整數>,
    "recommendation": "<Strong Buy|Buy|Hold|Sell|Strong Sell>",
    "current_price_estimate": "<必須使用上面提供的即時股價>",
    "target_price_range": "<目標價格區間，如 $150-$180>",
    "key_risks": [
        "<風險因子1>",
        "<風險因子2>",
        "<風險因子3>"
    ],
    "key_catalysts": [
        "<催化劑1>",
        "<催化劑2>",
        "<催化劑3>"
    ],
    "analysis_summary": "<200字以內的綜合分析摘要，包含投資建議的理由>"
}}

請務必只回傳 JSON，不要有其他說明文字。"""


def _format_market_cap(cap):
    """將市值數字格式化為人類可讀的字串"""
    if cap == 'N/A' or not isinstance(cap, (int, float)):
        return str(cap)
    if cap >= 1e12:
        return f"${cap / 1e12:.2f}T"
    elif cap >= 1e9:
        return f"${cap / 1e9:.2f}B"
    elif cap >= 1e6:
        return f"${cap / 1e6:.2f}M"
    return f"${cap:,.0f}"


def run_realtime_analysis():
    """
    執行一次即時分析（每分鐘呼叫一次，四面向輪替）
    """
    dimension = get_next_dimension()
    logger.info(f"[即時分析] 開始分析面向: {dimension['name']} ({dimension['id']})")

    try:
        # 1. 爬取最新新聞
        news_text = get_all_news()
        save_news_snapshot("realtime_combined", news_text[:5000])

        # 2. 取得該面向最近 3 次的歷史評分，作為參考基準
        prev_scores = []
        try:
            recent = get_recent_scores_by_dimension(dimension["id"], limit=3)
            # 只取成功的分數（score >= 0）
            prev_scores = [r for r in recent if r.get("score", -1) >= 0]
            if prev_scores:
                logger.info(f"[即時分析] 取得 {dimension['name']} 歷史評分: {[s['score'] for s in prev_scores]}")
        except Exception as e:
            logger.warning(f"[即時分析] 無法取得歷史評分: {e}")

        # 3. 建構 prompt 並呼叫 MiniMax（帶入歷史分數）
        prompt = build_realtime_prompt(dimension, news_text, previous_scores=prev_scores)
        response, error = call_minimax(prompt, model=MODEL_REALTIME, temperature=0.3, max_tokens=2048)

        if error:
            logger.error(f"[即時分析] MiniMax 呼叫失敗: {error}")
            save_realtime_score(
                dimension_id=dimension["id"],
                dimension_name=dimension["name"],
                score=-1,
                summary=f"分析失敗: {error}",
                key_factors=[],
                raw_news=news_text[:2000],
                raw_response=error
            )
            return

        # 3. 解析回傳的 JSON
        result = parse_json_response(response)
        if result:
            save_realtime_score(
                dimension_id=result.get("dimension_id", dimension["id"]),
                dimension_name=result.get("dimension_name", dimension["name"]),
                score=int(result.get("score", -1)),
                summary=result.get("summary", ""),
                key_factors=result.get("key_factors", []),
                raw_news=news_text[:2000],
                raw_response=response
            )
            logger.info(f"[即時分析] {dimension['name']} 評分: {result.get('score', '?')} | {result.get('summary', '')}")
        else:
            # JSON 解析失敗，仍嘗試儲存原始回覆
            save_realtime_score(
                dimension_id=dimension["id"],
                dimension_name=dimension["name"],
                score=-1,
                summary="JSON 解析失敗",
                key_factors=[],
                raw_news=news_text[:2000],
                raw_response=response
            )
            logger.warning(f"[即時分析] JSON 解析失敗，原始回覆已儲存")

    except Exception as e:
        logger.error(f"[即時分析] 執行異常: {e}", exc_info=True)


def run_stock_valuation():
    """
    執行股票深度估值分析（每天台灣時間5點）
    """
    logger.info(f"[股票估值] 開始深度估值分析，標的: {STOCK_TICKERS}")

    # 先批量獲取所有標的的即時股價
    logger.info("[股票估值] 正在獲取即時股價...")
    all_prices = fetch_stock_prices(STOCK_TICKERS)
    logger.info(f"[股票估值] 成功獲取 {len([v for v in all_prices.values() if v])} 支股票的即時股價")

    for ticker in STOCK_TICKERS:
        try:
            logger.info(f"[股票估值] 分析 {ticker}...")

            price_data = all_prices.get(ticker)
            prompt = build_valuation_prompt(ticker, price_data=price_data)
            response, error = call_minimax(
                prompt,
                system_prompt="你是一位擁有20年經驗的頂級股票研究分析師，擅長量化分析與質化判斷。",
                model=MODEL_VALUATION,
                temperature=0.2,
                max_tokens=4096
            )

            if error:
                logger.error(f"[股票估值] {ticker} MiniMax 呼叫失敗: {error}")
                save_stock_valuation(
                    ticker=ticker, overall_score=-1,
                    fundamental_score=-1, technical_score=-1,
                    sentiment_score=-1, political_score=-1,
                    recommendation="Error", target_price_range="N/A",
                    key_risks=[error], key_catalysts=[],
                    analysis_summary=f"分析失敗: {error}",
                    raw_response=error
                )
                continue

            result = parse_json_response(response)
            if result:
                save_stock_valuation(
                    ticker=result.get("ticker", ticker),
                    overall_score=int(result.get("overall_score", -1)),
                    fundamental_score=int(result.get("fundamental_score", -1)),
                    technical_score=int(result.get("technical_score", -1)),
                    sentiment_score=int(result.get("sentiment_score", -1)),
                    political_score=int(result.get("political_score", -1)),
                    recommendation=result.get("recommendation", "N/A"),
                    target_price_range=result.get("target_price_range", "N/A"),
                    key_risks=result.get("key_risks", []),
                    key_catalysts=result.get("key_catalysts", []),
                    analysis_summary=result.get("analysis_summary", ""),
                    raw_response=response
                )
                logger.info(f"[股票估值] {ticker} 完成 | 綜合評分: {result.get('overall_score', '?')} | 建議: {result.get('recommendation', '?')}")
            else:
                save_stock_valuation(
                    ticker=ticker, overall_score=-1,
                    fundamental_score=-1, technical_score=-1,
                    sentiment_score=-1, political_score=-1,
                    recommendation="Parse Error", target_price_range="N/A",
                    key_risks=["JSON解析失敗"], key_catalysts=[],
                    analysis_summary="JSON 解析失敗",
                    raw_response=response
                )
                logger.warning(f"[股票估值] {ticker} JSON 解析失敗")

        except Exception as e:
            logger.error(f"[股票估值] {ticker} 執行異常: {e}", exc_info=True)

    logger.info("[股票估值] 所有標的分析完成")
