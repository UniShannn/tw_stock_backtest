# 我想要找出漲超過10%的股票，確認是否為資料問題 還是該檔股票是沒有漲跌幅限制
import os
import pandas as pd
import path
import config

def find_abnormal_returns():
    print("🔍 開始掃描 processed 資料夾中的異常漲跌幅...")
    abnormal_records = []
    
    # 確保 processed 資料夾存在
    if not os.path.exists(config.PROCESSED_DIR):
        print(f"找不到資料夾: {config.PROCESSED_DIR}")
        return

    # 遍歷所有已經計算好指標的 CSV 檔案
    for filename in os.listdir(config.PROCESSED_DIR):
        if not filename.endswith('.csv'):
            continue
            
        filepath = os.path.join(config.PROCESSED_DIR, filename)
        try:
            df = pd.read_csv(filepath)
            
            # 確保有 Date 與 Close 欄位
            if 'Date' not in df.columns or 'Close' not in df.columns:
                continue
                
            # 即時計算每日實際漲跌幅 (避免讀取到未轉型的欄位)
            # pct_change() 會計算 (今天收盤 - 昨天收盤) / 昨天收盤
            df['Daily_Return'] = df['Close'].pct_change()
            
            # 抓出 漲幅大於 10.5% 或 跌幅大於 10.5% 的資料
            # (設定 10.5% 是為了避開 9.99% 四捨五入的問題)
            abnormal_df = df[abs(df['Daily_Return']) > 0.105].copy()
            
            if not abnormal_df.empty:
                # 提取股票代號 (例如從 ma_data_2330_TW.csv 提取出 2330_TW)
                stock_id = filename.replace('ma_data_', '').replace('.csv', '')
                abnormal_df['Stock_ID'] = stock_id
                
                # 將計算結果轉為百分比方便閱讀
                abnormal_df['Daily_Return_Pct'] = (abnormal_df['Daily_Return'] * 100).round(2)
                
                # 只保留我們需要檢查的欄位
                abnormal_records.append(abnormal_df[['Stock_ID', 'Date', 'Close', 'Daily_Return_Pct']])
                
        except Exception as e:
            print(f"讀取 {filename} 時發生錯誤: {e}")

    # 將所有異常紀錄合併並輸出
    if abnormal_records:
        final_df = pd.concat(abnormal_records)
        
        # 依照日期排序，方便您對照當時的新聞
        final_df = final_df.sort_values(by=['Stock_ID', 'Date'])
        
        # 儲存到 report 或 data 資料夾
        output_path = os.path.join(config.BASE_DIR, 'data', 'abnormal_returns_report.csv')
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"🚨 掃描完畢！共找到 {len(final_df)} 筆超過 ±10% 的異常資料。")
        print(f"📁 異常報告已儲存至: {output_path}")
        print("💡 建議：打開 CSV 後，可以去 Yahoo 股市或公開資訊觀測站，對照該股票在該日是否有「減資」或「新上市」。")
    else:
        print("✅ 掃描完畢！資料非常乾淨，沒有發現任何超過 10% 的異常漲跌幅。")

if __name__ == '__main__':
    find_abnormal_returns()
