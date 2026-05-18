import pandas as pd
import numpy as np
import os
import config

# key值設定：
# (請使用中文，保持與 CSV 欄位一致，方便後續分析，記得用中文註解說明每個指標的定義與計算方式)
# (打程式時記得加入 utf-8 編碼註解，確保中文不會亂碼) 
# 漲跌幅 (Daily Return): 今天的收盤價與昨天的收盤價相比的百分比變化。
# 漲跌幅等級 (Return Class): 根據漲跌幅的大小各分成5個等級，正負分開。
# N日累計漲跌幅 (Run-up / Drawdown): 過去 N 天內的最低 / 高點到今日收盤價的百分比變化。
# K線型態 (Candlestick Pattern): 根據 K 線的實體大小、影線長度和漲跌幅等級，定義不同的型態分類，例如大陽線、十字星、槌子線等。


# ⚠️資料預處理 (刪除成交量為0的資料欄，也就是當天放假的資料)
def preprocess_data(df):
    """傳入原始 DataFrame，刪除成交量為0的資料列，回傳清理後的 DataFrame"""
    df = df[df['Volume'] > 0].copy()  # 只保留成交量大於0的資料列
    df.reset_index(inplace=True)  # 重置索引，讓日期成為一個普通欄位
    return df


# 幫我加上紅色k棒 綠色K棒貼圖: 
# 模組 ：專門處理「K棒型態」
def add_K棒型態_v3(df):
    """ 將 K 棒的實體大小、影線長度等特徵與漲跌幅等級結合，定義更細緻的型態分類規則
    定義：
    陽線：只有實體K棒，完全沒有影線
    光頭紅K：只有實體K棒和下影線，且實體K棒長度佔總長40%以上
    光腳紅K：只有實體K棒和上影線，且實體K棒長度佔總長40%以上
    紡錘紅K：只有實體K棒和下影線，0%<實體K棒長度佔總長<=40%
    倒錘紅K：只有實體K棒和上影線，0%<實體K棒長度佔總長<=40%
    一般紅K：有實體K棒，且實體K棒長度佔總長>0%，但不符合上述其他型態定義
    陰線：只有實體K棒，完全沒有影線
    光頭綠K：只有實體K棒和下影線，且實體K棒長度佔總長40%以上
    光腳綠K：只有實體K棒和上影線，且實體K棒長度佔總長40%以上
    紡錘綠K：只有實體K棒和下影線，0%<實體K棒長度佔總長<=40%
    倒錘綠K：只有實體K棒和上影線，0%<實體K棒長度佔總長<=40%
    一般陰線: 有實體K棒，且實體K棒長度佔總長>0%，但不符合上述其他型態定義
    十字線：實體K棒長度佔總長0%，不論有無影線都歸類為十字線
    長脖十字線:上影線>下影線，且實體K棒長度佔總長0%
    長腳十字線:下影線>上影線，且實體K棒長度佔總長0%
    T字線:只有下影線，沒有上影線，且實體K棒長度佔總長0%
    倒T字線:只有上影線，沒有下影線，且實體K棒長度佔總長0%
    一字線: 開盤價=收盤價=最高價=最低價，完全沒有實體和影線
    """

    ## 複製一份資料以避免改動原始 df
    df = df.copy()
   
    ## 判斷是漲還是跌
    df['漲跌'] = df['Close'].diff() > 0

    ## 1. 解構K線型態
    df['實體'] = abs(df['Close'] - df['Open'])
    df['上影線'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['下影線'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['K線範圍'] = df['High'] - df['Low']
    
    ## 計算實體 K 棒佔總長的比例 (避免遇到一字線除以 0 的錯誤)
    df['實體比例'] = np.where(df['K線範圍'] > 0, df['實體'] / df['K線範圍'], 0)

    # ---------------------------------------------------------
    # 預先定義基礎布林邏輯，讓後面的型態判斷更簡潔清晰
    # ---------------------------------------------------------
    is_red   = df['Close'] > df['Open']   # 陽線系
    is_green = df['Close'] < df['Open']   # 陰線系
    is_doji  = df['Close'] == df['Open']  # 十字線系 (實體為0)
    
    no_us = df['上影線'] == 0       # 無上影線 (no upper shadow)
    no_ls = df['下影線'] == 0       # 無下影線 (no lower shadow)
    has_us = df['上影線'] > 0       # 有上影線 
    has_ls = df['下影線'] > 0       # 有下影線
    is_flat = df['K線範圍'] == 0      # 一字線 (毫無波動)

    # ---------------------------------------------------------
    # 定義型態條件 (注意：np.select 會由上往下匹配，越嚴格的條件要放越上面)
    # ---------------------------------------------------------
    conditions = [
        # === 特殊：一字線 ===
        is_flat,
        
        # === 十字線系列 (Body == 0) ===
        is_doji & no_us & has_ls,                            # T字線
        is_doji & no_ls & has_us,                            # 倒T字線
        is_doji & (df['上影線'] > df['下影線']), # 長脖十字線
        is_doji & (df['下影線'] > df['上影線']), # 長腳十字線
        is_doji,                                             # 十字線 (兜底：包含上下影線等長)

        # === 陽線系列 (Close > Open) ===
        is_red & no_us & no_ls,                              # 陽線 (純粹無影線)
        is_red & no_us & has_ls & (df['實體比例'] >= 0.4),   # 光頭紅K
        is_red & no_ls & has_us & (df['實體比例'] >= 0.4),   # 光腳紅K
        is_red & no_us & has_ls & (df['實體比例'] < 0.4),    # 紡錘紅K (實體<=40%)
        is_red & no_ls & has_us & (df['實體比例'] < 0.4),    # 倒錘紅K (實體<=40%)
        is_red,                                              # 一般紅K (兜底：同時有上下影線，或比例不符)

        # === 陰線系列 (Close < Open) ===
        is_green & no_us & no_ls,                            # 陰線 (純粹無影線)
        is_green & no_us & has_ls & (df['實體比例'] >= 0.4), # 光頭綠K
        is_green & no_ls & has_us & (df['實體比例'] >= 0.4), # 光腳綠K
        is_green & no_us & has_ls & (df['實體比例'] < 0.4),  # 紡錘綠K (實體<=40%)
        is_green & no_ls & has_us & (df['實體比例'] < 0.4),  # 倒錘綠K (實體<=40%)
        is_green                                             # 一般陰線 (兜底：同時有上下影線，或比例不符)
    ]

    # 與 conditions 一一對應的標籤名稱
    choices = [
        '一字線',
        'T字線', '倒T字線', '長脖十字線', '長腳十字線', '十字線',
        '陽線', '光頭紅K', '光腳紅K', '紡錘紅K', '倒錘紅K', '一般紅K',
        '陰線', '光頭綠K', '光腳綠K', '紡錘綠K', '倒錘綠K', '一般陰線'
    ]

    # 將條件與標籤映射到新欄位，防呆預設值為'未知'
    df['K線型態'] = np.select(conditions, choices, default='未知')

    return df

# 幫我加上漲跌幅貼圖:  
# 模組 : 專門處理漲跌幅相關數據
def add_每日漲跌幅(df, window=20):
    """
    1.計算每日收盤價的漲跌幅百分比 (Daily Return)
    2.將漲幅幅度做分類,分成5個等級
    (10%>=幅度>8%:5, 8%>=幅度>6%:4, 6%>=幅度>4%:3, 4%>=幅度>2%:2, 2%>=幅度>0%:1)
      ,反之,跌幅也分成5個等級
    (0%>=幅度>-2%:-1, -2%>=幅度>-4%:-2, -4%>=幅度>-6%:-3, -6%>=幅度>-8%:-4, -8%>=幅度>-10%:-5)
    3.計算過去 N 天內的最低 / 高點到今日收盤價的累計漲跌幅 (Run-up / Drawdown)
    """

    ## 1. 計算每日漲跌幅百分比
    # pct_change() 會自動拿今天的 Close 減去昨天的 Close 再除以昨天的 Close
    # 乘以 100 將其轉換為百分比格式 (例如 5.2 代表漲 5.2%)
    df['漲跌幅'] = df['Close'].pct_change() * 100  
    # 填補第一天的 NaN 為 0
    df['漲跌幅'] = df['漲跌幅'].fillna(0)
    
    ## 2. 漲跌幅等級分類
    def classify_return(pct):
        if  pct > 10.0:
            return 6  # 超過 10% 的漲幅 (正2的股票)，給予特別等級 6
        elif 10.0 >= pct > 8.0:
            return 5
        elif 8.0 >= pct > 6.0:
            return 4
        elif 6.0 >= pct > 4.0:
            return 3
        elif 4.0 >= pct > 2.0:
            return 2
        elif 2.0 >= pct > 0:
            return 1
        elif pct == 0:
            return 0  # 漲跌幅為 0%，給予等級 0
        elif 0 > pct > -2.0:
            return -1
        elif -2.0 >= pct > -4.0:
            return -2
        elif -4.0 >= pct > -6.0:
            return -3
        elif -6.0 >= pct > -8.0:
            return -4
        elif -8.0 >= pct > -10.0:
            return -5
        elif -10.0 >= pct:
            return -6  # 超過-10%的跌幅 (正2的股票)，給予特別等級 -6
        
    df['漲跌幅等級'] = df['漲跌幅'].apply(classify_return)


    ## 3.計算過去 N 天內（預設20天）的最低/高點，到今日收盤價的累計漲/跌幅 (Run-up / Drawdown)
    # 找出過去 window 天內的最低價和最高價，並預先建立欄位以避免後續計算時出現 KeyError
    rolling_max = df['High'].rolling(window=window, min_periods=1).max()
    rolling_min = df['Low'].rolling(window=window, min_periods=1).min()
    if f'{window}日累計漲跌幅' not in df.columns:
        #建立空欄位以避免後續計算時出現 KeyError
        df[f'{window}日累計漲跌幅'] = np.nan

    # 今日收盤價與最低價和最高價做比較，決定是計算漲幅還是跌幅
    if df['Close'].iloc[-1] >= rolling_min.iloc[-1]:
        # 如果今天的收盤價高於過去 window 天的最低價，計算漲幅 (Run-up)
        df[f'{window}日累計漲跌幅'] = ((df['Close'] - rolling_min) / rolling_min) * 100
    else:
        # 如果今天的收盤價低於過去 window 天的最高價，計算跌幅 (Drawdown)
        df[f'{window}日累計漲跌幅'] = ((df['Close'] - rolling_max) / rolling_max) * 100

    return df


# 模組 ：專門處理「價格均線計算」
def add_ma_indicators(df):
    """傳入 DataFrame，計算好均線後回傳"""
    # 使用迴圈讓計算更簡潔，消除重複的 rolling 程式碼
    ma_windows = [5, 10, 20, 60, 120, 240]
    for window in ma_windows:
        df[f'MA_{window}'] = df['Close'].rolling(window=window).mean()
    return df
# 模組：專門處理「成交量均線計算」 (如果未來想算成交量的均線，直接寫在這裡就好，保持結構清晰)
def add_volume_ma_indicators(df):
    """傳入 DataFrame，計算好成交量的均線後回傳"""
    volume_ma_windows = [5, 10, 20]
    for window in volume_ma_windows:
        df[f'Volume_MA_{window}'] = df['Volume'].rolling(window=window).mean()
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

# 模組: 乖離率(bias)計算 (如果未來想算其他類型的乖離率，直接寫在這裡就好，保持結構清晰)
def add_biass_indicators(df):
    """傳入 DataFrame，計算好乖離率後回傳"""
    bias_windows = [5, 10, 20, 60]
    for window in bias_windows:
        df[f'BIAS_{window}'] = ((df['Close'] - df[f'MA_{window}']) / df[f'MA_{window}']) * 100
    return df

#####

def ADD_ALL_INDICATORS(df):
    """一個函式把所有指標一次算好，讓主程式呼叫更簡潔"""
    df = preprocess_data(df)
    df = add_K棒型態_v3(df)
    df = add_每日漲跌幅(df)
    df = add_ma_indicators(df)
    df = add_volume_ma_indicators(df)
    # df = add_ema_indicators(df)
    # df = add_macd_indicators(df)
    # df = add_kd_indicators(df)
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
        df = ADD_ALL_INDICATORS(df)
        
        # 步驟三：只存檔一次
        processed_filepath = os.path.join(config.PROCESSED_DIR, f"ma_data_{safe_stock_id}.csv")
        df.to_csv(processed_filepath, encoding='utf-8-sig')  # 使用 utf-8-sig 編碼確保 Excel 打開不亂碼
        print(f"✅ {stock_id} 所有指標與型態計算完成並存檔！\n")

if __name__ == "__main__":
    process_all_stocks()