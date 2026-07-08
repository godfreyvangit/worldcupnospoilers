-- Curated presets. youtube_id values are the official channels' IDs;
-- verify/update before launch (channels occasionally change).
insert into public.presets (sport, name, source_type, youtube_id, filter_config) values
(
  'football', 'Premier League', 'channel', 'UCG5qGWdu8nIRZqJ_GgDwQ-w',
  '{
    "require_any": ["highlights"],
    "exclude_keywords": ["preview", "reaction", "press conference", "live", "full match",
      "every goal", "all goals", "top 10", "best goals", "interview", "trailer",
      "behind the scenes", "shootout", "shoot-out", "shoot out", "pens only", "penalties only"],
    "labels": { "mode": "vs_split" }
  }'::jsonb
),
(
  'football', 'FIFA World Cup', 'channel', 'UCpcTrCXblq78GZrTUTLWeBw',
  '{
    "require_all": ["world cup"],
    "exclude_keywords": ["preview", "compilation", "top 10", "top ten", "best goals",
      "every goal", "all goals", "review", "reaction", "press conference", "alt cast",
      "live", "watch along", "watchalong", "full match", "documentary", "trailer",
      "q&a", "predict", "analysis", "explained", "interview", "build-up", "build up",
      "vlog", "behind the scenes", "reacts", "pre-game", "pregame", "first 10",
      "first ten", "shootout", "shoot-out", "shoot out", "pens only", "penalties only"],
    "knockout_markers": ["round of", "last 16", "last 32", "knockout",
      "quarter-final", "quarter final", "quarterfinal",
      "semi-final", "semi final", "semifinal", "final"],
    "labels": { "mode": "vs_split" }
  }'::jsonb
),
(
  'american_football', 'NFL', 'channel', 'UCDVYQ4Zhbm3S2dlz7P1GBDg',
  '{
    "require_any": ["highlights", "game highlights"],
    "exclude_keywords": ["mic''d up", "micd up", "film study", "press conference",
      "top 10", "top plays", "power rankings", "preview", "predictions", "reaction",
      "live", "full game", "interview", "podcast", "draft"],
    "labels": { "mode": "vs_split" }
  }'::jsonb
),
(
  'basketball', 'NBA', 'channel', 'UCWJ2lWNubArHWmf3FIHbfcQ',
  '{
    "require_any": ["highlights", "full game highlights"],
    "exclude_keywords": ["top 10", "top plays", "mixtape", "press conference",
      "interview", "preview", "predictions", "reaction", "live", "podcast",
      "best of", "career highlights"],
    "labels": { "mode": "vs_split" }
  }'::jsonb
);
