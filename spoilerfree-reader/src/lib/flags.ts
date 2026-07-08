// Flag lookup ported from the World Cup site (index.html FLAGS/getFlag).
// Only national teams map to flags; club/other labels render as text chips.

const FLAGS: Record<string, string> = {
	england: 'gb-eng', scotland: 'gb-sct', wales: 'gb-wls', france: 'fr', germany: 'de',
	spain: 'es', portugal: 'pt', netherlands: 'nl', belgium: 'be',
	croatia: 'hr', austria: 'at', norway: 'no', sweden: 'se',
	switzerland: 'ch', czechia: 'cz', 'czech republic': 'cz', turkey: 'tr',
	'türkiye': 'tr', 'bosnia and herzegovina': 'ba', bosnia: 'ba', brazil: 'br',
	argentina: 'ar', colombia: 'co', ecuador: 'ec', uruguay: 'uy',
	paraguay: 'py', mexico: 'mx', usa: 'us', 'united states': 'us',
	canada: 'ca', panama: 'pa', haiti: 'ht', curacao: 'cw', 'curaçao': 'cw',
	japan: 'jp', 'south korea': 'kr', 'korea republic': 'kr', australia: 'au',
	iran: 'ir', 'ir iran': 'ir', iraq: 'iq', 'saudi arabia': 'sa', jordan: 'jo', qatar: 'qa',
	uzbekistan: 'uz', morocco: 'ma', senegal: 'sn', ghana: 'gh', egypt: 'eg',
	algeria: 'dz', tunisia: 'tn', 'south africa': 'za', 'ivory coast': 'ci',
	"côte d'ivoire": 'ci', 'dr congo': 'cd', 'congo dr': 'cd', 'cape verde': 'cv',
	'cabo verde': 'cv', 'new zealand': 'nz', italy: 'it', poland: 'pl', denmark: 'dk',
	ireland: 'ie', ukraine: 'ua', greece: 'gr', serbia: 'rs', romania: 'ro'
};

export function flagCode(label: string): string | null {
	return FLAGS[label.toLowerCase().trim()] ?? null;
}

export function flagUrl(label: string): string | null {
	const code = flagCode(label);
	return code ? `https://flagcdn.com/w80/${code}.png` : null;
}
