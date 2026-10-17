# Built in Seconds: autopilot

* `queue/<YYYY-MM-DD>/` holds `video.mp4`, `cover.jpg` and `post.json` for that morning. Claude's nightly run fills it.
* `.github/workflows/publish.yml` posts the queued item to YouTube Shorts + Instagram Reels at **06:00 IST**.
* `.github/workflows/analytics.yml` pulls metrics into `analytics/` at **21:00 IST**, which Claude reads before building the next video.
* `playbook.md`, `calendar.md` and `log.csv` are the agent's brain.
* **To veto a post:** delete its `queue/<date>/` folder before 6 AM.
