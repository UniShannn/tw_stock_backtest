import yfinance as yf
import pandas as pd
import os
import config

def fetch_and_save_data():
    # 確保 raw 資料夾存在
    os.makedirs(config.RAW_DIR, exist_ok=True)

    # 使用 for 迴圈，依序抓取 config 裡面設定的每一檔股票
    for stock_id in config.TARGET_STOCKS:
        print(f"開始抓取 {stock_id} 從 {config.START_DATE} 到 {config.END_DATE} 的資料...")
        
        # 抓取資料
        df = yf.download(stock_id, start=config.START_DATE, end=config.END_DATE, auto_adjust=True)
        
        # 檢查是否有抓到資料 (避免輸入錯誤代號導致程式崩潰)
        if df.empty:
            print(f"⚠️ 警告: 找不到 {stock_id} 的資料，請檢查代號或日期區間。\n")
            continue

        # 攤平多層次欄位 (MultiIndex) 修正，確保 pandas 之後能正確讀取
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 儲存成 CSV，檔名會自動帶入股票代號 (例如: raw_data_2330_TW.csv)
        safe_stock_id = stock_id.replace('.', '_') # 把 .TW 換成 _TW 避免檔名問題
        file_path = os.path.join(config.RAW_DIR, f"raw_data_{safe_stock_id}.csv")
        
        df.to_csv(file_path)
        print(f"✅ {stock_id} 資料已成功儲存至 {file_path}\n")

if __name__ == "__main__":
    fetch_and_save_data()