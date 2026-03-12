# 📊 Stock Valuation Dashboard - 股票估值分析系統

這是一個基於 **MiniMax AI** 的自動化股票市場分析與估值系統。它結合了即時新聞爬蟲、多維度 AI 指標分析以及現代化的 Glassmorphism 網頁介面。

![Dashboard Preview](https://github.com/lin-r0987765/jin10/raw/main/screenshots/preview.png) *(註：需要手動截圖並放置於 screenshots 資料夾)*

## 🌟 核心特色

- **多維度即時分析**：每分鐘輪替分析量化四大面向（基本面、技術面、情緒面、政策面）。
- **AI 穩定性優化**：分析時會參考近期歷史分數，確保指標連續性，避免大幅波動。
- **美觀視覺化**：採用現代玻璃擬物化 (Glassmorphism) 設計，動態 Glow 背景與流暢動畫。
- **平行趨勢圖**：修正了多維度資料的時間軸對齊問題，確保四條指標線精確並行。
- **安全性設計**：API Key 透過環境變數管理，符合開源安全性規範。
- **自動清理機制**：自動清理 14 天前的舊資料，保持資料庫輕巧。

## 📂 專案結構

```text
├── main.py              # 程式主入口
├── dashboard.py         # Flask Web Server 與 API 端點
├── analyzer.py          # AI 分析引擎（處理 prompt 與 AI 對接）
├── scraper.py           # 市場快訊爬蟲（金十數據、Yahoo 國際新聞）
├── minimax_client.py    # MiniMax API 通訊封裝
├── data_store.py        # SQLite 資料庫操作與資料清理
├── scheduler.py         # APScheduler 任務排程管理
├── config.py            # 系統全域配置（分析標的、排程間隔、資料保留等）
├── templates/
│   └── dashboard.html   # 主網頁介面（HTML/CSS/JS/Chart.js）
├── requirements.txt     # Python 依賴清單
├── .env.example         # 環境變數範例檔
└── .env                 # (自建) 存放 API Key 等敏感資訊
```

## 🚀 快速啟動

### 1. 安裝環境
確保您的系統已安裝 Python 3.8+，然後安裝必要套件：
```bash
pip install -r requirements.txt
```

### 2. 設定 API Key
將 `.env.example` 複製並命名為 `.env`，填入您的 MiniMax API Key：
```bash
cp .env.example .env
```

### 3. 啟動系統
使用以下指令啟動：
```bash
# 方法一: 直接執行主程式
python main.py

# 方法二: Windows 使用者
start.bat
```

啟動後訪問：`http://localhost:8080`

## ⏰ 自動任務排程

- **即時市場分析**：每 60 秒執行一次，四個面向循環切換。
- **深度股票估值**：每天台灣時間 05:00 對觀察清單（QQQ, NVDA, TSLA 等）執行。
- **資料庫清理**：每天凌晨 04:00 自動清理 14 天前的歷史資料。

## 🛠 技術棧

- **Backend**: Python, Flask, APScheduler, SQLite3
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism), Chart.js
- **AI**: MiniMax-M2.5 (LLM API)

## ⚠️ 注意事項

- 本系統數據僅供參考，不構成任何投資建議。
- 資料預設存放在使用者目錄下的 `.stock_valuation_data/` 內（含資料庫與日誌）。
- 若需調整分析頻率或標的，請修改 `config.py`。
