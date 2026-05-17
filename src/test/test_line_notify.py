import requests
import path
import config


def send_line_message(message_text):

    # 設定 HTTP 標頭
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}'
    }

    # 設定要傳送的資料內容
    data = {
        'to': config.LINE_USER_IDs["自己"],  # 這裡指定要發給自己的 User ID
        'messages': [
            {
                'type': 'text',
                'text': message_text
            }
        ]
    }

    # 發送請求給 LINE 伺服器
    response = requests.post(url = config.LINE_API_URL, headers=headers, json=data)
    
    # 檢查是否發送成功
    if response.status_code == 200:
        print("✅ 訊息發送成功！請檢查您的 LINE 手機 App。")
    else:
        print(f"❌ 發送失敗。錯誤碼：{response.status_code}")
        print(response.text)



# ======== 測試發送回測結果 ========
if __name__ == "__main__":

    backtest_result = """📊 【台股回測系統通知】
    股票：台積電 (2330)
    策略：5MA & 20MA 交叉策略
    區間：2023-01-01 至今
    結果：總報酬率 125% 📈
    狀態：目前訊號為【買進持有】"""

    # 呼叫函數，將字串傳出去
    send_line_message(backtest_result)