import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
const functionNames = [
  "todayDateRange",
  "todayIsMultiDate",
  "observationDays",
  "freshWindowData",
  "allObservations",
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

const day = (date, items, signals = []) => ({
  date,
  generated_at: `${date}T12:00:00Z`,
  selection: { recommendation_score: 40, minimum_score: 20 },
  evidence_items: items,
  attention: { observations: signals },
});

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
      days: [
        day("2026-09-01", evidence.slice(0, 1)),
        day("2026-09-02", evidence.slice(1, 2)),
        day("2026-09-03", evidence.slice(2, 3)),
        day("2026-09-04", evidence.slice(3, 4)),
        day("2026-09-05", evidence.slice(4, 5)),
        day("2026-09-06", [], attention),
      ],
    },
  };
  const indexState = {
    ...state,
    data: archiveState.data,
    searchData: {
      observations: [
        ...evidence.map((item) => ({
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
    days: evidence.map((item) => day(item.snapshot_date, [item])).concat([day("2026-09-06", [], attention)]),
  },
}), [
  "attention:attention",
  "evidence:new-match",
  "evidence:old-match",
]);

console.log("Search index parity cases passed.");
