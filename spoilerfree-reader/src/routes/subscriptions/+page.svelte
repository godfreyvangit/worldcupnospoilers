<script lang="ts">
	import { onMount } from 'svelte';
	import { supabase, type Preset, type Subscription } from '$lib/supabase';

	let presets: Preset[] = $state([]);
	let subs: Subscription[] = $state([]);
	let customUrl = $state('');
	let busy = $state(false);
	let message = $state('');
	let firstRun = $state(false);

	onMount(async () => {
		firstRun = new URLSearchParams(location.search).has('first');
		const [p, s] = await Promise.all([
			supabase.from('presets').select('*').order('sport'),
			supabase.from('subscriptions').select('*').order('created_at')
		]);
		presets = p.data ?? [];
		subs = s.data ?? [];
	});

	function isSubscribed(preset: Preset): boolean {
		return subs.some((s) => s.youtube_id === preset.youtube_id);
	}

	async function addPreset(preset: Preset) {
		busy = true;
		message = '';
		const { data: userData } = await supabase.auth.getUser();
		const { data, error } = await supabase
			.from('subscriptions')
			.insert({
				user_id: userData.user!.id,
				preset_id: preset.id,
				source_type: preset.source_type,
				youtube_id: preset.youtube_id,
				title: preset.name,
				folder: preset.sport,
				filter_config: preset.filter_config
			})
			.select()
			.single();
		if (error) {
			message = error.message;
			busy = false;
			return;
		}
		subs = [...subs, data];
		await sync(data.id, preset.name);
		busy = false;
	}

	async function addCustom(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		message = 'Resolving URL…';
		const { data: resolved, error: rErr } = await supabase.functions.invoke(
			'sync-subscription',
			{ body: { resolve: customUrl } }
		);
		if (rErr || resolved?.error) {
			message = resolved?.error ?? rErr?.message ?? 'Could not resolve that URL';
			busy = false;
			return;
		}
		const { data: userData } = await supabase.auth.getUser();
		const title = customUrl.match(/@([A-Za-z0-9._-]+)/)?.[1] ?? 'Custom feed';
		const { data, error } = await supabase
			.from('subscriptions')
			.insert({
				user_id: userData.user!.id,
				source_type: resolved.source_type,
				youtube_id: resolved.youtube_id,
				title,
				filter_config: {}
			})
			.select()
			.single();
		if (error) {
			message = error.message.includes('duplicate')
				? 'You are already subscribed to that source.'
				: error.message;
			busy = false;
			return;
		}
		subs = [...subs, data];
		customUrl = '';
		await sync(data.id, title);
		busy = false;
	}

	async function sync(id: string, name: string) {
		message = `Fetching highlights for ${name}…`;
		const { data, error } = await supabase.functions.invoke('sync-subscription', {
			body: { subscription_id: id }
		});
		message = error
			? `Added ${name}, but the first sync failed — it will retry on schedule.`
			: `${name}: ${data.found} highlights found.`;
	}

	async function remove(sub: Subscription) {
		if (!confirm(`Unsubscribe from ${sub.title}? Its items will be removed.`)) return;
		await supabase.from('subscriptions').delete().eq('id', sub.id);
		subs = subs.filter((s) => s.id !== sub.id);
	}

	async function toggleExternalFeed(sub: Subscription) {
		const token = sub.feed_token ? null : crypto.randomUUID();
		await supabase.from('subscriptions').update({ feed_token: token }).eq('id', sub.id);
		sub.feed_token = token;
		subs = [...subs];
	}

	function externalFeedUrl(sub: Subscription): string {
		const base = import.meta.env.PUBLIC_SUPABASE_URL ?? '';
		return `${base}/functions/v1/user-feed?token=${sub.feed_token}`;
	}
</script>

<main>
	<header>
		<h1>{firstRun ? 'Add your first feed' : 'Manage feeds'}</h1>
		{#if !firstRun}<a href="/">&larr; Back to reader</a>{/if}
	</header>

	{#if message}<p class="msg">{message}</p>{/if}

	<h2>Sport presets</h2>
	<div class="presets">
		{#each presets as preset}
			<button
				class="preset"
				disabled={busy || isSubscribed(preset)}
				onclick={() => addPreset(preset)}
			>
				<span class="sport">{preset.sport.replace('_', ' ')}</span>
				<span class="name">{preset.name}</span>
				<span class="cta">{isSubscribed(preset) ? 'Subscribed ✓' : '+ Subscribe'}</span>
			</button>
		{/each}
	</div>

	<h2>Custom channel or playlist</h2>
	<form onsubmit={addCustom}>
		<input
			type="url"
			placeholder="https://www.youtube.com/@channel or /playlist?list=…"
			bind:value={customUrl}
			required
		/>
		<button disabled={busy}>Add</button>
	</form>
	<p class="hint">
		Titles and thumbnails are always hidden — even for channels we don't have tuned filters
		for.
	</p>

	{#if subs.length > 0}
		<h2>Your subscriptions</h2>
		<ul class="subs">
			{#each subs as sub}
				<li>
					<div class="sub-main">
						<strong>{sub.title}</strong>
						<span class="meta">
							{sub.source_type} · last synced
							{sub.last_synced_at ? new Date(sub.last_synced_at).toLocaleString() : 'never'}
						</span>
					</div>
					<div class="sub-actions">
						<button class="small" onclick={() => sync(sub.id, sub.title)} disabled={busy}>
							Refresh
						</button>
						<button class="small" onclick={() => toggleExternalFeed(sub)}>
							{sub.feed_token ? 'Disable RSS' : 'External RSS'}
						</button>
						<button class="small danger" onclick={() => remove(sub)}>Remove</button>
					</div>
					{#if sub.feed_token}
						<code class="feed-url">{externalFeedUrl(sub)}</code>
						<p class="hint">
							Paste into any RSS reader — titles are sanitized, thumbnails removed, links play
							spoiler-free.
						</p>
					{/if}
				</li>
			{/each}
		</ul>
		{#if firstRun}
			<a class="done" href="/">Go to your feed &rarr;</a>
		{/if}
	{/if}
</main>

<style>
	main {
		max-width: 760px;
		margin: 0 auto;
		padding: 28px 20px 60px;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	h1 {
		font-size: 22px;
	}
	h2 {
		font-size: 15px;
		color: #8b949e;
		margin: 28px 0 12px;
	}
	a {
		color: #4ade80;
	}
	.msg {
		background: #16202b;
		border-radius: 8px;
		padding: 10px 14px;
		font-size: 14px;
	}
	.presets {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
		gap: 10px;
	}
	.preset {
		background: #10151c;
		border: 1px solid #1d2733;
		border-radius: 10px;
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 4px;
		cursor: pointer;
		color: #e6edf3;
		text-align: left;
	}
	.preset:hover:not(:disabled) {
		border-color: #0f6b35;
	}
	.preset:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.sport {
		font-size: 11px;
		text-transform: uppercase;
		color: #8b949e;
	}
	.name {
		font-weight: 600;
	}
	.cta {
		font-size: 12px;
		color: #4ade80;
		margin-top: 6px;
	}
	form {
		display: flex;
		gap: 8px;
	}
	input {
		flex: 1;
		background: #0d1117;
		border: 1px solid #2b3a4d;
		border-radius: 8px;
		padding: 10px 12px;
		color: #e6edf3;
	}
	form button {
		background: #0f6b35;
		border: none;
		border-radius: 8px;
		padding: 0 18px;
		color: #fff;
		cursor: pointer;
	}
	.hint {
		color: #8b949e;
		font-size: 12.5px;
	}
	.subs {
		list-style: none;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.subs li {
		background: #10151c;
		border: 1px solid #1d2733;
		border-radius: 10px;
		padding: 12px 14px;
	}
	.sub-main {
		display: flex;
		gap: 10px;
		align-items: baseline;
		flex-wrap: wrap;
	}
	.meta {
		color: #8b949e;
		font-size: 12px;
	}
	.sub-actions {
		display: flex;
		gap: 8px;
		margin-top: 8px;
	}
	.small {
		background: #16202b;
		border: 1px solid #2b3a4d;
		color: #c9d4e0;
		border-radius: 6px;
		padding: 4px 10px;
		font-size: 12.5px;
		cursor: pointer;
	}
	.small.danger {
		color: #f87171;
	}
	.feed-url {
		display: block;
		margin-top: 8px;
		font-size: 11.5px;
		word-break: break-all;
		color: #eab308;
	}
	.done {
		display: inline-block;
		margin-top: 20px;
		font-weight: 600;
	}
</style>
