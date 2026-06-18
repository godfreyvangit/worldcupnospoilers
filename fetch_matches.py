import json
import re
import subprocess
import sys


SEARCHES = [
    ("BBC Football", "2026 FIFA World Cup Highlights BBC Football"),
    ("BBC Sport", "2026 FIFA World Cup Highlights BBC Sport"),
]

MAX_RESULTS = 50


def is_highlight(title):
    t = title.lower()
    is_wc = "2026 fifa world cup" in t or "fifa world cup 2026" in t
    is_match = "highlight" in t
    return is_wc and is_match


def extract_teams(title):
    """
    Handles multiple formats:
      Iraq 1-4 Norway 🇮🇶 🇳🇴 | HAALAND DEBUT DOUBLE! | 2026 FIFA World Cup Highlights | Group G
      Highlights | Canada 1-1 Bosnia and Herzegovina | FIFA World Cup 2026™
      Spain vs Cape Verde Extended Highlights 🌎🏆 2026 FIFA World Cup™
      ARGENTINA vs ALGERIA 3-0 | 2026 FIFA World Cup | Match Highlights
    """
    # Strip emoji and symbols, normalise
    clean = re.sub(r"[^\x00-\x7F]+", " ", title).strip()

    # Format: "Team1 X-X Team2" (score in middle)
    m = re.match(r"^(.+?)\s+\d+[\-–]\d+\s+(.+?)(?:\s*[|\|].*)?$", clean)
    if m:
        t1, t2 = m.group(1).strip(), m.group(2).strip()
        # Strip trailing noise from team2
        t2 = re.split(r"\s+(?:extended|highlights|match)", t2, flags=re.IGNORECASE)[0].strip()
        if t1 and t2:
            return t1, t2

    # Format: "Highlights | Team1 X-X Team2 | ..."
    m = re.match(r"^highlights\s*\|\s*(.+?)\s+\d+[\-–]\d+\s+(.+?)(?:\s*\|.*)?$", clean, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Format: "Team1 vs Team2 ..." or "TEAM1 vs TEAM2 X-X | ..."
    m = re.match(r"^(.+?)\s+vs\.?\s+(.+?)(?:\s+\d+[\-–]\d+)?(?:\s*[|\|].*)?$", clean, re.IGNORECASE)
    if m:
        t1 = m.group(1).strip()
        t2 = re.split(r"\s+(?:extended|highlights|match|\d)", m.group(2), flags=re.IGNORECASE)[0].strip()
        if t1 and t2:
            return t1, t2

    return None, None


def parse_upload_date(date_str):
    """Convert yt-dlp upload_date (YYYYMMDD) to YYYY-MM-DD."""
    if date_str and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return None


def search_videos(label, query):
    print(f"\nSearching: {query}\n")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        f"ytsearch{MAX_RESULTS}:{query}",
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
            "channel": label,
        })
        print(f"ADDED (date: {upload_date})")
        print("---")

    return videos


def main():
    all_matches = []
    seen = set()

    for label, query in SEARCHES:
        videos = search_videos(label, query)
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
