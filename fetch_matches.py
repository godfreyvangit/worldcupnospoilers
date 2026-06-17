import json
import re
import subprocess
import sys


CHANNELS = {
    "BBC Football": "https://www.youtube.com/@BBCFootball/videos",
    "ITV Football": "https://www.youtube.com/@ITVFootball/videos",
}

MAX_VIDEOS = 50


def is_highlight(title):
    t = title.lower()
    return "2026 fifa world cup" in t and "highlight" in t


def extract_teams(title):
    """
    Example:
    Iraq 1-4 Norway | 2026 FIFA World Cup Highlights | Group G
    Returns: ("Iraq", "Norway")
    """
    first_part = title.split("|")[0].strip()
    first_part = re.sub(r"[^\x00-\x7F]+", "", first_part).strip()

    match = re.match(r"^(.+?)\s+\d+[\-–]\d+\s+(.+?)$", first_part)
    if not match:
        return None, None

    return match.group(1).strip(), match.group(2).strip()


def parse_upload_date(date_str):
    """Convert yt-dlp upload_date (YYYYMMDD) to YYYY-MM-DD."""
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return None


def fetch_channel_videos(channel_name, channel_url):
    print(f"\nFetching {channel_name}...\n")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--playlist-end", str(MAX_VIDEOS),
        channel_url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR fetching {channel_name}: {result.stderr[:500]}")
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
        upload_date = parse_upload_date(item.get("upload_date", ""))

        print(f"TITLE: {title}")

        if not is_highlight(title):
            print("SKIPPED: not a World Cup highlight")
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
            "date": upload_date,
            "channel": channel_name,
        })
        print(f"ADDED (date: {upload_date})")
        print("---")

    return videos


def main():
    all_matches = []
    seen = set()

    for channel_name, channel_url in CHANNELS.items():
        videos = fetch_channel_videos(channel_name, channel_url)
        for v in videos:
            key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
            if key not in seen:
                seen.add(key)
                all_matches.append(v)

    all_matches.sort(key=lambda x: x["date"] or "", reverse=True)

    with open("matches.json", "w") as f:
        json.dump(all_matches, f, indent=2)

    print("\n===================================")
    print(f"Written {len(all_matches)} matches")
    print("Output saved to matches.json")
    print("===================================\n")


if __name__ == "__main__":
    main()
