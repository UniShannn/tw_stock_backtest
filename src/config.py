import os

# 定義資料夾路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

# 定義要回測的股票清單 (台積電、聯電、聯發科)
# 未來想要新增股票，只要在這個中括號裡面加上代號即可！
TARGET_STOCKS = ["2330.TW", "2303.TW", "2454.TW"]

# 定義回測的時間區間 (可依需求自行修改)
START_DATE = "2025-01-01"
END_DATE = "2026-05-16"