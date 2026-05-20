import pandas as pd
import os
import glob
import numpy as np
import config
from datetime import datetime


def categorize_return(pct):
    """將漲跌幅連續數值轉換為等級"""
    if pd.isna(pct): return '00.未知'
    if pct > 10: return '01.>10%'
    elif pct >= 8: return '02.8~10%'
    elif pct >= 6: return '03.6~8%'
    elif pct >= 4: return '04.4~6%'
    elif pct >= 2: return '05.2~4%' 
    elif pct > 0: return '06.0~2%'
    elif pct == 0: return '07.0%'
    elif pct >= -2: return '08.-2~0%'
    elif pct >= -4: return '09.-4~-2%'
    elif pct >= -6: return '10.-6~-4%'
    elif pct >= -8: return '11.-8~-6%'
    elif pct > -10: return '12.-10~-8%'
    else: return '13.<-10%'

def categorize_amplitude(amp):
    """將振幅連續數值轉換為等級"""
    if pd.isna(amp): return '0.未知'
    if amp >= 15: return '4.>15%'
    elif amp >= 10: return '3.10~15%'
    elif amp >= 5: return '2.5~10%'
    else: return '1.<5%'

def 當日K線型態_未來5日勝率計算(file_name="勝率統計",
                    與昨日成交量相比="無條件", # "量增"(包含等於) 或 "量減"
                    與成交量均線相比="無條件",  # "量增"(包含等於) 或 "量減"
                    成交量倍數條件=1.0, # 例如 1.5 表示成交量要大於均量的 1.5 倍才算符合條件
                    ):
    
    """
    1.file_name 命名格式建議:
    預設 = "勝率統計"，會自動加上日期時間戳記，例如 "勝率統計_0615_1530.csv"
    格式 = "條件(量增/量減等)_命題_統計範圍及時間範圍(全市場/半導體業等)_統計當下的日期時間"
    例如 "成交量量增1.5倍均線_單日K線型態_近5日勝率_全市場2020_2026_0615_1530.csv"
    2.參數說明: K線型態、漲跌幅等級、震幅等級
    3.變數說明: 
        Volume_Rising=True表示量增,False表示量減
        Volume_MA=5表示用5日均量
        Volume_MULTIPLIER=1.0表示成交量要大於(或小於)均量的多少倍才算符合條件
    """
    # 確保輸出報表資料夾存在
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    
    # 尋找所有已經處理好的 CSV 檔案
    # 若您只想測試一兩檔，可以改寫為讀取特定檔案
    csv_files = glob.glob(os.path.join(config.PROCESSED_DIR, "ma_data_*.csv"))
    if not csv_files:
        print(f"⚠️ 找不到任何檔案在 {config.PROCESSED_DIR}，請確認路徑或先執行指標計算。")
        return

    all_data = []
    
    print(f"開始載入與分析 {len(csv_files)} 檔股票資料...")
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            
            # 確保必要欄位存在
            required_cols = ['Close', 'K線型態(簡化)', '漲跌幅', '振幅']
            if not all(col in df.columns for col in required_cols):
                continue
                
            # 計算未來 1~5 日的收盤價
            for i in range(1, 6):
                # 使用 shift(-i) 來取得未來第 i 天的收盤價
                df[f'Close_T+{i}'] = df['Close'].shift(-i)
                # 定義勝率：未來第 N 天的收盤價 > 當天收盤價，即算成功上漲
                df[f'Win_T+{i}'] = (df[f'Close_T+{i}'] > df['Close']).astype(int)
                # 遇到 NaN 的地方將勝負標記為 NaN（因為未來資料還沒發生）
                df.loc[df[f'Close_T+{i}'].isna(), f'Win_T+{i}'] = np.nan
            
            # 加入漲跌幅與振幅的級別分類
            df['漲跌幅等級'] = df['漲跌幅'].apply(categorize_return)
            df['振幅等級'] = df['振幅'].apply(categorize_amplitude)
            
            # 只保留我們需要統計的欄位，節省記憶體
            keep_cols = ['K線型態(簡化)', '漲跌幅等級', '振幅等級'] + [f'Win_T+{i}' for i in range(1, 6)]
            all_data.append(df[keep_cols].dropna())
            
        except Exception as e:
            print(f"處理檔案 {file} 時發生錯誤: {e}")
            
    if not all_data:
        print("沒有足夠的資料可以分析。")
        return
        
    # 將全市場資料合併成一個超級大的 DataFrame
    final_df = pd.concat(all_data, ignore_index=True)
    
    # === 開始多因子統計 ===
    print("資料合併完成，正在計算各組合勝率...")
    # 根據「型態 + 漲跌幅 + 振幅」進行分組
    grouped = final_df.groupby(['K線型態(簡化)', '漲跌幅等級', '振幅等級'])
    
    stats_list = []
    # 依序計算每一組的勝率，並記錄出現次數
    for name, group in grouped:
        # name 是一個 tuple，包含 (K線型態, 漲跌幅等級, 振幅等級)
        # group 是該組的 DataFrame，可以用來計算勝率
        pattern, ret_class, amp_class = name
        # 這組的樣本數 (出現次數)
        count = len(group)
        
        # 建立這組特徵的統計資料字典
        row_data = {
            'K線型態': pattern,
            '漲跌幅等級': ret_class,
            '振幅等級': amp_class,
        }
        
        # !!! 計算的核心程式位置 !!!
        # 計算 1~5 日勝率
        for i in range(1, 6):

            ## 此處可大量擴充想篩選的條件
            # 加入一些條件篩選，例如只計算成交量大於均量 1.5 倍的情況下的勝率
            condition1 = group[f'Win_T+{i}'].notna()  # 確保未來第 i 天的勝負不是 NaN

            
            

            # 條件判斷：與昨日成交量相比
            條件_與昨日成交量相比 = pd.Series([False] * len(group), index=group.index)
            if 與昨日成交量相比 in ["量增", "量減"]:
                # 檢查是否有成交量資料
                if group['Volume'].notna().any():
                    prev_volume = group['Volume'].shift(1)
                    
                    if 與昨日成交量相比 == "量增":
                        條件_與昨日成交量相比 = group['Volume'] >= prev_volume * 成交量倍數條件
                    else: # 量減
                        條件_與昨日成交量相比 = group['Volume'] < prev_volume * 成交量倍數條件
                else:
                    print(f"⚠️ {group.name} 該股票成交量欄位為空，跳過成交量條件檢查。")
                    
            elif 與昨日成交量相比 != "無條件":
                # 若不是上述三種情況，才印出警告
                print(f"⚠️ 無效的參數: 與昨日成交量相比={與昨日成交量相比}，請使用 '量增'、'量減' 或 '無條件'")
            
            # 條件判斷: 與成交量均線相比
            條件_與成交量均線相比 = pd.Series([False] * len(group), index=group.index)
            條件_與成交量均線相比 = group['Volume'] > (group['Volume_MA5'] * 1.5)  # 例如成交量大於均量 1.5 倍
            
            valid_group = group[condition1 & condition2]
            
            # 計算未來第 i 天的勝率，乘以 100 轉為百分比
            win_rate = valid_group[f'Win_T+{i}'].mean() * 100
            row_data[f'T+{i}'] = round(win_rate, 2) # T+N 勝率，保留兩位小數
            
        row_data['出現次數'] = count # 加入出現次數(放在勝率右方欄位)，方便後續過濾

        stats_list.append(row_data)
        
    # 轉為 DataFrame
    stats_df = pd.DataFrame(stats_list)
    
    # 為了統計意義，過濾掉出現次數太少（例如小於30次）的罕見極端值
    min_occurrence = 30
    valid_stats_df = stats_df[stats_df['出現次數'] >= min_occurrence].copy()
    
    # 輸出成 CSV 報表
    date_format = "%m%d_%H%M"
    output_path = os.path.join(config.REPORT_DIR, f"{file_name}_{datetime.now().strftime(date_format)}.csv")
    valid_stats_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"📁 統計結果已成功儲存至: {output_path}\n")
    
    # === 印出 T+1 勝率最高的前 10 名 ===
    print(f"🏆 【隔日 (T+1) 勝率最高前 10 名組合】 (過濾條件: 出現次數 >= {min_occurrence}次)")
    print("-" * 85)
    top_10_t1 = valid_stats_df.sort_values(by='T+1', ascending=False).head(10)
    
    # 格式化輸出
    for idx, row in top_10_t1.iterrows():
        print(f"型態: {row['K線型態'][:12]:<12} | "
              f"漲跌: {row['漲跌幅等級']:<14} | "
              f"振幅: {row['振幅等級']:<12} => "
              f"勝率: {row['T+1']:>5.2f}% "
              f"(次數: {row['出現次數']})")


def 當日K線型態_未來5日勝率計算2(file_name="勝率統計",
                    與昨日成交量相比="無條件", # "量增"(包含等於) 或 "量減"
                    與成交量均線相比="無條件",  # "量增"(包含等於) 或 "量減"
                    成交量倍數條件=1.0, 
                    ):
    
    # 確保輸出報表資料夾存在
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    
    csv_files = glob.glob(os.path.join(config.PROCESSED_DIR, "ma_data_*.csv"))
    if not csv_files:
        print(f"⚠️ 找不到任何檔案在 {config.PROCESSED_DIR}，請確認路徑或先執行指標計算。")
        return

    all_data = []
    
    print(f"開始載入與分析 {len(csv_files)} 檔股票資料...")
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            
            # 確保必要欄位存在 (新增確保有 Volume 與 Volume_MA_5)
            required_cols = ['Close', 'Volume', 'K線型態(簡化)', '漲跌幅', '振幅']
            if not all(col in df.columns for col in required_cols):
                continue
                
            # 1. 確保時間序列正確 (可選，但建議加上避免亂序)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date')

            # 2. 計算未來 1~5 日的勝率結果
            for i in range(1, 6):
                df[f'Close_T+{i}'] = df['Close'].shift(-i)
                # 先轉為 float 以支援 NaN
                df[f'Win_T+{i}'] = (df[f'Close_T+{i}'] > df['Close']).astype(float) 
                df.loc[df[f'Close_T+{i}'].isna(), f'Win_T+{i}'] = np.nan
            
            # ==========================================
            # 3. 🎯 核心修正：在時間序列正確時，計算成交量條件
            # ==========================================
            is_valid_condition = pd.Series([True] * len(df), index=df.index)
            
            # (A) 與昨日成交量相比
            if 與昨日成交量相比 != "無條件":
                prev_volume = df['Volume'].shift(1)
                if 與昨日成交量相比 == "量增":
                    is_valid_condition &= (df['Volume'] >= prev_volume * 成交量倍數條件)
                elif 與昨日成交量相比 == "量減":
                    is_valid_condition &= (df['Volume'] < prev_volume * 成交量倍數條件)
            
            # (B) 與成交量均線相比
            if 與成交量均線相比 != "無條件":
                # 您的 CSV 欄位名稱應為 'Volume_MA_5' (有底線)
                if 'Volume_MA_5' in df.columns: 
                    if 與成交量均線相比 == "量增":
                        is_valid_condition &= (df['Volume'] >= df['Volume_MA_5'] * 成交量倍數條件)
                    elif 與成交量均線相比 == "量減":
                        is_valid_condition &= (df['Volume'] < df['Volume_MA_5'] * 成交量倍數條件)
                else:
                    print(f"⚠️ {file} 缺少 Volume_MA_5 欄位，略過該條件。")
            
            # 依據條件進行過濾，過濾掉不符合條件的日子
            df = df[is_valid_condition].copy()
            
            if df.empty: # 如果這檔股票過濾後沒資料了，就換下一檔
                continue

            # 4. 加入漲跌幅與振幅的級別分類
            df['漲跌幅等級'] = df['漲跌幅'].apply(categorize_return)
            df['振幅等級'] = df['振幅'].apply(categorize_amplitude)
            
            # 只保留需要統計的欄位
            keep_cols = ['K線型態(簡化)', '漲跌幅等級', '振幅等級'] + [f'Win_T+{i}' for i in range(1, 6)]
            all_data.append(df[keep_cols])
            
        except Exception as e:
            print(f"處理檔案 {file} 時發生錯誤: {e}")
            
    if not all_data:
        print("沒有足夠的資料可以分析。可能是條件設太嚴格！")
        return
        
    final_df = pd.concat(all_data, ignore_index=True)
    
    # ==========================================
    # 5. 執行群組勝率統計
    # ==========================================
    print("資料合併完成，正在計算各組合勝率...")
    grouped = final_df.groupby(['K線型態(簡化)', '漲跌幅等級', '振幅等級'])
    
    stats_list = []
    for name, group in grouped:
        pattern, ret_class, amp_class = name
        count = len(group)
        
        row_data = {
            'K線型態': pattern,
            '漲跌幅等級': ret_class,
            '振幅等級': amp_class,
        }
        
        # 計算 1~5 日勝率
        for i in range(1, 6):
            # 剔除尚未發生的未來日(NaN)，確保勝率計算的分母是正確的
            valid_wins = group[f'Win_T+{i}'].dropna()
            
            if len(valid_wins) > 0:
                win_rate = valid_wins.mean() * 100
                row_data[f'T+{i}'] = round(win_rate, 2)
            else:
                row_data[f'T+{i}'] = np.nan
        
        # 擺在機率行col最右邊
        row_data['出現次數'] = count


        stats_list.append(row_data)
        
    # 轉為 DataFrame
    stats_df = pd.DataFrame(stats_list)
    
    # 依照出現次數排序 (排除極端罕見的情況)
    stats_df = stats_df.sort_values(by='出現次數', ascending=False)
    
    # ==========================================
    # 6. 自動輸出 CSV 報表
    # ==========================================
    timestamp = datetime.now().strftime("%m%d_%H%M")
    final_filename = f"{file_name}_{timestamp}.csv"
    output_path = os.path.join(config.REPORT_DIR, final_filename)
    
    stats_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 勝率統計已完成！共產出 {len(stats_df)} 組型態組合。")
    print(f"📁 檔案已儲存至: {output_path}")
    
    return stats_df



if __name__ == "__main__":
    category = "_" + "全市場"  # 可以改成 "上市半導體業" 或其他您想分析的類別
    date_range = "_" + "2020_2026"  # 可以改成您想分析的時間範圍，例如 "2010_2020"
    volume_condition = [
        "與昨日成交量相比",
        "與成交量均線相比"
    ]
    volume_condition_variable = [
        "無條件",
        "量增2.0倍",
        "量減0.5倍"
    ]

    condition = volume_condition[1] + volume_condition_variable[1]
    

    file_name = "當日K線型態_未來5日勝率_"+ condition  + category + date_range

    當日K線型態_未來5日勝率計算2(file_name,與成交量均線相比= "量增",成交量倍數條件=2.0)