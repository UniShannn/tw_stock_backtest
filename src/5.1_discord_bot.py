import discord
from discord.ext import commands
import yfinance as yf
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# https://discord.com/developers/applications

# ================= 1. 環境設定與初始化 =================
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CSV_FILE = "portfolio.csv"

# 設定機器人的權限 (Intents)
intents = discord.Intents.default()
intents.message_content = True

# 改用 commands.Bot 架構
bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)

# 確保 CSV 檔案與欄位存在
def init_csv():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['Stock_ID', 'Price', 'Shares', 'Date'])
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

init_csv()

# ================= 2. 互動 UI 介面設計 =================

# 定義控制面板 (View)
class MainMenuView(discord.ui.View):
    def __init__(self):
        # timeout=None 代表這個面板的按鈕永遠不會過期失效
        super().__init__(timeout=None)

    # 1. 查價按鈕 (藍色 Primary)
    @discord.ui.button(label="📈 查詢報價", style=discord.ButtonStyle.primary, custom_id="btn_price")
    async def btn_check_price(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ephemeral=True 代表這則訊息「只有點擊按鈕的人」看得到，不會洗版
        await interaction.response.send_message("您點擊了查詢報價！(未來這裡可以跳出輸入框讓您打代號)", ephemeral=True)

    # 2. 查庫存按鈕 (綠色 Success)
    @discord.ui.button(label="💼 查看庫存", style=discord.ButtonStyle.success, custom_id="btn_inventory")
    async def btn_check_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("正在為您撈取庫存資料...", ephemeral=True)

    # 3. 刪除庫存按鈕 (紅色 Danger)
    @discord.ui.button(label="🗑️ 刪除庫存", style=discord.ButtonStyle.danger, custom_id="btn_delete")
    async def btn_delete_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("請告訴我要刪除哪一檔股票？", ephemeral=True)



# 彈出式表單 (Modal)：填寫記帳資料
class AddStockModal(discord.ui.Modal, title='📝 新增股票庫存'):
    
    # 定義表單內的 4 個輸入框
    stock_id = discord.ui.TextInput(
        label='股號或簡稱 (例如: 2330 或 台積電)',
        placeholder='請輸入股號...',
        required=True
    )
    price = discord.ui.TextInput(
        label='買進價格',
        placeholder='例如: 850.5',
        required=True
    )
    shares = discord.ui.TextInput(
        label='股數',
        placeholder='例如: 1000',
        required=True
    )
    buy_date = discord.ui.TextInput(
        label='買進日期 (YYYY-MM-DD)',
        default=datetime.today().strftime('%Y-%m-%d'),
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 防呆：檢查輸入的價格和股數是否為數字
        try:
            p_val = float(self.price.value)
            s_val = int(self.shares.value)
        except ValueError:
            await interaction.response.send_message("❌ **格式錯誤**：價格必須為數字，股數必須為整數！", ephemeral=True)
            return

        # 簡單判斷中文簡稱轉代號 (可依需求擴充)
        s_id = self.stock_id.value.strip()
        if s_id == "聯發科": s_id = "2454"
        elif s_id == "台積電": s_id = "2330"

        # 存入 CSV
        new_data = pd.DataFrame([{
            'Stock_ID': s_id,
            'Price': p_val,
            'Shares': s_val,
            'Date': self.buy_date.value
        }])
        new_data.to_csv(CSV_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

        await interaction.response.send_message(f"✅ 成功新增 **{s_id}** 庫存紀錄！\n買價: `{p_val}` | 股數: `{s_val}` | 日期: `{self.buy_date.value}`", ephemeral=True)

# 包含按鈕的選單視圖 (View)
class PortfolioMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 讓按鈕永久有效

    @discord.ui.button(label='➕ 新增庫存', style=discord.ButtonStyle.success, custom_id='btn_add_stock')
    async def btn_add_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 點擊後彈出表單
        await interaction.response.send_modal(AddStockModal())

    @discord.ui.button(label='📊 查看庫存', style=discord.ButtonStyle.primary, custom_id='btn_view_portfolio')
    async def btn_view_portfolio(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🌟 重要：因為抓取 yfinance 需要時間，先 defer 讓 Discord 知道我們正在處理，避免超時報錯
        await interaction.response.defer(ephemeral=False) 

        df = pd.read_csv(CSV_FILE)
        if df.empty:
            await interaction.followup.send("⚠️ 目前 `portfolio.csv` 是空的，請先新增庫存！")
            return

        # 1. 算出每筆交易的總成本 (Price * Shares)
        df['Cost'] = df['Price'] * df['Shares']

        # 2. 依照股號群組彙整
        summary = df.groupby('Stock_ID').agg(
            Total_Shares=('Shares', 'sum'),
            Total_Cost=('Cost', 'sum')
        ).reset_index()

        # 3. 計算平均成本
        summary['Avg_Price'] = summary['Total_Cost'] / summary['Total_Shares']

        embed = discord.Embed(title="📊 個人台股庫存明細", color=discord.Color.blue(), timestamp=datetime.now())
        total_portfolio_cost = 0
        total_portfolio_value = 0

        # 4. 針對每檔股票抓取最新價格並計算損益
        for _, row in summary.iterrows():
            stock_id = str(row['Stock_ID'])
            t_shares = row['Total_Shares']
            avg_price = row['Avg_Price']
            t_cost = row['Total_Cost']
            
            total_portfolio_cost += t_cost

            # 抓取 yfinance 最新報價
            yf_ticker = f"{stock_id}.TW"
            try:
                hist = yf.Ticker(yf_ticker).history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    current_value = current_price * t_shares
                    total_portfolio_value += current_value
                    
                    pnl = current_value - t_cost
                    pnl_pct = (pnl / t_cost) * 100
                    
                    # 判斷賺賠顏色與符號
                    sign = "🔴" if pnl > 0 else "🟢" if pnl < 0 else "⚪"
                    pnl_str = f"{sign} {pnl:,.0f} ({pnl_pct:+.2f}%)"
                    
                    field_value = (
                        f"持股數: `{t_shares:,}` 股\n"
                        f"均價: `{avg_price:.2f}` | 現價: `{current_price:.2f}`\n"
                        f"總成本: `{t_cost:,.0f}` | 市值: `{current_value:,.0f}`\n"
                        f"未實現損益: **{pnl_str}**"
                    )
                else:
                    field_value = f"持股數: `{t_shares:,}` 股 | 均價: `{avg_price:.2f}`\n⚠️ *無法取得最新報價*"
            except Exception as e:
                field_value = f"持股數: `{t_shares:,}` 股 | 均價: `{avg_price:.2f}`\n⚠️ *報價抓取失敗*"

            embed.add_field(name=f"📌 {stock_id}", value=field_value, inline=False)

        # 5. 彙整總資產損益
        if total_portfolio_value > 0:
            total_pnl = total_portfolio_value - total_portfolio_cost
            total_pnl_pct = (total_pnl / total_portfolio_cost) * 100
            sign = "🔴" if total_pnl > 0 else "🟢" if total_pnl < 0 else "⚪"
            embed.description = (
                f"**💰 總投入成本**: `{total_portfolio_cost:,.0f}`\n"
                f"**📈 總目前市值**: `{total_portfolio_value:,.0f}`\n"
                f"**🔥 總未實現損益**: {sign} **{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)**"
            )

        # 送出報表
        await interaction.followup.send(embed=embed)

# ================= 3. 機器人指令與事件 =================

@bot.event
async def on_ready():
    print(f'✅ 登入成功！目前身分：{bot.user}')
    print('等待接收指令中...')

## 檢視主頁
@bot.command(name='?')
async def show_menu(ctx):
    view = MainMenuView()
    # 建立一個漂亮的 Embed 訊息框來搭配按鈕
    embed = discord.Embed(
        title="🤖 台股記帳與回測助理",
        description="歡迎使用！請點擊下方按鈕選擇您要執行的功能：",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

@bot.command(name="記帳", aliases=["選單", "menu"])
async def show_menu(ctx):
    """呼叫互動選單的指令"""
    embed = discord.Embed(
        title="🏦 台股資產管理小幫手",
        description="請點擊下方按鈕來新增庫存，或查看目前的資產損益狀況。",
        color=discord.Color.green()
    )
    # 發送包含兩個按鈕的 View
    await ctx.send(embed=embed, view=PortfolioMenu())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # 1. 先讓 bot 嘗試解析是否為註冊的指令 (如 ?記帳)
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.invoke(ctx)
        return

    # 2. 如果不是常規指令，但以 '?' 開頭，平滑過渡您原本的「即時報價」邏輯
    if message.content.startswith('?'):
        stock_query = message.content[1:].strip()
        if not stock_query:
            return

        if stock_query == "聯發科": stock_id = "2454"
        elif stock_query == "台積電": stock_id = "2330"
        else: stock_id = stock_query

        yf_ticker = f"{stock_id}.TW"
        reply_msg = await message.channel.send(f"🔍 正在查詢 {stock_id} 的最新股價，請稍候...")

        try:
            stock = yf.Ticker(yf_ticker)
            hist = stock.history(period="1d")
            
            if hist.empty:
                await reply_msg.edit(content=f"❌ 找不到代號為 {stock_id} 的股票資料。")
                return

            current_price = hist['Close'].iloc[-1]
            final_text = f"📊 **{stock_id} 最新報價**\n目前收盤價為：**{current_price:.2f}** 元"
            await reply_msg.edit(content=final_text)

        except Exception as e:
            await reply_msg.edit(content=f"⚠️ 查詢時發生錯誤: {e}")

# 啟動機器人
if __name__ == "__main__":
    if not TOKEN:
        print("❌ 找不到 DISCORD_BOT_TOKEN，請檢查 .env 檔案！")
    else:
        bot.run(TOKEN)