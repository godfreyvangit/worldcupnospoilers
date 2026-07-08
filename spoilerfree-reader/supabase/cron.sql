-- Schedule refresh-all every 30 minutes via pg_cron + pg_net.
-- Run once in the Supabase SQL editor AFTER deploying the functions.
-- Replace YOUR-PROJECT and YOUR-SERVICE-ROLE-KEY.
select cron.schedule(
  'refresh-subscriptions',
  '*/30 * * * *',
  $$
  select net.http_post(
    url := 'https://YOUR-PROJECT.supabase.co/functions/v1/refresh-all',
    headers := '{"Authorization": "Bearer YOUR-SERVICE-ROLE-KEY", "Content-Type": "application/json"}'::jsonb,
    body := '{}'::jsonb
  );
  $$
);
