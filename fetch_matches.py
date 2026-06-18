import json
import os
import re
import urllib.request
import urllib.parse


# Each channel writes its own JSON file consumed by the dropdown on the homepage
CHANNELS = [
    {"id": "UCli0KmmXMDjcgqvsheHfv-Q", "name": "BBC Football", "file": "matches_bbc.json"},
    {"id": "UCBzDz6beXDfMtfxQdEutD_w", "name": "ITV Sport", "file": "matches_itv.json"},
]
EARLIEST_DATE = "2026-06-08"

# The 48 qualified FIFA World Cup 2026 teams (with spelling variants)
TEAMS = [
    "Canada", "Mexico", "United States", "USA",
    "Australia", "Iraq", "IR Iran", "Iran", "Japan", "Jordan",
    "South Korea", "Republic of Korea", "Korea Republic", "Qatar", "Saudi Arabia", "Uzbekistan",
    "Algeria", "Cape Verde", "Cabo Verde", "DR Congo", "Congo DR", "Democratic Republic of Congo",
    "Ivory Coast", "Cote d'Ivoire", "Egypt", "Ghana", "Morocco",
    "Senegal", "South Africa", "Tunisia",
    "Curaçao", "Curacao", "Haiti", "Panama",
    "Argentina", "Brazil", "Colombia", "Ecuador", "Paraguay", "Uruguay",
    "New Zealand",
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
    "korea republic": "South Korea",
    "south korea": "South Korea",
    "ir iran": "Iran",
    "iran": "Iran",
    "türkiye": "Turkey",
    "turkey": "Turkey",
    "united states": "USA",
    "usa": "USA",
}


# Non-highlight clips (previews, reactions, full matches, live streams) would be
# mislabelled as matches, so exclude them explicitly. We can't rely on the word
# "highlights" being present (BBC sometimes omits it), so this list is the main guard.
EXCLUDE_KEYWORDS = [
    "preview", "compilation", "top 10", "top ten", "best goals",
    "every goal", "all goals", "review", "reaction", "press conference",
    "alt cast",  # FIFA posts an alternate-commentary duplicate of each match
    "live", "watch along", "watchalong", "full match", "extended",
    "documentary", "trailer", "q&a", "predict", "analysis", "explained",
    "interview", "build-up", "build up", "vlog", "behind the scenes",
]


def is_highlight(title):
    t = title.lower()
    # Channels vary the word order: BBC "2026 FIFA World Cup",
    # FIFA "FIFA World Cup 2026". Match on the stable parts. We do NOT require the
    # word "highlights" because BBC occasionally omits it (e.g. "Team v Team |
    # 2026 FIFA World Cup | Group A"); team extraction + EXCLUDE_KEYWORDS guard
    # against non-match clips instead.
    if "world cup" not in t or "2026" not in t:
        return False
    # Whole-word match so short keywords like "live" don't trip on "deliver",
    # "Oliver", "alive", etc.
    return not any(re.search(r"\b" + re.escape(kw) + r"\b", t) for kw in EXCLUDE_KEYWORDS)


def extract_teams(title):
    # Match against the known team list (handles any title format)
    title_lower = title.lower()
    hits = {}  # canonical -> position in title
    for team in sorted(TEAMS, key=len, reverse=True):
        pos = title_lower.find(team.lower())
        if pos == -1:
            continue
        canonical = CANONICAL.get(team.lower(), team)
        if canonical not in hits:
            hits[canonical] = pos
    ordered = sorted(hits, key=lambda c: hits[c])
    if len(ordered) >= 2:
        return ordered[0], ordered[1]

    # Fallback: regex-based extraction
    first_part = title.split("|")[0].strip()
    first_part = re.sub(r"[^\x00-\x7F]+", "", first_part).strip()
    first_part = re.sub(r"\s+[Hh]ighlights\s*$", "", first_part).strip()

    # "Team1 1-4 Team2" format
    m = re.match(r"^(.+?)\s+\d+[\-–]\d+\s+(.+?)$", first_part)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # "Team1 v Team2" format
    m = re.match(r"^(.+?)\s+v\s+(.+?)$", first_part)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return None, None


def fetch_page(api_key, channel_id, page_token=None):
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "maxResults": "50",
        "order": "date",
        "type": "video",
        "publishedAfter": f"{EARLIEST_DATE}T00:00:00Z",
        "regionCode": "GB",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def fetch_highlights(api_key, channel):
    print(f"Fetching {channel['name']} channel via YouTube API...\n")

    videos = []
    page_token = None

    while True:
        data = fetch_page(api_key, channel["id"], page_token)

        for item in data.get("items", []):
            video_id = item["id"].get("videoId", "")
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            published = snippet.get("publishedAt", "")[:10]  # YYYY-MM-DD

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
                "date": published,
                "channel": channel["name"],
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

    for channel in CHANNELS:
        try:
            videos = fetch_highlights(api_key, channel)
        except Exception as e:
            # Don't let one channel failing wipe the others; keep existing file
            print(f"ERROR fetching {channel['name']}: {e}")
            continue

        seen = set()
        matches = []
        for v in videos:
            key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
            if key not in seen:
                seen.add(key)
                matches.append(v)

        matches.sort(key=lambda x: x["date"] or "", reverse=True)

        with open(channel["file"], "w") as f:
            json.dump(matches, f, indent=2)

        print("\n===================================")
        print(f"{channel['name']}: written {len(matches)} matches -> {channel['file']}")
        print("===================================\n")


if __name__ == "__main__":
    main()
