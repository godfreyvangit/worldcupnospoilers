import json
import os
import re
import urllib.request
import urllib.parse


BBC_CHANNEL_ID = "UCli0KmmXMDjcgqvsheHfv-Q"
EARLIEST_DATE = "2026-06-08"

# The 48 qualified FIFA World Cup 2026 teams (with spelling variants)
TEAMS = [
    # Hosts
    "Canada", "Mexico", "United States", "USA",
    # AFC (Asia)
    "Australia", "Iraq", "Iran", "Japan", "Jordan",
    "South Korea", "Republic of Korea", "Qatar", "Saudi Arabia", "Uzbekistan",
    # CAF (Africa)
    "Algeria", "Cape Verde", "Cabo Verde", "DR Congo", "Congo DR", "Democratic Republic of Congo",
    "Ivory Coast", "Cote d'Ivoire", "Egypt", "Ghana", "Morocco",
    "Senegal", "South Africa", "Tunisia",
    # CONCACAF
    "Curaçao", "Curacao", "Haiti", "Panama",
    # CONMEBOL (South America)
    "Argentina", "Brazil", "Colombia", "Ecuador", "Paraguay", "Uruguay",
    # OFC
    "New Zealand",
    # UEFA (Europe)
    "Austria", "Belgium", "Bosnia and Herzegovina", "Croatia", "Czechia", "Czech Republic",
    "England", "France", "Germany", "Netherlands", "Norway", "Portugal",
    "Scotland", "Spain", "Sweden", "Switzerland", "Turkey", "Türkiye",
]

# Canonical names for display (normalize variants)
CANONICAL = {
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "cabo verde": "Cape Verde",
    "cape verde": "Cape Verde",
    "congo dr": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "dr congo": "DR Congo",
    "cote d'ivoire": "Ivory Coast",
    "ivory coast": "Ivory Coast",
    "republic of korea": "South Korea",
    "south korea": "South Korea",
    "türkiye": "Turkey",
    "turkey": "Turkey",
    "united states": "USA",
    "usa": "USA",
}


def is_highlight(title):
    t = title.lower()
    return "2026 fifa world cup" in t and "highlight" in t


def extract_teams(title):
    title_lower = title.lower()
    # Find each team and where it appears. Sort candidates by length desc so
    # longer names ("South Korea") win over substrings ("Korea") at the same spot.
    hits = {}  # canonical -> earliest position
    for team in sorted(TEAMS, key=len, reverse=True):
        pos = title_lower.find(team.lower())
        if pos == -1:
            continue
        canonical = CANONICAL.get(team.lower(), team)
        # Skip if this match overlaps a longer name already found at this spot
        if canonical in hits:
            continue
        hits[canonical] = pos
    # Order teams by their position in the title (team1 appears first)
    ordered = sorted(hits, key=lambda c: hits[c])
    if len(ordered) >= 2:
        return ordered[0], ordered[1]

    # Fallback: regex-based extraction
    first_part = title.split("|")[0].strip()
    first_part = re.sub(r"[^\x00-\x7F]+", "", first_part).strip()
    first_part = re.sub(r"\s+[Hh]ighlights\s*$", "", first_part).strip()

    m = re.match(r"^(.+?)\s+\d+[\-–]\d+\s+(.+?)$", first_part)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = re.match(r"^(.+?)\s+v\s+(.+?)$", first_part)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return None, None


def fetch_page(api_key, page_token=None):
    params = {
        "part": "snippet",
        "q": "2026 FIFA World Cup Highlights",
        "maxResults": "50",
        "order": "date",
        "type": "video",
        "publishedAfter": f"{EARLIEST_DATE}T00:00:00Z",
        "regionCode": "GB",
        "relevanceLanguage": "en",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def fetch_highlights(api_key):
    print("Searching for BBC Football highlights via YouTube API...\n")

    videos = []
    page_token = None
    pages = 0

    while pages < 5:
        data = fetch_page(api_key, page_token)
        pages += 1

        for item in data.get("items", []):
            video_id = item["id"].get("videoId", "")
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId", "")
            title = snippet.get("title", "")
            published = snippet.get("publishedAt", "")[:10]

            print(f"TITLE: {title}")

            if channel_id != BBC_CHANNEL_ID:
                print("SKIPPED (not BBC Football)")
                print("---")
                continue

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
                "date": published,
                "channel": "BBC Football",
            })
            print(f"ADDED (date: {published})")
            print("---")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY environment variable not set")
        return

    videos = fetch_highlights(api_key)

    seen = set()
    matches = []
    for v in videos:
        key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
        if key not in seen:
            seen.add(key)
            matches.append(v)

    matches.sort(key=lambda x: x["date"] or "", reverse=True)

    # Safety net: never overwrite a populated matches.json with an empty result
    # (e.g. API quota error or a transient search glitch).
    if not matches:
        existing = []
        if os.path.exists("matches.json"):
            try:
                with open("matches.json") as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        if existing:
            print("\nFound 0 matches; keeping existing matches.json unchanged.")
            return

    with open("matches.json", "w") as f:
        json.dump(matches, f, indent=2)

    print("\n===================================")
    print(f"Written {len(matches)} matches")
    print("Output saved to matches.json")
    print("===================================\n")


if __name__ == "__main__":
    main()
