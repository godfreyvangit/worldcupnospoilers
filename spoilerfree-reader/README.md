# Spoiler-Free Reader

An RSS-reader-style web app for sports highlights on YouTube — **without ever seeing the score**. Log in, subscribe to channels/playlists (curated sport presets or any custom URL), and get a private feed where titles and thumbnails are never shown. Videos play spoiler-free: embeddable ones in an in-page player behind a black cover, embed-disabled ones (e.g. Premier League) in a spoiler-safe YouTube popup.

Generalizes the proven player and filtering from [worldcupnospoilers.net](https://worldcupnospoilers.net).

> **This folder is a self-contained project.** It lives inside the worldcupnospoilers repo only because this session couldn't create a new repository. To extract it: copy this `spoilerfree-reader/` directory into a fresh repo — nothing outside it is referenced.

## How it works

- **Ingestion is RSS, not the YouTube Data API.** Every channel/playlist has a free feed (`youtube.com/feeds/videos.xml?channel_id=…`). No API key, no quota. Feeds only carry ~15 recent videos; the database keeps older items (rolling window).
- **Filtering** ports the battle-tested pipeline from `fetch_matches.py`: config-driven exclude keywords (pens-only clips, pre-game shows, watch-alongs…), knockout-title handling, team extraction, and filter-before-dedup with highlights preferred over moment clips. See `supabase/functions/_shared/filter.ts` + `tests/filter.test.ts`.
- **Spoiler guarantee by absence:** `items` has no thumbnail column, and the client reads `items_client`, a view that omits the raw title. Nothing score-bearing can reach the browser.
- **Embed-disabled videos** are detected server-side at ingest (oEmbed probe; `videos.list part=status` if `YOUTUBE_API_KEY` is set) and open via `src/lib/popout.ts`: a popup sized to crop YouTube's title/related rail (using the legacy bare-player `watch_popup` endpoint when available), the YouTube app on mobile, or a full tab when the Spoiler Shield extension is installed.
- **Spoiler Shield extension** (`extension/`): optional MV3 extension hiding titles, related videos, comments, end screens and the tab title on YouTube watch pages.
- **External RSS interop:** each subscription can expose a secret sanitized RSS URL (titles rewritten to "Team A v Team B — Highlights", no thumbnails) for use in Feedly/Reeder/etc.; links land on `/watch/<id>` which plays spoiler-free.

## Setup

1. **Supabase project** (free tier): create one at supabase.com, then in the SQL editor run `supabase/migrations/0001_init.sql` and `0002_presets_seed.sql`.
2. **Auth:** enable Email (magic link) under Authentication → Providers. Add your site URL to the redirect allowlist.
3. **Edge Functions:** `supabase functions deploy sync-subscription refresh-all user-feed`. Set secrets:
   ```sh
   supabase secrets set APP_URL=https://your-app.example
   # optional but recommended for reliable embeddability detection:
   supabase secrets set YOUTUBE_API_KEY=...
   ```
4. **Scheduled refresh:** run `supabase/cron.sql` in the SQL editor (fill in project ref + service-role key).
5. **Frontend:** copy `.env.example` to `.env` with your project URL + anon key, then:
   ```sh
   npm install
   npm run dev      # local
   npm run build    # static build in build/ — deploy to Vercel/Netlify/any static host
   ```
6. **Extension (optional):** chrome://extensions → Developer mode → Load unpacked → `extension/`. Add your production domain to `extension/manifest.json`'s second `matches` list so the app can detect it.

## Day-one spikes (do these in a real browser before launch)

Both were designed in from this sandbox, which cannot reach YouTube — verify behavior once:
1. **`watch_popup`:** open `https://www.youtube.com/watch_popup?v=<embed-disabled video>` — if it shows a bare player, the popup path is perfect as-is; if it redirects to `/watch`, the sized-popup crop still hides the title (no change needed, just confirm).
2. **oEmbed probe:** `curl -s -o /dev/null -w '%{http_code}' 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<embed-disabled video>'` — expect non-200 for embed-disabled, 200 for normal videos. If it doesn't discriminate, set `YOUTUBE_API_KEY` so detection uses `videos.list part=status` (1 quota unit per 50 videos — negligible).

## Testing

```sh
npm test          # filter pipeline against real production titles
npm run build     # must pass
```

RLS check: create two users, subscribe each to something, and confirm each user's JWT sees only their own rows in `subscriptions`/`items_client`.

Spoiler audit: with the app open, the network tab must show **zero** requests to `i.ytimg.com` (thumbnails) and the DOM must never contain a raw video title.

## Known limitations (by design, disclosed to users)

- A brand-new subscription backfills only the ~15 most recent videos (RSS depth). History accumulates from then on.
- Embed-disabled videos play on YouTube itself. The popup/extension hides the title, related videos and end screens; on mobile the YouTube app shows the title below the player — a small, one-time-disclosed leak.
- We never proxy or re-host streams; playback is always YouTube's own player (embedded or on youtube.com). This keeps the product within YouTube's Terms of Service.
