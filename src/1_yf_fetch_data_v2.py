# 檔案說明：從 Yahoo Finance 批次下載全市場股票的歷史資料，並儲存為 CSV 檔

import yfinance as yf
import pandas as pd
import os
import config
import time
import random

def fetch_and_save_data_batched():
    # 確保 raw 資料夾存在
    os.makedirs(config.RAW_DIR, exist_ok=True)

    stocks = config.TARGET_STOCKS
    
    # 【防呆機制】檢查股票清單是否為空
    if not stocks or len(stocks) == 0:
        print("❌ 錯誤：config.TARGET_STOCKS 裡面沒有任何股票代號！")
        print(f"請先檢查你的全市場 metadata 檔案是否存在，或檢查 src/config.py 是否正確載入。")
        return

    # 設定每批下載的股票數量 (建議 30 ~ 50 檔，既安全又快速)
    chunk_size = 40 
    
    print(f"📊 全市場共 {len(stocks)} 檔股票，將以每批 {chunk_size} 檔進行批次下載...")

    # 分批次進行迴圈
    for i in range(0, len(stocks), chunk_size):
        chunk = stocks[i : i + chunk_size]
        
        # 【優化 1：斷點續傳過濾】先排除掉這一批裡面已經下載過的股票
        chunk_to_download = []
        for stock_id in chunk:
            # 統一使用底線 _ 作為檔名規則，避免空格帶來的潛在 Bug
            safe_stock_id = stock_id.replace('.', '_')
            file_path = os.path.join(config.RAW_DIR, f"raw_data_{safe_stock_id}.csv")
            if not os.path.exists(file_path):
                chunk_to_download.append(stock_id)
            else:
                print(f"ℹ️ {stock_id} 資料已存在，跳過。")
                
        # 如果這一批股票都已經下載過了，直接跳下一批
        if not chunk_to_download:
            continue
            
        current_batch = (i // chunk_size) + 1
        total_batches = (len(stocks) + chunk_size - 1) // chunk_size
        print(f"🚀 [批次 {current_batch}/{total_batches}] 開始下載 {len(chunk_to_download)} 檔股票的資料...")
        
        try:
            # 一次性下載整批股票，並設定 group_by='ticker' 讓資料按股票代號分組
            df_all = yf.download(
                chunk_to_download, 
                start=config.START_DATE, 
                end=config.END_DATE, 
                auto_adjust=True, 
                group_by='ticker',
                progress=False # 關閉 yfinance 預設進度條，讓日誌更乾淨
            )
            
            if df_all.empty:
                print(f"⚠️ 批次 {current_batch} 下載回傳空資料。\n")
                continue
                
            # 【優化 2：動態解析與儲存】
            if isinstance(df_all.columns, pd.MultiIndex):
                # 取得這批實際下載成功的股票清單 (位於 MultiIndex 的第 0 層)
                downloaded_tickers = df_all.columns.get_level_values(0).unique()
                
                for stock_id in chunk_to_download:
                    if stock_id in downloaded_tickers:
                        # 提取該個股的 DataFrame
                        df_stock = df_all[stock_id]
                        
                        # 剔除全空的日期行
                        df_stock = df_stock.dropna(how='all')
                        
                        if df_stock.empty:
                            continue
                            
                        safe_stock_id = stock_id.replace('.', '_')
                        file_path = os.path.join(config.RAW_DIR, f"raw_data_{safe_stock_id}.csv")
                        df_stock.to_csv(file_path)
                        print(f"   ✅ {stock_id} 資料已儲存")
                    else:
                        print(f"   ❌ Yahoo 未回傳 {stock_id} 的資料")
            else:
                # 防呆機制：如果清單只剩一檔股票，yfinance 有時會退化成單層欄位的 DataFrame
                if len(chunk_to_download) == 1:
                    stock_id = chunk_to_download[0]
                    df_all = df_all.dropna(how='all')
                    if not df_all.empty:
                        safe_stock_id = stock_id.replace('.', '_')
                        file_path = os.path.join(config.RAW_DIR, f"raw_data_{safe_stock_id}.csv")
                        df_all.to_csv(file_path)
                        print(f"   ✅ {stock_id} 資料已儲存")

            print(f"✨ 批次 {current_batch} 處理完成！")
            
            # 【優化 3：批次間隨機延遲】
            sleep_time = random.uniform(3.0, 5.0)
            print(f"☕ 休息 {sleep_time:.1f} 秒，防止頻率過高...\n")
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"💥 批次 {current_batch} 發生未預期錯誤: {e}")
            print("安全機制啟動：休息 15 秒後自動嘗試下一批...\n")
            time.sleep(15)

if __name__ == "__main__":
    fetch_and_save_data_batched()