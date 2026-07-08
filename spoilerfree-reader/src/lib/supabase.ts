import { createClient } from '@supabase/supabase-js';
import { PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY } from '$env/static/public';

export const supabase = createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY);

export interface Item {
	id: string;
	video_id: string;
	label1: string | null;
	label2: string | null;
	published_at: string;
	embeddable: boolean;
	is_read: boolean;
	subscription_id: string;
}

export interface Subscription {
	id: string;
	title: string;
	folder: string | null;
	source_type: 'channel' | 'playlist';
	youtube_id: string;
	last_synced_at: string | null;
	feed_token: string | null;
}

export interface Preset {
	id: string;
	sport: string;
	name: string;
	source_type: 'channel' | 'playlist';
	youtube_id: string;
	filter_config: Record<string, unknown>;
}
