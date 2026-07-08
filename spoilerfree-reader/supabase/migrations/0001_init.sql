-- Spoiler-Free Reader: initial schema
-- Users live in auth.users (Supabase Auth, email magic-link).

-- ============================================================
-- presets: curated sport sources, global and read-only to users
-- ============================================================
create table public.presets (
  id            uuid primary key default gen_random_uuid(),
  sport         text not null,
  name          text not null,
  source_type   text not null check (source_type in ('channel', 'playlist')),
  youtube_id    text not null,
  filter_config jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

-- ============================================================
-- subscriptions: a user's subscription (RSS-reader "feed")
-- ============================================================
create table public.subscriptions (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  preset_id      uuid references public.presets (id),
  source_type    text not null check (source_type in ('channel', 'playlist')),
  youtube_id     text not null,
  title          text not null,
  folder         text,
  filter_config  jsonb not null default '{}'::jsonb,
  last_synced_at timestamptz,
  -- secret token enabling the sanitized external RSS output; null = disabled
  feed_token     uuid,
  created_at     timestamptz not null default now(),
  unique (user_id, source_type, youtube_id)
);

-- ============================================================
-- items: ingested videos.
-- raw_title is SERVER-ONLY (filtering/dedup); never exposed to clients.
-- There is deliberately NO thumbnail column: the spoiler guarantee is
-- enforced by absence.
-- ============================================================
create table public.items (
  id              uuid primary key default gen_random_uuid(),
  subscription_id uuid not null references public.subscriptions (id) on delete cascade,
  user_id         uuid not null references auth.users (id) on delete cascade,
  video_id        text not null,
  raw_title       text not null,
  label1          text,
  label2          text,
  published_at    timestamptz,
  embeddable      boolean not null default true,
  is_read         boolean not null default false,
  created_at      timestamptz not null default now(),
  unique (subscription_id, video_id)
);

create index items_user_published_idx on public.items (user_id, published_at desc);
create index items_subscription_idx on public.items (subscription_id);

-- ============================================================
-- Client-facing view: omits raw_title so the score-bearing title
-- can never reach the browser.
-- security_invoker makes the view run with the caller's RLS.
-- ============================================================
create view public.items_client
  with (security_invoker = true) as
  select id, video_id, label1, label2, published_at, embeddable, is_read, subscription_id
  from public.items;

-- ============================================================
-- Row-Level Security
-- ============================================================
alter table public.presets enable row level security;
create policy "presets are readable by everyone"
  on public.presets for select
  using (true);

alter table public.subscriptions enable row level security;
create policy "users manage own subscriptions"
  on public.subscriptions for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

alter table public.items enable row level security;
create policy "users read own items"
  on public.items for select
  using (user_id = auth.uid());
-- Clients may only toggle read state on their own items; all other writes
-- happen via Edge Functions using the service_role key.
create policy "users mark own items read"
  on public.items for update
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

revoke insert, delete on public.items from anon, authenticated;
-- Restrict client updates to the is_read column only.
revoke update on public.items from anon, authenticated;
grant update (is_read) on public.items to authenticated;
grant select on public.items_client to authenticated;
