import yfinance as yf
import pandas as pd
import os

def fetch_and_save_stock_data(stock_id, start_date, end_date, filename="stock_data.csv"):
    """
    抓取台股資料並儲存為 CSV 檔
    """
    # 台股代號在 yfinance 的格式為 "代號.TW" (上市) 或 "代號.TWO" (上櫃)
    # 這裡以台積電 (2330) 為例，上市股票加上 .TW
    ticker = f"{stock_id}.TW" 
    
    print(f"開始抓取 {ticker} 從 {start_date} 到 {end_date} 的資料...")
    try:
        # 使用 yfinance 抓取資料
        stock = yf.download(ticker, start=start_date, end=end_date)
        
        if stock.empty:
            print("抓取不到資料，請檢查代號或日期設定。")
            return False

        # --- 新增這段來處理 yfinance 新版的 MultiIndex 欄位結構 ---
        if isinstance(stock.columns, pd.MultiIndex):
            # 攤平欄位，只取第一層 (如 'Close', 'Volume')，捨棄股票代號層
            stock.columns = stock.columns.get_level_values(0)
        # -------------------------------------------------------------

        # 將資料存成 CSV 檔
        stock.to_csv(filename)
        print(f"資料已成功儲存至 {filename}")
        return True
    
    except Exception as e:
        print(f"發生錯誤: {e}")
        return False

def calculate_and_save_moving_averages(input_filename="stock_data.csv", output_filename="stock_ma_data.csv", windows=[5, 10, 20]):
    """
    讀取 CSV 檔，計算均線，並儲存結果
    """
    if not os.path.exists(input_filename):
        print(f"找不到檔案 {input_filename}，請先抓取資料。")
        return False

    print(f"開始讀取 {input_filename} 並計算均線...")
    
    # 讀取 CSV 檔
    df = pd.read_csv(input_filename, index_col='Date', parse_dates=True)

    # 計算收盤價 (Close) 和成交量 (Volume) 的移動平均線
    for window in windows:
        # 股價均線 (Price MA)
        df[f'Price_MA_{window}'] = df['Close'].rolling(window=window).mean()
        
        # 成交量均線 (Volume MA)
        df[f'Volume_MA_{window}'] = df['Volume'].rolling(window=window).mean()

    # 刪除因為計算均線產生 NaN (空值) 的資料列 (可選，視您的需求而定)
    # df.dropna(inplace=True) 

    # 將結果存成新的 CSV 檔
    df.to_csv(output_filename)
    print(f"均線計算完成，結果已儲存至 {output_filename}")
    return True

if __name__ == "__main__":
    # --- 參數設定 ---
    target_stock_id = "2330"       # 股票代號 (台積電)
    start_date = "2025-01-01"      # 開始日期
    end_date = "2026-05-16"        # 結束日期 (使用您提供的當前日期附近)
    raw_data_file = f"raw_data_{target_stock_id}.csv"
    ma_data_file = f"ma_data_{target_stock_id}.csv"
    ma_days = [5, 10, 20, 60]      # 您想計算的均線天數 (例如：5日、10日、20日、季線)

    # --- 步驟 1: 抓取並儲存原始資料 ---
    # 如果您只需要計算一次，抓下來後這段就可以註解掉，以後直接執行步驟 2
    fetch_and_save_stock_data(target_stock_id, start_date, end_date, filename=raw_data_file)

    # --- 步驟 2: 讀取原始資料，計算均線，並儲存 ---
    calculate_and_save_moving_averages(input_filename=raw_data_file, output_filename=ma_data_file, windows=ma_days)

    # --- 步驟 3: 驗證 (讀取剛剛存好的均線資料) ---
    if os.path.exists(ma_data_file):
        print("\n--- 驗證：讀取已計算好均線的資料 ---")
        loaded_df = pd.read_csv(ma_data_file, index_col='Date', parse_dates=True)
        # 印出最後 5 筆資料來檢查
        print(loaded_df.tail())