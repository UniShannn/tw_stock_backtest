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


def categorize_cumulative_return(pct):
    """專門用來分類 N 日累計漲跌幅"""
    if pd.isna(pct): return '00.未知'
    if pct > 30: return '01.>30%'
    elif pct >= 25: return '02.25~30%'
    elif pct >= 20: return '03.20~25%'
    elif pct >= 15: return '04.15~20%'
    elif pct >= 10: return '05.10~15%'
    elif pct >= 5: return '06.5~10%'
    elif pct > 0: return '07.0~5%'
    elif pct == 0: return '08.0%'
    elif pct >= -5: return '09.-5~0%'
    elif pct >= -10: return '10.-10~-5%'
    elif pct >= -15: return '11.-15~-10%'
    elif pct >= -20: return '12.-20~-15%'
    elif pct >= -25: return '13.-25~-20%'
    elif pct >= -30: return '14.-30~-25%'
    else: return '15.<-30%'


# 假設這些變數定義在您的 config 中，若無請自行定義路徑
try:
    import config
    PROCESSED_DIR = config.PROCESSED_DIR
    REPORT_DIR = config.REPORT_DIR
except ImportError:
    PROCESSED_DIR = "../data/processed"
    REPORT_DIR = "../data/report"

def categorize_cumulative_return(pct):
    """(請確保您原本的分類函式有在此定義或引入)"""
    if pd.isna(pct): return '00.未知'
    if pct > 30: return '01.>30%'
    elif pct >= 25: return '02.25~30%'
    elif pct >= 20: return '03.20~25%'
    elif pct >= 15: return '04.15~20%'
    elif pct >= 10: return '05.10~15%'
    elif pct > 0: return '06.0~10%'
    elif pct >= -10: return '07.-10~0%'
    elif pct >= -15: return '08.-15~-10%'
    elif pct >= -20: return '09.-20~-15%'
    elif pct >= -25: return '10.-25~-20%'
    elif pct >= -30: return '11.-30~-25%'
    else: return '12.<-30%'

def calculate_n_days_pattern_win_rate(
    n_days=3, 
    min_occurrence=30, 
    min_vol_ma20=1000000,
    volume_rule="無條件",      # 🌟 新增：成交量規則 ("無條件", "大於均量", "小於均量")
    volume_multiplier=1.0,    # 🌟 新增：倍率
    volume_ma_col='Volume_MA_5' # 🌟 新增：要比較的均量線
):
    """
    計算連續 N 日純K線組合 + 累計漲跌幅，對未來 5 日的勝率 (支援動態成交量濾網)。
    """
    print(f"啟動回測分析：連續 {n_days} 日組合")
    print(f"📊 基本濾網 -> 最低出現次數：{min_occurrence} 次 | 20日均量最低門檻：{min_vol_ma20} 股")
    print(f"📈 籌碼濾網 -> 規則：{volume_rule} | 倍率：{volume_multiplier}倍 | 基準：{volume_ma_col}")
    
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    all_files = glob.glob(os.path.join(PROCESSED_DIR, "*.csv"))
    if not all_files:
        print(f"❌ 找不到任何處理過的 CSV 檔案於 {PROCESSED_DIR}")
        return

    all_data_list = []

    for file_path in all_files:
        try:
            df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
            df = df.sort_index() 
            
            # 🌟 防呆：檢查必要欄位是否存在 (確保我們有 Volume 和指定的 MA 欄位)
            required_cols = ['Close', 'Volume', 'K線型態(簡化)', 'Volume_MA_20', volume_ma_col]
            if not all(col in df.columns for col in required_cols):
                continue
            
            # 【重要時序觀念】: 不能在這裡 drop 掉任何 K 棒，否則下面的 shift() 會錯亂！
            # 因此我們先將整個 df 完整算完，最後再套用 boolean mask 篩選。

            # 1. 強制降維簡化 K 線型態
            conditions = [
                df['K線型態(簡化)'].str.contains('紅|陽', na=False),
                df['K線型態(簡化)'].str.contains('綠|陰', na=False)
            ]
            choices = ['紅K', '綠K']
            df['Daily_Status'] = np.select(conditions, choices, default='十字')

            # 2. 參數化 N 天設計：利用 shift 拼接 N 天狀態
            pattern_series = []
            for i in range(n_days - 1, -1, -1):
                if i == 0:
                    pattern_series.append(df['Daily_Status'])
                else:
                    pattern_series.append(df['Daily_Status'].shift(i))
            
            df['N日型態組合'] = pattern_series[0].str.cat(pattern_series[1:], sep=" -> ")

            # 3. 計算「N日累計漲跌幅」與轉換等級
            df['N日累計漲幅數值'] = (df['Close'] - df['Close'].shift(n_days)) / df['Close'].shift(n_days) * 100
            df['N日累計漲跌幅等級'] = df['N日累計漲幅數值'].apply(categorize_cumulative_return)

            # 4. 計算未來 1 到 5 天的「上漲勝率」(T+1 ~ T+5)
            for i in range(1, 6):
                future_close = df['Close'].shift(-i)
                df[f'Win_T+{i}'] = (future_close > df['Close']).astype(float)
                df.loc[df.index[-i:], f'Win_T+{i}'] = np.nan 

            # ================= 🌟 核心過濾器：動態成交量與殭屍股濾網 =================
            # 條件 A：過濾 20 日均量低落的冷門股 (代替原本在上方剔除的作法)
            zombie_cond = df['Volume_MA_20'] >= min_vol_ma20
            
            # 條件 B：根據使用者設定的「籌碼濾網」進行判斷
            if volume_rule == "大於均量":
                vol_cond = df['Volume'] >= (df[volume_ma_col] * volume_multiplier)
            elif volume_rule == "小於均量":
                vol_cond = df['Volume'] <= (df[volume_ma_col] * volume_multiplier)
            else: # "無條件"
                vol_cond = pd.Series([True] * len(df), index=df.index)
            
            # 條件 C：防呆，確保我們依賴的均線沒有 NaN (例如上市前幾天)
            valid_ma_cond = df[volume_ma_col].notna()
            
            # 總條件合併
            final_mask = zombie_cond & vol_cond & valid_ma_cond
            # =======================================================================
            
            # 5. 提取需要的欄位，並「只留下」符合總條件的日子
            result_df = df.loc[final_mask, ['N日型態組合', 'N日累計漲跌幅等級', 'Win_T+1', 'Win_T+2', 'Win_T+3', 'Win_T+4', 'Win_T+5']].dropna()
            
            if not result_df.empty:
                all_data_list.append(result_df)

        except Exception as e:
            print(f"⚠️ 處理 {file_path} 時發生錯誤: {e}")
            continue

    if not all_data_list:
        print("❌ 沒有足夠的有效資料可供分析 (可能是均量門檻或倍數設太高，導致全市場都被濾掉了)。")
        return

    # 合併全市場資料
    market_df = pd.concat(all_data_list, ignore_index=True)

    # 6. 勝率統計與分組 (Groupby)
    print("正在統計全市場勝率矩陣...")
    grouped = market_df.groupby(['N日型態組合', 'N日累計漲跌幅等級'])
    
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

    # 將小數點轉換為百分比格式
    for i in range(1, 6):
        stats_df[f'T{i}_勝率'] = (stats_df[f'T{i}_勝率'] * 100).round(2)

    # 排序：依照 T+1 勝率由高至低排序
    stats_df = stats_df.sort_values(by='T1_勝率', ascending=False)

    # 8. 資料輸出至 CSV (動態產生檔名)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    vol_str = f"_{volume_rule}{volume_multiplier}倍" if volume_rule != "無條件" else ""
    output_filename = f"簡化版連續{n_days}日組合{vol_str}_未來5日勝率_{timestamp}.csv"
    output_path = os.path.join(REPORT_DIR, output_filename)
    
    stats_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 統計完成！報告已成功儲存至: {output_path}\n")

    # 9. 在終端機印出前 10 名
    print("="*65)
    print(f"🏆 終端機預覽: T+1 勝率最高的前 10 名組合 (已過濾出現次數 < {min_occurrence})")
    print(f"   [當前環境]: {volume_rule} {volume_multiplier} 倍 {volume_ma_col}")
    print("="*65)
    top_10 = stats_df.head(10)
    
    for index, row in top_10.iterrows():
        print(f"🔹 組合: {row['N日型態組合']:<20} | 累計漲幅: {row['N日累計漲跌幅等級']:<10}")
        print(f"   出現次數: {row['出現次數']:<5} | T+1 勝率: {row['T1_勝率']}% | T+3 勝率: {row['T3_勝率']}%")
        print("-" * 65)

if __name__ == "__main__":
    # ================= 參數調整區 =================
    
    # 測試情境一：無條件 (看原始機率)
    # calculate_n_days_pattern_win_rate(volume_rule="無條件")
    
    # 測試情境二：尋找主力爆量點火 (大於 5日均量 2.0倍)
    calculate_n_days_pattern_win_rate(
        n_days=3, 
        min_occurrence=30, 
        min_vol_ma20=1000 * 500,       # 20日均量需大於 500 張
        volume_rule="無條件",         # <--- 動態調整區
        volume_multiplier=2.0,         # <--- 倍數隨時改
        volume_ma_col='Volume_MA_5'    # <--- 可以改成 'Volume_MA_10' 等
    )
    
    # 測試情境三：尋找量縮整理極致 (小於 5日均量 0.5倍)
    # calculate_n_days_pattern_win_rate(volume_rule="小於均量", volume_multiplier=0.5)