<script lang="ts">
	import { onMount } from 'svelte';
	import { supabase, type Item, type Subscription } from '$lib/supabase';
	import { openSpoilerSafePopup } from '$lib/popout';
	import { flagUrl } from '$lib/flags';
	import VideoModal from '$lib/VideoModal.svelte';

	let subscriptions: Subscription[] = $state([]);
	let items: Item[] = $state([]);
	let selected: string | 'all' = $state('all');
	let unreadOnly = $state(false);
	let loading = $state(true);
	let playing: Item | null = $state(null);

	onMount(load);

	async function load() {
		loading = true;
		const [subsRes, itemsRes] = await Promise.all([
			supabase.from('subscriptions').select('*').order('created_at'),
			supabase
				.from('items_client')
				.select('*')
				.order('published_at', { ascending: false })
				.limit(500)
		]);
		subscriptions = subsRes.data ?? [];
		items = itemsRes.data ?? [];
		loading = false;
		if (subscriptions.length === 0) location.href = '/subscriptions?first=1';
	}

	const visible = $derived(
		items.filter(
			(i) =>
				(selected === 'all' || i.subscription_id === selected) && (!unreadOnly || !i.is_read)
		)
	);

	const grouped = $derived.by(() => {
		const byDay = new Map<string, Item[]>();
		for (const i of visible) {
			const day = (i.published_at ?? '').slice(0, 10) || 'Unknown date';
			if (!byDay.has(day)) byDay.set(day, []);
			byDay.get(day)!.push(i);
		}
		return [...byDay.entries()];
	});

	function unreadCount(subId: string): number {
		return items.filter((i) => i.subscription_id === subId && !i.is_read).length;
	}

	async function open(item: Item) {
		if (!item.is_read) {
			item.is_read = true;
			await supabase.from('items').update({ is_read: true }).eq('id', item.id);
		}
		if (item.embeddable) {
			playing = item;
		} else {
			openSpoilerSafePopup(item.video_id);
		}
	}

	function fmtDate(day: string): string {
		const d = new Date(day);
		return isNaN(d.getTime())
			? day
			: d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
	}

	async function signOut() {
		await supabase.auth.signOut();
	}
</script>

<div class="app">
	<aside>
		<div class="brand">Spoiler-Free<br />Reader</div>
		<button class:active={selected === 'all'} onclick={() => (selected = 'all')}>
			All feeds
		</button>
		{#each subscriptions as sub}
			<button class:active={selected === sub.id} onclick={() => (selected = sub.id)}>
				<span class="sub-name">{sub.title}</span>
				{#if unreadCount(sub.id) > 0}<span class="count">{unreadCount(sub.id)}</span>{/if}
			</button>
		{/each}
		<div class="side-foot">
			<label class="unread-toggle">
				<input type="checkbox" bind:checked={unreadOnly} /> Unread only
			</label>
			<a href="/subscriptions">Manage feeds</a>
			<button class="linkish" onclick={signOut}>Sign out</button>
		</div>
	</aside>

	<main>
		{#if loading}
			<p class="empty">Loading…</p>
		{:else if visible.length === 0}
			<p class="empty">No highlights yet. Feeds refresh automatically.</p>
		{:else}
			{#each grouped as [day, dayItems]}
				<h2>{fmtDate(day)}</h2>
				<div class="grid">
					{#each dayItems as item}
						<button class="card" class:read={item.is_read} onclick={() => open(item)}>
							<span class="labels">
								{#each [item.label1, item.label2] as label, i}
									{#if label}
										{#if flagUrl(label)}
											<img src={flagUrl(label)} alt={label} title={label} />
										{:else}
											<span class="chip">{label}</span>
										{/if}
									{:else}
										<span class="chip neutral">{i === 0 ? 'New' : 'highlights'}</span>
									{/if}
									{#if i === 0}<span class="v">v</span>{/if}
								{/each}
							</span>
							{#if !item.embeddable}
								<span class="badge" title="This video's owner disables embedding — it plays in a spoiler-safe popup on YouTube">
									opens in popup ↗
								</span>
							{/if}
						</button>
					{/each}
				</div>
			{/each}
		{/if}
	</main>
</div>

{#if playing}
	<VideoModal
		videoId={playing.video_id}
		label1={playing.label1}
		label2={playing.label2}
		onclose={() => (playing = null)}
	/>
{/if}

<style>
	.app {
		display: grid;
		grid-template-columns: 230px 1fr;
		min-height: 100vh;
	}
	aside {
		background: #10151c;
		border-right: 1px solid #1d2733;
		padding: 18px 12px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.brand {
		font-weight: 700;
		font-size: 17px;
		line-height: 1.25;
		padding: 4px 10px 16px;
		color: #4ade80;
	}
	aside > button {
		display: flex;
		justify-content: space-between;
		align-items: center;
		background: none;
		border: none;
		color: #c9d4e0;
		padding: 9px 10px;
		border-radius: 8px;
		font-size: 14px;
		cursor: pointer;
		text-align: left;
	}
	aside > button:hover {
		background: #16202b;
	}
	aside > button.active {
		background: #0f6b35;
		color: #fff;
	}
	.sub-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.count {
		background: #1d2733;
		border-radius: 10px;
		font-size: 11px;
		padding: 2px 7px;
	}
	.side-foot {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px 10px 4px;
		font-size: 13px;
	}
	.side-foot a,
	.linkish {
		color: #8b949e;
		background: none;
		border: none;
		padding: 0;
		font-size: 13px;
		cursor: pointer;
		text-align: left;
		text-decoration: none;
	}
	.side-foot a:hover,
	.linkish:hover {
		color: #e6edf3;
	}
	.unread-toggle {
		color: #8b949e;
		display: flex;
		gap: 6px;
		align-items: center;
	}

	main {
		padding: 24px 28px;
		overflow-y: auto;
	}
	h2 {
		font-size: 15px;
		color: #8b949e;
		font-weight: 600;
		margin: 22px 0 12px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 12px;
	}
	.card {
		background: #10151c;
		border: 1px solid #1d2733;
		border-radius: 10px;
		padding: 18px 12px 14px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		cursor: pointer;
		transition: border-color 0.15s;
	}
	.card:hover {
		border-color: #0f6b35;
	}
	.card.read {
		opacity: 0.55;
	}
	.labels {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.labels img {
		width: 42px;
		height: 31px;
		object-fit: cover;
		border-radius: 3px;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
	}
	.v {
		color: #8b949e;
		font-size: 13px;
	}
	.chip {
		background: #1d2733;
		border-radius: 6px;
		padding: 4px 10px;
		font-size: 13px;
		color: #c9d4e0;
		max-width: 90px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chip.neutral {
		color: #8b949e;
	}
	.badge {
		font-size: 11px;
		color: #eab308;
	}
	.empty {
		color: #8b949e;
		margin-top: 40vh;
		text-align: center;
	}

	@media (max-width: 700px) {
		.app {
			grid-template-columns: 1fr;
		}
		aside {
			flex-direction: row;
			flex-wrap: wrap;
			border-right: none;
			border-bottom: 1px solid #1d2733;
		}
		.brand {
			width: 100%;
			padding-bottom: 8px;
		}
		.side-foot {
			margin-top: 0;
			flex-direction: row;
			align-items: center;
		}
	}
</style>
