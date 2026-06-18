import json
import re
import subprocess
import sys


CHANNELS = {
    "BBC Football": "https://www.youtube.com/@BBCFootball/videos",
    "ITV Football": "https://www.youtube.com/@ITVFootball/videos",
}

MAX_VIDEOS = 50

# All 48 World Cup 2026 nations — sorted longest-first so multi-word names match before substrings
WC_TEAMS = sorted([
    "Bosnia and Herzegovina", "Saudi Arabia", "South Korea", "South Africa",
    "New Zealand", "Ivory Coast", "Cape Verde", "Cabo Verde", "Costa Rica",
    "United States", "Korea Republic", "IR Iran", "DR Congo", "Congo DR",
    "Côte d'Ivoire", "Trinidad and Tobago",
    "Argentina", "Australia", "Belgium", "Brazil", "Cameroon", "Canada",
    "Colombia", "Croatia", "Czechia", "Ecuador", "England", "France",
    "Germany", "Ghana", "Hungary", "Iran", "Iraq", "Jamaica", "Japan",
    "Jordan", "Mexico", "Morocco", "Netherlands", "Nigeria", "Norway",
    "Panama", "Paraguay", "Peru", "Poland", "Portugal", "Qatar",
    "Romania", "Scotland", "Senegal", "Serbia", "Slovenia", "Spain",
    "Sweden", "Switzerland", "Tunisia", "Turkey", "Türkiye",
    "Ukraine", "Uruguay", "USA", "Uzbekistan", "Venezuela",
    "Wales", "Algeria", "Egypt", "Cuba", "Haiti", "Curacao", "Curaçao",
], key=len, reverse=True)


def is_wc_video(title):
    t = title.lower()
    # BBC uses "FIFA 2026 World Cup", ITV may use "2026 FIFA World Cup"
    is_wc = "fifa 2026 world cup" in t or "2026 fifa world cup" in t
    # BBC posts "Football Daily" roundups; others may say "highlights"
    is_match = "football daily" in t or "highlight" in t
    return is_wc and is_match


def extract_teams(title):
    found = []
    title_lower = title.lower()
    for team in WC_TEAMS:
        if team.lower() in title_lower:
            found.append(team)
        if len(found) == 2:
            break
    if len(found) >= 2:
        return found[0], found[1]
    return None, None


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

        if not is_wc_video(title):
            print("SKIPPED: not a World Cup match video")
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
