"""
توابع مشترک برای ساخت تصویر جمله با پس‌زمینه و متن فارسی.
هم توسط main.py (تلگرام) و هم instagram_main.py (اینستاگرام) استفاده می‌شود.
"""
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "Vazirmatn-Bold.ttf"


def load_font(size):
    """فونت را با موتور raqm بارگذاری می‌کند (شکل‌دهی و راست‌به‌چپ فارسی را
    خودِ Pillow درست انجام می‌دهد). اگر raqm در دسترس نبود، به حالت پایه برمی‌گردد."""
    try:
        return ImageFont.truetype(FONT_PATH, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def wrap_farsi(text, font, draw, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def fit_to_size(img, width, height):
    """تصویر را طوری resize/crop می‌کند که دقیقاً اندازه‌ی width×height شود
    (مثل CSS object-fit: cover) بدون کش رفتن نسبت ابعاد."""
    img = img.convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_height = height
        new_width = int(height * src_ratio)
    else:
        new_width = width
        new_height = int(width / src_ratio)
    img = img.resize((new_width, new_height))
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def get_background(width, height):
    """پس‌زمینه‌ی انتزاعی رایگان از Pollinations؛ اگر شکست خورد، گرادیان محلی می‌سازیم."""
    prompt = "abstract soft dark gradient minimal calm background, no text, cinematic, high resolution"
    try:
        url = (
            "https://image.pollinations.ai/prompt/"
            + requests.utils.quote(prompt)
            + f"?width={width}&height={height}&nologo=true"
        )
        r = requests.get(url, timeout=40)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize((width, height))
    except Exception:
        img = Image.new("RGB", (width, height), (24, 24, 36))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            shade = int(24 + (y / height) * 40)
            draw.line([(0, y), (width, y)], fill=(shade, shade, shade + 20))
    return img


def build_quote_overlay(quote_text, width, height, tag_text="نابگفته", font_size=62, min_font_size=30):
    """یک تصویر RGBA با پس‌زمینه‌ی کاملاً شفاف می‌سازد که فقط شامل متن است،
    به همراه یک نوار نیمه‌شفاف پشت متن برای خوانا ماندن روی هر ویدیویی.
    برای قرار گرفتن روی ویدیوی ثابت دلخواه کاربر استفاده می‌شود."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_width = width - 160
    size = font_size

    font = load_font(size)
    lines = wrap_farsi(quote_text, font, draw, max_width)
    while len(lines) > 8 and size > min_font_size:
        size -= 4
        font = load_font(size)
        lines = wrap_farsi(quote_text, font, draw, max_width)

    line_height = size + 16
    total_height = line_height * len(lines)
    y = (img.height - total_height) // 2

    # نوار نیمه‌شفاف مشکی پشت متن برای کنتراست روی هر پس‌زمینه‌ای
    band_padding = 40
    draw.rectangle(
        [0, y - band_padding, width, y + total_height + band_padding],
        fill=(0, 0, 0, 130),
    )

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (img.width - w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    small_font = load_font(34)
    bbox = draw.textbbox((0, 0), tag_text, font=small_font)
    draw.rectangle(
        [width - bbox[2] - 70, height - 90, width - 10, height - 20],
        fill=(0, 0, 0, 130),
    )
    draw.text(
        (img.width - bbox[2] - 40, height - 70),
        tag_text,
        font=small_font,
        fill=(255, 255, 255, 255),
    )
    return img


def build_quote_image(quote_text, width, height, tag_text="نابگفته", font_size=62, min_font_size=30, bg_image=None):
    """تصویری با پس‌زمینه و متن جمله در وسط می‌سازد و برمی‌گرداند (PIL Image).
    اگر bg_image داده شود (یک PIL Image)، به‌جای ساخت پس‌زمینه‌ی خودکار از همان استفاده می‌شود."""
    if bg_image is not None:
        img = fit_to_size(bg_image, width, height)
    else:
        img = get_background(width, height)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 130))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    max_width = width - 160
    size = font_size

    font = load_font(size)
    lines = wrap_farsi(quote_text, font, draw, max_width)
    while len(lines) > 8 and size > min_font_size:
        size -= 4
        font = load_font(size)
        lines = wrap_farsi(quote_text, font, draw, max_width)

    line_height = size + 16
    total_height = line_height * len(lines)
    y = (img.height - total_height) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (img.width - w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    small_font = load_font(34)
    bbox = draw.textbbox((0, 0), tag_text, font=small_font)
    draw.text(
        (img.width - bbox[2] - 40, img.height - 70),
        tag_text,
        font=small_font,
        fill=(255, 255, 255),
    )
    return img
