import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

url = "https://api.telegram.org/bot" + token + "/sendMessage"
response = requests.post(url, data={"chat_id": chat_id, "text": "Hello from TCGWatch"})

print(response.status_code)
print(response.json())