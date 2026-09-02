import json
import os
import time
import requests
import unicodedata
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_RATIO = 0.5
MAX_PAGES = 20
REQUEST_DELAY_SECONDS = 2
EVENTS_PER_MESSAGE = 10
USER_AGENT = "TCGWatch/0.1 (+https://github.com/Duongtom/product-tracking-system) personal stock notifier"

SOURCES = [
    {
        "id": "trainertown",
        "name": "Trainer Town",
        "base_url": "https://trainertown.com.au",
        "collections": [],
    },
    {
        "id": "pokebox",
        "name": "Pokebox AU",
        "base_url": "https://www.pokebox.com.au",
        "collections": [
            "english-sealed-pokemon-trading-cards",
            "japanese-pokemon-tcg-booster-boxes",
        ],
    },
    {
        "id": "onlinecoins",
        "name": "Online Coins",
        "base_url": "https://www.onlinecoinsandcollectables.com.au",
        "collections": ["pokemon-tcg"],
    },
]

KEYWORDS = ["pokemon", "one piece", "op-17"]
EXCLUDE_KEYWORDS = ["single", "sleeve", "playmat", "gaming mat", "binder", "deck box"]


def strip_accents(text):
    decomposed = unicodedata.normalize("NFD", text)
    result = ""
    for char in decomposed:
        if not unicodedata.combining(char):
            result = result + char
    return result


def matches_keywords(title):
    clean = strip_accents(title).lower()
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in clean:
            return False
    for keyword in KEYWORDS:
        if keyword in clean:
            return True
    return False


def build_endpoints(source):
    if not source["collections"]:
        return [f"{source['base_url']}/products.json"]
    endpoints = []
    for handle in source["collections"]:
        endpoints.append(f"{source['base_url']}/collections/{handle}/products.json")
    return endpoints


def fetch_products(source):
    products = []
    for endpoint in build_endpoints(source):
        truncated = True
        for page in range(1, MAX_PAGES + 1):
            response = requests.get(
                f"{endpoint}?limit=250&page={page}",
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
            batch = response.json()["products"]
            time.sleep(REQUEST_DELAY_SECONDS)
            if not batch:
                truncated = False
                break
            products.extend(batch)
        if truncated:
            print(f"WARNING: hit page limit on {endpoint}")
    return products


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


def send_events(events):
    all_sent = True
    for start in range(0, len(events), EVENTS_PER_MESSAGE):
        chunk = events[start:start + EVENTS_PER_MESSAGE]
        if not send_telegram("\n\n".join(chunk)):
            all_sent = False
    return all_sent


def describe(kind, item):
    return f"{kind} [{item['source']}]\n{item['title']}\n${item['price']}\n{item['url']}"


current = {}
failed_sources = []

for source in SOURCES:
    try:
        products = fetch_products(source)
    except Exception as error:
        print(f"FAILED {source['name']}: {error}")
        failed_sources.append(source["name"])
        continue

    kept = 0
    for product in products:
        if not matches_keywords(product["title"]):
            continue
        variant = product["variants"][0]
        key = f"{source['id']}:{product['id']}"
        current[key] = {
            "source": source["name"],
            "title": product["title"],
            "price": variant["price"],
            "available": variant["available"],
            "url": f"{source['base_url']}/products/{product['handle']}",
        }
        kept += 1
    print(f"{source['name']}: fetched {len(products)}, matched {kept}")

previous = load_previous()
events = []
should_save = True

if failed_sources:
    warning = f"HEALTH: sources failed: {', '.join(failed_sources)}. State not saved."
    print(warning)
    send_telegram(warning)
    should_save = False
elif looks_broken(current, previous):
    warning = f"HEALTH: got {len(current)} products, expected around {len(previous)}. State not saved."
    print(warning)
    send_telegram(warning)
    should_save = False
elif not previous:
    print(f"First run - remembering {len(current)} products. No alerts.")
else:
    for key in current:
        current_item = current[key]
        if key not in previous:
            events.append(describe("NEW", current_item))
        else:
            previous_item = previous[key]
            if not previous_item["available"] and current_item["available"]:
                events.append(describe("BACK IN STOCK", current_item))

    for event in events:
        print(event.replace("\n", " | "))
    print(f"Done. {len(events)} events.")

    if events:
        should_save = send_events(events)

if should_save:
    with open("state.json", "w") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
else:
    print("State not saved - will retry next run")