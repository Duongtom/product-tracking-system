import json
import os
import requests
import unicodedata
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_RATIO = 0.5


def strip_accents(text):
    decomposed = unicodedata.normalize("NFD", text)
    result = ""
    for char in decomposed:
        if not unicodedata.combining(char):
            result = result + char
    return result


def load_previous():
    if os.path.exists("state.json"):
        with open("state.json") as f:
            return json.load(f)
    return {}


def looks_broken(current, previous):
    if not previous:
        return False
    if not current:
        return True
    return len(current) < len(previous) * MIN_RATIO


def send_telegram(text):
    api_url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    api_response = requests.post(
        api_url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )
    if api_response.status_code != 200:
        print("Telegram failed:", api_response.status_code)
        return False
    return True


url = "https://trainertown.com.au/products.json?limit=250"
response = requests.get(url)
data = response.json()

current = {}

for product in data["products"]:
    title = product["title"]
    variant = product["variants"][0]

    if "pokemon" in strip_accents(title).lower():
        product_id = str(product["id"])
        current[product_id] = {
            "title": title,
            "price": variant["price"],
            "available": variant["available"],
        }

previous = load_previous()
events = []
should_save = True

if looks_broken(current, previous):
    warning = f"HEALTH: got {len(current)} products, expected around {len(previous)}. State not saved."
    print(warning)
    send_telegram(warning)
    should_save = False
elif not previous:
    print("First run - remembering", len(current), "products. No alerts.")
else:
    for product_id in current:
        current_item = current[product_id]

        if product_id not in previous:
            events.append("NEW: " + current_item["title"])
        else:
            previous_item = previous[product_id]
            if not previous_item["available"] and current_item["available"]:
                events.append("BACK IN STOCK: " + current_item["title"])

    for event in events:
        print(event)
    print("Done.", len(events), "events.")

    if events:
        should_save = send_telegram("\n".join(events))

if should_save:
    with open("state.json", "w") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
else:
    print("State not saved - will retry next run")