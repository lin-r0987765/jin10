"""
分析模組 - 四大面向評分 + 股票深度估值
"""
import json
import logging
from datetime import datetime
from config import DIMENSIONS, MODEL_REALTIME, MODEL_VALUATION
from minimax_client import call_minimax, parse_json_response
from scraper import get_all_news, fetch_stock_prices
from data_store import (
    save_realtime_score, save_stock_valuation, save_news_snapshot,
    get_recent_scores_by_dimension, get_active_tickers
)

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


def build_valuation_prompt(ticker, price_data=None, news_text=None):
    """
    建構股票深度估值的 prompt（加強版 - 更深入的分析）
    price_data: 即時股價資訊 dict
    news_text: 最新爬取的市場新聞文字
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
你的 current_price 必須使用上面提供的「目前股價」，不要使用你訓練資料中的舊價格。
"""

    # 建構最新新聞區塊
    news_block = ""
    if news_text:
        trimmed_news = news_text[:4000]
        news_block = f"""\n【最新市場快訊（即時爬取）】
以下是透過爬蟲從金十數據、Yahoo Finance、Finviz 取得的最新市場消息，請務必參考這些最新資訊來輔助分析。
{trimmed_news}
"""

    return f"""你是一位擁有 20 年經驗的頂級華爾街股票研究分析師，專精於量化模型分析與基本面深度研究。
請對股票代號 {ticker} 進行全面深度估值分析，分析深度必須達到專業投行研報的水準。
{market_data_block}{news_block}

請運用你所有的知識，結合以上提供的即時市場數據與最新新聞，針對以下 8 個維度進行深入分析：

【一、基本面分析（Fundamental Analysis）】
- 最近 4 個季度的營收、淨利、EPS 及年增率（YoY）趨勢
- 毛利率、營業利益率、淨利率的變化趨勢
- 自由現金流（FCF）與經營現金流（OCF）的穩定性
- 資產負債表健康度：流動比率、負債權益比
- 下一季 Guidance 展望及分析師共識預期

【二、估值模型（Valuation Models）】
- P/E（本益比）、Forward P/E、PEG 比率
- P/S（市銷率）、P/B（市淨率）、EV/EBITDA
- DCF 內在價值估算（簡化版：基於預估未來 5 年現金流，折現率 8-10%）
- 與同業的估值倍數比較（至少列出 3 家可比公司）
- 目前股價相對於合理價值的溢價/折價百分比

【三、技術面分析（Technical Analysis）】
- 目前股價相對於 50 日、100 日、200 日移動平均線的位置
- RSI、MACD 等動量指標的訊號解讀
- 近期重要支撐位與壓力位（至少各 2 個價位）
- 成交量趨勢是否支持目前的價格走勢
- 近 3 個月的價格形態（頭肩、雙底、三角收斂等）

【四、市場情緒與機構動態（Sentiment & Institutional）】
- 華爾街分析師共識評級（買入/持有/賣出的比例）
- 最新的目標價上調或下調情況
- 機構持股變化（近期大型基金增持或減持動態）
- 散戶情緒指標（社交媒體熱度、期權市場的 Put/Call 比率）
- 空頭部位佔比（Short Interest %）

【五、產業與競爭格局（Industry & Competition）】
- 所屬產業的整體趨勢與成長前景
- 公司在產業中的市佔率與競爭優勢（護城河分析）
- 主要競爭對手的近期表現比較
- 產業供需變化與定價趨勢
- 技術革新或顛覆風險

【六、政策與地緣政治風險（Policy & Geopolitical）】
- 目前的利率環境與 Fed 政策對該股的影響
- 相關法規或政策變化（反壟斷、碳稅、補貼等）
- 國際貿易政策風險（關稅、制裁、供應鏈影響）
- 地緣政治衝突可能的間接影響

【七、風險評估（Risk Assessment）】
- 列出最關鍵的 5 個下行風險，並評估每個風險的發生概率（高/中/低）和潛在影響程度
- 黑天鵝事件的可能情境
- 最壞情況下的價格預估

【八、催化劑與時間框架（Catalysts & Timeline）】
- 列出未來 1-6 個月內最可能推動股價的正面催化劑
- 每個催化劑的預估時間點和可能的影響幅度
- 短期（1個月）、中期（3個月）、長期（12個月）的價格展望

【回傳格式要求】
請嚴格以下列 JSON 格式回傳，不要加入任何其他文字：
{{
    "ticker": "{ticker}",
    "company_name": "<公司全名>",
    "analysis_date": "<分析日期 YYYY-MM-DD>",
    "current_price": "<必須使用上面提供的即時股價>",
    "overall_score": <0到100的整數，綜合評分>,
    "fundamental_score": <0到100的整數>,
    "technical_score": <0到100的整數>,
    "sentiment_score": <0到100的整數>,
    "political_score": <0到100的整數>,
    "recommendation": "<Strong Buy|Buy|Hold|Sell|Strong Sell>",
    "target_price_range": "<目標價格區間，如 $150-$180>",
    "fair_value_estimate": "<DCF 模型估算的合理價值>",
    "upside_downside_pct": "<距合理價值的上漲/下跌空間百分比>",
    "valuation_summary": {{
        "pe_ratio": "<目前 P/E>",
        "forward_pe": "<預估 Forward P/E>",
        "peg_ratio": "<PEG 比率>",
        "ps_ratio": "<P/S 比率>",
        "ev_ebitda": "<EV/EBITDA>",
        "vs_industry_avg": "<相對產業平均估值是溢價還是折價，及百分比>"
    }},
    "comparable_companies": [
        {{"ticker": "<可比公司1代號>", "pe": "<P/E>", "note": "<簡短比較>"}},
        {{"ticker": "<可比公司2代號>", "pe": "<P/E>", "note": "<簡短比較>"}},
        {{"ticker": "<可比公司3代號>", "pe": "<P/E>", "note": "<簡短比較>"}}
    ],
    "technical_levels": {{
        "support_1": "<第一支撐位>",
        "support_2": "<第二支撐位>",
        "resistance_1": "<第一壓力位>",
        "resistance_2": "<第二壓力位>",
        "trend_signal": "<短期趨勢訊號: bullish/bearish/neutral>"
    }},
    "key_risks": [
        {{"risk": "<風險描述>", "probability": "<高/中/低>", "impact": "<高/中/低>"}},
        {{"risk": "<風險描述>", "probability": "<高/中/低>", "impact": "<高/中/低>"}},
        {{"risk": "<風險描述>", "probability": "<高/中/低>", "impact": "<高/中/低>"}},
        {{"risk": "<風險描述>", "probability": "<高/中/低>", "impact": "<高/中/低>"}},
        {{"risk": "<風險描述>", "probability": "<高/中/低>", "impact": "<高/中/低>"}}
    ],
    "key_catalysts": [
        {{"catalyst": "<催化劑描述>", "timeline": "<預估時間>", "impact": "<可能的影響幅度>"}},
        {{"catalyst": "<催化劑描述>", "timeline": "<預估時間>", "impact": "<可能的影響幅度>"}},
        {{"catalyst": "<催化劑描述>", "timeline": "<預估時間>", "impact": "<可能的影響幅度>"}}
    ],
    "price_targets": {{
        "short_term_1m": "<1個月目標價>",
        "mid_term_3m": "<3個月目標價>",
        "long_term_12m": "<12個月目標價>",
        "worst_case": "<最壞情況價格>"
    }},
    "analyst_consensus": {{
        "buy_pct": "<買入佔比>",
        "hold_pct": "<持有佔比>",
        "sell_pct": "<賣出佔比>",
        "avg_target": "<分析師平均目標價>"
    }},
    "analysis_summary": "<300字以內的綜合深度分析摘要，涵蓋核心投資邏輯、主要風險、以及明確的投資建議理由>"
}}

請務必只回傳 JSON，不要有其他說明文字。
分析必須深入、具體、有數據支持。避免泛泛而談，每個判斷都要有明確的依據。"""


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
        # 1. 爬取最新新聞（金十 + Yahoo + Finviz）
        news_text = get_all_news()
        save_news_snapshot("realtime_combined", news_text[:5000])

        # 2. 取得該面向最近 3 次的歷史評分，作為參考基準
        prev_scores = []
        try:
            recent = get_recent_scores_by_dimension(dimension["id"], limit=3)
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

        # 4. 解析回傳的 JSON
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
    使用動態股票代號列表
    """
    tickers = get_active_tickers()
    logger.info(f"[股票估值] 開始深度估值分析，標的: {tickers}")

    # 先批量獲取所有標的的即時股價
    logger.info("[股票估值] 正在獲取即時股價...")
    all_prices = fetch_stock_prices(tickers)
    logger.info(f"[股票估值] 成功獲取 {len([v for v in all_prices.values() if v])} 支股票的即時股價")

    # 爬取最新新聞作為分析參考
    logger.info("[股票估值] 正在爬取最新市場新聞...")
    news_text = get_all_news()
    save_news_snapshot("valuation_combined", news_text[:5000])
    logger.info(f"[股票估值] 新聞爬取完成，共 {len(news_text)} 字")

    for ticker in tickers:
        try:
            logger.info(f"[股票估值] 分析 {ticker}...")

            price_data = all_prices.get(ticker)
            prompt = build_valuation_prompt(ticker, price_data=price_data, news_text=news_text)
            response, error = call_minimax(
                prompt,
                system_prompt="你是一位擁有20年經驗的頂級華爾街股票研究分析師，專精量化分析、估值模型與產業研究。你的分析報告以深度、精確和專業著稱。請用繁體中文回答。",
                model=MODEL_VALUATION,
                temperature=0.2,
                max_tokens=8192
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
                # 從新的深度格式中提取 key_risks 和 key_catalysts
                key_risks = result.get("key_risks", [])
                if key_risks and isinstance(key_risks[0], dict):
                    key_risks = [r.get("risk", str(r)) for r in key_risks]

                key_catalysts = result.get("key_catalysts", [])
                if key_catalysts and isinstance(key_catalysts[0], dict):
                    key_catalysts = [c.get("catalyst", str(c)) for c in key_catalysts]

                save_stock_valuation(
                    ticker=result.get("ticker", ticker),
                    overall_score=int(result.get("overall_score", -1)),
                    fundamental_score=int(result.get("fundamental_score", -1)),
                    technical_score=int(result.get("technical_score", -1)),
                    sentiment_score=int(result.get("sentiment_score", -1)),
                    political_score=int(result.get("political_score", -1)),
                    recommendation=result.get("recommendation", "N/A"),
                    target_price_range=result.get("target_price_range", "N/A"),
                    key_risks=key_risks,
                    key_catalysts=key_catalysts,
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
