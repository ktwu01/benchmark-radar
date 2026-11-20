import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const source = readFileSync("site/assets/app.js", "utf8");
const functionNames = [
  "todayDateRange",
  "todayIsMultiDate",
  "observationDays",
  "freshWindowData",
  "allObservations",
  "sortObservations",
  "observationRecordKey",
  "latestObservationsByRecord",
  "observationAttention",
  "eventTimestamp",
  "isRelease",
  "releaseAgeHours",
  "releaseRank",
  "filteredObservations",
  "compareCodeUnits",
  "searchIndexActive",
  "decodeSearchIndex",
  "searchShard",
  "readSearchShard",
  "gramShard",
  "searchGram",
  "gramRows",
  "gramPositions",
  "hasPosition",
  "searchTiles",
  "alignedRows",
  "ensureSearchRows",
  "findSearchMatches",
];
const functions = functionNames.map((name) => {
  let start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  if (source.slice(start - 6, start) === "async ") start -= 6;
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}).join("\n");
const constants = [
  "const TODAY_WINDOWS = .*;",
  "const RELEASE_FRESH_HOURS = .*;",
  "const RELEASE_RECENT_HOURS = .*;",
].map((pattern) => source.match(new RegExp(pattern))[0]).join("\n");

const row = (date, id, extra = {}) => ({
  source: "GitHub",
  source_id: id,
  title: `${id} benchmark`,
  summary: `Summary for ${id}`,
  categories: ["benchmark"],
  organizations: ["Radar Lab"],
  event_kind: "released",
  snapshot_date: date,
  snapshot_generated_at: `${date}T12:00:00Z`,
  published_at: `${date}T10:00:00Z`,
  metrics: { downloads: id === "old-match" ? 4 : 0 },
  ...extra,
});

const evidence = [
  row("2026-09-01", "old-match", { summary: "contains needle" }),
  row("2026-09-03", "new-match", { summary: "contains needle" }),
  row("2026-09-04", "other-source", { source: "Hugging Face", organizations: ["Community"] }),
  row("2026-09-05", "updated", { event_kind: "updated", categories: ["evaluation"] }),
  // Case mapping, final sigma, CJK, and an emoji split into two UTF-16 units:
  // positions and grams count code units, as String.prototype.slice does.
  row("2026-09-03", "unicode", { title: "ΣΟΦΙΑ Bench 🚀", summary: "多模态 评测 ΟΔΟΣ İstanbul" }),
  // A template literal prints a null title as "null"; the index must too.
  row("2026-09-02", "null-title", { title: null, summary: "Untitled needle record" }),
];
const attention = [{
  ...row("2026-09-06", "attention", {
    observation_kind: "attention",
    observation_id: "attention-1",
    producer: "Radar News",
    source: "Hacker News",
    organizations: ["Radar News"],
    summary: "contains needle",
    metrics: { points: 8 },
  }),
}];

const sameDay = [
  row("2026-09-04", "same-day", {
    summary: "contains needle low priority",
    recency_score: 10,
    total_score: 10,
    published_at: "2026-09-04T09:00:00Z",
  }),
  row("2026-09-04", "same-day", {
    summary: "contains needle high priority",
    recency_score: 90,
    total_score: 90,
    published_at: "2026-09-04T11:00:00Z",
  }),
];

// Two records that tie on every sort key. tie-a was first seen a day earlier,
// so the generator emits it before tie-b, while the archive lists tie-b first
// on the shared day. Without a tie-breaker the two paths ordered them
// differently (#1170).
const tiePublished = { published_at: "2026-09-05T10:00:00Z" };
const tieEarly = row("2026-09-02", "tie-a", tiePublished);
const tied = [row("2026-09-05", "tie-b", tiePublished), row("2026-09-05", "tie-a", tiePublished)];

const day = (date, items, signals = []) => ({
  date,
  generated_at: `${date}T12:00:00Z`,
  selection: { recommendation_score: 40, minimum_score: 20 },
  evidence_items: items,
  attention: { observations: signals },
});

const dashboard = {
  schema_version: 2,
  generated_at: "build-1",
  latest_date: "2026-09-06",
  days: [
    day("2026-09-01", evidence.slice(0, 1)),
    day("2026-09-02", [...evidence.slice(1, 2), tieEarly, evidence[5]]),
    day("2026-09-03", evidence.slice(2, 3)),
    day("2026-09-04", [evidence[3], ...sameDay]),
    day("2026-09-05", [...evidence.slice(4, 5), ...tied]),
    day("2026-09-06", [], attention),
  ],
};

const argument = (name) => {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : "";
};
const indexDir = argument("--index");
const dashboardPath = argument("--write-dashboard");
if (dashboardPath) {
  writeFileSync(dashboardPath, JSON.stringify(dashboard));
  process.exit(0);
}

// The browser fetches shards from /data/<base>/...; read them from disk.
globalThis.fetch = async (url) => {
  const path = join(indexDir, url.replace(/^\/data\//, ""));
  try {
    const bytes = readFileSync(path);
    return { ok: true, status: 200, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length) };
  } catch {
    return { ok: false, status: 404, json: async () => null };
  }
};

function app(state, verifyLimit = 24) {
  return new Function(
    "state",
    `${constants}\nconst SEARCH_VERIFY_LIMIT = ${verifyLimit};\n`
      + "const trackLoad = (label, views, run) => run();\n"
      + `${functions}\n`
      + "return { filteredObservations, decodeSearchIndex, findSearchMatches, ensureSearchRows };",
  )(state);
}

const ids = (items) => items.map((item) => `${item.observation_kind}:${item.source_id}`);

const baseState = (filters) => ({
  ...filters,
  source: filters.source || "",
  kind: filters.kind || "",
  category: filters.category || "",
  organization: filters.organization || "",
  event: filters.event || "",
  todaySort: filters.todaySort || "newest",
  windowData: {},
  fullDataLoaded: false,
  data: {
    latest_date: "2026-09-06",
    generated_at: "build-1",
    facets: { dates: ["2026-09-06"] },
    days: dashboard.days,
  },
});

function archiveResults(filters) {
  const state = baseState(filters);
  return ids(app(state).filteredObservations());
}

// verifyLimit 24 takes the path that checks a short candidate list against
// row text; 0 forces every trigram of the query to be read.
async function indexResults(filters, verifyLimit) {
  const state = baseState(filters);
  const functions = app(state, verifyLimit);
  const data = JSON.parse(readFileSync(join(indexDir, "radar-search.json"), "utf8"));
  state.searchData = functions.decodeSearchIndex(data);
  const index = state.searchData;
  const query = state.q.trim().toLowerCase();
  if (query) index.matches.set(query, await functions.findSearchMatches(index, query));
  // Index rows carry no identifiers; read them from the rows a page would show.
  await functions.ensureSearchRows(index.observations.map((item) => item.search_row), index);
  return ids(functions.filteredObservations().map((item) => index.fullRows.get(item.search_row)));
}

const cases = [
  { q: "needle", todayDate: "all" },
  { q: "needle", todayDate: "all", source: "GitHub" },
  { q: "benchmark", todayDate: "all", organization: "Radar Lab" },
  { q: "needle", todayDate: "all", category: "evaluation" },
  { q: "tie", todayDate: "all" },
  { q: "", todayDate: "all" },
  { q: "", todayDate: "all", todaySort: "attention" },
  { q: "needle", todayDate: "all", todaySort: "attention" },
  // Mid-word, one and two units, across the title/summary join, long, absent.
  { q: "eedl", todayDate: "all" },
  { q: "n", todayDate: "all" },
  { q: "ne", todayDate: "all" },
  { q: "benchmark summary for", todayDate: "all" },
  { q: "contains needle low priority", todayDate: "all" },
  { q: "  Contains NEEDLE  ", todayDate: "all" },
  { q: "zzzq", todayDate: "all" },
  // Every trigram but the last matches "summary for"; only the final, overlapping
  // one rules it out.
  { q: "summary fox", todayDate: "all" },
  { q: "null untitled", todayDate: "all" },
  { q: "σοφια", todayDate: "all" },
  { q: "οδος", todayDate: "all" },
  { q: "🚀", todayDate: "all" },
  { q: "bench 🚀", todayDate: "all" },
  { q: "多模态", todayDate: "all" },
  { q: "i̇stanbul", todayDate: "all" },
  { q: "github", todayDate: "all" },
];

// The archive path itself still finds what the cases above expect.
assert.deepEqual(archiveResults({ q: "needle", todayDate: "all" }), [
  "attention:attention",
  "evidence:same-day",
  "evidence:new-match",
  "evidence:null-title",
  "evidence:old-match",
]);
assert.deepEqual(archiveResults({ q: "σοφια", todayDate: "all" }), ["evidence:unicode"]);
assert.deepEqual(archiveResults({ q: "🚀", todayDate: "all" }), ["evidence:unicode"]);

if (indexDir) {
  for (const filters of cases) {
    const expected = archiveResults(filters);
    for (const verifyLimit of [24, 0]) {
      assert.deepEqual(
        await indexResults(filters, verifyLimit),
        expected,
        `${JSON.stringify(filters)} verifyLimit=${verifyLimit}`,
      );
    }
  }
}

console.log("Search index parity cases passed.");
