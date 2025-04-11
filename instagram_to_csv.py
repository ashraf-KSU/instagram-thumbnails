from instagrapi import Client
import csv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import pandas as pd
import requests
from urllib.parse import urlparse
import subprocess

# --- CONFIGURATION ---
USERNAME = "venuekent"
PASSWORD = "Venue2023/24"  # Keep blank or use env var
REPO_PATH = "C:/Users/ayuba/Repository/instagram-thumbnails"
CSV_PATH = os.path.join(REPO_PATH, "instagram_metrics.csv")
THUMBNAIL_DIR = os.path.join(REPO_PATH, "thumbnails")
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/ashraf-KSU/instagram-thumbnails/main/thumbnails/"  # UPDATE with actual repo name

# --- LOGIN ---
cl = Client()
cl.login(USERNAME, PASSWORD)
cl.load_settings("session.json")
cl.dump_settings("session.json")

# --- FETCH RECENT MEDIA ---
uk_timezone = ZoneInfo("Europe/London")
cutoff_date = datetime.now(uk_timezone) - timedelta(days=30)
medias = cl.user_medias(cl.user_id, amount=100)
recent_medias = [m for m in medias if m.taken_at and m.taken_at >= cutoff_date]

# --- MEDIA TYPE MAPPING ---
MEDIA_TYPE_MAPPING = {
    1: "Post",
    2: "Carousel",
    8: "Reel",
    10: "Story",
    11: "IGTV",
}

# --- METRICS EXTRACTION ---
def extract_metrics(insights, media):
    metrics = insights.get("inline_insights_node", {}).get("metrics", {})
    reach = metrics.get("reach_count") or metrics.get("reach", {}).get("value", 0)
    impressions = metrics.get("impression_count") or metrics.get("impressions", {}).get("value", 0)
    saves = getattr(media, "save_count", 0)
    likes = media.like_count or 0
    comments = media.comment_count or 0

    shares = 0
    try:
        shares_nodes = metrics.get("share_count", {}).get("tray", {}).get("nodes", [])
        shares = sum(node.get("value", 0) for node in shares_nodes)
    except:
        pass

    engagement = likes + comments + saves + shares
    engagement_rate = round((engagement / reach) * 100, 2) if reach else 0

    profile_views = metrics.get("owner_profile_views_count", 0)
    story_metrics = {
        "Exits": metrics.get("exits_count", 0),
        "Taps Forward": metrics.get("taps_forward_count", 0),
        "Taps Back": metrics.get("taps_back_count", 0),
        "Replies": metrics.get("replies_count", 0),
        "Follows": metrics.get("follows_count", 0),
    }

    return {
        "Reach": reach,
        "Impressions": impressions,
        "Saves": saves,
        "Shares": shares,
        "Engagement": engagement,
        "Engagement Rate (%)": engagement_rate,
        "Profile Views": profile_views,
        **story_metrics
    }

# --- COLLECT DATA ---
data = []
for media in recent_medias:
    media_id = media.id
    media_type = MEDIA_TYPE_MAPPING.get(getattr(media, "media_type", None), "Other")
    print(f"\n📸 Fetching insights for {media_type}: {media_id}")

    try:
        insights = cl.insights_media(media_id)
        print("🔍 Insights returned.")

        thumb_url = getattr(media, "thumbnail_url", None) or getattr(media, "display_url", None)
        metrics = extract_metrics(insights, media)

        data.append({
            "Post ID": media_id,
            "Media Type": media_type,
            "Taken At": media.taken_at.strftime('%Y-%m-%d') if media.taken_at else None,
            "Caption": (media.caption_text[:60] + "...") if media.caption_text else "",
            "Likes": media.like_count,
            "Comments": media.comment_count,
            "Thumbnail": thumb_url,
            **metrics,
        })

    except Exception as e:
        print("❌ Failed to fetch insights:", e)

# --- DOWNLOAD THUMBNAILS ---
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
local_paths = []
for row in data:
    url = row["Thumbnail"]

    if not url or not str(url).startswith("http"):
        row["Thumbnail Local Path"] = ""
        continue

    url_str = str(url)  # define only after it’s verified

    filename = os.path.basename(urlparse(url_str).path)
    local_path = os.path.join(THUMBNAIL_DIR, filename)

    try:
        if not os.path.exists(local_path):
            r = requests.get(url_str, timeout=10)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
        # Update to GitHub raw URL path
        row["Thumbnail Local Path"] = GITHUB_RAW_BASE + filename
    except Exception as e:
        print(f"❌ Error downloading thumbnail for {row['Post ID']}: {e}")
        row["Thumbnail Local Path"] = ""

# --- WRITE TO CSV ---
fieldnames = list(data[0].keys())
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
print(f"\n✅ CSV saved to {CSV_PATH}")

# --- PUSH TO GITHUB ---
try:
    subprocess.run(["git", "-C", REPO_PATH, "add", "."], check=True)
    subprocess.run(["git", "-C", REPO_PATH, "commit", "-m", "Daily update"], check=True)
    subprocess.run(["git", "-C", REPO_PATH, "push"], check=True)
    print("✅ Pushed to GitHub.")
except subprocess.CalledProcessError as e:
    print(f"❌ Git push failed: {e}")