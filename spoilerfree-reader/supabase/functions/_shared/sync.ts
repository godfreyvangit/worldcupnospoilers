// Core sync logic shared by sync-subscription (on demand) and refresh-all (cron).
import { createClient, SupabaseClient } from 'jsr:@supabase/supabase-js@2';
import { filterAndDedup, GENERIC_CONFIG, type FilterConfig } from './filter.ts';
import { detectEmbeddable, fetchFeedEntries } from './youtube.ts';

export function serviceClient(): SupabaseClient {
	return createClient(
		Deno.env.get('SUPABASE_URL')!,
		Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
	);
}

export interface SubscriptionRow {
	id: string;
	user_id: string;
	source_type: 'channel' | 'playlist';
	youtube_id: string;
	filter_config: FilterConfig | null;
}

/** Sync one subscription: fetch RSS, filter, detect embeddability, upsert. */
export async function syncSubscription(
	db: SupabaseClient,
	sub: SubscriptionRow
): Promise<{ found: number; inserted: number }> {
	const config: FilterConfig =
		sub.filter_config && Object.keys(sub.filter_config).length > 0
			? sub.filter_config
			: GENERIC_CONFIG;

	const entries = await fetchFeedEntries(sub.source_type, sub.youtube_id);
	const items = filterAndDedup(entries, config);

	const embeddable = await detectEmbeddable(
		items.map((i) => i.videoId),
		Deno.env.get('YOUTUBE_API_KEY') ?? undefined
	);

	let inserted = 0;
	for (const item of items) {
		const { error, count } = await db
			.from('items')
			.upsert(
				{
					subscription_id: sub.id,
					user_id: sub.user_id,
					video_id: item.videoId,
					raw_title: item.title,
					label1: item.label1,
					label2: item.label2,
					published_at: item.published || null,
					embeddable: embeddable.get(item.videoId) ?? true
				},
				{ onConflict: 'subscription_id,video_id', ignoreDuplicates: false, count: 'exact' }
			);
		if (error) throw new Error(`upsert failed: ${error.message}`);
		inserted += count ?? 0;
	}

	await db
		.from('subscriptions')
		.update({ last_synced_at: new Date().toISOString() })
		.eq('id', sub.id);

	return { found: items.length, inserted };
}

export const CORS = {
	'Access-Control-Allow-Origin': '*',
	'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type'
};
