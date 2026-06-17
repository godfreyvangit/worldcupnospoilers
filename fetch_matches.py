import os
import json
import re
from googleapiclient.discovery import build

API_KEY = os.environ["YOUTUBE_API_KEY"]

CHANNELS = {
    "BBC Football": "UCli0KmmXMDjcgqvsheHfv-Q",
}

SEARCH_QUERY = "2026 FIFA World Cup Highlights"


def is_highlight(title):
    return "2026 fifa world cup highlights" in title.lower()


def extract_teams(title):
    """
    Example:

    Iraq 1-4 Norway 🇮🇶 🇳🇴 | HAALAND DEBUT DOUBLE! |
    2026 FIFA World Cup Highlights | Group G

    Returns:
    ("Iraq", "Norway")
    """

    first_part = title.split("|")[0].strip()

    match = re.match(
        r"^(.+?)\s+\d+\-\d+\s+(.+?)(?:\s+[^\w\s].*)?$",
        first_part
    )

    if not match:
        return None, None

    team1 = match.group(1).strip()
    team2 = match.group(2).strip()

    return team1, team2


def fetch_channel_videos(youtube, channel_id, channel_name):
    results = []

    print(f"\nSearching {channel_name}...\n")

    response = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=50,
        order="date",
        type="video",
        q=SEARCH_QUERY,
    ).execute()

    print(f"YouTube returned {len(response.get('items', []))} videos\n")

    for item in response.get("items", []):

        title = item["snippet"]["title"]

        print("TITLE:", title)

        if not is_highlight(title):
            print("SKIPPED: Not a World Cup highlight")
            print("---")
            continue

        team1, team2 = extract_teams(title)

        print("TEAM1:", team1)
        print("TEAM2:", team2)

        if not team1 or not team2:
            print("FAILED TEAM EXTRACTION")
            print("---")
            continue

        results.append(
            {
                "videoId": item["id"]["videoId"],
                "title": title,
                "team1": team1,
                "team2": team2,
                "date": item["snippet"]["publishedAt"][:10],
                "channel": channel_name,
            }
        )

        print("ADDED")
        print("---")

    return results


def main():
    youtube = build(
        "youtube",
        "v3",
        developerKey=API_KEY,
    )

    all_matches = []
    seen = set()

    for channel_name, channel_id in CHANNELS.items():

        videos = fetch_channel_videos(
            youtube,
            channel_id,
            channel_name,
        )

        for video in videos:

            key = (
                f"{video['team1'].lower()}_"
                f"{video['team2'].lower()}_"
                f"{video['date']}"
            )

            if key not in seen:
                seen.add(key)
                all_matches.append(video)

    all_matches.sort(
        key=lambda x: x["date"],
        reverse=True,
    )

    with open("matches.json", "w") as f:
        json.dump(all_matches, f, indent=2)

    print("\n===================================")
    print(f"Written {len(all_matches)} matches")
    print("Output saved to matches.json")
    print("===================================\n")


if __name__ == "__main__":
    main()
