import requests
import config

def send_line_broadcast_message(message_text):

    # 設定 HTTP 標頭
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}'
    }

    # 🔴 注意這裡！因為是廣播給所有人，所以不需要 'to': user_id 這個欄位了
    data = {
        'messages': [
            {
                'type': 'text',
                'text': message_text
            }
        ]
    }

    # 發送請求給 LINE 伺服器
    # 🔴 注意這裡！網址從 push 改成了 broadcast
    response = requests.post(config.LINE_API_BROADCAST_URL, headers=headers, json=data)
    
    if response.status_code == 200:
        print("✅ 廣播發送成功！所有加好友的家人都會收到。")
    else:
        print(f"❌ 發送失敗。錯誤碼：{response.status_code}")
        print(response.text)

# ======== 測試發送廣播 ========
if __name__ == "__main__":

    backtest_result = """📊 【台股回測系統通知】
    股票：台積電 (2330)
    狀態：目前訊號為【買進持有】
    (此為系統自動廣播測試)"""

    # 呼叫函數，將字串傳出去
    send_line_broadcast_message(backtest_result)