import os
import glob
import pandas as pd
import numpy as np

# 嘗試載入 config，若無設定檔則使用相對路徑
try:
    import config
    PROCESSED_DIR = config.PROCESSED_DIR
    BASE_DIR = config.BASE_DIR
except ImportError:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# 設定報表輸出的資料夾
REPORT_DIR = os.path.join(BASE_DIR, "data", "report")
os.makedirs(REPORT_DIR, exist_ok=True)

# 當日k線型態 + 漲幅等級 對未來5天漲幅的勝率統計
def run_multi_factor_analysis_v1():
    print("🚀 開始執行全市場多因子勝率統計 (條件：爆量 + K線型態 + 漲幅等級)...")
    
    # 取得所有 processed 資料夾下的 csv 檔案
    csv_files = glob.glob(os.path.join(PROCESSED_DIR, "ma_data_*.csv"))
    
    if not csv_files:
        print(f"⚠️ 在 {PROCESSED_DIR} 找不到任何處理過的 CSV 檔案。")
        return

    all_market_data = []

    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
            
            # 檢查必備欄位是否存在
            required_cols = ['Close', 'Volume', 'Volume_MA_5', 'K線型態', '漲跌幅等級']
            if not all(col in df.columns for col in required_cols):
                continue  # 缺少必要欄位就跳過這檔股票
                
            # 1. 建立「未來 1~5 天」的收盤價
            for i in range(1, 6):
                df[f'Close_T{i}'] = df['Close'].shift(-i)
                # 判斷是否上漲 (大於當天收盤價為 True (1)，否則為 False (0))
                # 注意：如果未來股價是 NaN (例如最新幾天)，計算結果保留為 NaN
                df[f'Up_T{i}'] = np.where(df[f'Close_T{i}'].isna(), np.nan, 
                                          (df[f'Close_T{i}'] > df['Close']).astype(int))

            # 2. 條件過濾：只挑選「當日成交量 > 當日5日均量」的爆量/量增狀態
            condition_vol = df['Volume'] > df['Volume_MA_5']
            df_filtered = df[condition_vol].copy()
            
            # 排除沒有計算出K線型態或漲跌幅的極端情況
            df_filtered = df_filtered.dropna(subset=['K線型態', '漲跌幅等級'])
            
            # 3. 建立分組組合名稱 (縱軸：K線型態_等級)
            df_filtered['組合名稱'] = df_filtered['K線型態'].astype(str) + "_等級" + df_filtered['漲跌幅等級'].astype(str)
            
            # 提取需要的欄位加入大集合
            cols_to_keep = ['組合名稱'] + [f'Up_T{i}' for i in range(1, 6)]
            all_market_data.append(df_filtered[cols_to_keep])
            
        except Exception as e:
            print(f"處理檔案 {os.path.basename(filepath)} 時發生錯誤: {e}")

    # 合併全市場所有符合條件的訊號
    if not all_market_data:
        print("沒有符合條件的資料可以統計。")
        return
        
    master_df = pd.concat(all_market_data, ignore_index=True)
    print(f"✅ 全市場資料讀取完畢，共掃描出 {len(master_df)} 筆「量增」的 K 線訊號。")
    
    # 4. 分組統計機率與次數
    stats_list = []
    grouped = master_df.groupby('組合名稱')
    
    for factor, group in grouped:
        row_data = {'組合名稱': factor}
        
        # 計算 T+1 到 T+5
        for i in range(1, 6):
            col_name = f'Up_T{i}'
            valid_cases = group[col_name].dropna() # 排除沒有未來股價的 NaN
            
            occurrences = len(valid_cases)
            if occurrences > 0:
                win_rate = (valid_cases.sum() / occurrences) * 100
            else:
                win_rate = 0.0
                
            row_data[f'隔{i}日上漲(%)'] = round(win_rate, 2)
            row_data[f'次數{i}'] = occurrences
            
        stats_list.append(row_data)

    # 轉成 DataFrame 並設定 Index
    stats_df = pd.DataFrame(stats_list).set_index('組合名稱')
    
    # 5. 輸出成全新的 CSV
    output_path = os.path.join(REPORT_DIR, "multi_factor_win_rate_stats_v1.csv")
    stats_df.to_csv(output_path, encoding='utf-8-sig')
    print(f"📁 統計結果已成功儲存至: {output_path}\n")
    
    # ================= 終端機列印最高機率前 5 名 =================
    print("🏆 【全市場】量增狀態下，隔日上漲勝率最高的前 5 名型態：")
    print("(為確保統計意義，已自動過濾掉出現次數少於 10 次的罕見極端值)")
    print("-" * 65)
    
    # 過濾出「隔1日出現次數」大於等於 10 的資料，避免極少數的 100% 霸



# ====== 新增：漲幅等級轉換文字函式 ======
def convert_level_to_str(level):
    """
    將數字等級轉換為好讀的百分比區間。
    漲幅幅度分成5個等級
    (10%>=幅度>8%:5, 8%>=幅度>6%:4, 6%>=幅度>4%:3, 4%>=幅度>2%:2, 2%>=幅度>0%:1)
      ,反之,跌幅也分成5個等級
    (0%>=幅度>-2%:-1, -2%>=幅度>-4%:-2, -4%>=幅度>-6%:-3, -6%>=幅度>-8%:-4, -8%>=幅度>-10%:-5)
    持平:0
    """
    try:
        lvl = int(level)
        if lvl == 6:
            return "+10%以上"
        elif lvl == -6:
            return "-10%以上"
        elif lvl == 5:
            return "+8% ~ +10%"
        elif lvl == -5:
            return "-8% ~ -10%"
        elif lvl == 0:    
            return "平盤"
        elif lvl > 0:
            return f"+{lvl*2-2}% ~ +{lvl*2}%"
        else:
            return f"-{abs(lvl)*2-2}% ~ -{abs(lvl)*2}%"
    except:
        return str(level)
# ========================================

def run_multi_factor_analysis_v2(Volume_MULTIPLIER=1.0):
    print("🚀 開始執行全市場多因子勝率統計 (條件：爆量 + K線型態 + 漲幅等級)...")
    
    # 取得所有 processed 資料夾下的 csv 檔案
    csv_files = glob.glob(os.path.join(PROCESSED_DIR, "ma_data_*.csv"))
    
    if not csv_files:
        print(f"⚠️ 在 {PROCESSED_DIR} 找不到任何處理過的 CSV 檔案。")
        return

    all_market_data = []

    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
            
            # 檢查必備欄位是否存在
            required_cols = ['Close', 'Volume', 'Volume_MA_5', 'K線型態', '漲跌幅等級']
            if not all(col in df.columns for col in required_cols):
                continue  # 缺少必要欄位就跳過這檔股票
                
            # 1. 建立「未來 1~5 天」的收盤價
            for i in range(1, 6):
                df[f'Close_T{i}'] = df['Close'].shift(-i)
                # 判斷是否上漲
                df[f'Up_T{i}'] = np.where(df[f'Close_T{i}'].isna(), np.nan, 
                                          (df[f'Close_T{i}'] > df['Close']).astype(int))

            # 2. 條件過濾：只挑選「當日成交量 > 當日5日均量」的爆量/量增狀態
            condition_vol = df['Volume'] > df['Volume_MA_5'] * Volume_MULTIPLIER
            df_filtered = df[condition_vol].copy()
            
            # 排除沒有計算出K線型態或漲跌幅的極端情況
            df_filtered = df_filtered.dropna(subset=['K線型態', '漲跌幅等級'])
            
            # 3. 提取需要的欄位加入大集合 (保留獨立的兩欄，不再結合成單一字串)
            cols_to_keep = ['K線型態', '漲跌幅等級'] + [f'Up_T{i}' for i in range(1, 6)]
            all_market_data.append(df_filtered[cols_to_keep])
            
        except Exception as e:
            print(f"處理檔案 {os.path.basename(filepath)} 時發生錯誤: {e}")

    # 合併全市場所有符合條件的訊號
    if not all_market_data:
        print("沒有符合條件的資料可以統計。")
        return
        
    master_df = pd.concat(all_market_data, ignore_index=True)
    print(f"✅ 全市場資料讀取完畢，共掃描出 {len(master_df)} 筆「量增」的 K 線訊號。")
    
    # 4. 分組統計機率與次數 (直接用這兩欄做群組)
    stats_list = []
    grouped = master_df.groupby(['K線型態', '漲跌幅等級'])
    
    for (pattern, level), group in grouped:
        # 將等級轉換為人類好讀的區間文字
        level_str = convert_level_to_str(level)
        
        row_data = {
            'K線型態': pattern,
            '漲幅區間': level_str
        }
        
        # 計算 T+1 到 T+5
        for i in range(1, 6):
            col_name = f'Up_T{i}'
            valid_cases = group[col_name].dropna() # 排除沒有未來股價的 NaN
            
            occurrences = len(valid_cases)
            if occurrences > 0:
                win_rate = (valid_cases.sum() / occurrences) * 100
            else:
                win_rate = 0.0
                
            row_data[f'隔{i}日上漲(%)'] = round(win_rate, 2)
            row_data[f'次數({i})'] = occurrences
            
        stats_list.append(row_data)

    # 轉成 DataFrame 並設定雙重索引 (MultiIndex) 是合併儲存格的魔法關鍵！
    stats_df = pd.DataFrame(stats_list)
    stats_df.set_index(['K線型態', '漲幅區間'], inplace=True)
    
    # 5. 輸出結果
    # 輸出 CSV (供程式讀取用)
    csv_path = os.path.join(REPORT_DIR, "multi_factor_win_rate_stats_v2.csv")
    stats_df.to_csv(csv_path, encoding='utf-8-sig')
    
    # 輸出 Excel (供人類閱讀，會自動合併儲存格)
    excel_path = os.path.join(REPORT_DIR, "multi_factor_win_rate_stats_v2.xlsx")
    try:
        stats_df.to_excel(excel_path)
        print(f"📁 統計結果已成功儲存至:\n - CSV: {csv_path}\n - EXCEL (已合併儲存格): {excel_path}\n")
    except ModuleNotFoundError:
        print(f"📁 統計結果已成功儲存至 CSV。")
        print(f"💡 提示: 若要在終端機輸出自動合併儲存格的 Excel，請先執行 `pip install openpyxl`。")

    # ================= 終端機列印最高機率前 5 名 =================
    print("🏆 【全市場】量增狀態下，隔日上漲勝率最高的前 5 名型態：")
    print("(為確保統計意義，已自動過濾掉出現次數少於 10 次的罕見極端值)")
    print("-" * 65)

if __name__ == "__main__":
    #run_multi_factor_analysis()
    run_multi_factor_analysis_v2(1.5)
