import pandas as pd
import matplotlib.pyplot as plt
import os

import config

def run_backtest():
    # 將字型設定移到最外面，設定一次即可
    # 支援繁體中文顯示 (如果您使用的是 Windows，通常微軟正黑體可以正常顯示)
    # 若是 Mac 用戶，請改成 ['Arial Unicode MS'] 或 ['PingFang HK']
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
    plt.rcParams['axes.unicode_minus'] = False

    # 1. 使用 for 迴圈，依序處理 config 裡面設定的每一檔股票
    for stock_id in config.TARGET_STOCKS:
        # 取得處理後的檔案路徑
        safe_stock_id = stock_id.replace('.', '_')
        processed_filename = f"ma_data_{safe_stock_id}.csv"
        processed_filepath = os.path.join(config.PROCESSED_DIR, processed_filename)
        
        # 檢查檔案是否存在
        if not os.path.exists(processed_filepath):
            print(f"⚠️ 找不到已處理的資料檔：{processed_filepath}，請先執行 2_calc_indicators.py")
            continue # 2. 如果找不到這檔股票的資料，就跳過並繼續下一檔
            
        print(f"\n開始執行 {stock_id} 的回測策略...")
        
        # 讀取 CSV
        df = pd.read_csv(processed_filepath, index_col='Date', parse_dates=True)
        
        # 刪除剛開局沒有均線數值(NaN)的日子，這樣才能正確比較均線
        df = df.dropna(subset=['MA_5', 'MA_20'])
        
        # ==========================================
        # 交易邏輯設定：5日均線與20日均線的黃金/死亡交叉
        # ==========================================
        df['Signal'] = 0
        df.loc[df['MA_5'] > df['MA_20'], 'Signal'] = 1
        
        # 計算股票每日的真實漲跌幅
        df['Daily_Return'] = df['Close'].pct_change()
        
        # 計算策略的實際報酬率
        df['Strategy_Return'] = df['Signal'].shift(1) * df['Daily_Return']
        
        # 將每天的報酬率連乘，計算出資金累積成長的曲線
        df['Cumulative_Buy_Hold'] = (1 + df['Daily_Return']).cumprod()
        df['Cumulative_Strategy'] = (1 + df['Strategy_Return']).cumprod()
        
        # ==========================================
        # 輸出文字結果與畫圖
        # ==========================================
        final_buy_hold_return = (df['Cumulative_Buy_Hold'].iloc[-1] - 1) * 100
        final_strategy_return = (df['Cumulative_Strategy'].iloc[-1] - 1) * 100
        
        print("=" * 40)
        print(f"💰 {stock_id} 買進一直抱著 (Buy & Hold) 總報酬率: {final_buy_hold_return:.2f}%")
        print(f"📈 {stock_id} 均線交叉策略 (5MA & 20MA) 總報酬率: {final_strategy_return:.2f}%")
        print("=" * 40)
        
        # 3. 迴圈內呼叫 plt.figure()，代表為當前這檔股票「建立一張獨立的新畫布」
        plt.figure(figsize=(12, 6))
        
        # 畫出兩種策略的資產曲線
        plt.plot(df.index, df['Cumulative_Buy_Hold'], label='Buy & Hold (一直抱著)', color='gray', alpha=0.7)
        plt.plot(df.index, df['Cumulative_Strategy'], label='Strategy (5MA & 20MA 交叉)', color='red', linewidth=2)
        
        # 圖表美化設定
        plt.title(f'{stock_id} 策略回測比較圖', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Cumulative Return (累積倍數)', fontsize=12)
        plt.legend(fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        
    # 4. 把 plt.show() 移到迴圈的「外面」（最後面）
    # 這樣程式就會在畫完 3 張圖之後，一口氣把它們全部彈出來
    print("\n正在繪製圖表，請查看彈出的視窗 (您可以透過滑鼠或 Alt+Tab 切換 3 張圖表)...")
    plt.show()

if __name__ == "__main__":
    run_backtest()