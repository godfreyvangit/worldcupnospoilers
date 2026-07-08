<script lang="ts">
	import { supabase } from '$lib/supabase';

	let email = $state('');
	let sent = $state(false);
	let error = $state('');
	let busy = $state(false);

	async function sendLink(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		const { error: err } = await supabase.auth.signInWithOtp({
			email,
			options: { emailRedirectTo: location.origin }
		});
		busy = false;
		if (err) error = err.message;
		else sent = true;
	}
</script>

<main>
	<div class="card">
		<h1>Spoiler-Free Reader</h1>
		<p class="tag">Your sports highlights. Never the score.</p>

		{#if sent}
			<p class="ok">Check your email — we sent you a sign-in link.</p>
		{:else}
			<form onsubmit={sendLink}>
				<input
					type="email"
					placeholder="you@example.com"
					bind:value={email}
					required
					autocomplete="email"
				/>
				<button disabled={busy}>{busy ? 'Sending…' : 'Send magic link'}</button>
			</form>
			{#if error}<p class="err">{error}</p>{/if}
		{/if}
	</div>
</main>

<style>
	main {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
	}
	.card {
		background: #10151c;
		border: 1px solid #1d2733;
		border-radius: 12px;
		padding: 2.5rem;
		width: min(380px, 90vw);
		text-align: center;
	}
	h1 {
		margin: 0 0 4px;
		font-size: 22px;
	}
	.tag {
		color: #8b949e;
		margin: 0 0 24px;
		font-size: 14px;
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	input {
		background: #0d1117;
		border: 1px solid #2b3a4d;
		border-radius: 8px;
		padding: 10px 12px;
		color: #e6edf3;
		font-size: 15px;
	}
	button {
		background: #0f6b35;
		border: none;
		border-radius: 8px;
		padding: 10px;
		color: #fff;
		font-size: 15px;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.6;
	}
	.ok {
		color: #4ade80;
	}
	.err {
		color: #f87171;
		font-size: 13px;
	}
</style>
