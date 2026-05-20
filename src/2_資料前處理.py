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

# 模組：專門處理「幅度」相關的指標
def add_漲跌幅(df):
    """
    計算每日收盤價的漲跌幅百分比 (Daily Return)
    """
    # pct_change() 會自動拿今天的 Close 減去昨天的 Close 再除以昨天的 Close
    # 乘以 100 將其轉換為百分比格式 (例如 5.2 代表漲 5.2%)
    df['漲跌幅'] = df['Close'].pct_change() * 100  
    # 填補第一天的 NaN 為 0
    df['漲跌幅'] = df['漲跌幅'].fillna(0)
    
    return df

def add_漲跌幅等級(df):
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
    return df

def add_累計漲跌幅(df, window=20):
    """計算過去 N 天內的最低 / 高點到今日收盤價的累計漲跌幅 (Run-up / Drawdown)"""
    rolling_max = df['High'].rolling(window=window, min_periods=1).max()
    rolling_min = df['Low'].rolling(window=window, min_periods=1).min()
    
    df[f'{window}日累計漲跌幅'] = np.where(
        df['Close'] >= rolling_min,
        ((df['Close'] - rolling_min) / rolling_min) * 100,  # Run-up
        ((df['Close'] - rolling_max) / rolling_max) * 100   # Drawdown
    )
    
    return df

def add_振幅(df):
    """計算每日的振幅 (Daily Range)，反映當天的波動程度"""
    df['振幅'] = ((df['High'] - df['Low']) / df['Close']) * 100
    df['振幅'] = df['振幅'].fillna(0)  # 填補 NaN 為 0
    return df

def add_振幅等級(df):
    def classify_range(pct):
        if pct > 20.0:
            return 4  # 超過 20% 的振幅，給予特別等級 4
        elif 20.0 >= pct > 15.0:
            return 3
        elif 15.0 >= pct > 10.0:
            return 2
        elif 10.0 >= pct > 5.0:
            return 1
        elif 5.0 >= pct >= 0:
            return 0
        else:
            return -1  # 不合理的振幅，給予等級 -1
        
    df['振幅等級(每10%為1級)'] = df['振幅'].apply(classify_range)
    return df

# 模組 ：專門處理「K棒型態」
def add_K棒型態_詳細版(df,shadow_threshold_min=0.2,shadow_threshold_max=0.5):
    """ 
    將 K 棒的實體大小、影線長度、實體影線相對比例特徵拆解
    命名(直觀好讀)
    1.實體紅K(無上下影線)
    實體紅K(只有上影線)
        2.實體紅K(有上影線,占整體50%以上)
        3.實體紅K(有上影線,占整體20%~50%之間)
        4.實體紅K(有上影線,占整體20%以下)
    實體紅K(只有下影線)
        5.實體紅K(有下影線,占整體50%以上)
        6.實體紅K(有下影線,占整體20%~50%之間)
        7.實體紅K(有下影線,占整體20%以下)
    .實體紅K(有上下影線)
        8.實體紅K(有上下影線,占整體50%以上,上長下短)
        9.實體紅K(有上下影線,占整體50%以上,上下等長)
        10.實體紅K(有上下影線,占整體50%以上,上短下長)
        11.實體紅K(有上下影線,占整體20%~50%之間,上長下短)
        12.實體紅K(有上下影線,占整體20%~50%之間,上下等長)
        13.實體紅K(有上下影線,占整體20%~50%之間,上短下長)
        14.實體紅K(有上下影線,占整體20%以下,上長下短)
        15.實體紅K(有上下影線,占整體20%以下,上下等長)
        16.實體紅K(有上下影線,占整體20%以下,上短下長)
    17.實體綠K(無上下影線)
    實體綠K(只有上影線)
        18.實體綠K(有上影線,占整體50%以上)
        19.實體綠K(有上影線,占整體20%~50%之間)
        20.實體綠K(有上影線,占整體20%以下)
    實體綠K(只有下影線)
        21.實體綠K(有下影線,占整體50%以上)
        22.實體綠K(有下影線,占整體20%~50%之間)
        23.實體綠K(有下影線,占整體20%以下)
    實體綠K(有上下影線)
        24.實體綠K(有上下影線,占整體50%以上,上長下短)
        25.實體綠K(有上下影線,占整體50%以上,上下等長)
        26.實體綠K(有上下影線,占整體50%以上,上短下長)
        27.實體綠K(有上下影線,占整體20%~50%之間,上長下短)
        28.實體綠K(有上下影線,占整體20%~50%之間,上下等長)
        29.實體綠K(有上下影線,占整體20%~50%之間,上短下長)
        30.實體紅K(有上下影線,占整體20%以下,上長下短)
        31.實體紅K(有上下影線,占整體20%以下,上下等長)
        32.實體紅K(有上下影線,占整體20%以下,上短下長)
    33.一字線(無上下影線)
    34.倒T字線(只有上影線)
    35.T字線(只有下影線)
    36.十字線(上下等長)
        37.十字線(上長下短) 
        38.十字線(上短下長)
    """

    # 定義K線型態的分類標籤(38項)，必須與下方 conditions 的順序一一對應
    # 與 conditions 一一對應的標籤名稱 (38項)
    choices = [
        '1.實體紅K(無上下影線)',
        '2.實體紅K(有上影線,占整體50%以上)', '3.實體紅K(有上影線,占整體20%~50%之間)', '4.實體紅K(有上影線,占整體20%以下)',
        '5.實體紅K(有下影線,占整體50%以上)', '6.實體紅K(有下影線,占整體20%~50%之間)', '7.實體紅K(有下影線,占整體20%以下)',
        '8.實體紅K(有上下影線,占整體50%以上,上長下短)', '9.實體紅K(有上下影線,占整體50%以上,上下等長)', '10.實體紅K(有上下影線,占整體50%以上,上短下長)',
        '11.實體紅K(有上下影線,占整體20%~50%之間,上長下短)', '12.實體紅K(有上下影線,占整體20%~50%之間,上下等長)', '13.實體紅K(有上下影線,占整體20%~50%之間,上短下長)',
        '14.實體紅K(有上下影線,占整體20%以下,上長下短)', '15.實體紅K(有上下影線,占整體20%以下,上下等長)', '16.實體紅K(有上下影線,占整體20%以下,上短下長)',
        '17.實體綠K(無上下影線)',
        '18.實體綠K(有上影線,占整體50%以上)', '19.實體綠K(有上影線,占整體20%~50%之間)', '20.實體綠K(有上影線,占整體20%以下)',
        '21.實體綠K(有下影線,占整體50%以上)', '22.實體綠K(有下影線,占整體20%~50%之間)', '23.實體綠K(有下影線,占整體20%以下)',
        '24.實體綠K(有上下影線,占整體50%以上,上長下短)', '25.實體綠K(有上下影線,占整體50%以上,上下等長)', '26.實體綠K(有上下影線,占整體50%以上,上短下長)',
        '27.實體綠K(有上下影線,占整體20%~50%之間,上長下短)', '28.實體綠K(有上下影線,占整體20%~50%之間,上下等長)', '29.實體綠K(有上下影線,占整體20%~50%之間,上短下長)',
        '30.實體綠K(有上下影線,占整體20%以下,上長下短)', '31.實體綠K(有上下影線,占整體20%以下,上下等長)', '32.實體綠K(有上下影線,占整體20%以下,上短下長)',
        '33.一字線(無上下影線)',
        '34.倒T字線(只有上影線)', '35.T字線(只有下影線)', '36.十字線(上下等長)', '37.十字線(上長下短)', '38.十字線(上短下長)',
    ]

    ## 複製一份資料以避免改動原始 df
    df = df.copy()
    
    ## 判斷是漲還是跌
    df['漲跌'] = df['Close'].diff() > 0

    ## 1. 解構 K 線特徵
    df['實體'] = abs(df['Close'] - df['Open'])
    df['上影線'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['下影線'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['K線幅度'] = df['High'] - df['Low']
    
    ## 計算實體 K 棒佔總長的比例 (避免遇到一字線除以 0 的錯誤)
    df['實體比例'] = np.where(df['K線幅度'] > 0, df['實體'] / df['K線幅度'], 0)

    # ---------------------------------------------------------
    # 預先定義基礎布林邏輯，讓後面的型態判斷更簡潔清晰
    # ---------------------------------------------------------
    is_red   = df['Close'] > df['Open']   # 陽線系
    is_green = df['Close'] < df['Open']   # 陰線系
    is_doji  = df['Close'] == df['Open']  # 十字線系 (實體為0)
    
    no_us = df['上影線'] == 0             # 無上影線 
    no_ls = df['下影線'] == 0             # 無下影線 
    has_us = df['上影線'] > 0             # 有上影線 
    has_ls = df['下影線'] > 0             # 有下影線
    is_flat = df['K線幅度'] == 0          # 一字線 (毫無波動)

    # --- 實體佔整體比例條件 ---
    body_large = df['實體比例'] >= shadow_threshold_max
    body_mid   = (df['實體比例'] >= shadow_threshold_min) & (df['實體比例'] < shadow_threshold_max)
    body_small = df['實體比例'] < shadow_threshold_min

    # --- 影線相對長度條件 ---
    us_longer = df['上影線'] > df['下影線']
    ls_longer = df['下影線'] > df['上影線']
    shadows_equal = df['上影線'] == df['下影線']

    # ---------------------------------------------------------
    # 定義型態條件 (嚴格對應您的 1~38 項分類)
    # ---------------------------------------------------------
    conditions = [

        # === 陽線系列 (Close > Open) ===
        is_red & no_us & no_ls,                                     # 1. 實體紅K(無上下影線)
        is_red & has_us & no_ls & body_large,                       # 2. 只有上影線, 實體≥50%
        is_red & has_us & no_ls & body_mid,                         # 3. 只有上影線, 實體20%~50%
        is_red & has_us & no_ls & body_small,                       # 4. 只有上影線, 實體<20%
        is_red & no_us & has_ls & body_large,                       # 5. 只有下影線, 實體≥50%
        is_red & no_us & has_ls & body_mid,                         # 6. 只有下影線, 實體20%~50%
        is_red & no_us & has_ls & body_small,                       # 7. 只有下影線, 實體<20%
        is_red & has_us & has_ls & body_large & us_longer,          # 8. 有上下影線, 實體≥50%, 上長下短
        is_red & has_us & has_ls & body_large & shadows_equal,      # 9. 有上下影線, 實體≥50%, 上下等長
        is_red & has_us & has_ls & body_large & ls_longer,          # 10. 有上下影線, 實體≥50%, 上短下長
        is_red & has_us & has_ls & body_mid & us_longer,            # 11. 有上下影線, 實體20~50%, 上長下短
        is_red & has_us & has_ls & body_mid & shadows_equal,        # 12. 有上下影線, 實體20~50%, 上下等長
        is_red & has_us & has_ls & body_mid & ls_longer,            # 13. 有上下影線, 實體20~50%, 上短下長
        is_red & has_us & has_ls & body_small & us_longer,          # 14. 有上下影線, 實體<20%, 上長下短
        is_red & has_us & has_ls & body_small & shadows_equal,      # 15. 有上下影線, 實體<20%, 上下等長
        is_red & has_us & has_ls & body_small & ls_longer,          # 16. 有上下影線, 實體<20%, 上短下長

        # === 陰線系列 (Close < Open) ===
        is_green & no_us & no_ls,                                   # 17. 實體綠K(無上下影線)
        is_green & has_us & no_ls & body_large,                     # 18. 只有上影線, 實體≥50%
        is_green & has_us & no_ls & body_mid,                       # 19. 只有上影線, 實體20%~50%
        is_green & has_us & no_ls & body_small,                     # 20. 只有上影線, 實體<20%
        is_green & no_us & has_ls & body_large,                     # 21. 只有下影線, 實體≥50%
        is_green & no_us & has_ls & body_mid,                       # 22. 只有下影線, 實體20%~50%
        is_green & no_us & has_ls & body_small,                     # 23. 只有下影線, 實體<20%
        is_green & has_us & has_ls & body_large & us_longer,        # 24. 有上下影線, 實體≥50%, 上長下短
        is_green & has_us & has_ls & body_large & shadows_equal,    # 25. 有上下影線, 實體≥50%, 上下等長
        is_green & has_us & has_ls & body_large & ls_longer,        # 26. 有上下影線, 實體≥50%, 上短下長
        is_green & has_us & has_ls & body_mid & us_longer,          # 27. 有上下影線, 實體20~50%, 上長下短
        is_green & has_us & has_ls & body_mid & shadows_equal,      # 28. 有上下影線, 實體20~50%, 上下等長
        is_green & has_us & has_ls & body_mid & ls_longer,          # 29. 有上下影線, 實體20~50%, 上短下長
        is_green & has_us & has_ls & body_small & us_longer,        # 30. 有上下影線, 實體<20%, 上長下短
        is_green & has_us & has_ls & body_small & shadows_equal,    # 31. 有上下影線, 實體<20%, 上下等長
        is_green & has_us & has_ls & body_small & ls_longer,        # 32. 有上下影線, 實體<20%, 上短下長
  
        # === 特殊：一字線 ===
        is_flat,                                                    # 33. 一字線(無上下影線)
        
        # === 十字線系列 (實體為 0) ===
        is_doji & no_ls & has_us,                                   # 34. 倒T字線(只有上影線)
        is_doji & no_us & has_ls,                                   # 35. T字線(只有下影線)
        is_doji & has_us & has_ls & shadows_equal,                  # 36. 十字線(上下等長)
        is_doji & has_us & has_ls & us_longer,                      # 37. 十字線(上長下短)
        is_doji & has_us & has_ls & ls_longer,                      # 38. 十字線(上短下長)
    ]

    

    # 將條件與標籤映射到新欄位，防呆預設值為 '問題K線'
    df['K線型態'] = np.select(conditions, choices, default='問題K線')

    return df

def add_K棒型態_簡易版(df, shadow_threshold=0.5):
    """
    將 K 棒型態精簡為 12 種最具統計意義的經典分類。
    包含：一字線、十字線家族、大實體K線、長影線K線、一般紡錘線。
    """
    df = df.copy()
    
    ## 判斷是漲還是跌
    df['漲跌'] = df['Close'].diff() > 0

    ## 1. 解構 K 線特徵
    df['實體'] = abs(df['Close'] - df['Open'])
    df['上影線'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['下影線'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['K線幅度'] = df['High'] - df['Low']
    
    ## 計算實體 K 棒佔總長的比例
    df['實體比例'] = np.where(df['K線幅度'] > 0, df['實體'] / df['K線幅度'], 0)

    # ---------------------------------------------------------
    # 基礎布林邏輯
    # ---------------------------------------------------------
    is_red   = df['Close'] > df['Open']
    is_green = df['Close'] < df['Open']
    is_doji  = df['Close'] == df['Open']
    is_flat  = df['K線幅度'] == 0
    
    # 核心特徵定義：
    # 大實體：實體佔整體波動 50% 以上
    body_large = df['實體比例'] >= shadow_threshold 
    
    # 長上影線：上影線大於下影線，且上影線長度大於實體 (避雷針/倒槌)
    us_long = (df['上影線'] > df['下影線']) & (df['上影線'] > df['實體'])
    
    # 長下影線：下影線大於上影線，且下影線長度大於實體 (槌子/吊人)
    ls_long = (df['下影線'] > df['上影線']) & (df['下影線'] > df['實體'])

    # ---------------------------------------------------------
    # 定義條件 (由嚴格到寬鬆，np.select 會由上往下匹配)
    # ---------------------------------------------------------
    conditions = [
        # === 特殊：一字線 ===
        is_flat,                                           

        # === 十字線系列 (實體為 0) ===
        is_doji & (df['上影線'] == 0) & (df['下影線'] > 0),  # T字線
        is_doji & (df['下影線'] == 0) & (df['上影線'] > 0),  # 倒T字線
        is_doji,                                           # 十字線 (兜底)

        # === 陽線系列 ===
        is_red & body_large,                               # 實體紅K (大陽線)
        is_red & us_long,                                  # 長上影線紅K
        is_red & ls_long,                                  # 長下影線紅K
        is_red,                                            # 一般紅K (紡錘線，兜底)

        # === 陰線系列 ===
        is_green & body_large,                             # 實體綠K (大陰線)
        is_green & us_long,                                # 長上影線綠K
        is_green & ls_long,                                # 長下影線綠K
        is_green                                           # 一般綠K (紡錘線，兜底)
    ]

    choices = [
        '01.一字線',
        '02.T字線', '03.倒T字線', '04.十字線',
        '05.實體紅K(大陽線)', '08.長上影線紅K', '06.長下影線紅K', '07.紅K',
        '09.實體綠K(大陰線)', '12.長上影線綠K', '10.長下影線綠K', '11.綠K'
    ]

    df['K線型態(簡化)'] = np.select(conditions, choices, default='未知')

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

def DROP_UNNECESSARY_COLUMNS(df):
    """如果有一些不必要的欄位想丟掉，可以在這裡統一處理，保持主程式的簡潔"""
    # 刪除臨時計算欄位以保持資料清潔 (如果不需要保留實體、影線等中間計算結果，可以取消註解以下程式碼)
    df.drop(
        columns=['實體', '上影線', '下影線', 'K線幅度', '實體比例',],
        inplace=True, errors='ignore')
    return df

def ADD_ALL_INDICATORS(df):
    """一個函式把所有指標一次算好，讓主程式呼叫更簡潔"""
    df = preprocess_data(df)
    df = add_K棒型態_簡易版(df)  # 先算 K 棒型態，因為後面可能會用到漲跌幅等級來判斷影線長短
    df = add_漲跌幅(df)
    df = add_振幅(df)
    # df = add_ma_indicators(df)
    df = add_volume_ma_indicators(df)
    # df = add_ema_indicators(df)
    # df = add_macd_indicators(df)
    # df = add_kd_indicators(df)
    return df

#############################################################################

# 主程式：負責控制流程與讀寫檔案
def process_all_stocks():
    # 確保處理後的資料夾存在，避免存檔時出錯
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    
    # 依序處理每一檔股票的資料
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