import pandas as pd
import os
import config
import send_discord_msg as dc  # 模組統一移到最上方

def analyze_candlestick_patterns():
    # ==========================================
    # 1. 嘗試載入台股名冊，以便動態取得公司簡稱
    # ==========================================
    name_map = {}
    metadata_path = os.path.join(config.RAW_DIR, "tw_stock_metadata.csv")
    
    if os.path.exists(metadata_path):
        try:
            meta_df = pd.read_csv(metadata_path)
            # 清理欄位前後可能存在的空白字元
            meta_df.columns = meta_df.columns.str.strip()
            
            # 支援舊版與新版名冊欄位結構 (優先匹配 YF_Ticker 或 Stock_ID)
            if 'YF_Ticker' in meta_df.columns and 'Name' in meta_df.columns:
                name_map = dict(zip(meta_df['YF_Ticker'].astype(str).str.strip(), meta_df['Name'].astype(str).str.strip()))
            elif 'Stock_ID' in meta_df.columns and 'Name' in meta_df.columns:
                name_map = dict(zip(meta_df['Stock_ID'].astype(str).str.strip(), meta_df['Name'].astype(str).str.strip()))
        except Exception as e:
            print(f"⚠️ 載入股票名冊對齊簡稱時發生錯誤: {e}")

    # ==========================================
    # 2. 初始化統計變數
    # ==========================================
    total_super_red_cases = 0     # 累計符合條件的總次數
    total_super_red_up_cases = 0  # 累計隔日真正上漲的總次數
    
    stock_details = []            # 用來存放個別股票詳細訊息的清單
    total_stocks_count = len(config.TARGET_STOCKS)

    # ==========================================
    # 3. 循環處理每檔股票
    # ==========================================
    for stock_id in config.TARGET_STOCKS:
        safe_stock_id = stock_id.replace('.', '_')
        filepath = os.path.join(config.PROCESSED_DIR, f"ma_data_{safe_stock_id}.csv")
        
        if not os.path.exists(filepath):
            print(f"找不到資料檔：{filepath}")
            continue
            
        df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
        
        # 【防呆機制】如果之前的處理漏算 Next_Day_Up，這裡自動補算
        if 'Next_Close' not in df.columns:
            df['Next_Close'] = df['Close'].shift(-1)
        if 'Next_Day_Up' not in df.columns:
            df['Next_Day_Up'] = df['Next_Close'] > df['Close']
            
        df = df.dropna(subset=['Next_Close'])
       
        # 因子條件計算
        # 1. 均量條件：若之前沒算過 5日均量，先算出來
        if 'Volume_MA5' not in df.columns:
            df['Volume_MA5'] = df['Volume'].rolling(5).mean()
        is_high_volume = df['Volume'] > (df['Volume_MA5'] * 1.1)  # 成交量大於 5日均量 1.1 倍
        
        # 2. 趨勢條件：站在 20MA 之上
        is_uptrend = df['Close'] > df['MA_20']

        # 3. 技術面 K 線型態篩選 (防呆：若無 Pattern 欄位則給全 False)
        large_red_mask = df['Pattern'].str.contains('大陽線', na=False) if 'Pattern' in df.columns else pd.Series(False, index=df.index)
        
        # 【多因子交叉篩選】：大陽線 + 爆量 + 多頭趨勢
        super_red_cases = df[large_red_mask & is_high_volume & is_uptrend]
        
        # 計算此檔股票的勝率與次數
        cases_count = len(super_red_cases)
        up_cases_count = len(super_red_cases[super_red_cases['Next_Day_Up'] == True]) if cases_count > 0 else 0
        prob_super_red = (up_cases_count / cases_count) * 100 if cases_count > 0 else 0.0
        
        # 累計到全市場總計數器
        total_super_red_cases += cases_count
        total_super_red_up_cases += up_cases_count

        # 取得公司簡稱 (先用完整代號 2330.TW 找，找不到再用純數字 2330 找)
        pure_id = stock_id.split('.')[0]
        stock_name = name_map.get(stock_id, name_map.get(pure_id, ""))
        display_name = f"{pure_id} {stock_name}".strip() if stock_name else stock_id

        # 如果選股池數量小於 10 檔，則記錄個股明細字串
        if total_stocks_count < 10:
            stock_details.append(f"🔹 **[{display_name}]** 出現 `{cases_count}` 次 ➡️ 隔日上漲率：**{prob_super_red:.2f}%**")

    # ==========================================
    # 4. 組裝與打包 Discord 訊息
    # ==========================================
    final_messages = ["**📊 台股 K 線型態與多因子勝率分析報告**\n"]
    
    # 條件分流：數量小於 10 檔才加入每檔明細
    if total_stocks_count < 10 and stock_details:
        final_messages.append("**📌 個別股票監控明細**")
        final_messages.extend(stock_details)
        final_messages.append("\n" + "─" * 20 + "\n")
        
    # 放入總體平均報告
    final_messages.append("**📈 整體多因子篩選成果**")
    final_messages.append(f"💡 策略特徵：`大陽線` + `爆量(>5MA 1.1倍)` + `多頭趨勢(20MA之上)`")
    final_messages.append(f"🗂️ 選股池總計：`{total_stocks_count}` 檔股票")
    final_messages.append(f"🔢 總型態出現次數：`{total_super_red_cases}` 次")
    
    if total_super_red_cases > 0:
        overall_prob = (total_super_red_up_cases / total_super_red_cases) * 100
        final_messages.append(f"🎯 綜合隔日平均勝率：**{overall_prob:.2f}%**")
    else:
        final_messages.append(f"🎯 綜合隔日平均勝率：**0.00%** *(此觀測區間未出現符合特徵之型態)*")
        
    # 合併成單一字串
    full_report = "\n".join(final_messages)
    print(full_report)
    
    # 確保不超過 Discord 2000 字元限制
    if len(full_report) > 1950:
        dc.send_discord_message(full_report[:1900] + "\n...(報告內容過長，已自動省略後續明細)")
    else:
        dc.send_discord_message(full_report)

if __name__ == "__main__":
    analyze_candlestick_patterns()