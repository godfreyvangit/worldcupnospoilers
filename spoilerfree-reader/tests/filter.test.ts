// Fixtures are REAL titles observed on BBC/ITV/Fox/TSN channels during the
// 2026 World Cup (from the original site's production data), so these tests
// encode the exact bugs already fixed once: pens-only clips, knockout titles
// missing the year, moment-clips crowding out real highlights.
import { describe, expect, it } from 'vitest';
import {
	filterAndDedup,
	GENERIC_CONFIG,
	isHighlight,
	extractLabels,
	type FilterConfig
} from '../supabase/functions/_shared/filter';

const WORLD_CUP: FilterConfig = {
	require_all: ['world cup'],
	exclude_keywords: [
		'preview', 'compilation', 'top 10', 'top ten', 'best goals', 'every goal',
		'all goals', 'review', 'reaction', 'press conference', 'alt cast', 'live',
		'watch along', 'watchalong', 'full match', 'documentary', 'trailer', 'q&a',
		'predict', 'analysis', 'explained', 'interview', 'build-up', 'build up',
		'vlog', 'behind the scenes', 'reacts', 'pre-game', 'pregame', 'first 10',
		'first ten', 'shootout', 'shoot-out', 'shoot out', 'pens only', 'penalties only'
	],
	knockout_markers: [
		'round of', 'last 16', 'last 32', 'knockout', 'quarter-final', 'quarter final',
		'quarterfinal', 'semi-final', 'semi final', 'semifinal', 'final'
	],
	labels: { mode: 'vs_split' }
};

describe('isHighlight', () => {
	it('accepts standard highlights titles', () => {
		expect(isHighlight('Netherlands vs. Morocco Full Highlights | FIFA World Cup 2026', WORLD_CUP)).toBe(true);
		expect(isHighlight('Germany vs Paraguay Highlights 🌎🏆 2026 FIFA World Cup™ | Round of 32', WORLD_CUP)).toBe(true);
	});

	it('rejects penalty-shootout-only clips (all real observed formats)', () => {
		expect(isHighlight('Full Penalty Shootout | Netherlands v Morocco 🇳🇱🇲🇦 | 2026 FIFA World Cup | Round of 32', WORLD_CUP)).toBe(false);
		expect(isHighlight('FULL Penalty Shoot-Out | Germany v Paraguay | FIFA World Cup 2026', WORLD_CUP)).toBe(false);
		expect(isHighlight('FULL Penalty Shootout: Netherlands vs. Morocco | FIFA World Cup 2026', WORLD_CUP)).toBe(false);
	});

	it('keeps full highlights that merely mention penalties', () => {
		expect(isHighlight('Croatia vs Brazil Highlights | win on penalties | FIFA World Cup 2026', WORLD_CUP)).toBe(true);
	});

	it('accepts knockout titles that drop the year (real ITV format)', () => {
		expect(isHighlight('HIGHLIGHTS - Netherlands v Morocco | All Action Knockout Match! | FIFA World Cup', WORLD_CUP)).toBe(true);
	});

	it('rejects pre-game and first-10 clips (real TSN formats)', () => {
		expect(isHighlight('Argentina vs. Austria Pre-Game + First 10 Minutes | FIFA World Cup', WORLD_CUP)).toBe(false);
		expect(isHighlight('Norway vs. France Pre-Game + First 10 Minutes | FIFA World Cup', WORLD_CUP)).toBe(false);
	});

	it('whole-word matching: "live" does not trip on "deliver"/"Oliver"', () => {
		expect(isHighlight('Oliver delivers as England win | FIFA World Cup 2026 Highlights', WORLD_CUP)).toBe(true);
	});
});

describe('extractLabels', () => {
	it('parses vs., v and score formats', () => {
		expect(extractLabels('Netherlands vs. Morocco Full Highlights | FIFA World Cup 2026', WORLD_CUP)).toEqual(['Netherlands', 'Morocco']);
		expect(extractLabels('HIGHLIGHTS - Germany v Paraguay | Nail-biting Round of 32 Game | FIFA World Cup 2026', WORLD_CUP)).toEqual(['HIGHLIGHTS - Germany', 'Paraguay']);
		expect(extractLabels('Netherlands 1-1 (2-3) Morocco 🇳🇱 🇲🇦 | 2026 FIFA World Cup Highlights | Round of 32', WORLD_CUP)).toEqual(['Netherlands', 'Morocco']);
	});

	it('team_list mode canonicalizes and orders by title position', () => {
		const cfg: FilterConfig = {
			labels: {
				mode: 'team_list',
				teams: ['Netherlands', 'Morocco', 'Korea Republic', 'South Korea'],
				canonical: { 'korea republic': 'South Korea' }
			}
		};
		expect(extractLabels('Morocco v Netherlands | FIFA World Cup 2026', cfg)).toEqual(['Morocco', 'Netherlands']);
		expect(extractLabels('Korea Republic vs Morocco Highlights', cfg)).toEqual(['South Korea', 'Morocco']);
	});

	it('returns nulls when unparseable (card still renders neutral chips)', () => {
		expect(extractLabels('SAVES of June 25th | FIFA World Cup 2026', WORLD_CUP)).toEqual([null, null]);
	});
});

describe('filterAndDedup', () => {
	it('a stale pens-only clip cannot crowd out the real highlights (the production bug)', () => {
		const entries = [
			// existing DB row (pens-only, saved before filter existed) comes first
			{ videoId: 'pens1', title: 'FULL Penalty Shoot-Out | Netherlands v Morocco | FIFA World Cup 2026', published: '2026-06-30T10:00:00Z' },
			{ videoId: 'high1', title: 'Netherlands vs. Morocco Full Highlights | FIFA World Cup 2026', published: '2026-06-30T11:00:00Z' }
		];
		const out = filterAndDedup(entries, WORLD_CUP);
		expect(out).toHaveLength(1);
		expect(out[0].videoId).toBe('high1');
	});

	it('prefers a highlights video over a moment clip for the same match', () => {
		const entries = [
			{ videoId: 'clip1', title: 'Cody Gakpo Scores Emotional Opener for Netherlands v Morocco | FIFA World Cup 2026', published: '2026-06-30T09:00:00Z' },
			{ videoId: 'high1', title: 'HIGHLIGHTS - Netherlands v Morocco | All Action Knockout Match! | FIFA World Cup', published: '2026-06-30T10:00:00Z' }
		];
		const out = filterAndDedup(entries, {
			...WORLD_CUP,
			labels: {
				mode: 'team_list',
				teams: ['Netherlands', 'Morocco']
			}
		});
		expect(out).toHaveLength(1);
		expect(out[0].videoId).toBe('high1');
	});

	it('items without labels dedup by videoId, not by a shared null key', () => {
		const entries = [
			{ videoId: 'a', title: 'Matchday Highlights | FIFA World Cup 2026', published: '2026-06-30T09:00:00Z' },
			{ videoId: 'b', title: 'More Highlights | FIFA World Cup 2026', published: '2026-06-30T10:00:00Z' }
		];
		const out = filterAndDedup(entries, { ...WORLD_CUP, labels: { mode: 'none' } });
		expect(out).toHaveLength(2);
	});
});

describe('GENERIC_CONFIG (custom channels)', () => {
	it('drops obvious non-highlights and keeps plain highlights', () => {
		expect(isHighlight('Arsenal vs Chelsea | Premier League Highlights', GENERIC_CONFIG)).toBe(true);
		expect(isHighlight('Arsenal vs Chelsea | LIVE Watch Along', GENERIC_CONFIG)).toBe(false);
		expect(isHighlight('Manager press conference after the match', GENERIC_CONFIG)).toBe(false);
	});
});
