"""
MiniMax API 客戶端模組
"""
import requests
import json
import logging
from config import MINIMAX_API_KEY, MINIMAX_BASE_URL, MODEL_REALTIME, MODEL_VALUATION

logger = logging.getLogger(__name__)


def call_minimax(prompt, system_prompt="你是一個專業的金融分析師。", model=None, temperature=0.3, max_tokens=4096):
    """
    呼叫 MiniMax API
    """
    if model is None:
        model = MODEL_REALTIME

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINIMAX_API_KEY}"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "stream": False
    }

    try:
        resp = requests.post(MINIMAX_BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        # 檢查 MiniMax 特有的錯誤格式
        if "base_resp" in data and data["base_resp"].get("status_code", 0) != 0:
            error_msg = data["base_resp"].get("status_msg", "Unknown error")
            logger.error(f"[MiniMax] API 錯誤: {error_msg}")
            return None, error_msg

        # 提取回覆內容
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            logger.info(f"[MiniMax] 成功回覆 | tokens: prompt={usage.get('prompt_tokens', '?')}, "
                        f"completion={usage.get('completion_tokens', '?')}")
            return content, None

        logger.error(f"[MiniMax] 回覆格式異常: {json.dumps(data, ensure_ascii=False)[:500]}")
        return None, "回覆格式異常"

    except requests.exceptions.Timeout:
        logger.error("[MiniMax] 請求逾時")
        return None, "請求逾時"
    except requests.exceptions.RequestException as e:
        logger.error(f"[MiniMax] 請求失敗: {e}")
        return None, str(e)
    except Exception as e:
        logger.error(f"[MiniMax] 未預期錯誤: {e}")
        return None, str(e)


def parse_json_response(content):
    """
    從 MiniMax 回覆中提取 JSON
    支持 markdown code block 包裹的 JSON
    """
    if not content:
        return None

    # 嘗試直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 嘗試從 markdown code block 中提取
    import re
    json_patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'(\{.*\})',
    ]

    for pattern in json_patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    logger.warning(f"[MiniMax] 無法解析 JSON 回覆: {content[:300]}")
    return None
