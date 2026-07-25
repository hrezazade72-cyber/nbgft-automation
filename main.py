import os
import json
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]  # مثل @nabgofteh یا -100xxxxxxxxxx
CHANNEL_HANDLE = os.environ.get("CHANNEL_HANDLE", "@nabgofteh")

QUOTES_FILE = "quotes.json"
POSTED_FILE = "posted.json"
FONT_PATH = "Vazirmatn-Bold.ttf"

IMG_SIZE = 1080


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


def shape_farsi(text):
    """حروف فارسی را به شکل چسبیده (presentation forms) تبدیل می‌کند و سپس
    کل رشته را برعکس می‌کند تا وقتی PIL آن را چپ‌به‌راست رسم می‌کند،
    خروجی به‌صورت درست راست‌به‌چپ دیده شود.
    (این روش ساده برای متن خالص فارسی/عربی بدون عدد یا حروف لاتین مطمئن است.)"""
    reshaped = arabic_reshaper.reshape(text)
    return reshaped[::-1]


def wrap_farsi(text, font, draw, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        shaped = shape_farsi(test)
        bbox = draw.textbbox((0, 0), shaped, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def get_background():
    """پس‌زمینه‌ی انتزاعی رایگان از Pollinations؛ اگر شکست خورد، گرادیان محلی می‌سازیم."""
    prompt = "abstract soft dark gradient minimal calm background, no text, cinematic, high resolution"
    try:
        url = (
            "https://image.pollinations.ai/prompt/"
            + requests.utils.quote(prompt)
            + f"?width={IMG_SIZE}&height={IMG_SIZE}&nologo=true"
        )
        r = requests.get(url, timeout=40)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize((IMG_SIZE, IMG_SIZE))
    except Exception:
        img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (24, 24, 36))
        draw = ImageDraw.Draw(img)
        for y in range(IMG_SIZE):
            shade = int(24 + (y / IMG_SIZE) * 40)
            draw.line([(0, y), (IMG_SIZE, y)], fill=(shade, shade, shade + 20))
    return img


def build_image(quote_text):
    img = get_background()
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 130))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_size = 62
    max_width = img.width - 160

    font = ImageFont.truetype(FONT_PATH, font_size)
    lines = wrap_farsi(quote_text, font, draw, max_width)
    while len(lines) > 6 and font_size > 30:
        font_size -= 4
        font = ImageFont.truetype(FONT_PATH, font_size)
        lines = wrap_farsi(quote_text, font, draw, max_width)

    line_height = font_size + 16
    total_height = line_height * len(lines)
    y = (img.height - total_height) // 2

    for line in lines:
        shaped = shape_farsi(line)
        bbox = draw.textbbox((0, 0), shaped, font=font)
        w = bbox[2] - bbox[0]
        x = (img.width - w) // 2
        draw.text((x, y), shaped, font=font, fill=(255, 255, 255))
        y += line_height

    small_font = ImageFont.truetype(FONT_PATH, 34)
    tag = shape_farsi("نابگفته")
    bbox = draw.textbbox((0, 0), tag, font=small_font)
    draw.text(
        (img.width - bbox[2] - 40, img.height - 70),
        tag,
        font=small_font,
        fill=(255, 255, 255),
    )
    return img


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
    quote = pick_quote()
    img = build_image(quote)
    caption = f"{quote}\n\n📍 {CHANNEL_HANDLE}"
    result = send_photo(img, caption)
    print("Posted successfully:", result.get("ok"))


if __name__ == "__main__":
    main()
