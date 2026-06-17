import json
import re
import subprocess
import sys


BBC_CHANNEL_ID = "UCli0KmmXMDjcgqvsheHfv-Q"

SEARCH_QUERIES = [
    "2026 FIFA World Cup Highlights BBC Football Group",
    "2026 FIFA World Cup Highlights BBC Football",
]


def is_highlight(title):
    t = title.lower()
    return "2026 fifa world cup" in t and "highlight" in t


def extract_teams(title):
    first_part = title.split("|")[0].strip()
    first_part = re.sub(r"[^\x00-\x7F]+", "", first_part).strip()

    m = re.match(r"^(.+?)\s+\d+[\-–]\d+\s+(.+?)$", first_part)
    if not m:
        return None, None

    return m.group(1).strip(), m.group(2).strip()


def search_youtube(query, max_results=50):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        f"ytsearch{max_results}:{query}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr[:300]}")
        return []

    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def fetch_video_date(video_id):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-warnings",
        "--skip-download",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        d = data.get("upload_date", "")
        if d and len(d) == 8:
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    except Exception:
        pass
    return None


def fetch_highlights():
    print("Searching YouTube for BBC World Cup highlights...\n")

    seen_ids = set()
    candidates = []

    for query in SEARCH_QUERIES:
        print(f"Query: {query}")
        items = search_youtube(query)
        for item in items:
            video_id = item.get("id", "")
            channel_id = item.get("channel_id", "")
            title = item.get("title", "")
            duration = item.get("duration") or 0

            if video_id in seen_ids:
                continue
            if channel_id != BBC_CHANNEL_ID:
                continue
            if duration and duration <= 60:
                continue
            if not is_highlight(title):
                continue

            seen_ids.add(video_id)
            candidates.append({"id": video_id, "title": title})
            print(f"  FOUND: {title}")

    print(f"\nFetching dates for {len(candidates)} highlights...")
    videos = []
    for c in candidates:
        title = c["title"]
        video_id = c["id"]

        team1, team2 = extract_teams(title)
        print(f"\nTITLE: {title}")
        if not team1 or not team2:
            print("FAILED TEAM EXTRACTION")
            continue

        date = fetch_video_date(video_id)
        print(f"TEAM1: {team1}  TEAM2: {team2}  DATE: {date}")

        videos.append({
            "videoId": video_id,
            "title": title,
            "team1": team1,
            "team2": team2,
            "date": date,
            "channel": "BBC Football",
        })

    return videos


def main():
    videos = fetch_highlights()

    seen = set()
    matches = []
    for v in videos:
        if v["videoId"] not in seen:
            seen.add(v["videoId"])
            matches.append(v)

    matches.sort(key=lambda x: x["date"] or "", reverse=True)

    with open("matches.json", "w") as f:
        json.dump(matches, f, indent=2)

    print("\n===================================")
    print(f"Written {len(matches)} matches")
    print("Output saved to matches.json")
    print("===================================\n")


if __name__ == "__main__":
    main()
