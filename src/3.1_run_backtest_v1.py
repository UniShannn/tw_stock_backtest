import pandas as pd
import numpy as np
import os
import glob
import math
from datetime import datetime
import re
import sys

# 假設您有 config 檔案，若無則使用預設路徑
try:
    import config
    PROCESSED_DIR = config.PROCESSED_DIR
    REPORT_DIR = config.REPORT_DIR
except ImportError:
    PROCESSED_DIR = "../data/processed"
    REPORT_DIR = "../data/report"

def run_backtest():
    print("🚀 開始執行策略回測...")
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    csv_files = glob.glob(os.path.join(PROCESSED_DIR, "*.csv"))
    if not csv_files:
        print("❌ 找不到處理好的 CSV 檔案，請確認資料夾路徑。")
        return

    # 取得總檔案數，方便計算進度
    total_files = len(csv_files)
    print(f"📂 共找到 {total_files} 檔股票資料，準備開始逐一掃描...\n")

    all_trades = []

    # 使用 enumerate 來取得當前的索引值 (idx)
    for idx, filepath in enumerate(csv_files, 1):
        filename = os.path.basename(filepath)
        # 定義要移除的後綴列表，未來想加新市場類型只要在列表內新增即可
        # 例如：未來若出現 '.ETF' 或其他後綴，直接加進這個 list 即可
        suffixes_to_remove = ['_TW', '_TWO', '_ETF']
        # 建立一個正規表達式模式，例如：(_TW|_TWO|_ETF)
        pattern = '|'.join(suffixes_to_remove)
        stock_id = filename.replace('ma_data_', '').replace('.csv', '').replace('_TW', '')
        # 利用 Regex 把所有定義好的後綴一次清乾淨
        stock_id = re.sub(pattern, '', stock_id)

        print(f"\r⏳ [{idx}/{total_files}] 正在掃描股票: {stock_id:<6} ...", end="", flush=True)
        
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        if len(df) < 25: continue # 資料太少不回測
        
        # ==========================================
        # 💡 優化 1：將可以提前計算的指標與條件「向量化(Vectorized)」，移出迴圈外
        # 📝 [擴充區] 在此處定義各種「出場訊號」
        # 未來若要新增條件 (例如跌破 5MA、RSI 超賣)，都統一寫在這裡
        # ==========================================

        #df['20D_High'] = df['Close'].rolling(window=20).max()
        #df['20D_Vol_MA'] = df['Volume'].rolling(window=20).mean()
        if 'MA_20' not in df.columns:
            df['MA_20'] = df['Close'].rolling(window=20).mean()
            
        # 出場條件: 破月線 
        df['Below_20MA'] = df['Close'] < df['MA_20']
        df['Below_20MA_Yesterday'] = df['Below_20MA'].shift(1)
        # 連兩日跌破月線
        df['Exit_Signal_MA'] = df['Below_20MA'] & df['Below_20MA_Yesterday'] 
        # 當日收盤跌破月線
        df['Exit_Signal_MA'] = df['Below_20MA']  # 跌破當下即觸發
        # df['Exit_Signal_5MA_Break'] = df['Close'] < df['MA_5'] # (未來擴充範例)
        # ------------------------------------------

        # 進場條件預先判斷
        df['Entry_Condition'] = (df['創20日新高'] == True ) & (df['Volume_MA_20'] > 500000)
        #df['Entry_Condition'] = (df['Close'] == df['創20日新高']) & (df['Volume_MA_20'] > 500000)
        
        # 利用 shift(-1) 預先取得「隔日」的資料，避免在迴圈內反覆 index 取值
        df['Tomorrow_Open'] = df['Open'].shift(-1)
        df['Tomorrow_High'] = df['High'].shift(-1)
        df['Tomorrow_Low'] = df['Low'].shift(-1)
        df['Tomorrow_Close'] = df['Close'].shift(-1)
        
        # 預先判斷隔日是否開盤漲停鎖死
        limit_up_price = df['Close'] * 1.095
        df['Tomorrow_Is_Limit_Up'] = (df['Tomorrow_Open'] >= limit_up_price) & \
                                     (df['Tomorrow_Open'] == df['Tomorrow_High']) & \
                                     (df['Tomorrow_Open'] == df['Tomorrow_Low']) & \
                                     (df['Tomorrow_Open'] == df['Tomorrow_Close'])
        
        in_position = False
        trade_data = {}
        
        # 狀態變數：將計算結果存在記憶體，避免迴圈內重複算
        stop_loss_price = 0.0
        trailing_stop_price = 0.0
        
        # 逐日掃描
        for i in range(20, len(df) - 1):
            today = df.iloc[i]
            date_today = df.index[i]
            
            # ==========================================
            # 1. 判斷進場條件 (空手狀態)
            # ==========================================
            if not in_position:
                # 💡 優化 2：直接使用外部算好的布林值，省略迴圈內的數學運算
                if today['Entry_Condition'] and not today['Tomorrow_Is_Limit_Up']:
                    entry_price = today['Tomorrow_Open']
                    if pd.isna(entry_price) or entry_price <= 0: continue
                        
                    shares = math.floor(50000 / entry_price)
                    if shares <= 0: continue
                        
                    in_position = True
                    
                    # 💡 優化 3：進場當下直接算好「固定停損價」和「初始移動停損價」，後面不用每天重算
                    stop_loss_price = entry_price * 0.85
                    trailing_stop_price = entry_price * 0.80
                    
                    trade_data = {
                        '股票代號': stock_id,
                        '進場日期': df.index[i+1].strftime('%Y-%m-%d'),
                        '進場股價': entry_price,
                        '買進股數': shares,
                        '總投入成本': entry_price * shares,
                        'highest_since_entry': entry_price,
                        'days_since_highest': 0,
                        'days_held': 0,
                        'max_positive_return': 0,
                        'max_negative_return': 0
                    }
                    continue 
            
            # ==========================================
            # 2. 判斷出場條件 (持倉狀態)
            # ==========================================
            else:
                trade_data['days_held'] += 1
                
                # 💡 優化 4：只在「創新高」的時候，才重新計算移動停損價
                if today['High'] > trade_data['highest_since_entry']:
                    trade_data['highest_since_entry'] = today['High']
                    trade_data['days_since_highest'] = 0
                    trailing_stop_price = today['High'] * 0.80  # 更新防守線
                else:
                    trade_data['days_since_highest'] += 1
                
                current_ret_high = (today['High'] - trade_data['進場股價']) / trade_data['進場股價']
                current_ret_low = (today['Low'] - trade_data['進場股價']) / trade_data['進場股價']
                
                if current_ret_high > trade_data['max_positive_return']:
                    trade_data['max_positive_return'] = current_ret_high
                if current_ret_low < trade_data['max_negative_return']:
                    trade_data['max_negative_return'] = current_ret_low

                exit_triggered = False
                exit_reason = ""
                exit_price = 0

                # 💡 優化 5：比較時直接取用預先算好的變數 (stop_loss_price, trailing_stop_price)
                if today['Low'] <= stop_loss_price:
                    exit_triggered = True
                    exit_reason = "固定停損(-15%)"
                    exit_price = min(today['Open'], stop_loss_price)

                elif today['Low'] <= trailing_stop_price:
                    exit_triggered = True
                    exit_reason = "移動停損(高回落20%)"
                    exit_price = min(today['Open'], trailing_stop_price)

                elif today['Exit_Signal_MA']:
                    exit_triggered = True
                    #exit_reason = "跌破月線(連兩日)"
                    #exit_price = today['Tomorrow_Open']
                    exit_reason = "跌破月線"
                    exit_price = today['Close']

                elif trade_data['days_since_highest'] >= 20:
                    exit_triggered = True
                    exit_reason = "時間停損(20日未創高)"
                    exit_price = today['Tomorrow_Open']

                # 執行出場紀錄
                if exit_triggered:
                    actual_return = (exit_price - trade_data['進場股價']) / trade_data['進場股價']
                    
                    trade_record = {
                        '股票代號': trade_data['股票代號'],
                        '進場日期': trade_data['進場日期'],
                        '出場日期': df.index[i+1].strftime('%Y-%m-%d') if exit_reason in ["跌破月線(連兩日)", "時間停損(20日未創高)"] else date_today.strftime('%Y-%m-%d'),
                        '進場股價': round(trade_data['進場股價'], 2),
                        '出場股價': round(exit_price, 2),
                        '買進股數': trade_data['買進股數'],
                        '總投入成本': round(trade_data['總投入成本']),
                        '持有天數': trade_data['days_held'],
                        '期間最大正報酬(%)': round(trade_data['max_positive_return'] * 100, 2),
                        '期間最大負報酬(%)': round(trade_data['max_negative_return'] * 100, 2),
                        '出場報酬率(%)': round(actual_return * 100, 2),
                        '出場觸發條件': exit_reason
                    }
                    all_trades.append(trade_record)
                    in_position = False
                    
                    # 檢查bug用
                    #print(f"\n  👉 [交易成立] {stock_id:<6} | 買:{trade_record['進場日期']} -> 賣:{trade_record['出場日期']} | 報酬: {trade_record['出場報酬率(%)']:>6.2f}% ({exit_reason})")


    # ==========================================
    # 3. 輸出回測報告
    # ==========================================
    print("\n\n✅ 所有股票掃描完畢！正在計算統計數據...")
    
    if not all_trades:
        print("沒有符合條件的交易紀錄。")
        return

    trades_df = pd.DataFrame(all_trades)
    
    # 儲存 CSV 檔
    output_path = os.path.join(REPORT_DIR, f"backtest_records_{datetime.now().strftime('%Y%m%d%H%M')}.csv")
    trades_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    # 統計數據計算
    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df['出場報酬率(%)'] > 0]
    losing_trades = trades_df[trades_df['出場報酬率(%)'] <= 0]
    
    win_rate = len(winning_trades) / total_trades * 100
    avg_return = trades_df['出場報酬率(%)'].mean()
    
    avg_win = winning_trades['出場報酬率(%)'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['出場報酬率(%)'].mean() if not losing_trades.empty else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # ---------------------------------------------------------
    # 📝 優化後的 Print 報表 (加入策略條件說明)
    # ---------------------------------------------------------
# ==========================================
    # 3. 輸出回測報告與發送通知
    # ==========================================
    
    # ... (前面的計算 total_trades, win_rate 等等保留不動) ...

    # 1. 將所有報告內容打包進 msg 變數中
    msg = f"""
        {"="*55}
        📊 量化策略回測統計報告
        {"="*55}
        📝 【策略參數設定】
        🔹 進場條件：收盤創20日新高 且 20日均量>500張 (隔日開盤買進)
        🔹 過濾條件：隔日開盤若漲停鎖死則放棄進場
        🔹 出場條件：
        1. 固定停損：進場後跌幅達 -15%
        2. 移動停損：從持倉最高點回落 20%
        3. 破線停損：連續兩日收盤跌破月線 (20MA)
        4. 時間停損：持有期間超過 20 日未再創新高
        {"-"*55}
        🔹 總交易次數:     {total_trades} 次
        🔹 策略總勝率:     {win_rate:.2f} %
        🔹 每次平均報酬率: {avg_return:.2f} %
        {"-"*55}
        🔸 獲利交易平均報酬:  +{avg_win:.2f} %
        🔸 虧損交易平均報酬:   {avg_loss:.2f} %
        🔸 盈虧比 (賺/賠):     {profit_factor:.2f}
        {"="*55}
        ✅ 交易明細已儲存至: {output_path}
        """

    return msg


if __name__ == "__main__":
    msg = run_backtest()
    import send_discord_msg as dc
    dc.send_discord_message(msg)