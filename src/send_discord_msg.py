# src/send_discord_msg.py (範例，請依你實際的發送程式修改)
import requests
import config # 確保有引入你的設定檔

def send_discord_message(msg):
    # 🌟 核心防呆：如果網址是空的，就印出警告並優雅結束，不要讓程式崩潰！
    if not config.DISCORD_WEBHOOK_URL:
        print("⚠️ [通知提示] Discord Webhook URL 為空，跳過線上發送通知。")
        return
        
    try:
        payload = {"content": msg}
        response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("✅ Discord 訊息發送成功！")
        else:
            print(f"❌ Discord 發送失敗，狀態碼: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 發送通知時發生非預期錯誤: {e}")


if __name__ == "__main__":
    # 測試發送
    msg ="""
    📊 【台股回測系統通知】
    股票：台積電 (2330) 
    狀態：目前訊號為【買進持有】
    (此為系統自動測試 Discord Webhook 的訊息)
    """

    send_discord_message(msg)
