import os
import json
import random
import subprocess
import requests

from common import build_quote_image, build_quote_overlay

QUOTES_FILE = "quotes.json"
POSTED_FILE = "posted_instagram.json"
AUDIO_DIR = "audio"
FIXED_VIDEO_PATH = "assets/background.mp4"  # اگر این فایل وجود داشته باشد، به‌جای پس‌زمینه‌ی خودکار استفاده می‌شود

REEL_WIDTH = 1080
REEL_HEIGHT = 1920
MAX_DURATION = 20  # حداکثر طول ریلز به ثانیه
FPS = 30

IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
GRAPH_API_VERSION = "v21.0"

# برای ساخت لینک عمومی ویدیو (raw.githubusercontent.com) از روی همین ریپازیتوری
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")  # مثل owner/repo
GITHUB_SHA = os.environ.get("GITHUB_SHA")


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
        posted = []
        remaining = quotes
    quote = random.choice(remaining)
    posted.append(quote)
    save_json(POSTED_FILE, posted)
    return quote


def pick_audio():
    if not os.path.isdir(AUDIO_DIR):
        raise RuntimeError(f"پوشه‌ی {AUDIO_DIR} پیدا نشد؛ باید چند فایل mp3 داخلش بگذاری.")
    files = [f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    if not files:
        raise RuntimeError(f"هیچ فایل صوتی داخل پوشه‌ی {AUDIO_DIR} پیدا نشد.")
    return os.path.join(AUDIO_DIR, random.choice(files))


def get_audio_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def get_video_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def build_video(frame_path, audio_path, out_path):
    """حالت خودکار: پس‌زمینه‌ی ساخته‌شده + افکت زوم آرام (Ken Burns)."""
    duration = min(get_audio_duration(audio_path), MAX_DURATION)
    frames = int(duration * FPS)
    filter_complex = (
        f"[0:v]scale={REEL_WIDTH*2}:{REEL_HEIGHT*2},"
        f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}:s={REEL_WIDTH}x{REEL_HEIGHT}:fps={FPS}[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", frame_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", "-t", str(duration),
        out_path,
    ]
    subprocess.run(cmd, check=True)


def build_video_on_fixed_background(video_path, overlay_path, audio_path, out_path):
    """حالت ویدیوی ثابت: متن به‌صورت لایه‌ی شفاف روی ویدیوی خودِ کاربر می‌نشیند.
    اگر ویدیو کوتاه‌تر از موزیک باشد لوپ می‌شود، اگر بلندتر باشد بریده می‌شود.
    صدای اصلی ویدیو با موزیک انتخابی جایگزین می‌شود."""
    duration = min(get_audio_duration(audio_path), MAX_DURATION)
    filter_complex = (
        f"[0:v]scale={REEL_WIDTH}:{REEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={REEL_WIDTH}:{REEL_HEIGHT},setsar=1[bg];"
        f"[bg][1:v]overlay=0:0:shortest=1[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_path,
        "-loop", "1", "-i", overlay_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-t", str(duration), "-shortest",
        out_path,
    ]
    subprocess.run(cmd, check=True)


def git_commit_video(path):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", path], check=True)
    subprocess.run(["git", "commit", "-m", "add generated reel [skip ci]"], check=False)
    subprocess.run(["git", "push"], check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return sha


def public_video_url(sha, path):
    return f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{sha}/{path}"


def create_media_container(video_url, caption):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    r = requests.post(url, data=payload, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def wait_until_ready(container_id, max_tries=30, delay=10):
    import time
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{container_id}"
    for _ in range(max_tries):
        r = requests.get(url, params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN}, timeout=30)
        r.raise_for_status()
        status = r.json().get("status_code")
        print("status:", status)
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError("پردازش ویدیو در اینستاگرام با خطا مواجه شد.")
        time.sleep(delay)
    raise TimeoutError("زمان انتظار برای آماده شدن ویدیو تمام شد.")


def publish_media(container_id):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}/media_publish"
    r = requests.post(url, data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    quote = pick_quote()
    audio_path = pick_audio()
    print("Selected audio:", audio_path)

    video_path = "media/reel.mp4"
    os.makedirs("media", exist_ok=True)

    if os.path.exists(FIXED_VIDEO_PATH):
        print("Using fixed background video:", FIXED_VIDEO_PATH)
        overlay = build_quote_overlay(quote, REEL_WIDTH, REEL_HEIGHT)
        overlay_path = "reel_overlay.png"
        overlay.save(overlay_path)
        build_video_on_fixed_background(FIXED_VIDEO_PATH, overlay_path, audio_path, video_path)
    else:
        print("No fixed video found, generating background automatically")
        img = build_quote_image(quote, REEL_WIDTH, REEL_HEIGHT)
        frame_path = "reel_frame.png"
        img.save(frame_path)
        build_video(frame_path, audio_path, video_path)

    sha = git_commit_video(video_path)
    video_url = public_video_url(sha, video_path)
    print("Public video URL:", video_url)

    caption = f"{quote}\n\n#انگیزشی #نابگفته\n📍 @nab_gofte"
    container_id = create_media_container(video_url, caption)
    print("Container created:", container_id)

    wait_until_ready(container_id)
    result = publish_media(container_id)
    print("Published:", result)


if __name__ == "__main__":
    main()
