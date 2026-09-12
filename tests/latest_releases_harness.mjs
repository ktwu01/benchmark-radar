// Execute the latest-releases functions (issue #530) with small deterministic
// inputs, without a browser: mode resolution, window fallback, signal text,
// the empty-state suggestion, and the URL round trip.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('site/assets/app.js', 'utf8');
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf('\n}\n', start) + 2);
}
function section(start, end) {
  const from = source.indexOf(start);
  assert(from >= 0, start);
  return source.slice(from, source.indexOf(end, from));
}

const t = (key, params) => {
  let value = key;
  for (const [name, replacement] of Object.entries(params || {})) {
    value = value.replaceAll(`{${name}}`, String(replacement));
  }
  return value;
};
const formatDate = (value) => String(value).slice(0, 10);

const payload = {
  schema_version: 1,
  method_version: 'attention-ranking-v1',
  generated_at: '2026-09-10T09:00:00+00:00',
  default_window: '30d',
  windows: {
    '7d': { window_start: '2026-09-03T09:00:00+00:00', window_end: '2026-09-10T09:00:00+00:00', ranked_count: 0, total_cohort_count: 0, entries: [] },
    '30d': {
      window_start: '2026-08-11T09:00:00+00:00', window_end: '2026-09-10T09:00:00+00:00',
      ranked_count: 1, total_cohort_count: 2,
      entries: [
        {
          canonical_artifact_id: 'artifact:github:org/bench', name: 'Bench', purpose: 'agents', release_date: '2026-09-01T00:00:00+00:00',
          score: 87, coverage: 0.85, confidence: 'High', status: 'ranked', rank: 1,
          components: {
            github_stars: { value: 1204, normalized: 1, weight: 0.55, status: 'fresh', source_url: 'https://github.com/org/bench' },
            hf_paper_upvotes: { value: 33, normalized: 0.9, weight: 0.3, status: 'stale', source_url: 'https://huggingface.co/papers/2609.01234', last_successful_date: '2026-09-08' },
            hf_dataset_downloads: { value: null, normalized: null, weight: 0.15, status: 'unavailable', source_url: 'https://huggingface.co/datasets/org/bench-data' },
          },
        },
        {
          canonical_artifact_id: 'artifact:arxiv:2609.02222', name: 'Quiet', purpose: '', release_date: '2026-08-20T00:00:00+00:00',
          score: null, coverage: 0, confidence: 'Low', status: 'limited_signals', rank: null,
          components: {
            github_stars: { value: null, normalized: null, weight: 0.55, status: 'unknown', source_url: null },
            hf_paper_upvotes: { value: null, normalized: null, weight: 0.3, status: 'unknown', source_url: null },
            hf_dataset_downloads: { value: null, normalized: null, weight: 0.15, status: 'unknown', source_url: null },
          },
        },
      ],
    },
  },
};

const state = { data: { latest_releases_leaderboard: payload }, lwindow: '', lmode: 'latest', fullDataLoaded: false };
const names = ['leaderboardModeFromParams', 'latestReleasesPayload', 'latestReleasesDefaultWindow', 'latestReleasesWindowKey', 'latestWindowLabel', 'latestSignalText', 'latestReleasesEmptyState', 'latestReleasesWeights', 'latestReleasesMethodNote'];
const latest = new Function('state', 't', 'formatDate', `${section('const LATEST_WINDOWS =', 'function leaderboardModeFromParams(')}\n${names.map(fn).join('\n')}\nreturn {${names.join(',')}};`)(state, t, formatDate);

// Mode: the page opens on the latest releases; a permalink carrying any of the
// adoption view's own filters, written before the page had modes, still opens
// the adoption view; an explicit lmode wins either way.
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('')), 'latest');
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lwindow=7d')), 'latest');
for (const legacy of ['lscore=70', 'lq=agent', 'ldomain=code', 'lorg=OpenAI', 'lera=2025', 'lheight=documents']) {
  assert.equal(latest.leaderboardModeFromParams(new URLSearchParams(legacy)), 'adoption', legacy);
}
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lmode=latest&lscore=70')), 'latest');
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lmode=adoption')), 'adoption');
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lmode=bogus')), 'latest');
// Read from a Saturation address, whose every URL carries the shared cutoff,
// the cutoff alone is no choice of a leaderboard mode; the adoption view's
// own filters still are.
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lscore=60'), 'saturation'), 'latest');
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lscore=60&lq=agent'), 'saturation'), 'adoption');
assert.equal(latest.leaderboardModeFromParams(new URLSearchParams('lmode=adoption&lscore=60'), 'saturation'), 'adoption');

// Window: the payload's default unless the reader picked a valid one.
assert.equal(latest.latestReleasesDefaultWindow(), '30d');
assert.equal(latest.latestReleasesDefaultWindow({ default_window: '7d' }), '7d');
assert.equal(latest.latestReleasesDefaultWindow({ default_window: '14d' }), '30d');
assert.equal(latest.latestReleasesWindowKey(), '30d');
state.lwindow = '90d';
assert.equal(latest.latestReleasesWindowKey(), '90d');
state.lwindow = '14d';
assert.equal(latest.latestReleasesWindowKey(), '30d');
state.lwindow = '';
assert.equal(latest.latestWindowLabel('7d'), '7 days');

// Signals: null is "no signal", never zero; a stale reading carries the day
// it was read; a gone resource says so.
const bench = payload.windows['30d'].entries[0].components;
assert.equal(latest.latestSignalText(bench.github_stars), '1,204');
assert.equal(latest.latestSignalText(bench.hf_paper_upvotes), '33 · stale since 2026-09-08');
assert.equal(latest.latestSignalText(bench.hf_dataset_downloads), 'unavailable');
assert.equal(latest.latestSignalText({ value: 5, status: 'stale' }), '5 · stale');
assert.equal(latest.latestSignalText({ value: 0, status: 'fresh' }), '0');
assert.equal(latest.latestSignalText({ value: null, status: 'unknown' }), 'not observed');
assert.equal(latest.latestSignalText(undefined), 'not observed');

// Empty state: the 7-day window is empty, so it points at the 30-day window,
// which has entries; the 90-day window is not loaded yet and is still
// offered. Past the widest window the suggestion is the adoption view.
const empty7 = latest.latestReleasesEmptyState('7d', payload);
assert.equal(empty7.message, 'No benchmark released in the last 7 days has a measurable attention signal yet.');
assert.deepEqual(empty7.windows, ['30d', '90d']);
assert.equal(empty7.adoption, false);
const loadedEmpty = { ...payload, windows: { ...payload.windows, '30d': { entries: [] }, '90d': { entries: [] } } };
assert.deepEqual(latest.latestReleasesEmptyState('7d', loadedEmpty).windows, []);
assert.equal(latest.latestReleasesEmptyState('7d', loadedEmpty).adoption, true);
assert.equal(latest.latestReleasesEmptyState('90d', payload).adoption, true);

// Method note: weights come from the published components, not from a
// number restated in the browser.
assert.deepEqual(latest.latestReleasesWeights(payload.windows['30d'].entries), { github_stars: 0.55, hf_paper_upvotes: 0.3, hf_dataset_downloads: 0.15 });
const note = latest.latestReleasesMethodNote(payload, payload.windows['30d']);
assert(note.startsWith('Ranking attention-ranking-v1: 55% GitHub stars, 30% Hugging Face paper upvotes, 15% Hugging Face dataset downloads, last 30 days,'), note);
assert(note.includes('never a cumulative total'));
assert(note.includes('Window 2026-08-11 to 2026-09-10, UTC.'));
const bare = latest.latestReleasesMethodNote({ method_version: 'v9' }, { entries: [], window_start: '2026-08-11', window_end: '2026-09-10' });
assert(bare.startsWith('Ranking v9: GitHub stars, Hugging Face paper upvotes, Hugging Face dataset downloads, last 30 days,'), bare);

// URL round trip through the real readUrl / writeUrl: the latest mode writes
// only a non-default window; the adoption mode writes its filters and names
// itself, so its address survives a reload in the same mode.
const routeSource = [
  section('const VIEW_SEO = {', '// These sheets are also indexable pages.'),
  section('const UTILITY_SEO = {', '// One list, not two:'),
  section('const VIEW_PATHS =', 'function applySeo('),
  section('function scoreCutoff(', 'function matchesScoreFilter('),
  section('const LATEST_WINDOWS =', 'function latestReleasesWindowKey('),
  section('function readUrl()', '// `push` adds a history entry'),
  section('function writeUrl(', '// A pushed entry changes the URL'),
].join('\n');
const routes = new Function('state', 'BENCHMARK_SEARCH_LIMIT', `
  const window = { location: { origin: 'https://benchmark-radar.org', pathname: '/', search: '', hash: '' }, history: { state: null,
    pushState(s, _t, url) { const u = new URL(url, 'https://benchmark-radar.org'); window.location.pathname = u.pathname; window.location.search = u.search; window.location.hash = u.hash; },
    replaceState(s, _t, url) { this.pushState(s, _t, url); } } };
  ${routeSource}
  return {
    install(url) { const u = new URL(url, 'https://benchmark-radar.org'); window.location.pathname = u.pathname; window.location.search = u.search; window.location.hash = u.hash; },
    readUrl, writeUrl, current() { return window.location.pathname + window.location.search; },
  };
`)(state, 50);

routes.install('/leaderboard/');
routes.readUrl();
assert.equal(state.lmode, 'latest');
assert.equal(state.lwindow, '');
routes.writeUrl('replace');
assert.equal(routes.current(), '/leaderboard/', 'the default view writes a clean address');

routes.install('/leaderboard/?lwindow=90d');
routes.readUrl();
assert.equal(state.lwindow, '90d');
routes.writeUrl('replace');
assert.equal(routes.current(), '/leaderboard/?lwindow=90d');
state.lwindow = '30d';
routes.writeUrl('replace');
assert.equal(routes.current(), '/leaderboard/', 'the default window is not written');

routes.install('/leaderboard/?lscore=70&lq=agent');
routes.readUrl();
assert.equal(state.lmode, 'adoption', 'a pre-mode permalink opens the view it filtered');
assert.equal(state.lq, 'agent');
routes.writeUrl('replace');
assert.equal(routes.current(), '/leaderboard/?lscore=70&lq=agent', 'the address keeps its pre-mode shape');
routes.readUrl();
assert.equal(state.lmode, 'adoption');

routes.install('/leaderboard/?lmode=adoption');
routes.readUrl();
state.lmode = 'latest';
state.lwindow = '7d';
routes.writeUrl('replace');
assert.equal(routes.current(), '/leaderboard/?lwindow=7d', 'switching back to latest drops the adoption filters');

// Back from Saturation restores an address with the shared cutoff; opening
// the leaderboard from there must not land on a mode the reader never chose.
routes.install('/saturation/?lscore=60');
routes.readUrl();
assert.equal(state.view, 'saturation');
assert.equal(state.lmode, 'latest', 'the shared cutoff on a Saturation address is not a mode choice');
state.view = 'leaderboard';
routes.writeUrl('push');
assert.equal(routes.current(), '/leaderboard/');
// A legacy leaderboard permalink for one benchmark is a Saturation address
// now, and its cutoff no more chooses a mode than any other.
routes.install('/leaderboard/?lfrontier=bench-95&lscore=70');
routes.readUrl();
assert.equal(state.view, 'saturation');
assert.equal(state.lmode, 'latest');
// The adoption view's own filters, wherever they were read from, still open it.
routes.install('/saturation/?lscore=40&lq=agent&lheight=documents');
routes.readUrl();
assert.equal(state.lmode, 'adoption');
state.view = 'leaderboard';
routes.writeUrl('push');
assert.equal(routes.current(), '/leaderboard/?lscore=40&lheight=documents&lq=agent');

console.log('latest releases harness ok');
