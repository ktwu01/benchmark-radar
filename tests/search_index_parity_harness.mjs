import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";

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
];
const functions = functionNames.map((name) => {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
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
    day("2026-09-02", [...evidence.slice(1, 2), tieEarly]),
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
const indexPath = argument("--index");
const dashboardPath = argument("--write-dashboard");
if (dashboardPath) {
  writeFileSync(dashboardPath, JSON.stringify(dashboard));
  process.exit(0);
}
const generatedIndex = indexPath ? JSON.parse(readFileSync(indexPath, "utf8")) : null;

function run(state, indexed) {
  return new Function(
    "state",
    `${constants}\n${functions}\nreturn filteredObservations();`,
  )(state).map((item) => `${item.observation_kind}:${item.source_id}`);
}

const cases = [
  { q: "needle", todayDate: "all" },
  { q: "needle", todayDate: "all", source: "GitHub" },
  { q: "benchmark", todayDate: "all", organization: "Radar Lab" },
  { q: "", todayDate: "2026-09-01" },
  { q: "", todayDate: "30d", event: "released" },
  { q: "needle", todayDate: "all", category: "evaluation" },
  { q: "tie", todayDate: "all" },
];

for (const filters of cases) {
  const state = {
    ...filters,
    source: filters.source || "",
    kind: filters.kind || "",
    category: filters.category || "",
    organization: filters.organization || "",
    event: filters.event || "",
    todaySort: "newest",
    windowData: {},
    data: { latest_date: "2026-09-06", facets: { dates: ["2026-09-06"] } },
  };
  const archiveState = {
    ...state,
    data: {
      ...state.data,
      generated_at: "build-1",
      days: dashboard.days,
    },
  };
  const indexState = {
    ...state,
    data: archiveState.data,
    searchData: {
      observations: generatedIndex?.observations || [
        ...evidence.map((item) => ({
          ...item,
          observation_kind: "evidence",
          snapshot_generated_at: `${item.snapshot_date}T12:00:00Z`,
          recommendation_score: 40,
          minimum_score: 20,
        })),
        ...sameDay.map((item) => ({
          ...item,
          observation_kind: "evidence",
          snapshot_generated_at: `${item.snapshot_date}T12:00:00Z`,
          recommendation_score: 40,
          minimum_score: 20,
        })),
        ...[tied[1], tied[0]].map((item) => ({
          ...item,
          observation_kind: "evidence",
          snapshot_generated_at: `${item.snapshot_date}T12:00:00Z`,
          recommendation_score: 40,
          minimum_score: 20,
        })),
        ...attention,
      ],
    },
  };
  assert.deepEqual(run(archiveState), run(indexState), JSON.stringify(filters));
}

assert.deepEqual(run({
  q: "needle",
  todayDate: "all",
  todaySort: "newest",
  source: "",
  kind: "",
  category: "",
  organization: "",
  event: "",
  windowData: {},
  data: {
    latest_date: "2026-09-06",
    generated_at: "build-1",
    days: dashboard.days,
  },
}), [
  "attention:attention",
  "evidence:same-day",
  "evidence:new-match",
  "evidence:old-match",
]);

console.log("Search index parity cases passed.");
