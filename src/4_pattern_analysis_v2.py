import pandas as pd
import os
import config
import send_discord_msg as dc  # 移到最上方

def analyze_candlestick_patterns():
    # 用一個列表來收集所有股票的訊息，最後再一起發送
    final_messages = ["**📊 台股 K 線型態與隔日勝率分析報告**\n"]

    # 紀錄累計大陽線次數
    total_super_red_cases = 0
    # 紀錄累計機率加總（用來算整體平均勝率）
    total_super_red_prob = 0

    for stock_id in config.TARGET_STOCKS:
        safe_stock_id = stock_id.replace('.', '_')
        filepath = os.path.join(config.PROCESSED_DIR, f"ma_data_{safe_stock_id}.csv")
        
        if not os.path.exists(filepath):
            print(f"找不到資料檔：{filepath}")
            continue
            
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        
        # 【防呆機制】如果之前的程式沒算出 Next_Day_Up，這裡動態補算
        if 'Next_Close' not in df.columns:
            df['Next_Close'] = df['Close'].shift(-1)
        if 'Next_Day_Up' not in df.columns:
            df['Next_Day_Up'] = df['Next_Close'] > df['Close']
            
        df = df.dropna(subset=['Next_Close'])
       
        # 定義因子條件
        # 1. 均量條件：若之前沒算過 5日均量，先算出來
        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(5).mean()
        is_high_volume = df['Volume'] > (df['Volume_MA5'] * 1.1) # 成交量大於 5日均量 1.0 倍
        
        # 2. 趨勢條件：站在 20MA 之上
        is_uptrend = df['Close'] > df['MA_20']

        # --- 開始進行多因子篩選 ---
        # 基礎大陽線
        large_red_mask = df['Pattern'].str.contains('大陽線', na=False)
        
        # 多因子超級陽線：大陽線 + 爆量 + 多頭趨勢
        super_red_cases = df[large_red_mask & is_high_volume & is_uptrend]
        
        # 計算勝率
        if len(super_red_cases) > 0:
            super_red_up_cases = super_red_cases[super_red_cases['Next_Day_Up'] == True]
            prob_super_red = (len(super_red_up_cases) / len(super_red_cases)) * 100
        else:
            prob_super_red = 0

            


        # 將結果加入訊息中
        #msg = f"**[{stock_id}]**\n"
        #msg += f"🔥 【爆量多頭大陽線】出現 {len(super_red_cases)} 次 ➡️ 隔日上漲機率：**{prob_super_red:.2f}%**\n"
        #final_messages.append(msg)
        total_super_red_cases += len(super_red_cases)
        total_super_red_prob += prob_super_red * len(super_red_cases)

    # 將所有訊息合併成一個大字串，一次發送給 Discord
    final_messages.append(f"\n**整體分析：**\n")
    if total_super_red_cases > 0:
        overall_prob = total_super_red_prob / total_super_red_cases
        final_messages.append(f"🔥 【爆量多頭大陽線】在選股池{len(config.TARGET_STOCKS)}檔股票中共出現 {total_super_red_cases} 次 ➡️ 平均隔日上漲機率：**{overall_prob:.2f}%**\n")
    full_report = "".join(final_messages)
    print(full_report)
    
    # 避免字數超過 Discord 限制 (單則上限約 2000 字元)
    if len(full_report) > 1900:
        dc.send_discord_message(full_report[:1900] + "\n...(字數過長省略)")
    else:
        dc.send_discord_message(full_report)

if __name__ == "__main__":
    analyze_candlestick_patterns()