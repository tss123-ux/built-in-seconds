"""Pulls per-post metrics from Instagram and YouTube into analytics/<date>.json (runs 21:00 IST, before the nightly build)."""
import os, json, glob, datetime, requests
from zoneinfo import ZoneInfo
GRAPH = "https://graph.instagram.com/v23.0"; now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
out = {"pulled_at": now.isoformat(), "instagram": {}, "youtube": {}, "account": {}}
uid, tok = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
if uid and tok:
    acct = requests.get(f"{GRAPH}/{uid}", params={"fields": "followers_count,media_count", "access_token": tok}).json(); out["account"]["instagram"] = acct
    media = requests.get(f"{GRAPH}/{uid}/media", params={"fields": "id,caption,timestamp,permalink,like_count,comments_count", "limit": 50, "access_token": tok}).json().get("data", [])
    for m in media:
        ins = requests.get(f"{GRAPH}/{m['id']}/insights", params={"metric": "views,reach,saved,shares,total_interactions,ig_reels_avg_watch_time,ig_reels_video_view_total_time", "access_token": tok}).json()
        m["insights"] = {x["name"]: x["values"][0]["value"] for x in ins.get("data", [])} if "data" in ins else ins
        out["instagram"][m["id"]] = m
    # keep the long-lived token fresh (valid 60 days; refresh extends it)
    requests.get(f"{GRAPH}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": tok})
if os.environ.get("YT_REFRESH_TOKEN"):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    ids = [json.load(open(p)).get("youtube", {}).get("id") for p in glob.glob("queue/*/published.json")]; ids = [i for i in ids if i]
    if ids:
        yt = build("youtube", "v3", credentials=creds)
        for v in yt.videos().list(part="statistics,snippet", id=",".join(ids[:50])).execute().get("items", []):
            out["youtube"][v["id"]] = {"title": v["snippet"]["title"], **v["statistics"]}
        try:
            ya = build("youtubeAnalytics", "v2", credentials=creds)
            r = ya.reports().query(ids="channel==MINE", startDate="2026-10-01", endDate=now.strftime("%Y-%m-%d"), metrics="views,averageViewPercentage,averageViewDuration,subscribersGained,shares", dimensions="video", filters="video==" + ",".join(ids[:50])).execute()
            for row in r.get("rows", []): out["youtube"].setdefault(row[0], {}).update(dict(zip(["views_a", "avg_view_pct", "avg_view_s", "subs_gained", "shares"], row[1:])))
        except Exception as e: out["youtube_analytics_error"] = str(e)
os.makedirs("analytics", exist_ok=True); json.dump(out, open(f"analytics/{now.strftime('%Y-%m-%d')}.json", "w"), indent=2); print("saved")
