import pandas as pd
import os
import config
import send_discord_msg as dc  # 移到最上方

def analyze_candlestick_patterns():
    # 用一個列表來收集所有股票的訊息，最後再一起發送
    final_messages = ["**📊 台股 K 線型態與隔日勝率分析報告**\n"]

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
        
        # 為了涵蓋之前寫的「大陽線、光頭光腳大陽線」等，使用 str.contains 包含關鍵字
        large_red_cases = df[df['Pattern'].str.contains('大陽線', na=False)]
        large_red_up_cases = large_red_cases[large_red_cases['Next_Day_Up'] == True]
        prob_large_red_up = (len(large_red_up_cases) / len(large_red_cases)) * 100 if len(large_red_cases) > 0 else 0
        
        # 其他紅線：顏色是紅色，但名稱不包含大陽線
        other_red_cases = df[(df['Color'] == '紅') & (~df['Pattern'].str.contains('大陽線', na=False))]
        other_red_up_cases = other_red_cases[other_red_cases['Next_Day_Up'] == True]
        prob_other_red_up = (len(other_red_up_cases) / len(other_red_cases)) * 100 if len(other_red_cases) > 0 else 0
        
        # 組合該檔股票的訊息
        msg = f"**[{stock_id}]**\n"
        msg += f"📈 【大陽線】出現 {len(large_red_cases)} 次 ➡️ 隔日上漲機率：**{prob_large_red_up:.2f}%**\n"
        msg += f"🕯️ 【其他紅線】出現 {len(other_red_cases)} 次 ➡️ 隔日上漲機率：**{prob_other_red_up:.2f}%**\n"
        msg += "-" * 30 + "\n"
        
        final_messages.append(msg)

    # 將所有訊息合併成一個大字串，一次發送給 Discord
    full_report = "".join(final_messages)
    print(full_report)
    
    # 避免字數超過 Discord 限制 (單則上限約 2000 字元)
    if len(full_report) > 1900:
        dc.send_discord_message(full_report[:1900] + "\n...(字數過長省略)")
    else:
        dc.send_discord_message(full_report)

if __name__ == "__main__":
    analyze_candlestick_patterns()