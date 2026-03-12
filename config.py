"""
股票估值系統 - 配置檔
"""
import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ===== MiniMax API 設定 =====
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"
MODEL_REALTIME = "MiniMax-M2.5"             # 即時分析用
MODEL_VALUATION = "MiniMax-M2.5"            # 股票估值分析用

# ===== 爬蟲來源 =====
JIN10_API_URL = "https://flash-api.jin10.com/get_flash_list"
YAHOO_FINANCE_URL = "https://finance.yahoo.com/"
FINVIZ_NEWS_URL = "https://finviz.com/news.ashx"

# ===== 分析標的（預設值，可從網頁動態新增）=====
DEFAULT_STOCK_TICKERS = ["QQQ", "GOOG", "MSFT", "NVDA", "TSLA"]

# 向後相容：其他模組仍可 import STOCK_TICKERS
# 實際運行時會從 data_store 讀取動態列表
STOCK_TICKERS = DEFAULT_STOCK_TICKERS.copy()

# ===== 四大面向（每分鐘輪替）=====
DIMENSIONS = [
    {
        "id": "fundamental",
        "name": "基本面",
        "name_en": "Fundamentals",
        "description": """評估基本面，包含：
【宏觀經濟】利率與貨幣政策（Fed升降息影響）、通貨膨脹水平、GDP成長率、非農就業數據、PMI指數
【微觀企業】營收與獲利(EPS是否超預期)、產業地位與競爭護城河（技術專利、品牌效應）、公司未來展望(Guidance)"""
    },
    {
        "id": "technical",
        "name": "技術面",
        "name_en": "Technical",
        "description": """評估技術面，包含：
【趨勢與形態】多頭/空頭排列、頭肩頂/底型等價格形態
【移動平均線】50日線、200日線的支撐阻力與趨勢判斷
【動量指標】RSI相對強弱指數、MACD指標的超買超賣判斷
【成交量】價量配合程度，上漲是否有成交量支持"""
    },
    {
        "id": "sentiment",
        "name": "市場心理與情緒",
        "name_en": "Market Sentiment",
        "description": """評估市場心理與情緒，包含：
【恐慌指數】VIX指數反映的市場波動預期與焦慮程度
【市場共識】分析師評級（買入/賣出）、新聞媒體輿論導向
【羊群效應】熱門議題（AI、電動車等）的資金流向，是否存在泡沫或恐慌性拋售"""
    },
    {
        "id": "political",
        "name": "政治政策與外部衝擊",
        "name_en": "Political & External",
        "description": """評估政治、政策與外部衝擊，包含：
【地緣政治】戰爭、貿易制裁、區域局勢緊張（如晶片限制政策）
【政府監管】針對特定產業的法律法規（反壟斷法、碳稅政策）
【黑天鵝事件】意料之外的突發事件（疫情、天然災害等）"""
    }
]

# ===== 排程設定 =====
REALTIME_INTERVAL_SECONDS = 60       # 每分鐘執行一次即時分析
VALUATION_HOUR_TW = 5               # 台灣時間早上5點做深度估值
VALUATION_MINUTE_TW = 0

# ===== Dashboard 設定 =====
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8080

# ===== 資料儲存 =====
# 使用本地路徑存放 SQLite（掛載目錄不支援 SQLite 的鎖定機制）
DATA_DIR = os.path.join(os.path.expanduser("~"), ".stock_valuation_data")
DB_PATH = os.path.join(DATA_DIR, "stock_valuation.db")

# ===== 資料保留天數 =====
DATA_RETENTION_DAYS = 14
