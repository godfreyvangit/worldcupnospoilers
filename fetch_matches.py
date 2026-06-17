import os
import json
import re
from googleapiclient.discovery import build

API_KEY = os.environ["YOUTUBE_API_KEY"]

CHANNELS = {
    "BBC Football": "UCnJ1r80tMKnWlPS99TMICdg",
}

WORLD_CUP_KEYWORDS = ["world cup 2026", "fifa world cup", "worldcup2026", "fifaworldcup"]

TEAM_NAMES = [
    "england", "scotland", "france", "germany", "spain", "portugal",
    "netherlands", "belgium", "croatia", "austria", "norway", "sweden",
    "switzerland", "czechia", "turkey", "türkiye", "bosnia and herzegovina",
    "brazil", "argentina", "colombia", "ecuador", "uruguay", "paraguay",
    "mexico", "usa", "united states", "canada", "panama", "haiti",
    "curaçao", "curacao",
    "japan", "south korea", "korea republic", "australia", "iran", "ir iran",
    "iraq", "saudi arabia", "jordan", "qatar", "uzbekistan",
    "morocco", "senegal", "ghana", "egypt", "algeria", "tunisia",
    "south africa", "côte d'ivoire", "ivory coast", "congo dr", "dr congo",
    "cabo verde", "cape verde", "new zealand"
]

def extract_teams(title):
    title_lower = title.lower()
    found = []
    for t in TEAM_NAMES:
        if t in title_lower and t not in found:
            found.append(t)
    if len(found) >= 2:
        return found[0].title(), found[1].title()
    parts = re.split(r'\bv\b|\bvs\.?\b', title, flags=re.IGNORECASE)
    if len(parts) >= 2:
        t1 = parts[0].strip().split("|")[-1].strip()
        t2 = parts[1].strip().split("|")[0].strip()
        return t1, t2
    return None, None

def is_highlight(title):
    title_lower = title.lower()
    is_wc = any(kw in title_lower for kw in WORLD_CUP_KEYWORDS)
    has_highlight = "highlight" in title_lower
    return is_wc and has_highlight

def fetch_channel_videos(youtube, channel_id, channel_name):
    results = []
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=50,
        order="date",
        type="video",
        q="World Cup 2026 highlights"
    )
    response = request.execute()

    for item in response.get("items", []):
        title = item["snippet"]["title"]
        if not is_highlight(title):
            continue

        team1, team2 = extract_teams(title)
        if not team1 or not team2:
            continue

        published = item["snippet"]["publishedAt"][:10]
        video_id = item["id"]["videoId"]

        results.append({
            "videoId": video_id,
            "title": title,
            "team1": team1,
            "team2": team2,
            "date": published,
            "channel": channel_name
        })

    return results

def main():
    youtube = build("youtube", "v3", developerKey=API_KEY)

    all_matches = []
    seen = set()

    for channel_name, channel_id in CHANNELS.items():
        videos = fetch_channel_videos(youtube, channel_id, channel_name)
        for v in videos:
            key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
            if key not in seen:
                seen.add(key)
                all_matches.append(v)

    all_matches.sort(key=lambda x: x["date"])

    with open("matches.json", "w") as f:
        json.dump(all_matches, f, indent=2)

    print(f"Written {len(all_matches)} matches to matches.json")

if __name__ == "__main__":
    main()
