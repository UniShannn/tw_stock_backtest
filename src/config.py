import os
from dotenv import load_dotenv
from dotenv import load_dotenv
import pandas as pd

# 定義資料夾路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORT_DIR = os.path.join(BASE_DIR, "data", "report")

METADATA_FILE = os.path.join(RAW_DIR, "tw_stock_metadata.csv")
def get_stock_pool(market=None, industry=None, custom_list=None):
    """
    強大的動態選股引擎
    :param market: '上市' 或 '上櫃' 或 None (全市場)
    :param industry: 例如 '半導體業', '金融保險業' 或 None
    :param custom_list: 直接傳入手動清單，例如 ['2330', '2303']
    """
    # 如果有手動清單，直接回傳
    if custom_list:
        return custom_list
        
    if not os.path.exists(METADATA_FILE):
        print(f"⚠️ 找不到 {METADATA_FILE}，請先執行 0_update_stock_list.py")
        return []

    # 讀取全市場資料庫
    df = pd.read_csv(METADATA_FILE)

    # 條件篩選 (Filter)
    if market:
        df = df[df['Market'] == market]
    if industry:
        df = df[df['Industry'] == industry]
        
    # 回傳純數字代號清單 (給 Fugle 用)
    # 如果要給 yfinance 用，改成 return df['YF_Ticker'].tolist()
    # return df['Stock_ID'].astype(str).tolist() 
    return df['YF_Ticker'].tolist()

# 🚀 未來您只要在這裡切換策略池即可！
# 情境 1：我想跑【全市場】大數據回測 (約 1800 檔)
TARGET_STOCKS = get_stock_pool()
# 情境 2：我只想測試【上市的半導體業】
# TARGET_STOCKS = get_stock_pool(market='上市', industry='半導體業')
# 情境 3：手動測試觀察名單
# TARGET_STOCKS = get_stock_pool(custom_list=['2330.TW', '2454.TW', '2303.TW'])
print(f"目前選股池共 {len(TARGET_STOCKS)} 檔股票。")
print(f"前 10 檔股票代號：{TARGET_STOCKS[:10]}")

# 定義回測的時間區間 (可依需求自行修改)
START_DATE = "2000-01-01"
END_DATE = "2026-05-16"

# 測試用的時間區間 (可以用來快速測試程式碼是否正確，或是做單元測試)
TEST_START_DATE = "2020-01-01"
TEST_END_DATE = "2020-12-31"



#############################################################################
# from dotenv import load_dotenv

# 1. 取得當前 config.py 的絕對路徑 (在 src/ 資料夾內)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. 找到上一層的專案根目錄路徑 (tw_stock_backtest/)
project_root = os.path.dirname(current_dir)

# 3. 組合出根目錄下 .env 檔案的絕對路徑
env_path = os.path.join(project_root, '.env')

# 4. 強制指定絕對路徑來載入 .env
load_dotenv(dotenv_path=env_path)



### 其他第三方服務的 API Key 或設定參數也可以放在這裡，例如：

## Discord
# DISCORD_WEBHOOK_URL 是用來發送訊息到 Discord 頻道的 Webhook URL，必須從 Discord 伺服器的頻道設定中取得並設定在環境變數中
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

## 富果
# FUGLE_API_KEY 是用來驗證您使用富果 API 的身份，必須從富果開發者平台取得並設定在環境變數中
FUGLE_API_KEY = os.getenv("FUGLE_API_KEY", "")

## LINE Notify
# LINE User ID 和 Group ID (請替換成您在 LINE 官方帳號管理後台取得的 ID)
LINE_USER_IDs = {
    "自己": os.getenv("LINE_USER_SELF", "")
}
LINE_GROUP_IDs = {
    "工作紀錄": os.getenv("LINE_GROUP_WORK", ""),
    "Family": os.getenv("LINE_GROUP_FAMILY", "")
}
# LINE_CHANNEL_ACCESS_TOKEN 是用來驗證您發送訊息的身份，必須從 LINE 官方帳號管理後台取得並設定在環境變數中
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
# LINE_API_URL 是用來發送訊息給特定使用者的 API 網址 (Push API)
LINE_API_URL = os.getenv("LINE_API_URL", "")
# LINE_API_BROADCAST_URL 是用來發送訊息給所有使用者的 API 網址 (Broadcast API)
LINE_API_BROADCAST_URL = os.getenv("LINE_API_BROADCAST_URL", "")


###########################################################################


## 這段程式碼的目的是為了讓test資料夾裡的測試程式能順利找到src資料夾裡的config.py
import sys
# 1. 自動動態取得 config.py 本身所在的資料夾（也就是 src/ 資料夾的絕對路徑）
src_dir = os.path.dirname(os.path.abspath(__file__))

# 2. 自動把 src/ 資料夾動態加進 Python 的搜尋路徑中
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
