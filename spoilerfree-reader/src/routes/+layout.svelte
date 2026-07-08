<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { supabase } from '$lib/supabase';
	import type { Session } from '@supabase/supabase-js';

	let { children } = $props();
	let session: Session | null = $state(null);
	let ready = $state(false);

	onMount(() => {
		supabase.auth.getSession().then(({ data }) => {
			session = data.session;
			ready = true;
			guard();
		});
		const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
			session = s;
			guard();
		});
		return () => sub.subscription.unsubscribe();
	});

	function guard() {
		if (!ready) return;
		const path = $page.url.pathname;
		if (!session && path !== '/login') goto('/login');
		if (session && path === '/login') goto('/');
	}
</script>

{#if ready}
	{@render children()}
{:else}
	<div class="boot">Loading…</div>
{/if}

<style>
	:global(body) {
		margin: 0;
		background: #0d1117;
		color: #e6edf3;
		font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
	}
	.boot {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
		color: #8b949e;
	}
</style>
