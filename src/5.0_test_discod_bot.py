import discord
import yfinance as yf
import os
from dotenv import load_dotenv

# 讀取 .env 檔案中的環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 設定機器人的權限 (Intents)
intents = discord.Intents.default()
intents.message_content = True  # 允許讀取訊息內容

# 建立 Discord 客戶端 (Bot)
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ 登入成功！目前身分：{client.user}')
    print('等待接收指令中...')

@client.event
async def on_message(message):
    # 避免機器人自己回覆自己，造成無限迴圈
    if message.author == client.user:
        return

    # 制定我們的觸發指令，例如輸入 "?2330" 或 "?聯發科"
    if message.content.startswith('?'):
        # 取得 '?' 後面的字串 (例如 "?2330" 會變成 "2330")
        stock_query = message.content[1:].strip()
        
        # 簡單判斷：如果是中文名，這裡先示範硬體轉換 (您未來可串接全市場清單做自動對應)
        if stock_query == "聯發科":
            stock_id = "2454"
        elif stock_query == "台積電":
            stock_id = "2330"
        else:
            stock_id = stock_query # 假設使用者直接輸入代號

        # 加上 .TW 讓 yfinance 能辨識台股
        yf_ticker = f"{stock_id}.TW"
        
        # 讓機器人先發送一個「讀取中」的訊息 (提升體驗)
        reply_msg = await message.channel.send(f"🔍 正在查詢 {stock_id} 的最新股價，請稍候...")

        try:
            # 抓取今天最新的股價資料
            stock = yf.Ticker(yf_ticker)
            # 抓取最近 1 天的歷史資料
            hist = stock.history(period="1d")
            
            if hist.empty:
                await reply_msg.edit(content=f"❌ 找不到代號為 {stock_id} 的股票資料，請確認輸入是否正確。")
                return

            # 提取收盤價
            current_price = hist['Close'].iloc[-1]
            
            # 編輯剛剛的「讀取中」訊息，換成最終結果
            final_text = f"📊 **{stock_id} 最新報價**\n目前收盤價為：**{current_price:.2f}** 元"
            await reply_msg.edit(content=final_text)

        except Exception as e:
            await reply_msg.edit(content=f"⚠️ 查詢時發生錯誤: {e}")

# 啟動機器人
if __name__ == "__main__":
    if not TOKEN:
        print("❌ 找不到 DISCORD_BOT_TOKEN，請檢查 .env 檔案！")
    else:
        client.run(TOKEN)