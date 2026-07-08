// POST { subscription_id } (user JWT required) -> syncs that subscription.
// Also accepts { resolve: "<pasted url>" } to translate a URL/handle into
// { source_type, youtube_id } without creating anything (used by the add-feed UI).
import { createClient } from 'jsr:@supabase/supabase-js@2';
import { CORS, serviceClient, syncSubscription } from '../_shared/sync.ts';
import { resolveSource } from '../_shared/youtube.ts';

Deno.serve(async (req) => {
	if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });

	try {
		const body = await req.json();

		// URL/handle resolution mode (no DB writes; no auth needed beyond anon key)
		if (typeof body.resolve === 'string') {
			const resolved = await resolveSource(body.resolve);
			return json(resolved);
		}

		// Sync mode: verify the caller owns the subscription.
		const auth = req.headers.get('Authorization') ?? '';
		const userClient = createClient(
			Deno.env.get('SUPABASE_URL')!,
			Deno.env.get('SUPABASE_ANON_KEY')!,
			{ global: { headers: { Authorization: auth } } }
		);
		const { data: userData, error: userErr } = await userClient.auth.getUser();
		if (userErr || !userData.user) return json({ error: 'unauthenticated' }, 401);

		const db = serviceClient();
		const { data: sub, error } = await db
			.from('subscriptions')
			.select('id, user_id, source_type, youtube_id, filter_config')
			.eq('id', body.subscription_id)
			.eq('user_id', userData.user.id)
			.single();
		if (error || !sub) return json({ error: 'subscription not found' }, 404);

		const result = await syncSubscription(db, sub);
		return json(result);
	} catch (e) {
		return json({ error: e instanceof Error ? e.message : String(e) }, 500);
	}
});

function json(data: unknown, status = 200): Response {
	return new Response(JSON.stringify(data), {
		status,
		headers: { ...CORS, 'content-type': 'application/json' }
	});
}
