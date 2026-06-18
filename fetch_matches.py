import json
import os
import re
import urllib.request
import urllib.parse


BBC_CHANNEL_ID = "UCli0KmmXMDjcgqvsheHfv-Q"
EARLIEST_DATE = "2026-06-08"

# All 48 FIFA World Cup 2026 teams
TEAMS = [
    "Argentina", "Australia", "Austria", "Belgium", "Bolivia", "Bosnia and Herzegovina",
    "Brazil", "Canada", "Cape Verde", "Chile", "Colombia", "Costa Rica",
    "Croatia", "Curaçao", "Curacao", "Czechia", "Czech Republic",
    "DR Congo", "Democratic Republic of Congo",
    "Ecuador", "Egypt", "England", "France", "Germany", "Ghana", "Greece",
    "Haiti", "Honduras", "Hungary",
    "Indonesia", "Iran", "Iraq", "Ivory Coast", "Cote d'Ivoire",
    "Japan", "Jordan", "Kenya",
    "Mali", "Mexico", "Montenegro", "Morocco",
    "Netherlands", "New Zealand", "Nigeria", "North Korea", "Norway",
    "Panama", "Paraguay", "Peru", "Poland", "Portugal",
    "Qatar",
    "Romania",
    "Saudi Arabia", "Scotland", "Senegal", "Serbia", "Slovakia", "Slovenia",
    "South Africa", "South Korea", "Republic of Korea", "Spain", "Sweden", "Switzerland",
    "Thailand", "Tunisia", "Turkey",
    "Ukraine", "United States", "USA", "Uruguay", "Uzbekistan",
    "Venezuela",
]

# Canonical names for display (normalize variants)
CANONICAL = {
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "democratic republic of congo": "DR Congo",
    "dr congo": "DR Congo",
    "cote d'ivoire": "Ivory Coast",
    "ivory coast": "Ivory Coast",
    "republic of korea": "South Korea",
    "south korea": "South Korea",
    "united states": "USA",
    "usa": "USA",
}


def is_highlight(title):
    t = title.lower()
    return "2026 fifa world cup" in t and "highlight" in t


def extract_teams(title):
    title_lower = title.lower()
    found = []
    # Sort by length desc so "South Korea" matches before "Korea"
    for team in sorted(TEAMS, key=len, reverse=True):
        if team.lower() in title_lower:
            canonical = CANONICAL.get(team.lower(), team)
            if canonical not in found:
                found.append(canonical)
        if len(found) == 2:
            break
    if len(found) >= 2:
        return found[0], found[1]

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
        "channelId": BBC_CHANNEL_ID,
        "maxResults": "50",
        "order": "date",
        "type": "video",
        "publishedAfter": f"{EARLIEST_DATE}T00:00:00Z",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def fetch_highlights(api_key):
    print("Fetching BBC Football channel via YouTube API...\n")

    videos = []
    page_token = None

    while True:
        data = fetch_page(api_key, page_token)

        for item in data.get("items", []):
            video_id = item["id"].get("videoId", "")
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            published = snippet.get("publishedAt", "")[:10]

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

    with open("matches.json", "w") as f:
        json.dump(matches, f, indent=2)

    print("\n===================================")
    print(f"Written {len(matches)} matches")
    print("Output saved to matches.json")
    print("===================================\n")


if __name__ == "__main__":
    main()
