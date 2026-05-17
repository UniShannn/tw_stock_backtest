# 檔案說明：更新台股全市場股票清單，包含上市與上櫃公司，並儲存為 CSV 檔以供後續使用
import pandas as pd
import requests
import os
import config

# 自動引入並關閉不安全連線的警告訊息（因為 verify=False 會產生警告，我們把它隱藏起來）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def process_market_df(df, market_name):
    """
    自動辨識並統一各交易所的欄位名稱（完美解決上櫃英文欄位交叉干擾，並自動清洗上櫃冗長全名）
    """
    id_col, name_col, ind_col = None, None, None
    
    # 遍歷所有欄位，利用關鍵字自動鎖定
    for col in df.columns:
        col_str = str(col).strip()
        col_lower = col_str.lower()
        
        # 防錯機制 1：排除所有帶有「英文」或「english」的欄位，防止中文名稱被覆蓋
        if '英文' in col_str or 'english' in col_lower:
            continue
            
        # 1. 【優先級最高】鎖定產業欄位 
        if '產業' in col_str or 'industry' in col_lower:
            ind_col = col
            
        # 2. 鎖定代號欄位 (防錯機制 2：排除 symbol，避免上櫃數字代號被英文縮寫覆蓋)
        elif ('代號' in col_str or 'code' in col_lower or col_lower in ['stock_id', 'id']) and 'symbol' not in col_lower:
            id_col = col
            
        # 3. 鎖定名稱欄位
        elif '名稱' in col_str or 'name' in col_lower or '簡稱' in col_str:
            name_col = col
            
    # 防呆機制：如果真的找不到欄位，給予提示
    if id_col is None or name_col is None or ind_col is None:
        print(f"⚠️ {market_name} 資料欄位解析異常！目前的欄位有: {list(df.columns)}")
        return pd.DataFrame(columns=['Stock_ID', 'Name', 'Industry', 'Market'])
        
    # 擷取核心資料並統一命名
    res_df = df[[id_col, name_col, ind_col]].copy()
    res_df.columns = ['Stock_ID', 'Name', 'Industry']
    res_df['Market'] = market_name
    
    # 💡 核心優化：如果是「上櫃」公司，自動將冗長全名清洗為看盤軟體簡稱
    if market_name == '上櫃':
        def clean_otc_name(name):
            if not isinstance(name, str):
                return name
            
            # 步驟 A：先移除常見的公司法人尾綴
            corporate_suffixes = ['股份有限公司', '有限公司', '股份公司', '公司']
            for suffix in corporate_suffixes:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
                    break # 移除一種類型即可跳出
            
            # 步驟 B：再移除常見的行業別特徵詞，精準還原為看盤軟體簡稱 (通常為 2~4 個字)
            # 範例：安心食品服務 -> 安心 / 德麥食品 -> 德麥 / 穩懋半導體 -> 穩懋
            industry_suffixes = ['食品服務', '食品', '科技', '電子', '半導體', '光電', '生技', '生醫', '材料', '工業', '工程', '建設', '營造']
            for ind in industry_suffixes:
                # 💡 len(name) > len(ind) + 1 的目的是確保刪除行業詞後，最少還保留 2 個字作為股票簡稱
                if name.endswith(ind) and len(name) > len(ind) + 1:
                    name = name[:-len(ind)]
                    break
            return name
            
        # 執行清洗
        res_df['Name'] = res_df['Name'].apply(clean_otc_name)
        
    return res_df

def update_taiwan_stock_list():
    print("開始下載台股全市場清單...")
    
    # 1. 抓取【上市】公司基本資料 (證交所 OpenAPI)
    print("  -> 抓取上市公司資料...")
    twse_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        twse_res = requests.get(twse_url, verify=False)
        twse_df = pd.DataFrame(twse_res.json())
        twse_processed = process_market_df(twse_df, '上市')
    except Exception as e:
        print(f"❌ 上市公司資料抓取或解析失敗: {e}")
        twse_processed = pd.DataFrame(columns=['Stock_ID', 'Name', 'Industry', 'Market'])

    # 2. 抓取【上櫃】公司基本資料 (櫃買中心 OpenAPI)
    print("  -> 抓取上櫃公司資料...")
    tpex_url = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
    try:
        tpex_res = requests.get(tpex_url, verify=False)
        tpex_df = pd.DataFrame(tpex_res.json())
        tpex_processed = process_market_df(tpex_df, '上櫃')
    except Exception as e:
        print(f"❌ 上櫃公司資料抓取或解析失敗: {e}")
        tpex_processed = pd.DataFrame(columns=['Stock_ID', 'Name', 'Industry', 'Market'])

    # 3. 合併上市與上櫃資料
    all_stocks = pd.concat([twse_processed, tpex_processed], ignore_index=True)
    
    # 清洗資料：將代號轉為字串並剔除空值
    all_stocks = all_stocks.dropna(subset=['Stock_ID'])
    all_stocks['Stock_ID'] = all_stocks['Stock_ID'].astype(str).str.strip()
    all_stocks = all_stocks[all_stocks['Stock_ID'] != '']
    
    # 去除重複值
    all_stocks = all_stocks.drop_duplicates(subset=['Stock_ID']).reset_index(drop=True)
    
    if all_stocks.empty:
        print("❌ 錯誤：未成功取得任何交易所的股票資料，終止存檔。")
        return

    # 4. 配合 yfinance 格式，幫代號加上 .TW (上市) 或 .TWO (上櫃)
    def get_yf_ticker(row):
        if row['Market'] == '上市':
            return f"{row['Stock_ID']}.TW"
        else:
            return f"{row['Stock_ID']}.TWO"
            
    all_stocks['YF_Ticker'] = all_stocks.apply(get_yf_ticker, axis=1)
    
    # 5. 新增未來擴充用的預留欄位
    all_stocks['Tags'] = ''
    all_stocks['Market_Cap'] = 0

    # 確保 data 資料夾存在並存檔
    os.makedirs(config.RAW_DIR, exist_ok=True)
    save_path = os.path.join(config.RAW_DIR, 'tw_stock_metadata.csv')
    all_stocks.to_csv(save_path, index=False, encoding='utf-8-sig')
    
    print(f"✅ 更新完成！共取得 {len(all_stocks)} 檔股票，已成功儲存至 {save_path}")

if __name__ == "__main__":
    update_taiwan_stock_list()