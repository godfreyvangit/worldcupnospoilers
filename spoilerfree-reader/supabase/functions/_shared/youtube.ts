// YouTube RSS + embeddability helpers. Keyless by default; the Data API is
// used only as an optional fallback when YOUTUBE_API_KEY is configured.

import type { FeedEntry } from './filter.ts';

const FEED_BASE = 'https://www.youtube.com/feeds/videos.xml';

export function feedUrl(sourceType: 'channel' | 'playlist', youtubeId: string): string {
	return sourceType === 'playlist'
		? `${FEED_BASE}?playlist_id=${encodeURIComponent(youtubeId)}`
		: `${FEED_BASE}?channel_id=${encodeURIComponent(youtubeId)}`;
}

/**
 * Fetch and parse a YouTube RSS feed (Atom). Returns newest-first entries.
 * The feed only carries ~15 most recent videos; persistence in the DB
 * provides the rolling window beyond that.
 */
export async function fetchFeedEntries(
	sourceType: 'channel' | 'playlist',
	youtubeId: string
): Promise<FeedEntry[]> {
	const res = await fetch(feedUrl(sourceType, youtubeId), {
		headers: { accept: 'application/atom+xml, application/xml, text/xml' }
	});
	if (!res.ok) {
		throw new Error(`YouTube RSS fetch failed (${res.status}) for ${sourceType} ${youtubeId}`);
	}
	return parseFeedXml(await res.text());
}

/**
 * Minimal Atom parsing with regex — the YouTube feed shape is stable and
 * flat, and this avoids an XML dependency in the edge runtime. Each <entry>
 * has exactly one <yt:videoId>, <title> and <published>.
 */
export function parseFeedXml(xml: string): FeedEntry[] {
	const entries: FeedEntry[] = [];
	const blocks = xml.split('<entry>').slice(1);
	for (const block of blocks) {
		const videoId = block.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1];
		const rawTitle = block.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? '';
		const published = block.match(/<published>([^<]+)<\/published>/)?.[1] ?? '';
		if (!videoId) continue;
		entries.push({ videoId, title: decodeXmlEntities(rawTitle.trim()), published });
	}
	return entries;
}

function decodeXmlEntities(s: string): string {
	return s
		.replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#39;|&apos;/g, "'")
		.replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)));
}

/**
 * Embeddability detection.
 * Preferred (reliable): Data API videos.list part=status, 50 ids per call,
 * when YOUTUBE_API_KEY is set. Fallback (keyless): oEmbed probe — YouTube's
 * oEmbed endpoint returns a non-200 for embed-disabled videos.
 * Unknown/error cases default to embeddable=true so the in-page player's
 * onError → popup fallback still covers them at play time.
 */
export async function detectEmbeddable(
	videoIds: string[],
	apiKey?: string
): Promise<Map<string, boolean>> {
	const result = new Map<string, boolean>();
	if (videoIds.length === 0) return result;

	if (apiKey) {
		for (let i = 0; i < videoIds.length; i += 50) {
			const batch = videoIds.slice(i, i + 50);
			const url =
				'https://www.googleapis.com/youtube/v3/videos?part=status&id=' +
				batch.join(',') +
				'&key=' +
				apiKey;
			const res = await fetch(url);
			if (!res.ok) continue; // leave batch as default below
			const data = await res.json();
			for (const item of data.items ?? []) {
				result.set(item.id, item.status?.embeddable !== false);
			}
		}
	} else {
		await Promise.all(
			videoIds.map(async (id) => {
				try {
					const res = await fetch(
						`https://www.youtube.com/oembed?url=${encodeURIComponent(
							'https://www.youtube.com/watch?v=' + id
						)}&format=json`,
						{ method: 'GET' }
					);
					result.set(id, res.ok);
				} catch {
					/* leave unset -> defaults true */
				}
			})
		);
	}

	for (const id of videoIds) if (!result.has(id)) result.set(id, true);
	return result;
}

/**
 * Resolve a pasted YouTube URL / handle to {source_type, youtube_id, title?}.
 * /channel/UC… and ?list=PL… parse directly; /@handle requires fetching the
 * channel page (keyless) and extracting the channelId.
 */
export async function resolveSource(
	input: string
): Promise<{ source_type: 'channel' | 'playlist'; youtube_id: string }> {
	const raw = input.trim();

	const list = raw.match(/[?&]list=([A-Za-z0-9_-]+)/);
	if (list) return { source_type: 'playlist', youtube_id: list[1] };
	if (/^PL[A-Za-z0-9_-]{10,}$/.test(raw)) return { source_type: 'playlist', youtube_id: raw };

	const chan = raw.match(/\/channel\/(UC[A-Za-z0-9_-]{20,})/);
	if (chan) return { source_type: 'channel', youtube_id: chan[1] };
	if (/^UC[A-Za-z0-9_-]{20,}$/.test(raw)) return { source_type: 'channel', youtube_id: raw };

	const handle = raw.match(/(?:youtube\.com\/)?(@[A-Za-z0-9._-]+)/);
	if (handle) {
		const res = await fetch(`https://www.youtube.com/${handle[1]}`, {
			headers: { 'accept-language': 'en' }
		});
		if (res.ok) {
			const html = await res.text();
			const m =
				html.match(/"channelId":"(UC[A-Za-z0-9_-]{20,})"/) ??
				html.match(/channel_id=(UC[A-Za-z0-9_-]{20,})/);
			if (m) return { source_type: 'channel', youtube_id: m[1] };
		}
		throw new Error(`Could not resolve handle ${handle[1]} to a channel id`);
	}

	throw new Error('Unrecognised YouTube URL — paste a channel, @handle or playlist link');
}
