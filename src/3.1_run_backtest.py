import pandas as pd
import numpy as np
import os
import glob
import math
from datetime import datetime
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
        stock_id = filename.replace('ma_data_', '').replace('.csv', '').replace('_TW', '')
        
        # ==========================================
        # 🔔 新增：動態進度條 (使用 \r 讓它在同一行刷新)
        # ==========================================
        print(f"\r⏳ [{idx}/{total_files}] 正在掃描股票: {stock_id:<6} ...", end="", flush=True)
        
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        if len(df) < 25: continue # 資料太少不回測
        
        # --- 預先計算策略所需的技術指標 ---
        df['20D_High'] = df['Close'].rolling(window=20).max()
        df['20D_Vol_MA'] = df['Volume'].rolling(window=20).mean()
        if 'MA_20' not in df.columns:
            df['MA_20'] = df['Close'].rolling(window=20).mean()
            
        # 建立欄位：昨日收盤價是否低於昨日月線 (判斷連續兩日破月線用)
        df['Below_20MA'] = df['Close'] < df['MA_20']
        df['Below_20MA_Yesterday'] = df['Below_20MA'].shift(1)
        
        in_position = False
        trade_data = {}
        
        # 逐日掃描 (為了取得隔日開盤價，我們迴圈跑到 len(df) - 1)
        for i in range(20, len(df) - 1):
            today = df.iloc[i]
            tomorrow = df.iloc[i+1]
            yesterday = df.iloc[i-1]
            date_today = df.index[i]
            
            # ==========================================
            # 1. 判斷進場條件 (空手狀態)
            # ==========================================
            if not in_position:
                # 條件A: 收盤價創 20 日新高
                cond_new_high = (today['Close'] == today['20D_High'])
                # 條件B: 20日均量 > 50萬股 (500張)
                cond_volume = (today['20D_Vol_MA'] > 500000)
                
                if cond_new_high and cond_volume:
                    # 條件C: 檢查隔日開盤是否漲停鎖死 (開盤價 >= 昨收*1.095 且 開=高=低=收)
                    limit_up_price = today['Close'] * 1.095
                    is_limit_up = (tomorrow['Open'] >= limit_up_price) and \
                                  (tomorrow['Open'] == tomorrow['High'] == tomorrow['Low'] == tomorrow['Close'])
                    
                    if not is_limit_up:
                        # 執行進場 (隔日開盤買進)
                        entry_price = tomorrow['Open']
                        if pd.isna(entry_price) or entry_price <= 0: continue
                            
                        # 計算可買零股股數 (上限5萬元)
                        shares = math.floor(50000 / entry_price)
                        if shares <= 0: continue
                            
                        in_position = True
                        
                        # 初始化持倉狀態紀錄
                        trade_data = {
                            '股票代號': stock_id,
                            '進場日期': df.index[i+1].strftime('%Y-%m-%d'),
                            '進場股價': entry_price,
                            '買進股數': shares,
                            '總投入成本': entry_price * shares,
                            'highest_since_entry': entry_price, # 進場後最高價
                            'days_since_highest': 0,            # 距離創高天數
                            'days_held': 0,
                            'max_positive_return': 0,
                            'max_negative_return': 0
                        }
                        # 買進當天不算持有天數的盤中檢查，直接跳下一天
                        continue 
            
            # ==========================================
            # 2. 判斷出場條件 (持倉狀態)
            # ==========================================
            else:
                trade_data['days_held'] += 1
                
                # 更新持倉期間的高低點與最大獲利/虧損
                if today['High'] > trade_data['highest_since_entry']:
                    trade_data['highest_since_entry'] = today['High']
                    trade_data['days_since_highest'] = 0  # 創新高，天數歸零
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

                # 條件 A: 固定停損 -15% (盤中觸及即出場，若開盤直接跳空跌破，以開盤價計)
                stop_loss_price = trade_data['進場股價'] * 0.85
                if today['Low'] <= stop_loss_price:
                    exit_triggered = True
                    exit_reason = "固定停損(-15%)"
                    exit_price = min(today['Open'], stop_loss_price)

                # 條件 B: 移動停利/停損，從最高點回落 20% (盤中觸及即出場)
                elif today['Low'] <= trade_data['highest_since_entry'] * 0.80:
                    exit_triggered = True
                    exit_reason = "移動停損(高回落20%)"
                    exit_price = min(today['Open'], trade_data['highest_since_entry'] * 0.80)

                # 條件 C: 連續兩日跌破月線 (今日收盤破，且昨日收盤破 -> 隔日開盤出)
                elif today['Below_20MA'] and today['Below_20MA_Yesterday']:
                    exit_triggered = True
                    exit_reason = "跌破月線(連兩日)"
                    exit_price = tomorrow['Open']

                # 條件 D: 時間停損 (持有 > 20天 且未再創新高 -> 隔日開盤出)
                elif trade_data['days_since_highest'] >= 20:
                    exit_triggered = True
                    exit_reason = "時間停損(20日未創高)"
                    exit_price = tomorrow['Open']

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
                    
                    # ==========================================
                    # 🔔 新增：印出捕捉到的交易 (加上換行，避免覆蓋進度條)
                    # ==========================================
                    print(f"\n  👉 [交易成立] {stock_id:<6} | 買:{trade_record['進場日期']} -> 賣:{trade_record['出場日期']} | 報酬: {trade_record['出場報酬率(%)']:>6.2f}% ({exit_reason})")

    # ==========================================
    # 3. 輸出回測報告
    # ==========================================
    # 🔔 新增：清空最後一行的進度條，準備印出報告
    print("\n\n✅ 所有股票掃描完畢！正在計算統計數據...")
    
    if not all_trades:
        print("沒有符合條件的交易紀錄。")
        return

    trades_df = pd.DataFrame(all_trades)
    
    # 儲存 CSV 檔
    output_path = os.path.join(REPORT_DIR, f"backtest_records_{datetime.now().strftime('%Y%m%d')}.csv")
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

    print("\n" + "="*50)
    print("📊 量化策略回測統計報告")
    print("="*50)
    print(f"🔹 總交易次數: {total_trades} 次")
    print(f"🔹 策略勝率:   {win_rate:.2f} %")
    print(f"🔹 平均報酬率: {avg_return:.2f} %")
    print("-" * 50)
    print(f"🔸 獲利交易平均報酬:  +{avg_win:.2f} %")
    print(f"🔸 虧損交易平均報酬:  {avg_loss:.2f} %")
    print(f"🔸 盈虧比 (賠率):     {profit_factor:.2f}")
    print("="*50)
    print(f"✅ 交易明細已儲存至: {output_path}")

if __name__ == "__main__":
    run_backtest()