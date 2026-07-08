<script lang="ts">
	// Landing page for links from the sanitized external RSS feed.
	// Looks up the item and runs the same embeddable-vs-popup branching.
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { supabase, type Item } from '$lib/supabase';
	import { openSpoilerSafePopup } from '$lib/popout';
	import VideoModal from '$lib/VideoModal.svelte';

	let item: Item | null = $state(null);
	let error = $state('');

	onMount(async () => {
		const { data, error: err } = await supabase
			.from('items_client')
			.select('*')
			.eq('id', $page.params.id)
			.single();
		if (err || !data) {
			error = 'Item not found (are you signed in with the right account?)';
			return;
		}
		item = data;
		if (!item.embeddable) openSpoilerSafePopup(item.video_id);
		supabase.from('items').update({ is_read: true }).eq('id', item.id).then(() => {});
	});
</script>

{#if error}
	<main class="center"><p>{error}</p><a href="/">Back to reader</a></main>
{:else if item && item.embeddable}
	<VideoModal
		videoId={item.video_id}
		label1={item.label1}
		label2={item.label2}
		onclose={() => (location.href = '/')}
	/>
{:else if item}
	<main class="center">
		<p>This video plays in a spoiler-safe popup on YouTube.</p>
		<button onclick={() => openSpoilerSafePopup(item!.video_id)}>Open player</button>
		<a href="/">Back to reader</a>
	</main>
{:else}
	<main class="center"><p>Loading…</p></main>
{/if}

<style>
	.center {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 14px;
		color: #8b949e;
	}
	a {
		color: #4ade80;
	}
	button {
		background: #0f6b35;
		border: none;
		border-radius: 8px;
		padding: 10px 22px;
		color: #fff;
		font-size: 15px;
		cursor: pointer;
	}
</style>
