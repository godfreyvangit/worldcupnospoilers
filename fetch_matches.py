import json
import os
import re
import urllib.request
import urllib.parse
from datetime import date, timedelta


# Each channel writes its own JSON file consumed by the dropdown on the homepage
CHANNELS = [
    {"id": "UCli0KmmXMDjcgqvsheHfv-Q", "name": "BBC Football", "file": "matches_bbc.json"},
    {"id": "UCBzDz6beXDfMtfxQdEutD_w", "name": "ITV Sport", "file": "matches_itv.json"},
    {"playlist": "PLSoN6Th-EepMUaxmTobuR_SBwVkdkxdfO", "name": "Fox Sports (USA)", "file": "matches_fox.json", "allow_extended": True},
    {"id": "UC--i2rV5NCxiEIPefr3l-zQ", "name": "TSN (Canada)", "file": "matches_tsn.json", "allow_extended": True, "region": "CA"},
]

# Only search YouTube for videos published in the last N days.
# Older matches are already persisted in the JSON files and won't be lost.
LOOKBACK_DAYS = 5

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
    "Austria", "Belgium", "Bosnia and Herzegovina", "Bosnia-Herzegovina", "Croatia", "Czechia", "Czech Republic",
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
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
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
    "reacts", "football daily",
    # TSN posts pre-game shows and "First 10 Minutes" livestream clips that aren't highlights
    "pre-game", "pregame", "first 10", "first ten",
    # Knockout games get a separate penalties-only clip as well as the full
    # highlights (which already include the shootout). Drop the pens-only one.
    # "shootout"/"shoot-out" only appears in those clips; full highlights are
    # titled "Highlights"/"Full Highlights" and never contain it. We avoid the
    # bare word "penalties" because a full-highlights title may say "on penalties".
    "shootout", "shoot-out", "shoot out", "pens only", "penalties only",
]

# Knockout-stage markers. Channels (e.g. ITV) sometimes drop "2026" from
# knockout titles ("... | All Action Knockout Match! | FIFA World Cup"), so we
# accept "FIFA World Cup" + one of these as a 2026 stand-in.
KNOCKOUT_MARKERS = [
    "round of", "last 16", "last 32", "knockout",
    "quarter-final", "quarter final", "quarterfinal",
    "semi-final", "semi final", "semifinal", "final",
]


def is_highlight(title, allow_extended=False):
    t = title.lower()
    # Channels vary the word order: BBC "2026 FIFA World Cup",
    # FIFA "FIFA World Cup 2026". Match on the stable parts. We do NOT require the
    # word "highlights" because BBC occasionally omits it (e.g. "Team v Team |
    # 2026 FIFA World Cup | Group A"); team extraction + EXCLUDE_KEYWORDS guard
    # against non-match clips instead.
    if "world cup" not in t:
        return False
    # Normally require "2026", but accept knockout titles that omit it.
    if "2026" not in t and not any(m in t for m in KNOCKOUT_MARKERS):
        return False
    # Some channels (e.g. Fox Sports) title their highlight packages "Extended
    # Highlights", so "extended" must not exclude them there. BBC/ITV keep the
    # default behaviour.
    keywords = EXCLUDE_KEYWORDS
    if allow_extended:
        keywords = [kw for kw in EXCLUDE_KEYWORDS if kw != "extended"]
    # Whole-word match so short keywords like "live" don't trip on "deliver",
    # "Oliver", "alive", etc.
    return not any(re.search(r"\b" + re.escape(kw) + r"\b", t) for kw in keywords)


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


def match_key(team1, team2):
    """Order-independent key for a team pair."""
    t1 = CANONICAL.get(team1.lower(), team1).lower()
    t2 = CANONICAL.get(team2.lower(), team2).lower()
    return frozenset([t1, t2])


def check_missing(matches_by_channel):
    """Cross-reference channels: flag any match present on one but absent on another."""
    channel_names = list(matches_by_channel.keys())
    if len(channel_names) < 2:
        return

    sets = {
        name: {match_key(m["team1"], m["team2"]) for m in matches}
        for name, matches in matches_by_channel.items()
    }

    print("\n--- Cross-channel coverage check ---")
    any_gap = False
    for i, ch_a in enumerate(channel_names):
        for ch_b in channel_names[i + 1:]:
            only_a = sets[ch_a] - sets[ch_b]
            only_b = sets[ch_b] - sets[ch_a]
            for pair in sorted(only_a, key=str):
                teams = " vs ".join(sorted(pair))
                print(f"⚠️  On {ch_a} but not {ch_b}: {teams}")
                any_gap = True
            for pair in sorted(only_b, key=str):
                teams = " vs ".join(sorted(pair))
                print(f"⚠️  On {ch_b} but not {ch_a}: {teams}")
                any_gap = True
    if not any_gap:
        print("✅  Both channels have the same set of matches.")


def fetch_page(api_key, channel, page_token=None):
    # A channel can be sourced either from a curated playlist or from a
    # channel-wide search. Playlists are pulled in full (no date window) since
    # they're already a hand-picked list of highlights.
    if channel.get("playlist"):
        params = {
            "part": "snippet",
            "playlistId": channel["playlist"],
            "maxResults": "50",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        url = "https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params)
    else:
        published_after = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
        params = {
            "part": "snippet",
            "channelId": channel["id"],
            "maxResults": "50",
            "order": "date",
            "type": "video",
            "publishedAfter": f"{published_after}T00:00:00Z",
            # Search only returns videos viewable in this region. BBC/ITV are
            # licensed for GB; TSN's highlights are Canada-only, so they need CA
            # or the API silently drops them.
            "regionCode": channel.get("region", "GB"),
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
        data = fetch_page(api_key, channel, page_token)

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            # Playlist items carry the video id under snippet.resourceId;
            # search results carry it under id.
            if channel.get("playlist"):
                video_id = snippet.get("resourceId", {}).get("videoId", "")
            else:
                video_id = item["id"].get("videoId", "")
            title = snippet.get("title", "")
            published = snippet.get("publishedAt", "")[:10]  # YYYY-MM-DD

            print(f"TITLE: {title}")

            if not is_highlight(title, channel.get("allow_extended", False)):
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

    matches_by_channel = {}

    for channel in CHANNELS:
        try:
            videos = fetch_highlights(api_key, channel)
        except Exception as e:
            # Don't let one channel failing wipe the others; keep existing file
            print(f"ERROR fetching {channel['name']}: {e}")
            continue

        # Load existing matches so we never lose ones that fell off the API results
        existing = []
        if os.path.exists(channel["file"]):
            with open(channel["file"]) as f:
                existing = json.load(f)

        allow_extended = channel.get("allow_extended", False)
        seen = {}  # match key -> index in matches
        matches = []
        for v in existing + videos:
            # Filter BEFORE dedup: otherwise a non-highlight (e.g. a pens-only
            # clip that was saved before the filter existed) can win the dedup
            # slot for a match and crowd out the real highlights, which then
            # vanish entirely when the non-highlight is stripped.
            if not is_highlight(v["title"], allow_extended):
                continue
            key = f"{v['team1'].lower()}_{v['team2'].lower()}_{v['date']}"
            if key not in seen:
                seen[key] = len(matches)
                matches.append(v)
            else:
                # Same match already kept. Prefer a proper "highlights" video
                # over a single-goal/moment clip (e.g. "X Scores Opener ...").
                idx = seen[key]
                kept = matches[idx]
                if "highlight" in v["title"].lower() and "highlight" not in kept["title"].lower():
                    matches[idx] = v

        matches.sort(key=lambda x: x["date"] or "", reverse=True)

        with open(channel["file"], "w") as f:
            json.dump(matches, f, indent=2)

        print("\n===================================")
        print(f"{channel['name']}: written {len(matches)} matches -> {channel['file']}")
        print("===================================\n")

        matches_by_channel[channel["name"]] = matches

    check_missing(matches_by_channel)


if __name__ == "__main__":
    main()
