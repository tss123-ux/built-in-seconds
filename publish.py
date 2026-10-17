"""Publishes today's queued video to YouTube Shorts and Instagram Reels.
Runs in GitHub Actions at 06:00 IST. Reads queue/<YYYY-MM-DD>/{video.mp4,post.json}; writes published.json."""
import os, json, time, datetime, sys, requests
from zoneinfo import ZoneInfo
GRAPH = "https://graph.instagram.com/v23.0"
today = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
day = sys.argv[1] if len(sys.argv) > 1 else today
d = f"queue/{day}"
if not os.path.exists(f"{d}/video.mp4"): print("nothing queued for", day); sys.exit(0)
done_path = f"{d}/published.json"; done = json.load(open(done_path)) if os.path.exists(done_path) else {}
post = json.load(open(f"{d}/post.json")); video = f"{d}/video.mp4"

def youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": post["yt_title"], "description": post["yt_description"],
                        "tags": [t.strip() for t in post.get("yt_tags", "").split(",") if t.strip()], "categoryId": "27"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}}
    r = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video, resumable=True)).execute()
    if os.path.exists(f"{d}/cover.jpg"):
        try: yt.thumbnails().set(videoId=r["id"], media_body=MediaFileUpload(f"{d}/cover.jpg", mimetype="image/jpeg")).execute()
        except Exception as e: print("thumbnail not set (channel may need phone verification):", e)
    return {"id": r["id"], "url": f"https://youtube.com/shorts/{r['id']}", "privacy": r["status"]["privacyStatus"]}

def instagram():
    uid, tok = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    c = requests.post(f"{GRAPH}/{uid}/media", data={"media_type": "REELS", "upload_type": "resumable",
        "caption": post["ig_caption"], "share_to_feed": "true", "access_token": tok,
        **({"cover_url": f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/main/{d}/cover.jpg"} if os.path.exists(f"{d}/cover.jpg") and os.environ.get("GITHUB_REPOSITORY") else {"thumb_offset": "1000"})}).json()
    if "id" not in c: raise RuntimeError(c)
    size = os.path.getsize(video)
    up = requests.post(f"https://rupload.facebook.com/ig-api-upload/v23.0/{c['id']}",
        headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=open(video, "rb")).json()
    if not up.get("success"): raise RuntimeError(up)
    for _ in range(60):
        s = requests.get(f"{GRAPH}/{c['id']}", params={"fields": "status_code,status", "access_token": tok}).json()
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": raise RuntimeError(s)
        time.sleep(10)
    p = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": c["id"], "access_token": tok}).json()
    if "id" not in p: raise RuntimeError(p)
    link = requests.get(f"{GRAPH}/{p['id']}", params={"fields": "permalink", "access_token": tok}).json().get("permalink")
    return {"id": p["id"], "url": link}

errors = {}
for name, fn in (("youtube", youtube), ("instagram", instagram)):
    if name in done: continue
    try: done[name] = fn(); print(name, "OK", done[name])
    except Exception as e: errors[name] = str(e); print(name, "FAILED", e)
done["published_at"] = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
if errors: done["errors"] = errors
json.dump(done, open(done_path, "w"), indent=2)
sys.exit(1 if errors else 0)
