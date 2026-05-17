import os
from dotenv import load_dotenv

load_dotenv()
print("---- 環境變數測試 ----")
print("目前終端機工作目錄 ( os.getcwd ) :", os.getcwd())
print("Discord URL 是否抓到 :", "✅ 有抓到" if os.getenv("DISCORD_WEBHOOK_URL") else "❌ 空的")
print("富果 API Key 是否抓到 :", "✅ 有抓到" if os.getenv("FUGLE_API_KEY") else "❌ 空的")