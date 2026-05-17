import pandas as pd
import numpy as np
import os
import config

# 模組 : 專門處理漲跌幅相關數據
def add_每日漲跌幅(df, window=20):
    """
    計算每日收盤價的漲跌幅百分比 (Daily Return)
    """
    # pct_change() 會自動拿今天的 Close 減去昨天的 Close 再除以昨天的 Close
    # 乘以 100 將其轉換為百分比格式 (例如 5.2 代表漲 5.2%)
    df['Daily_Return_Pct'] = df['Close'].pct_change() * 100
    
    # 填補第一天的 NaN 為 0
    df['Daily_Return_Pct'] = df['Daily_Return_Pct'].fillna(0)
    

    #計算過去 N 天內（預設20天）的最高點，到今日收盤價的累計跌幅 (Drawdown)
    # 找出過去 window 天內的最高價（通常波段高點看 'High'，若您只看收盤價可改為 'Close'）
    # min_periods=1 代表就算資料筆數不足 20 天，也會以現有的天數取最高
    rolling_max = df['High'].rolling(window=window, min_periods=1).max()  
    # 計算公式：(今日收盤價 - 區間最高價) / 區間最高價 * 100
    # 注意：算出來通常會是負數（代表跌幅），如果今天創新高，則數值為 0 或正數（如果看收盤與盤中高的差距）
    df[f'Drawdown_{window}D_Pct'] = ((df['Close'] - rolling_max) / rolling_max) * 100
    
    # 計算過去 N 天內（預設20天）的最低點，到今日收盤價的累計漲幅 (Run-up)
    # 找出過去 window 天內的最低價
    rolling_min = df['Low'].rolling(window=window, min_periods=1).min()
    # 計算公式：(今日收盤價 - 區間最低價) / 區間最低價 * 100
    # 算出來通常為正數，代表相較於波段低點，目前已經反彈/上漲了多少百分比
    df[f'Runup_{window}D_Pct'] = ((df['Close'] - rolling_min) / rolling_min) * 100

    return df

# 模組 ：專門處理「K棒型態」
def add_K棒型態(df, 
                           large_body_pct=3.0, 
                           doji_body_pct=0.3, 
                           shadow_multiplier=2.0):
    """
    傳入 DataFrame，計算包含上下影線與實體大小的客製化 K 棒型態。
    
    參數 (可客製化調整):
    - large_body_pct: 實體佔開盤價幾 % 以上視為「大陽/大陰線」(預設 3%)
    - doji_body_pct: 實體小於幾 % 視為「十字線」(預設 0.3%)
    - shadow_multiplier: 影線長度必須是實體的「幾倍」才算長影線 (預設 2倍)
    """
    
    # ==========================================
    # 1. 基礎距離與長度計算
    # ==========================================
    df['Body'] = df['Close'] - df['Open']
    df['Abs_Body'] = df['Body'].abs()  # 實體絕對長度
    df['Body_Pct'] = (df['Abs_Body'] / df['Open']) * 100 
    
    # 計算上下影線長度 (利用 max 和 min 找出實體上下緣)
    # df[['Open', 'Close']].max(axis=1) 會抓出每一列開盤與收盤較高的那個值
    df['Upper_Shadow'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['Lower_Shadow'] = df[['Open', 'Close']].min(axis=1) - df['Low']

    # ==========================================
    # 2. 條件判斷標籤 (布林值)
    # ==========================================
    df['Is_Red'] = df['Close'] > df['Open']      # 收紅
    
    # 實體條件
    df['Is_Large_Body'] = df['Body_Pct'] >= large_body_pct
    df['Is_Doji'] = df['Body_Pct'] <= doji_body_pct
    
    # 影線條件：影線長度 > (實體長度 * 倍數)
    # 加上一個極小值 (1e-5) 是為了防止十字線時實體為 0 導致錯誤
    df['Has_Long_Upper'] = df['Upper_Shadow'] > (df['Abs_Body'] * shadow_multiplier + 1e-5)
    df['Has_Long_Lower'] = df['Lower_Shadow'] > (df['Abs_Body'] * shadow_multiplier + 1e-5)

    # ==========================================
    # 3. 綜合型態判斷邏輯 (實體混搭影線)
    # ==========================================
    def get_complex_pattern(row):
        # 狀況 A：十字線家族
        if row['Is_Doji']:
            if row['Lower_Shadow'] > row['Upper_Shadow'] * 3:
                return '蜻蜓十字 (長下影)'
            elif row['Upper_Shadow'] > row['Lower_Shadow'] * 3:
                return '墓碑十字 (長上影)'
            else:
                return '一般十字線'
                
        # 決定顏色稱呼
        color = "紅" if row['Is_Red'] else "黑"

        # 狀況 B：帶有長影線的反轉型態
        if row['Has_Long_Upper'] and not row['Has_Long_Lower']:
            return f'長上影線{color}實體 (避雷針)'
            
        if row['Has_Long_Lower'] and not row['Has_Long_Upper']:
            return f'長下影線{color}實體 (槌子線)'
            
        if row['Has_Long_Upper'] and row['Has_Long_Lower']:
            return f'上下長影線{color}實體 (紡錘線)'

        # 狀況 C：無明顯長影線，依實體大小判斷
        if row['Is_Large_Body']:
            return f'大{color}線'
            
        return f'一般{color}線'
            
    # 套用判斷邏輯
    df['Pattern'] = df.apply(get_complex_pattern, axis=1)
    
    # ==========================================
    # 4. 計算隔日是否上漲與欄位清理
    # ==========================================
    df['Next_Close'] = df['Close'].shift(-1)
    df['Next_Day_Up'] = df['Next_Close'] > df['Close']
    
    # 清除運算過程產生的過渡欄位，讓 CSV 保持乾淨
    cols_to_drop = ['Abs_Body', 'Is_Red', 'Is_Large_Body', 'Is_Doji', 'Has_Long_Upper', 'Has_Long_Lower']
    df.drop(columns=cols_to_drop, inplace=True)
    
    return df

def add_K棒型態_v2(df, large_body_pct=4.5, doji_pct=0.3, shadow_mult=2.0):
    """
    計算單根 K 棒的 16 種基本型態，並結合每日漲跌幅。
    
    參數:
      df: 包含 Open, High, Low, Close 的 DataFrame
      large_body_pct: 實體佔開盤價的百分比，大於此值視為「大陽/大陰線」(預設 4.5%)
      doji_pct: 實體佔開盤價的百分比，小於此值視為「十字星」(預設 0.3%)
      shadow_mult: 影線長度必須是實體的幾倍，才算是「長影線」(預設 2.0 倍)
    """
    # 複製一份資料以避免改動原始 df
    df = df.copy()

    # --- 1. 新增：每日漲跌幅 ---
    # 使用前一天的收盤價計算今天的漲跌幅 (%)
    df['Daily_Return_Pct'] = df['Close'].pct_change() * 100

    # --- 2. K棒基礎解構 (絕對數值) ---
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Upper_Shadow'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['Lower_Shadow'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['Total_Range'] = df['High'] - df['Low']
    
    # 實體佔股價的百分比 (用來判斷是否為大實體或十字星)
    df['Body_Pct'] = (df['Body'] / df['Open']) * 100

    # 判斷顏色
    df['Color'] = np.where(df['Close'] > df['Open'], '紅',
                  np.where(df['Close'] < df['Open'], '綠', '平'))

    # --- 3. 設定邏輯遮罩 (Masks) ---
    is_doji = df['Body_Pct'] <= doji_pct                 # 實體極小
    is_large_body = df['Body_Pct'] >= large_body_pct     # 實體很大
    
    # 為了避免除以 0，改用乘法來判斷影線比例
    has_long_upper = df['Upper_Shadow'] >= (df['Body'] * shadow_mult)
    has_long_lower = df['Lower_Shadow'] >= (df['Body'] * shadow_mult)
    
    # 幾乎沒有影線 (光頭/光腳)
    no_upper = df['Upper_Shadow'] <= (df['Open'] * 0.001) 
    no_lower = df['Lower_Shadow'] <= (df['Open'] * 0.001)

    # 初始化預設值
    df['Pattern'] = '一般型態'

    # --- 4. 開始標註 16 種型態 (條件從嚴格到寬鬆) ---

    # (1) 一字線 (開盤=收盤=最高=最低，漲跌停常見)
    df.loc[(df['Total_Range'] == 0), 'Pattern'] = '一字線'

    # (2-4) 十字星家族
    df.loc[is_doji & no_upper & (df['Lower_Shadow'] > 0), 'Pattern'] = '蜻蜓十字'
    df.loc[is_doji & no_lower & (df['Upper_Shadow'] > 0), 'Pattern'] = '墓碑十字'
    df.loc[is_doji & has_long_upper & has_long_lower, 'Pattern'] = '長腳十字'
    df.loc[is_doji & (df['Pattern'] == '一般型態'), 'Pattern'] = '一般十字星'

    # (5-8) 極端無影線大K棒
    df.loc[is_large_body & (df['Color'] == '紅') & no_upper & no_lower, 'Pattern'] = '光頭光腳大陽線'
    df.loc[is_large_body & (df['Color'] == '綠') & no_upper & no_lower, 'Pattern'] = '光頭光腳大陰線'
    df.loc[is_large_body & (df['Color'] == '紅') & has_long_upper & no_lower, 'Pattern'] = '光腳長上影大陽線'
    df.loc[is_large_body & (df['Color'] == '綠') & no_upper & has_long_lower, 'Pattern'] = '光頭長下影大陰線'

    # (9-12) 帶影線的中小實體 (槌子、流星、吊人線)
    # 紅色
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '紅') & has_long_lower & ~has_long_upper, 'Pattern'] = '下影陽線(槌子/吊人)'
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '紅') & has_long_upper & ~has_long_lower, 'Pattern'] = '上影陽線(倒槌/流星)'
    # 綠色
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '綠') & has_long_lower & ~has_long_upper, 'Pattern'] = '下影陰線'
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '綠') & has_long_upper & ~has_long_lower, 'Pattern'] = '上影陰線'

    # (13-14) 紡錘線 (上下影線皆長，實體不大)
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '紅') & has_long_upper & has_long_lower, 'Pattern'] = '紅紡錘線'
    df.loc[~is_large_body & ~is_doji & (df['Color'] == '綠') & has_long_upper & has_long_lower, 'Pattern'] = '綠紡錘線'

    # (15-16) 剩下的大陽線與大陰線 (帶有普通長度的影線)
    df.loc[is_large_body & (df['Color'] == '紅') & (df['Pattern'] == '一般型態'), 'Pattern'] = '大陽線'
    df.loc[is_large_body & (df['Color'] == '綠') & (df['Pattern'] == '一般型態'), 'Pattern'] = '大陰線'

    # --- 5. 清理過渡計算用的欄位 (保持 CSV 乾淨) ---
    df.drop(columns=['Body', 'Upper_Shadow', 'Lower_Shadow', 'Total_Range', 'Body_Pct'], inplace=True)

    return df

# 模組 ：專門處理「價格均線計算」
def add_ma_indicators(df):
    """傳入 DataFrame，計算好均線後回傳"""
    # 使用迴圈讓計算更簡潔，消除重複的 rolling 程式碼
    ma_windows = [5, 10, 20, 60, 120, 240]
    for window in ma_windows:
        df[f'MA_{window}'] = df['Close'].rolling(window=window).mean()
    return df

# 模組 ：專門處理「EMA、MACD、KD 指標計算」
def add_ema_indicators(df):
    """傳入 DataFrame，計算好 EMA 均線後回傳"""
    ema_windows = [12, 26]
    for window in ema_windows:
        df[f'EMA_{window}'] = df['Close'].ewm(span=window, adjust=False).mean()
    return df
def add_macd_indicators(df):
    """傳入 DataFrame，計算好 MACD 後回傳"""
    # 計算 EMA12 和 EMA26
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # 計算 MACD 線和 Signal 線
    df['MACD_Line'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()
    
    return df
def add_kd_indicators(df):
    """傳入 DataFrame，計算好 KD 指標後回傳"""
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = df['RSV'].ewm(span=3, adjust=False).mean()
    df['D'] = df['K'].ewm(span=3, adjust=False).mean()
    
    return df

#####
# 模組：專門處理「成交量均線計算」 (如果未來想算成交量的均線，直接寫在這裡就好，保持結構清晰)
def add_volume_ma_indicators(df):
    """傳入 DataFrame，計算好成交量的均線後回傳"""
    volume_ma_windows = [5, 10, 20]
    for window in volume_ma_windows:
        df[f'Volume_MA_{window}'] = df['Volume'].rolling(window=window).mean()
    return df


def add_all_indicators(df):
    """一個函式把所有指標一次算好，讓主程式呼叫更簡潔"""
    df = add_每日漲跌幅(df)
    df = add_ma_indicators(df)
    df = add_K棒型態_v2(df)
    df = add_ema_indicators(df)
    df = add_macd_indicators(df)
    df = add_kd_indicators(df)
    df = add_volume_ma_indicators(df)
    return df

#############################################################################

# 主程式：負責控制流程與讀寫檔案
def process_all_stocks():
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    
    for stock_id in config.TARGET_STOCKS:
        safe_stock_id = stock_id.replace('.', '_')
        raw_filepath = os.path.join(config.RAW_DIR, f"raw_data_{safe_stock_id}.csv")
        
        if not os.path.exists(raw_filepath):
            print(f"找不到原始資料檔：{raw_filepath}，跳過處理。")
            continue
            
        print(f"開始計算 {stock_id} 的各項指標...")
        
        # 步驟一：只讀取一次資料
        df = pd.read_csv(raw_filepath, index_col='Date', parse_dates=True)
        
        # 步驟二：像流水線一樣，依序掛上指標模組
        df = add_每日漲跌幅(df)
        df = add_ma_indicators(df)
        df = add_K棒型態_v2(df)
        df = add_ema_indicators(df)
        df = add_macd_indicators(df)
        df = add_kd_indicators(df)
        df = add_volume_ma_indicators(df)
        
        # 步驟三：只存檔一次
        processed_filepath = os.path.join(config.PROCESSED_DIR, f"ma_data_{safe_stock_id}.csv")
        df.to_csv(processed_filepath)
        print(f"✅ {stock_id} 所有指標與型態計算完成並存檔！\n")

if __name__ == "__main__":
    process_all_stocks()