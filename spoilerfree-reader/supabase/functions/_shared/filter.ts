// Filter pipeline ported from the World Cup site's fetch_matches.py.
// Pure functions, no runtime dependencies: runs in Deno (Edge Functions)
// and Node (vitest) unchanged.

export interface LabelsConfig {
	mode: 'team_list' | 'vs_split' | 'none';
	teams?: string[];
	canonical?: Record<string, string>;
}

export interface FilterConfig {
	/** Every one of these must appear in the title (lowercased). */
	require_all?: string[];
	/** At least one of these must appear, if the list is non-empty. */
	require_any?: string[];
	/** Whole-word matches that reject a title. */
	exclude_keywords?: string[];
	/**
	 * If set, a title missing require_all terms still passes when it contains
	 * one of these (e.g. knockout titles that drop the year).
	 */
	knockout_markers?: string[];
	labels?: LabelsConfig;
}

export interface FeedEntry {
	videoId: string;
	title: string;
	published: string; // ISO timestamp
}

export interface FilteredItem extends FeedEntry {
	label1: string | null;
	label2: string | null;
}

const escapeRegex = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Port of is_highlight() (fetch_matches.py:95-115), config-driven.
 * Whole-word matching so short keywords like "live" don't trip on
 * "deliver"/"Oliver"/"alive".
 */
export function isHighlight(title: string, config: FilterConfig): boolean {
	const t = title.toLowerCase();

	for (const req of config.require_all ?? []) {
		if (!t.includes(req.toLowerCase())) {
			// Knockout titles sometimes omit a required term (e.g. the year);
			// accept if a knockout marker is present instead.
			const markers = config.knockout_markers ?? [];
			if (!markers.some((m) => t.includes(m.toLowerCase()))) return false;
		}
	}

	const any = config.require_any ?? [];
	if (any.length > 0 && !any.some((a) => t.includes(a.toLowerCase()))) {
		return false;
	}

	for (const kw of config.exclude_keywords ?? []) {
		const re = new RegExp(`\\b${escapeRegex(kw.toLowerCase())}\\b`);
		if (re.test(t)) return false;
	}

	return true;
}

/**
 * Port of extract_teams() (fetch_matches.py:118-148), pluggable by mode.
 * Returns [null, null] when labels can't be parsed — the card then renders
 * neutral chips; title/thumbnail are never shown regardless.
 */
export function extractLabels(
	title: string,
	config: FilterConfig
): [string | null, string | null] {
	const labels = config.labels ?? { mode: 'vs_split' };
	if (labels.mode === 'none') return [null, null];

	if (labels.mode === 'team_list' && labels.teams?.length) {
		const canonical = labels.canonical ?? {};
		const titleLower = title.toLowerCase();
		const hits = new Map<string, number>(); // canonical -> position
		const sorted = [...labels.teams].sort((a, b) => b.length - a.length);
		for (const team of sorted) {
			const pos = titleLower.indexOf(team.toLowerCase());
			if (pos === -1) continue;
			const canon = canonical[team.toLowerCase()] ?? team;
			if (!hits.has(canon)) hits.set(canon, pos);
		}
		const ordered = [...hits.entries()].sort((a, b) => a[1] - b[1]).map(([c]) => c);
		if (ordered.length >= 2) return [ordered[0], ordered[1]];
		// fall through to vs_split as the fallback, mirroring the python original
	}

	return vsSplit(title);
}

/** "Team1 1-4 Team2" / "Team1 v Team2" / "Team1 vs. Team2" extraction. */
function vsSplit(title: string): [string | null, string | null] {
	let first = title.split('|')[0].trim();
	// Strip non-ASCII decorations (emoji, flags) like the python original.
	first = first.replace(/[^\x20-\x7e]+/g, ' ').replace(/\s+/g, ' ').trim();
	// Strip trailing descriptors so "A vs B Full Highlights" parses cleanly.
	first = first
		.replace(/\b(full|extended|game|quick)?\s*highlights?\s*$/i, '')
		.trim();

	// "Team1 1-4 Team2" (optionally with aggregate "(2-3)" scores)
	let m = first.match(/^(.+?)\s+\d+\s*[-–]\s*\d+(?:\s*\(\d+\s*[-–]\s*\d+\))?\s+(.+?)$/);
	if (m) return [m[1].trim(), m[2].trim()];

	// "Team1 v Team2" / "Team1 vs Team2" / "Team1 vs. Team2"
	m = first.match(/^(.+?)\s+vs?\.?\s+(.+?)$/i);
	if (m) return [m[1].trim(), m[2].trim()];

	return [null, null];
}

/**
 * Port of the filter-BEFORE-dedup loop (fetch_matches.py main:303-320).
 * Ordering matters: existing (DB) items come first so they keep their slot,
 * but a proper "highlight"-titled video replaces a moment-clip for the same
 * match. Non-highlights are dropped before dedup so a stale non-highlight
 * can never crowd out the real highlights (this was a real production bug).
 */
export function filterAndDedup(
	entries: FeedEntry[],
	config: FilterConfig
): FilteredItem[] {
	const seen = new Map<string, number>(); // match key -> index in out
	const out: FilteredItem[] = [];

	for (const e of entries) {
		if (!isHighlight(e.title, config)) continue;
		const [label1, label2] = extractLabels(e.title, config);
		const item: FilteredItem = { ...e, label1, label2 };

		// Without labels we can't identify "the same match"; dedup by videoId.
		const day = (e.published ?? '').slice(0, 10);
		const key = label1 && label2
			? `${label1.toLowerCase()}_${label2.toLowerCase()}_${day}`
			: `vid_${e.videoId}`;

		const existing = seen.get(key);
		if (existing === undefined) {
			seen.set(key, out.length);
			out.push(item);
		} else {
			const kept = out[existing];
			const newIsHl = e.title.toLowerCase().includes('highlight');
			const keptIsHl = kept.title.toLowerCase().includes('highlight');
			if (newIsHl && !keptIsHl) out[existing] = item;
		}
	}

	return out;
}

/** Generic conservative config applied to custom (non-preset) subscriptions. */
export const GENERIC_CONFIG: FilterConfig = {
	exclude_keywords: [
		'preview', 'reaction', 'press conference', 'live', 'watch along', 'watchalong',
		'full match', 'full game', 'interview', 'podcast', 'trailer', 'documentary',
		'behind the scenes', 'vlog', 'q&a', 'predict', 'top 10', 'top ten', 'top plays',
		'every goal', 'all goals', 'best goals', 'compilation', 'mixtape',
		'shootout', 'shoot-out', 'shoot out', 'pens only', 'penalties only',
		'pre-game', 'pregame'
	],
	labels: { mode: 'vs_split' }
};
