import json
import os
import requests
import unicodedata


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

if not previous:
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

with open("state.json", "w") as f:
    json.dump(current, f, indent=2, ensure_ascii=False)