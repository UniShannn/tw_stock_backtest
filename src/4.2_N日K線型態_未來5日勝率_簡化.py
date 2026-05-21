import pandas as pd
import os
import glob
from datetime import datetime
import numpy as np

# 假設您有 config 檔案，若無可直接在這裡替換路徑
try:
    import config
    PROCESSED_DIR = config.PROCESSED_DIR
    REPORT_DIR = config.REPORT_DIR
except ImportError:
    PROCESSED_DIR = "../data/processed"
    REPORT_DIR = "../data/report"


def categorize_return(pct,window=1):
    """將漲跌幅連續數值轉換為等級 (沿用您先前的標準)"""
    if window == 1 : #單日
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
    elif window == 3: #3日
        if pd.isna(pct): return '00.未知'
        if pct > 30: return '01.>30%'
        elif pct >= 25: return '02.25~30%'
        elif pct >= 20: return '03.20~25%'
        elif pct >= 15: return '04.15~20%'
        elif pct >= 10: return '05.10~15%'
        elif pct > 5: return '06.5~10%'
        elif pct > 0: return '07.0~5%'
        elif pct == 0: return '08.0%'
        elif pct >= -5: return '09.-5~0%'
        elif pct >= -10: return '10.-10~-5%'
        elif pct >= -15: return '11.-15~-10%'
        elif pct >= -20: return '12.-20~-15%'
        elif pct >= -25: return '13.-25~-20%'
        elif pct >= -30: return '14.-30~-25%'
        else: return '15.<-30%'


def calculate_n_days_pattern_win_rate(n_days=3, min_occurrence=30):
    """
    計算連續 N 日 K線與漲跌幅組合，對未來 5 日的勝率。
    :param n_days: 連續觀察的天數 (預設 3 天)
    :param min_occurrence: 組合最少需出現的次數，低於此數值將被過濾 (預設 30 次)
    """
    print(f"啟動回測分析：連續 {n_days} 日多因子組合，最低出現次數門檻：{min_occurrence} 次")
    
    # 確保輸出目錄存在
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    all_files = glob.glob(os.path.join(PROCESSED_DIR, "*.csv"))
    if not all_files:
        print(f"❌ 找不到任何處理過的 CSV 檔案於 {PROCESSED_DIR}")
        return

    all_data_list = []

    for file_path in all_files:
        try:
            df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
            df = df.sort_index() # 確保時間順序正確
            
            # 防呆：檢查必要欄位是否存在
            required_cols = ['Close', 'K線型態(簡化)', '漲跌幅']
            if not all(col in df.columns for col in required_cols):
                continue

            # 1. 將單日漲跌幅轉換為等級
            df['漲跌幅等級'] = df['漲跌幅'].apply(categorize_return)
            
            # ================= 新增：強制降維簡化 K 線型態 =================
            # 利用字串包含 '紅' 或 '陽' 視為 紅K；'綠' 或 '陰' 視為 綠K；其餘(包含十字/T字/一字)皆歸為 十字線
            conditions = [
                df['K線型態(簡化)'].str.contains('紅|陽', na=False),
                df['K線型態(簡化)'].str.contains('綠|陰', na=False)
            ]
            choices = ['紅K', '綠K']
            # 使用 np.select 快速替換，預設值為 '十字線'
            df['K線型態(極簡)'] = np.select(conditions, choices, default='十字線')
            # ===============================================================

            # 2. 單日狀態拼接 (改用極簡版的 K 線型態) 
            # 結果會變成類似: "[紅K|05.2~4%]"
            df['Daily_Status'] = "[" + df['K線型態(極簡)'] + "|" + df['漲跌幅等級'] + "]"

            # 3. 參數化 N 天設計：利用 shift 拼接 N 天狀態
            # 從 N-1 天前、N-2天前... 一路拼接到今天
            # 動態字串拼接防呆：使用 range(n_days - 1, -1, -1) 
            # 迴圈動態讀取 shift()，這保證了不管您未來將 n_days 設定為 2 還是 10，
            # 字串拼接都不會出錯（時間順序保證為 Day1 -> Day2 -> Day3）。
            pattern_series = []
            for i in range(n_days - 1, -1, -1):
                if i == 0:
                    pattern_series.append(df['Daily_Status'])
                else:
                    pattern_series.append(df['Daily_Status'].shift(i))
            
            # 結合成 N日型態組合，中間用 " -> " 隔開
            df['N日型態組合'] = pattern_series[0].str.cat(pattern_series[1:], sep=" -> ")

            # 4. 新增「N日累計漲跌幅」與轉換等級
            # 公式: (當天收盤價 - N天前的收盤價) / N天前的收盤價 * 100
            df['N日累計漲幅數值'] = (df['Close'] - df['Close'].shift(n_days)) / df['Close'].shift(n_days) * 100
            df['N日累計漲跌幅等級'] = df['N日累計漲幅數值'].apply(categorize_return, window=3)

            # 5. 計算未來 1 到 5 天的「上漲勝率」(T+1 ~ T+5)
            # 若未來收盤價大於今日收盤價，即為上漲 (True/1)，否則為下跌 (False/0)
            for i in range(1, 6):
                future_close = df['Close'].shift(-i)
                df[f'Win_T+{i}'] = (future_close > df['Close']).astype(float)
                # 將沒有未來資料的日子設為 NaN 避免誤算
                df.loc[df.index[-i:], f'Win_T+{i}'] = np.nan 
                
            # 提取需要的欄位加入大集合
            result_df = df[['N日型態組合', 'N日累計漲跌幅等級', 'Win_T+1', 'Win_T+2', 'Win_T+3', 'Win_T+4', 'Win_T+5']].dropna()
            all_data_list.append(result_df)

        except Exception as e:
            print(f"⚠️ 處理 {file_path} 時發生錯誤: {e}")
            continue

    if not all_data_list:
        print("❌ 沒有足夠的有效資料可供分析。")
        return

    # 合併全市場資料
    market_df = pd.concat(all_data_list, ignore_index=True)

    # 6. 勝率統計與分組 (Groupby)
    print("正在統計全市場勝率矩陣...")
    grouped = market_df.groupby(['N日型態組合', 'N日累計漲跌幅等級'])
    
    # 計算出現次數與平均勝率
    stats_df = grouped.agg(
        出現次數=('Win_T+1', 'count'),
        T1_勝率=('Win_T+1', 'mean'),
        T2_勝率=('Win_T+2', 'mean'),
        T3_勝率=('Win_T+3', 'mean'),
        T4_勝率=('Win_T+4', 'mean'),
        T5_勝率=('Win_T+5', 'mean')
    ).reset_index()

    # 7. 過濾極端值：排除全市場出現總次數小於 min_occurrence 的組合
    stats_df = stats_df[stats_df['出現次數'] >= min_occurrence]

    # 將小數點轉換為百分比格式 (乘 100 並保留兩位小數)
    for i in range(1, 6):
        stats_df[f'T{i}_勝率'] = (stats_df[f'T{i}_勝率'] * 100).round(2)

    # 排序：依照 T+1 勝率由高至低排序
    stats_df = stats_df.sort_values(by='T1_勝率', ascending=False)

    # 8. 資料輸出至 CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_filename = f"連續{n_days}日組合_未來5日勝率_{timestamp}.csv"
    output_path = os.path.join(REPORT_DIR, output_filename)
    
    stats_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 統計完成！報告已成功儲存至: {output_path}\n")

    # 9. 在終端機印出前 10 名
    print("="*60)
    print(f"🏆 終端機預覽: T+1 勝率最高的前 10 名組合 (已過濾出現次數 < {min_occurrence})")
    print("="*60)
    top_10 = stats_df.head(10)
    
    # 為了終端機好讀，排版一下印出格式
    for index, row in top_10.iterrows():
        print(f"🔹 累計漲幅: {row['N日累計漲跌幅等級']:<10} | 出現次數: {row['出現次數']:<5}")
        print(f"   組合: {row['N日型態組合']}")
        print(f"   勝率 -> T+1: {row['T1_勝率']}% | T+3: {row['T3_勝率']}% | T+5: {row['T5_勝率']}%")
        print("-" * 60)

if __name__ == "__main__":
    # 預設執行 N=3 的回測，您隨時可以改成 2, 4, 5 等天數
    calculate_n_days_pattern_win_rate(n_days=3, min_occurrence=0)