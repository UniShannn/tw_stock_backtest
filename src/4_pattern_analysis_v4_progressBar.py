import pandas as pd
import os
import config
import send_discord_msg as dc  # 模組統一移到最上方

def analyze_candlestick_patterns(volume_threshold=1.5):
    """分析台股 K 線型態與隔日勝率，並加入實時進度條顯示
    volume_threshold 參數用來調整「爆量」的倍數閾值，預設為 1.5 倍，可以根據需求進行測試和優化
    """
    # ==========================================
    # 1. 嘗試載入台股名冊，以便動態取得公司簡稱
    # ==========================================
    name_map = {}
    metadata_path = os.path.join(config.RAW_DIR, "tw_stock_metadata.csv")
    
    if os.path.exists(metadata_path):
        try:
            meta_df = pd.read_csv(metadata_path)
            meta_df.columns = meta_df.columns.str.strip()
            if 'YF_Ticker' in meta_df.columns and 'Name' in meta_df.columns:
                name_map = dict(zip(meta_df['YF_Ticker'].astype(str).str.strip(), meta_df['Name'].astype(str).str.strip()))
            elif 'Stock_ID' in meta_df.columns and 'Name' in meta_df.columns:
                name_map = dict(zip(meta_df['Stock_ID'].astype(str).str.strip(), meta_df['Name'].astype(str).str.strip()))
        except Exception as e:
            # 由於進度條會用 \r，這裡出錯時先給個空行再印，避免排版壞掉
            print(f"\n⚠️ 載入股票名冊對齊簡稱時發生錯誤: {e}")

    # ==========================================
    # 2. 初始化統計變數
    # ==========================================
    total_super_red_cases = 0     # 累計符合條件的總次數
    total_super_red_up_cases = 0  # 累計隔日真正上漲的總次數
    
    stock_details = []            # 用來存放個別股票詳細訊息的清單
    total_stocks_count = len(config.TARGET_STOCKS)

    print(f"🚀 開始執行台股 K 線型態篩選，目標總數：{total_stocks_count} 檔...")

    # ==========================================
    # 3. 循環處理每檔股票 (加入 index 用於計算進度)
    # ==========================================
    for idx, stock_id in enumerate(config.TARGET_STOCKS):
        # ------------------------------------------
        # 📌 實時更新終端機進度條 (回車手段 \r)
        # ------------------------------------------
        current_num = idx + 1
        progress_pct = (current_num / total_stocks_count) * 100
        
        # 繪製方塊進度條 (長度固定為 20 格)
        bar_length = 20
        filled_length = int(bar_length * current_num // total_stocks_count)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # 動態印出進度：包含 [當前檔數/總檔數] 正在處理代號 進度條 百分比
        # {stock_id:<8} 代表靠左對齊並固定佔 8 個字元長度，防止長短代號切換時畫面閃爍
        print(f"\r⏳ 正在量化分析... [{current_num}/{total_stocks_count}] 🚀 處理中: {stock_id:<8} |{bar}| {progress_pct:.1f}%", end='', flush=True)

        safe_stock_id = stock_id.replace('.', '_')
        filepath = os.path.join(config.PROCESSED_DIR, f"ma_data_{safe_stock_id}.csv")
        
        if not os.path.exists(filepath):
            # 為了不破壞進度條，先用 \n 換行印出警告，下一輪進度條會自動在下一行重新繪製
            print(f"\n❌ 找不到資料檔：{filepath}")
            continue
            
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        
        # 【防呆機制】補算 Next_Day_Up
        if 'Next_Close' not in df.columns:
            df['Next_Close'] = df['Close'].shift(-1)
        if 'Next_Day_Up' not in df.columns:
            df['Next_Day_Up'] = df['Next_Close'] > df['Close']
            
        df = df.dropna(subset=['Next_Close'])
       
        # 因子條件計算
        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(5).mean()
        is_high_volume = df['Volume'] > (df['Volume_MA5'] * volume_threshold)  # 成交量大於 5日均量 1.1 倍
        is_uptrend = df['Close'] > df['MA_20']

        # 技術面 K 線型態篩選
        large_red_mask = df['Pattern'].str.contains('大陽線', na=False) if 'Pattern' in df.columns else pd.Series(False, index=df.index)
        
        # 多因子交叉篩選
        super_red_cases = df[large_red_mask & is_high_volume & is_uptrend]
        
        cases_count = len(super_red_cases)
        up_cases_count = len(super_red_cases[super_red_cases['Next_Day_Up'] == True]) if cases_count > 0 else 0
        prob_super_red = (up_cases_count / cases_count) * 100 if cases_count > 0 else 0.0
        
        total_super_red_cases += cases_count
        total_super_red_up_cases += up_cases_count

        # 取得公司簡稱
        pure_id = stock_id.split('.')[0]
        stock_name = name_map.get(stock_id, name_map.get(pure_id, ""))
        display_name = f"{pure_id} {stock_name}".strip() if stock_name else stock_id

        if total_stocks_count < 10:
            stock_details.append(f"🔹 **[{display_name}]** 出現 `{cases_count}` 次 ➡️ 隔日上漲率：**{prob_super_red:.2f}%**")

    # 迴圈完全結束後，必須主動印一個空的 print() 來進行「真正換行」，否則後續輸出的報告會把進度條覆蓋掉
    print() 
    print("✅ 所有股票分析完成！開始打包報告並發送至 Discord...\n")

    # ==========================================
    # 4. 組裝與打包 Discord 訊息 123
    # ==========================================
    final_messages = ["**📊 台股 K 線型態與多因子勝率分析報告**\n"]
    
    if total_stocks_count < 10 and stock_details:
        final_messages.append("**📌 個別股票監控明細**")
        final_messages.extend(stock_details)
        final_messages.append("\n" + "─" * 20 + "\n")
        
    final_messages.append("**📈 整體多因子篩選成果**")
    final_messages.append(f"💡 策略特徵：`大陽線` + `爆量(>5MA {volume_threshold}倍)` + `多頭趨勢(20MA之上)`")
    final_messages.append(f"🗂️ 選股池總計：`{total_stocks_count}` 檔股票")
    final_messages.append(f"🔢 總型態出現次數：`{total_super_red_cases}` 次")
    
    if total_super_red_cases > 0:
        overall_prob = (total_super_red_up_cases / total_super_red_cases) * 100
        final_messages.append(f"🎯 綜合隔日平均勝率：**{overall_prob:.2f}%**")
    else:
        final_messages.append(f"🎯 綜合隔日平均勝率：**0.00%** *(此觀測區間未出現符合特徵之型態)*")
        
    full_report = "\n".join(final_messages)
    print(full_report)
    
    if len(full_report) > 1950:
        dc.send_discord_message(full_report[:1900] + "\n...(報告內容過長，已自動省略後續明細)")
    else:
        dc.send_discord_message(full_report)

if __name__ == "__main__":
    analyze_candlestick_patterns(volume_threshold=3.0)  # 可以在這裡調整爆量的倍數閾值，例如 2.0、3.0 等，根據需求進行測試和優化