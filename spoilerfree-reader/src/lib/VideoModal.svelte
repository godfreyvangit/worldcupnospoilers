<script lang="ts">
	// Spoiler-free player ported from worldcupnospoilers index.html:
	// black cover + muted autoplay, reveal on BUFFERING/PLAYING, green
	// title-bar over YouTube's title, custom desktop fullscreen (fs:0),
	// 6s safety timeout. Embed failures route to the spoiler-safe popup.
	import { flagUrl } from '$lib/flags';
	import { IS_MOBILE, openSpoilerSafePopup } from '$lib/popout';

	interface Props {
		videoId: string;
		label1: string | null;
		label2: string | null;
		onclose: () => void;
	}
	let { videoId, label1, label2, onclose }: Props = $props();

	let starting = $state(false);
	let spinning = $state(false);
	let covered = $state(true);
	let player: YTPlayer | null = null;
	let wrapEl: HTMLDivElement;

	function startVideo() {
		if (starting) return;
		starting = true;
		spinning = true;

		const revealAndUnmute = () => {
			covered = false;
			spinning = false;
			try {
				player?.unMute();
				player?.setVolume(100);
			} catch {
				/* player may be gone */
			}
		};

		const make = () => {
			player = new window.YT!.Player('yt-player', {
				videoId,
				playerVars: {
					autoplay: 1,
					mute: 1,
					rel: 0,
					playsinline: 1,
					modestbranding: 1,
					// Desktop: disable YouTube fullscreen so our button can
					// fullscreen the wrapper (keeping the title-bar on top).
					fs: IS_MOBILE ? 1 : 0
				},
				events: {
					onReady: (e) => {
						e.target.mute();
						e.target.playVideo();
					},
					onStateChange: (e) => {
						// BUFFERING or PLAYING both mean the thumbnail is gone.
						if (
							e.data === window.YT!.PlayerState.PLAYING ||
							e.data === window.YT!.PlayerState.BUFFERING
						) {
							revealAndUnmute();
						}
					},
					onError: () => {
						// Embedding blocked at runtime despite embeddable=true:
						// treat as non-embeddable and use the spoiler-safe popup.
						openSpoilerSafePopup(videoId);
						onclose();
					}
				}
			});
			// Never leave the user staring at a spinner forever.
			setTimeout(revealAndUnmute, 6000);
		};

		if (window.YT?.Player) {
			make();
		} else {
			loadIframeApi();
			const wait = setInterval(() => {
				if (window.YT?.Player) {
					clearInterval(wait);
					make();
				}
			}, 50);
		}
	}

	function loadIframeApi() {
		if (document.querySelector('script[src*="iframe_api"]')) return;
		const s = document.createElement('script');
		s.src = 'https://www.youtube.com/iframe_api';
		document.head.appendChild(s);
	}

	function toggleFullscreen() {
		const fsEl = document.fullscreenElement;
		if (fsEl) {
			document.exitFullscreen?.();
		} else {
			wrapEl?.requestFullscreen?.().catch(() => {});
		}
	}

	function close() {
		try {
			player?.destroy();
		} catch {
			/* noop */
		}
		onclose();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="overlay" onclick={(e) => e.target === e.currentTarget && close()} role="presentation">
	<div class="box">
		<div class="head">
			<div class="head-flags">
				{#each [label1, label2] as label}
					{#if label}
						{#if flagUrl(label)}
							<img src={flagUrl(label)} alt={label} title={label} />
						{:else}
							<span class="chip">{label}</span>
						{/if}
					{/if}
				{/each}
			</div>
			<button class="close" onclick={close} aria-label="Close">&#x2715;</button>
		</div>

		<div class="video-wrap" bind:this={wrapEl}>
			<div id="player-container"><div id="yt-player"></div></div>

			<!-- Green bar permanently covering YouTube's title overlay -->
			<div class="title-bar">
				{#each [label1, label2] as label}
					{#if label && flagUrl(label)}
						<img src={flagUrl(label)} alt={label} />
					{:else if label}
						<span class="chip">{label}</span>
					{/if}
				{/each}
			</div>

			{#if !IS_MOBILE}
				<button class="fs-btn" title="Fullscreen" onclick={toggleFullscreen} aria-label="Fullscreen">
					<svg viewBox="0 0 24 24"
						><path
							d="M4 9V4h5v2H6v3H4zm0 6h2v3h3v2H4v-5zm16 0v5h-5v-2h3v-3h2zm0-6h-2V6h-3V4h5v5z"
						/></svg
					>
				</button>
			{/if}

			{#if covered}
				<div
					class="cover"
					onclick={startVideo}
					onkeydown={(e) => e.key === 'Enter' && startVideo()}
					role="button"
					tabindex="0"
				>
					{#if spinning}
						<div class="spinner"></div>
					{:else}
						<div class="play-btn">
							<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21" /></svg>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.75);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		padding: 16px;
	}
	.box {
		width: min(960px, 100%);
		background: #10151c;
		border-radius: 10px;
		overflow: hidden;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
	}
	.head-flags {
		display: flex;
		gap: 10px;
		align-items: center;
	}
	.head-flags img {
		width: 34px;
		height: 25px;
		object-fit: cover;
		border-radius: 3px;
	}
	.chip {
		background: #1d2733;
		border-radius: 6px;
		padding: 3px 10px;
		font-size: 13px;
		color: #c9d4e0;
	}
	.close {
		background: none;
		border: none;
		color: #8b949e;
		font-size: 18px;
		cursor: pointer;
	}
	.close:hover {
		color: #fff;
	}

	.video-wrap {
		position: relative;
		padding-bottom: 56.25%;
		height: 0;
		background: #000;
	}
	.video-wrap :global(#player-container),
	.video-wrap :global(#yt-player),
	.video-wrap :global(iframe) {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		border: none;
	}

	/* Green bar covering the YouTube title at the top of the video */
	.title-bar {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 60px;
		background: #0f6b35;
		z-index: 20;
		pointer-events: none;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 14px;
	}
	.title-bar img {
		width: 40px;
		height: 30px;
		object-fit: cover;
		border-radius: 3px;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
	}

	/* Fullscreen the wrapper (not the bare iframe) so the bar stays on top */
	.video-wrap:fullscreen {
		padding-bottom: 0;
		width: 100%;
		height: 100%;
	}
	.video-wrap:fullscreen .title-bar {
		height: 80px;
	}
	.video-wrap:fullscreen .title-bar img {
		width: 52px;
		height: 39px;
	}

	.fs-btn {
		position: absolute;
		top: 0;
		right: 0;
		width: 60px;
		height: 60px;
		z-index: 30;
		background: transparent;
		border: none;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.fs-btn svg {
		width: 22px;
		height: 22px;
		fill: #fff;
		opacity: 0.8;
	}
	.fs-btn:hover svg {
		opacity: 1;
	}
	.video-wrap:fullscreen .fs-btn {
		height: 80px;
	}

	/* Opaque cover hides the thumbnail until playback is confirmed */
	.cover {
		position: absolute;
		inset: 0;
		background: #000;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
	}
	.play-btn {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.15);
		border: 3px solid rgba(255, 255, 255, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.play-btn:hover {
		background: rgba(255, 255, 255, 0.25);
	}
	.play-btn svg {
		width: 32px;
		height: 32px;
		fill: #fff;
		margin-left: 4px;
	}
	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid rgba(255, 255, 255, 0.25);
		border-top-color: #fff;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 600px) {
		.title-bar {
			height: 44px;
			gap: 10px;
		}
		.title-bar img {
			width: 32px;
			height: 24px;
		}
	}
</style>
