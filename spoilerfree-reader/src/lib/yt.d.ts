// Minimal typings for the YouTube IFrame API (loaded at runtime).
interface YTPlayer {
	mute(): void;
	unMute(): void;
	setVolume(v: number): void;
	playVideo(): void;
	destroy(): void;
}

interface YTNamespace {
	Player: new (
		el: string | HTMLElement,
		opts: {
			videoId: string;
			playerVars?: Record<string, string | number>;
			events?: {
				onReady?: (e: { target: YTPlayer }) => void;
				onStateChange?: (e: { data: number }) => void;
				onError?: (e: { data: number }) => void;
			};
		}
	) => YTPlayer;
	PlayerState: { PLAYING: number; BUFFERING: number };
}

interface Window {
	YT?: YTNamespace;
}
