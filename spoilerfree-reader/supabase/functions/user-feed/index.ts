// Sanitized external RSS output: GET ?token=<feed_token>
// Emits spoiler-free titles ("Arsenal v Chelsea — Highlights"), NO thumbnails
// (no media: tags), links pointing at the app's spoiler-safe watch page.
// The token is a per-subscription secret; anyone with it can read the feed,
// so treat it like an unlisted URL (standard RSS-reader interop model).
import { CORS, serviceClient } from '../_shared/sync.ts';

const APP_URL = Deno.env.get('APP_URL') ?? 'http://localhost:5173';

Deno.serve(async (req) => {
	const token = new URL(req.url).searchParams.get('token');
	if (!token) return new Response('missing token', { status: 400, headers: CORS });

	const db = serviceClient();
	const { data: sub } = await db
		.from('subscriptions')
		.select('id, title')
		.eq('feed_token', token)
		.single();
	if (!sub) return new Response('unknown feed', { status: 404, headers: CORS });

	const { data: items } = await db
		.from('items')
		.select('id, label1, label2, published_at')
		.eq('subscription_id', sub.id)
		.order('published_at', { ascending: false })
		.limit(50);

	const xmlItems = (items ?? [])
		.map((i) => {
			const title = i.label1 && i.label2
				? `${i.label1} v ${i.label2} — Highlights`
				: 'New highlights';
			const link = `${APP_URL}/watch/${i.id}`;
			return `  <item>
    <title>${escapeXml(title)}</title>
    <link>${escapeXml(link)}</link>
    <guid isPermaLink="false">${i.id}</guid>
    <pubDate>${new Date(i.published_at ?? Date.now()).toUTCString()}</pubDate>
  </item>`;
		})
		.join('\n');

	const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>${escapeXml(sub.title)} — Spoiler-Free</title>
  <link>${escapeXml(APP_URL)}</link>
  <description>Spoiler-free highlights feed. Titles and thumbnails are sanitized.</description>
${xmlItems}
</channel>
</rss>`;

	return new Response(rss, {
		headers: { ...CORS, 'content-type': 'application/rss+xml; charset=utf-8' }
	});
});

function escapeXml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}
