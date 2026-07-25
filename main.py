import os
import json
import random
import requests
from io import BytesIO

from PIL import Image
from common import build_quote_image

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]  # مثل @nabgofteh یا -100xxxxxxxxxx
CHANNEL_HANDLE = os.environ.get("CHANNEL_HANDLE", "@nabgofteh")

QUOTES_FILE = "quotes.json"
POSTED_FILE = "posted.json"
IMG_SIZE = 1080
FIXED_BG_PATH = "assets/telegram_background.png"  # اگر این فایل وجود داشته باشد، به‌جای پس‌زمینه‌ی خودکار استفاده می‌شود


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_quote():
    quotes = load_json(QUOTES_FILE, [])
    posted = load_json(POSTED_FILE, [])
    if not quotes:
        raise RuntimeError("quotes.json is empty")
    remaining = [q for q in quotes if q not in posted]
    if not remaining:
        # همه‌ی جمله‌ها پست شدند، چرخه از نو شروع می‌شود
        posted = []
        remaining = quotes
    quote = random.choice(remaining)
    posted.append(quote)
    save_json(POSTED_FILE, posted)
    return quote


def send_photo(img, caption):
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": ("quote.jpg", buf, "image/jpeg")}
    data = {"chat_id": CHANNEL_ID, "caption": caption}
    r = requests.post(url, data=data, files=files, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    try:
        from PIL import features
        print("raqm feature available:", features.check_feature("raqm"))
    except Exception as e:
        print("could not check raqm feature:", e)

    quote = pick_quote()

    bg_image = None
    if os.path.exists(FIXED_BG_PATH):
        print("Using fixed background image:", FIXED_BG_PATH)
        bg_image = Image.open(FIXED_BG_PATH)
    else:
        print("No fixed background found, generating automatically")

    img = build_quote_image(quote, IMG_SIZE, IMG_SIZE, bg_image=bg_image)
    caption = f"{quote}\n\n📍 {CHANNEL_HANDLE}"
    result = send_photo(img, caption)
    print("Posted successfully:", result.get("ok"))


if __name__ == "__main__":
    main()
