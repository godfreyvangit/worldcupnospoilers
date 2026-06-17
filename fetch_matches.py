import json
import re
import subprocess
import sys


BBC_CHANNEL_ID = "UCli0KmmXMDjcgqvsheHfv-Q"
BBC_CHANNEL_URL = f"https://www.youtube.com/channel/{BBC_CHANNEL_ID}/videos"


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


def parse_upload_date(date_str):
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return None


def fetch_bbc_videos():
    print("Fetching BBC Football channel...\n")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--geo-bypass-country", "GB",
        "--extractor-args", "youtubetab:approximate_date",
        BBC_CHANNEL_URL,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: {result.stderr[:500]}")
        return []

    videos = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        title = item.get("title", "")
        video_id = item.get("id", "")
        upload_date = item.get("upload_date", "")
        duration = item.get("duration") or 0

        if duration <= 60:
            continue

        print(f"TITLE: {title}")

        if not is_highlight(title):
            print("SKIPPED")
            print("---")
            continue

        team1, team2 = extract_teams(title)
        print(f"TEAM1: {team1}")
        print(f"TEAM2: {team2}")

        if not team1 or not team2:
            print("FAILED TEAM EXTRACTION")
            print("---")
            continue

        videos.append({
            "videoId": video_id,
            "title": title,
            "team1": team1,
            "team2": team2,
            "date": parse_upload_date(upload_date),
            "channel": "BBC Football",
        })
        print(f"ADDED (date: {upload_date})")
        print("---")

    return videos


def main():
    videos = fetch_bbc_videos()

    seen = set()
    matches = []
    for v in videos:
        key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
        if key not in seen:
            seen.add(key)
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
