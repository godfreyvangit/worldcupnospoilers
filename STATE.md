# World Cup No Spoilers — State of the Product

_Last updated: 2026-06-21_

## What it is

**World Cup No Spoilers** is a single-page website that lets fans watch official
World Cup 2026 highlights **without seeing the score first**. The whole point is
that normal YouTube highlight videos spoil the result through the thumbnail, the
video title, and the suggested-videos rail. This site strips all of that away so
you can watch a match cold.

- **Live at:** [worldcupnospoilers.net](https://worldcupnospoilers.net) (see `CNAME`)
- **Hosted on:** GitHub Pages (static site, no backend server)
- **Monetisation:** a "Support on Ko-fi" button ([ko-fi.com/worldcupnospoilers](https://ko-fi.com/worldcupnospoilers))
- **Analytics:** Google Analytics (tag `G-Q6478RB7CJ`)

## How it works

The product has two halves: a **static front end** and an **automated data pipeline**.

### 1. Front end — `index.html`

A single self-contained HTML file (inline CSS + JS, no build step, no framework).

- Fetches a per-channel JSON file (`matches_bbc.json` / `matches_itv.json`) and
  renders match cards grouped by date (most recent first).
- Each card shows only the **two countries' flags and names** — never a score.
- A dropdown in the header switches between **BBC Football** and **ITV Sport**
  as the highlights source.
- Clicking a card opens a modal video player. To keep things spoiler-free:
  - An **opaque black cover** sits over the player so YouTube's thumbnail (which
    reveals the score) is never visible.
  - A **green title bar** covers the top of the embed where YouTube prints the
    video title (which also reveals the score), showing the two flags instead.
  - Video starts **muted** so autoplay is allowed everywhere (including iOS),
    then unmutes once playback begins. The cover only lifts once the video is
    `PLAYING`/`BUFFERING`, with a 6-second safety fallback.
  - If a video blocks embedding, it falls back to a plain iframe so it still plays.
- The page auto-reloads every 45 minutes to pick up newly published matches.
- Flags come from `flagcdn.com`, mapped from country name via a `FLAGS` lookup.

### 2. Data pipeline — `fetch_matches.py` + GitHub Actions

The match list is built automatically — no manual data entry.

- `fetch_matches.py` queries the **YouTube Data API v3** for recent uploads from
  the BBC Football and ITV Sport channels (`CHANNELS`), looking back
  `LOOKBACK_DAYS = 5` days.
- It filters to genuine match highlights:
  - Title must contain "world cup" **and** "2026".
  - `EXCLUDE_KEYWORDS` drops previews, reactions, compilations, full matches,
    live streams, "alt cast" duplicates, etc. (whole-word matched so "live"
    doesn't trip on "Oliver").
  - `extract_teams()` identifies the two countries by matching against the list
    of all 48 qualified teams (`TEAMS`), with a regex fallback for
    `Team1 v Team2` / `Team1 1-4 Team2` formats. Name variants are normalised to
    canonical names via `CANONICAL` (e.g. "Türkiye" → "Turkey").
- Results are **merged** with the existing JSON (deduped by team+team+date) so
  older matches that have fallen outside the lookback window are never lost.
- `check_missing()` cross-references the two channels and prints a warning when a
  match appears on one channel but not the other (a coverage gap).
- `.github/workflows/update.yml` runs the script on a **cron schedule ~10×/day**
  (evening through early morning UK time, covering match kickoff windows) plus
  manual `workflow_dispatch`. It commits and pushes any changed JSON, which
  GitHub Pages then serves. The `YOUTUBE_API_KEY` is stored as a repo secret.

## Repository layout

| File | Purpose |
|------|---------|
| `index.html` | The entire front end (HTML + CSS + JS, ~570 lines) |
| `fetch_matches.py` | Pipeline that builds the match JSON from the YouTube API |
| `matches_bbc.json` | BBC Football highlights data (currently ~31 matches) |
| `matches_itv.json` | ITV Sport highlights data (currently ~36 matches) |
| `matches.json` | Legacy/empty (`[]`) — no longer referenced by the front end |
| `.github/workflows/update.yml` | Scheduled job that runs the pipeline |
| `CNAME` | Custom domain config for GitHub Pages (`worldcupnospoilers.net`) |
| `.gitignore` | Ignores `__pycache__/` |

## Current status

- **Live and operating.** The tournament is underway and the pipeline is
  committing fresh matches (commit history shows a steady stream of automated
  "Update matches" commits).
- Two channels supported: **BBC** and **ITV**.
- ITV currently has slightly more matches than BBC (36 vs 31) — the cross-channel
  check exists to surface exactly these kinds of coverage gaps.

## Known rough edges / opportunities

- **Stray file:** `.github/workflows/matches.json` sits inside the workflows
  directory and appears to be an accidental commit; it serves no purpose there.
- **Legacy file:** root `matches.json` is empty and unused — safe to remove.
- **Title-matching fragility:** highlight detection depends on broadcasters'
  title conventions. If a channel changes its format, `is_highlight()` /
  `extract_teams()` may silently miss matches.
- **Spoiler cover timing:** the cover-lift logic has a 6-second fallback; on slow
  connections there's a small window where the approach relies on YouTube not
  having painted the thumbnail yet.
- **No automated tests** for the parsing logic in `fetch_matches.py`.
- **Single hardcoded analytics/Ko-fi/flag-CDN** dependencies — all external.
