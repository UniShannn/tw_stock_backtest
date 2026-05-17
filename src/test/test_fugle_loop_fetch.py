import time
from datetime import datetime
from fugle_marketdata import RestClient

import config

# 1. 初始化富果 API (請填入您在富果註冊取得的 API Key)
# 富果 API KEY：https://developer.fugle.tw/docs/key/ion
# 看盤網址：https://www.fugle.tw/marketdata/api-doc#section/Authentication
client = RestClient(api_key=config.FUGLE_API_KEY)

# 2. 設定您的 20 檔股票清單 (此處以幾檔權值股為例，請自行補齊至20檔)
target_stocks = [
    "2330", "2303", "2454", "2317", "2881", 
    "2882", "1301", "1303", "2002", "2412",
    "2891", "2886", "2884", "1216", "2308",
    "2885", "3231", "2382", "2356", "2324"
]

print("🚀 開始執行：每 10 秒抓取一檔股票即時報價...")

# 3. 建立無窮迴圈，讓程式不斷運行
try:
    while True:
        # 遍歷這 20 檔股票
        for stock_id in target_stocks:
            try:
                # 取得當下時間
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 呼叫富果 API 取得該檔股票的「即時報價 (Quote)」
                # 注意：盤後或假日測試時，會回傳最後一個交易日的最終報價
                quote_data = client.stock.intraday.quote(symbol=stock_id)
                
                # 從回傳的資料中提取最新成交價 (若剛開盤無成交價，可抓參考價)
                # 富果 API v1.0 回傳結構中，最新價格通常位於 quote_data['lastPrice'] 或是 'lastTrade' 裡面
                # 這裡為了保證您能看到所有資訊，我們先印出完整或部分關鍵資料
                last_price = quote_data.get('lastPrice', '無最新價格')
                
                print(f"[{now}] 股票代號: {stock_id} | 最新股價: {last_price}")
                
            except Exception as e:
                print(f"[{now}] 抓取 {stock_id} 失敗，錯誤訊息: {e}")
            
            # 4. 關鍵：每抓完一檔，讓程式暫停 10 秒
            time.sleep(10)
            
except KeyboardInterrupt:
    # 讓您在終端機按下 Ctrl+C 時，可以優雅地關閉程式
    print("\n🛑 接收到中斷指令，程式已停止執行。")