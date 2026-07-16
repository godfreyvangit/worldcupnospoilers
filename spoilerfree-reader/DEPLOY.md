# Deploy runbook — Spoiler-Free Reader

A copy-paste guide to get the app live. ~20 minutes. Everything is free-tier.
You need: a [Supabase](https://supabase.com) account, a [Vercel](https://vercel.com)
(or Netlify) account, and the [Supabase CLI](https://supabase.com/docs/guides/cli)
(`npm i -g supabase`).

---

## 1. Create the Supabase project
1. supabase.com → **New project**. Note the project **ref** (the `xxxx` in `xxxx.supabase.co`) and your DB password.
2. In the dashboard: **Project Settings → API**. Copy:
   - **Project URL** (`https://xxxx.supabase.co`)
   - **anon public** key
   - **service_role** key (keep secret)

## 2. Create the database schema
Dashboard → **SQL Editor** → run each file's contents, in order:
1. `supabase/migrations/0001_init.sql`
2. `supabase/migrations/0002_presets_seed.sql`

> The preset `youtube_id`s are best-guesses — verify the Premier League / NFL / NBA
> channel IDs and update rows in the `presets` table if a preset returns nothing.

## 3. Enable magic-link auth
Dashboard → **Authentication → Providers → Email**: enable it (magic link is on by
default). Then **Authentication → URL Configuration**: set **Site URL** to your future
app URL (from step 6, e.g. `https://your-app.vercel.app`) and add it to **Redirect URLs**.
(You can revisit this after step 6 once you know the URL.)

## 4. Deploy the Edge Functions
From the `spoilerfree-reader/` directory:
```sh
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase functions deploy sync-subscription refresh-all user-feed
```
Set secrets (service_role/url are auto-available to functions; these are the extras):
```sh
supabase secrets set APP_URL=https://your-app.vercel.app
# Optional but recommended for reliable embed-disabled detection (1 quota unit / 50 videos):
supabase secrets set YOUTUBE_API_KEY=your-youtube-data-api-key
```

## 5. Schedule the auto-refresh
Dashboard → **SQL Editor** → run `supabase/cron.sql` **after** editing it to insert your
project ref and service_role key. (Enable the `pg_cron` and `pg_net` extensions first via
**Database → Extensions** if prompted.)

## 6. Deploy the frontend (Vercel)
1. Push this repo to GitHub (or `vercel` CLI from `spoilerfree-reader/`).
2. Vercel → **New Project** → import the repo → set **Root Directory** to
   `spoilerfree-reader` (if it lives inside the worldcupnospoilers repo).
3. **Environment Variables** (from step 1):
   - `PUBLIC_SUPABASE_URL` = `https://xxxx.supabase.co`
   - `PUBLIC_SUPABASE_ANON_KEY` = your anon key
4. Deploy. `vercel.json` already handles the SPA rewrite; `build/` is the output.
5. Copy the deployed URL and, if you skipped it, complete step 3's Site URL / Redirect URL
   and step 4's `APP_URL` secret with it.

Netlify works too: build command `npm run build`, publish dir `build`, same env vars
(`static/_redirects` handles SPA routing).

## 7. First run
Open the app → sign in with your email (magic link) → add a preset or paste a channel URL
→ you should see flags-only cards. Tap one: embeddable videos play in-page; embed-disabled
ones open the spoiler-safe popup.

## 8. Wire it to the World Cup site
Tell the assistant (or edit yourself) the deployed URL, and the **Custom feeds** link in the
main site's `index.html` header gets pointed at it. Until then it's a harmless placeholder.

---

### Optional: Spoiler Shield extension
For full desktop protection on embed-disabled videos, load `extension/` as an unpacked
Chrome extension (chrome://extensions → Developer mode → Load unpacked). Add your deployed
domain to the second `matches` array in `extension/manifest.json` first, so the app can
detect it.

### Troubleshooting
- **A feed returns 0 items:** the channel may not publish match highlights to YouTube, or
  the preset's `filter_config` is too strict. Check the function logs (Dashboard → Edge
  Functions → Logs).
- **Login link goes nowhere:** Site URL / Redirect URLs (step 3) must exactly match the
  deployed origin.
- **Embed-disabled detection unreliable without an API key:** set `YOUTUBE_API_KEY`
  (step 4) — the keyless oEmbed probe is a best-effort fallback.
