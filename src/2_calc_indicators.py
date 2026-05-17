import pandas as pd
import os

# 引入我們的設定檔
import config

def calculate_indicators():
    # 確保儲存處理後資料的資料夾存在
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    
    # 使用 for 迴圈，依序處理 config 裡面設定的每一檔股票
    for stock_id in config.TARGET_STOCKS:
        
        # 取得原始檔案路徑
        safe_stock_id = stock_id.replace('.', '_')
        raw_filename = f"raw_data_{safe_stock_id}.csv"
        raw_filepath = os.path.join(config.RAW_DIR, raw_filename)
        
        # 檢查檔案是否存在
        if not os.path.exists(raw_filepath):
            print(f"⚠️ 找不到原始資料檔：{raw_filepath}，請先確認是否已執行 1_fetch_data.py 抓取該股票")
            continue # 找不到就跳過這檔股票，繼續處理下一檔
            
        print(f"開始計算 {stock_id} 的技術指標...")
        
        # 讀取 CSV，並將 Date 設為索引(Index)，這對時間序列計算很重要
        df = pd.read_csv(raw_filepath, index_col='Date', parse_dates=True)
        
        # ==========================================
        # 計算收盤價的移動平均線 (MA)
        # ==========================================
        df['MA_5'] = df['Close'].rolling(window=5).mean()
        df['MA_10'] = df['Close'].rolling(window=10).mean()
        df['MA_20'] = df['Close'].rolling(window=20).mean()
        
        # 計算成交量的移動平均線
        df['Vol_MA_5'] = df['Volume'].rolling(window=5).mean()
        df['Vol_MA_20'] = df['Volume'].rolling(window=20).mean()
        
        # 儲存到 processed 資料夾
        processed_filename = f"ma_data_{safe_stock_id}.csv"
        processed_filepath = os.path.join(config.PROCESSED_DIR, processed_filename)
        
        # 存檔
        df.to_csv(processed_filepath)
        print(f"✅ {stock_id} 指標計算完成，已儲存至：{processed_filepath}\n")

if __name__ == "__main__":
    calculate_indicators()