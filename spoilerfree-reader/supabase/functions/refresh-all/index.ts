// Scheduled refresh over all subscriptions (stalest first). Invoke from
// pg_cron (see supabase/cron.sql) or manually. Protected by requiring the
// service-role key as the bearer token.
import { CORS, serviceClient, syncSubscription } from '../_shared/sync.ts';

Deno.serve(async (req) => {
	if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });

	const auth = req.headers.get('Authorization') ?? '';
	if (auth !== `Bearer ${Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')}`) {
		return new Response('forbidden', { status: 403, headers: CORS });
	}

	const db = serviceClient();
	const { data: subs, error } = await db
		.from('subscriptions')
		.select('id, user_id, source_type, youtube_id, filter_config')
		.order('last_synced_at', { ascending: true, nullsFirst: true })
		.limit(50);
	if (error) return new Response(error.message, { status: 500, headers: CORS });

	const results: Record<string, string> = {};
	for (const sub of subs ?? []) {
		try {
			const r = await syncSubscription(db, sub);
			results[sub.id] = `ok (${r.found} found, ${r.inserted} upserted)`;
		} catch (e) {
			// One bad subscription must not block the rest.
			results[sub.id] = `error: ${e instanceof Error ? e.message : e}`;
		}
	}

	return new Response(JSON.stringify(results), {
		headers: { ...CORS, 'content-type': 'application/json' }
	});
});
