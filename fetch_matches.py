import json
import re
import subprocess
import sys


EARLIEST_DATE = "20260608"
MAX_RESULTS = 200


def is_highlight(title):
    t = title.lower()
    return "2026 fifa world cup" in t and "highlight" in t


def extract_teams(title):
    """
    Iraq 1-4 Norway 🇮🇶 🇳🇴 | HAALAND DEBUT DOUBLE! | 2026 FIFA World Cup Highlights | Group G
    Returns: ("Iraq", "Norway")
    """
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


def fetch_highlights():
    print("Searching YouTube for 2026 FIFA World Cup Highlights...\n")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        f"ytsearch{MAX_RESULTS}:2026 FIFA World Cup Highlights",
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
        channel = item.get("channel", "") or item.get("uploader", "") or ""

        if "bbc" not in channel.lower():
            print(f"SKIP (not BBC, channel={channel!r}): {title[:60]}")
            continue

        if upload_date and upload_date < EARLIEST_DATE:
            print(f"SKIP (too old {upload_date}): {title[:60]}")
            continue

        if duration <= 60:
            continue

        print(f"TITLE: {title}")
        print(f"CHANNEL: {channel}")

        if not is_highlight(title):
            print("SKIPPED (not a highlight)")
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
            "channel": "BBC Sport",
        })
        print(f"ADDED (date: {upload_date})")
        print("---")

    return videos


def main():
    videos = fetch_highlights()

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
