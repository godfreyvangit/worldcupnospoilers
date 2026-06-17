import json
import os
import re
import urllib.request
import urllib.parse


BBC_CHANNEL_ID = "UCli0KmmXMDjcgqvsheHfv-Q"
EARLIEST_DATE = "2026-06-08"


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


def search_page(api_key, page_token=None):
    params = {
        "part": "snippet",
        "q": "2026 FIFA World Cup Highlights BBC Football",
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
    print("Searching YouTube API for BBC World Cup highlights...\n")

    videos = []
    page_token = None
    pages = 0

    while pages < 4:
        data = search_page(api_key, page_token)
        pages += 1

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId", "")
            title = snippet.get("title", "")
            video_id = item["id"].get("videoId", "")
            published = snippet.get("publishedAt", "")[:10]

            print(f"TITLE: {title}  CHANNEL: {channel_id}")

            if channel_id != BBC_CHANNEL_ID:
                print("SKIPPED (wrong channel)")
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
