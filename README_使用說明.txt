========================================
  股票估值分析系統 - 使用說明
========================================

【啟動方式】
  方法一: 雙擊 start.bat（Windows）
  方法二: 在終端執行 python main.py

【Dashboard 網址】
  http://localhost:8080

【系統流程】
  1. 每60秒自動爬取金十數據 + Yahoo國際新聞
  2. 將新聞傳給 MiniMax M2.5 做四面向輪替評分
     - 第1分鐘: 基本面
     - 第2分鐘: 技術面
     - 第3分鐘: 市場心理與情緒
     - 第4分鐘: 政治政策與外部衝擊
     - 第5分鐘: 回到基本面...循環
  3. 每天台灣時間 05:00 對 QQQ, GOOG, MSFT, NVDA, TSLA 做深度估值
  4. 所有結果自動更新至 Dashboard

【手動觸發】
  Dashboard 上方有按鈕可手動觸發即時分析或股票估值

【專案結構】
  config.py          - 設定檔（API Key、模型、排程等）
  scraper.py         - 爬蟲模組（金十、Yahoo）
  minimax_client.py  - MiniMax API 客戶端
  analyzer.py        - 分析引擎（四面向 + 股票估值）
  scheduler.py       - 排程管理
  dashboard.py       - Dashboard 後端 API
  main.py            - 主程式入口
  templates/         - Dashboard 前端頁面
  data/              - SQLite 資料庫（自動建立於使用者目錄下）

【依賴安裝】
  pip install -r requirements.txt

【注意事項】
  - MiniMax-M2.5-highspeed 需要升級方案才可使用，目前統一用 MiniMax-M2.5
  - SQLite 資料庫存放在 ~/.stock_valuation_data/ 目錄下
  - 系統日誌同樣在該目錄的 system.log
  - Dashboard 預設監聽 0.0.0.0:8080，內網可直接訪問
