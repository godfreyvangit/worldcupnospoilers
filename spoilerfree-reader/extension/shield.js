// Neutralize the document title (the tab otherwise shows the video title,
// which may contain the score). Re-assert because YouTube is a SPA that
// rewrites it on navigation and metadata loads.
const NEUTRAL = 'YouTube — Spoiler Shield';

function neutralize() {
	if (document.title !== NEUTRAL) document.title = NEUTRAL;
}

neutralize();
new MutationObserver(neutralize).observe(document.documentElement, {
	subtree: true,
	childList: true,
	characterData: true
});
