// Spoiler-safe playback for embed-disabled videos.
//
// A video with embedding disabled cannot play inside our page (YouTube
// enforces this server-side; proxying streams violates YouTube ToS). Instead
// we open YouTube itself in the least-spoilery way possible:
//  - Desktop: a popup window sized to the player area only, cropping the
//    title/related rail out of view. If the legacy bare-player endpoint
//    watch_popup still works it is used (no title at all); otherwise the
//    sized crop of /watch does the job.
//  - If the Spoiler Shield extension is installed (it stamps a marker on our
//    page), a full tab is fine — the extension hides all spoiler chrome.
//  - Mobile: deep-link into the YouTube app, falling back to m.youtube.com.

export const IS_MOBILE =
	typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;

export function extensionInstalled(): boolean {
	return document.documentElement.dataset.spoilerShield === 'on';
}

export function openSpoilerSafePopup(videoId: string): void {
	if (IS_MOBILE) {
		openMobile(videoId);
		return;
	}

	if (extensionInstalled()) {
		window.open(`https://www.youtube.com/watch?v=${videoId}&autoplay=1`, '_blank');
		return;
	}

	// Player-only geometry: 16:9 video + ~90px of player chrome/masthead,
	// clamped to the screen. The title block sits below the player in
	// YouTube's layout, so it falls outside the popup.
	const width = Math.min(1100, Math.floor(screen.availWidth * 0.72));
	const height = Math.floor((width * 9) / 16) + 90;
	const left = Math.floor((screen.availWidth - width) / 2);
	const top = Math.max(0, Math.floor((screen.availHeight - height) / 2) - 20);

	// watch_popup is a legacy bare-player page (no title/related). If YouTube
	// redirects it to /watch, the sized crop still hides the title.
	const url = `https://www.youtube.com/watch_popup?v=${videoId}&autoplay=1`;
	const features = `popup=yes,width=${width},height=${height},left=${left},top=${top},noopener,noreferrer`;
	const win = window.open(url, 'spoilerfree-player', features);
	if (!win) {
		// Popup blocked: fall back to a plain tab (least-bad option).
		window.open(`https://www.youtube.com/watch?v=${videoId}`, '_blank');
	}
}

function openMobile(videoId: string): void {
	const fallback = setTimeout(() => {
		location.href = `https://m.youtube.com/watch?v=${videoId}`;
	}, 400);
	// If the app opens, the page is backgrounded and the timer never fires.
	addEventListener(
		'visibilitychange',
		() => {
			if (document.visibilityState === 'hidden') clearTimeout(fallback);
		},
		{ once: true }
	);
	location.href = `vnd.youtube://${videoId}`;
}
