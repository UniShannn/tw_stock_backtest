import requests

import config

def send_discord_message(msg):

    # 依照 Discord 官方要求的 JSON 格式打包訊息
    payload = {
        "content": msg
    }
    
    try:
        response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload)
        # Discord Webhook 成功發送會回傳 204
        if response.status_code == 204:
            print("✅ Discord 備援訊息發送成功！")
            return True
        else:
            print(f"❌ Discord 發送失敗，狀態碼：{response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ 發生錯誤：{e}")
        return False
    
if __name__ == "__main__":
    # 測試發送
    msg ="""
    📊 【台股回測系統通知】
    股票：台積電 (2330) 
    狀態：目前訊號為【買進持有】
    (此為系統自動測試 Discord Webhook 的訊息)
    """

    send_discord_message(msg)
