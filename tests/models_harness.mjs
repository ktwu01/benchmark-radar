// Execute the Models view's production code without a browser: the matrix
// helpers, the shared-benchmark average's three rules, and the three reported
// interaction defects (#862 review), against a small DOM stub.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const block = source.slice(source.indexOf("// --- Models ---"), source.indexOf("// --- Catalog detail ---"));

// --- A DOM stub with just enough selector matching, focus and events. ---------
class Node {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parent = null;
    this.attributes = {};
    this.dataset = {};
    this.listeners = {};
    this.className = "";
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.value = "";
    this._text = "";
    this.classList = { add() {}, remove() {} };
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return this.children.length ? this.children.map((child) => child.textContent).join("") : this._text;
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
    if (key.startsWith("data-")) this.dataset[key.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = String(value);
    if (key === "id") this.id = String(value);
  }
  getAttribute(key) {
    return this.attributes[key] ?? null;
  }
  append(...children) {
    for (const child of children.filter(Boolean)) {
      child.parent = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = null;
    this.children = [];
    this.append(...children);
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  dispatch(type, event = {}) {
    // Bubble to the ancestors, as a click on a cell reaches #models-list.
    for (let node = this; node; node = node.parent) {
      for (const listener of node.listeners[type] || []) listener({ target: this, ...event });
    }
  }
  click() {
    this.dispatch("click");
  }
  focus() {
    document.activeElement = this;
  }
  contains(node) {
    for (let current = node; current; current = current.parent) if (current === this) return true;
    return false;
  }
  matches(selector) {
    const match = selector.match(/^([a-z]*)((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/);
    assert(match, `unsupported selector ${selector}`);
    const [, tag, classes, attrs] = match;
    if (tag && this.tagName !== tag.toUpperCase()) return false;
    const own = this.className.split(/\s+/);
    if (classes && !classes.slice(1).split(".").every((name) => own.includes(name))) return false;
    for (const [, key, value] of attrs.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
      if (!(key in this.attributes) || (value !== undefined && this.attributes[key] !== value)) return false;
    }
    return true;
  }
  closest(selector) {
    for (let node = this; node; node = node.parent) if (node.matches(selector)) return node;
    return null;
  }
  querySelectorAll(selector) {
    const found = [];
    const walk = (node) => node.children.forEach((child) => {
      if (child instanceof Node) {
        if (child.matches(selector)) found.push(child);
        walk(child);
      }
    });
    walk(this);
    return found;
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

const nodes = new Map();
const byId = (id) => {
  // An id rendered inside a container (the panel's Close button) is found
  // there, as getElementById would.
  for (const root of nodes.values()) {
    const inner = root.querySelectorAll("button").find((node) => node.id === id);
    if (inner) return inner;
  }
  if (!nodes.has(id)) {
    const node = new Node(id === "models-lab-select" ? "select" : id === "models-search" ? "input" : "div");
    node.id = id;
    nodes.set(id, node);
  }
  return nodes.get(id);
};
globalThis.document = {
  activeElement: null,
  body: new Node("body"),
  createElement: (tag) => new Node(tag),
  createTextNode: (value) => ({ textContent: String(value) }),
  addEventListener(type, listener) {
    (this.listeners ||= {})[type] = [...(this.listeners?.[type] || []), listener];
  },
};
globalThis.CSS = { escape: (value) => value };

// --- The production Models block, with the app-wide helpers it calls. ----------
const shards = new Map();
let scoresResponse;
const env = {
  state: {},
  byId,
  t: (key, params) => Object.entries(params || {}).reduce((text, [k, v]) => text.replaceAll(`{${k}}`, String(v)), key),
  formatDate: (value) => value,
  scoreSourceLabel: (value) => ({ llm_stats: "LLM Stats", model_reports: "Model reports" })[value] || value,
  libraryCategoryNames: () => new Map(),
  loadBenchmarkIndex: async () => env.records,
  loadBenchmarkShard: async (slug) => shards.get(slug) ?? null,
  writeUrl: () => { env.urlWrites += 1; },
  fetch: async () => scoresResponse,
  // The load-feedback pill is app-wide chrome, not Models behaviour; run the
  // load straight through.
  trackLoad: (label, views, run) => run(null),
  urlWrites: 0,
  records: [],
};
const names = [
  "modelDocuments", "modelFirstMentions", "modelCapabilityGroup", "modelFamily", "modelAverageValue",
  "modelSharedAverage", "modelMatrixModels", "modelMatrixTable", "modelOrder", "modelMatches", "modelLabCounts",
  "renderModelLabs", "modelValueText", "modelSeriesScale", "modelLatestDate", "openModelPanel", "closeModelPanel", "renderModels", "initModels",
];
const models = new Function(
  ...Object.keys(env),
  `${source.match(/const MODEL_PAGE_COLUMNS = .*;/)[0]}\n${fn("safeHttpUrl")}\n${fn("element")}\n${fn("replaceChildren")}\n${fn("debounce")}\n${block}\nreturn {${names.join(",")}};`,
)(...Object.values(env));
const { state } = env;

// --- Model documents: first mentions per lab (unchanged behaviour). ------------
const bench = (id) => ({ benchmark_id: id, name: id.toUpperCase() });
const doc = (id, organization, published, benchmarks, type = "model_card") => ({
  id, organization, published, document_type: type, benchmarks: benchmarks.map(bench),
});
state.catalogDocuments = {
  documents: [
    doc("a1", "Acme", "2025-01-01", ["mmlu", "aime"]),
    doc("a2", "Acme", "2026-01-01", ["aime", "swe"]),
    doc("x", "Acme", "2026-03-01", ["leader"], "benchmark_leaderboard"),
    doc("u", "Acme", null, ["hle"]),
  ],
};
assert.deepEqual(models.modelDocuments().map((d) => d.id), ["a2", "a1", "u"]);
const firsts = models.modelFirstMentions(models.modelDocuments());
assert.deepEqual([...firsts.get("a2")], ["swe"]);
assert.deepEqual([...firsts.get("u")], []);

// --- Families, capability groups. -----------------------------------------------
assert.deepEqual(models.modelFamily("Claude Opus 5 (Adaptive Reasoning, High Effort)"), ["Claude Opus 5", "Adaptive Reasoning, High Effort"]);
assert.deepEqual(models.modelFamily("Claude-Opus-5 (max)"), ["Claude-Opus-5", "max"]);
assert.deepEqual(models.modelFamily("GPT-5"), ["GPT-5", ""]);
assert.equal(models.modelCapabilityGroup({ categories: ["math", "reasoning"] }), "Mathematics");
assert.equal(models.modelCapabilityGroup({ categories: [], library_direction: { categories: ["agentic-coding"] } }), "Coding");
assert.equal(models.modelCapabilityGroup({ categories: ["safety"] }), "Other");
// Whole words: "multilingual" is language, not Multimodal.
assert.equal(models.modelCapabilityGroup({ categories: [], library_direction: { categories: ["multilingual"] } }), "Reasoning & Knowledge");

// The scale rule, as model_scores.score_scale: the multiplier alone is not a percentage.
assert.equal(models.modelSeriesScale({ declared_max: 1, score_summary: { display_multiplier: 100, raw_max: 0.6 } }).percent, true);
assert.equal(models.modelSeriesScale({ score_summary: { display_multiplier: 100, raw_max: 0.6 } }).percent, false);
assert.equal(models.modelSeriesScale({ score_summary: { display_multiplier: 1, unit: "percent", raw_max: 140 } }).percent, false);
assert.equal(models.modelSeriesScale({ declared_max: 3000, score_summary: { display_multiplier: 1, unit: "elo" } }).unit, "Elo");
// A column's date: the latest over its sources, or the selected source's.
const twoDates = { a: ["2026-01-01", "x"], b: ["2026-02-01", "y"] };
assert.deepEqual(models.modelLatestDate(twoDates), ["2026-02-01", "y"]);
assert.deepEqual(models.modelLatestDate(twoDates, "a"), ["2026-01-01", "x"]);

// --- The shared-benchmark average's three rules. ----------------------------------
const pct = { percent: true, direction: "higher_is_better" };
const benchmarks = new Map([
  ["hard", pct],
  ["easy", pct],
  ["elo", { percent: false, direction: "higher_is_better", unit: "Elo" }],
  ["error", { percent: true, direction: "lower_is_better" }],
]);
const cells = (entries) => new Map(Object.entries(entries).map(([key, value]) => [key, { value, count: 1 }]));
// Rule 1: only benchmarks every compared model has count. B also reported an
// easy benchmark (99), which must not lift its average over A's.
const onlyShared = models.modelSharedAverage([cells({ hard: 40 }), cells({ hard: 40, easy: 99 })], benchmarks);
assert.deepEqual(onlyShared, { means: [40, 40], shared: ["hard"] });
// Rule 2: values arrive on their display scale (a 0.6 fraction is 60 after the
// build's display_multiplier); Elo is left out, lower-is-better is flipped.
const scaled = models.modelSharedAverage(
  [cells({ hard: 60, elo: 1577, error: 10 }), cells({ hard: 80, elo: 1200, error: 30 })], benchmarks,
);
assert.deepEqual(scaled.shared, ["error", "hard"]);
assert.deepEqual(scaled.means, [75, 75]); // (90 + 60) / 2 and (70 + 80) / 2
assert.equal(models.modelAverageValue(1577, benchmarks.get("elo")), null);
assert.equal(models.modelAverageValue(10, benchmarks.get("error")), 90);
// Rule 1 within a record: two protocols or scaffolds are not one benchmark.
const grouped = (entries) => new Map(Object.entries(entries).map(([key, [value, group]]) => [key, { value, count: 1, group }]));
assert.deepEqual(
  models.modelSharedAverage([grouped({ hard: [40, 0], easy: [50, null] }), grouped({ hard: [60, 1], easy: [70, null] })], benchmarks),
  { means: [50, 70], shared: ["easy"] },
);
// Rule 3: the number of shared benchmarks is returned, and none shared is said.
assert.deepEqual(models.modelSharedAverage([cells({ hard: 1 }), cells({ easy: 2 })], benchmarks), { means: [null, null], shared: [] });
// Rounds like model_scores.round_tenth (half up, not to even).
assert.deepEqual(models.modelSharedAverage([cells({ hard: 0.25 })], benchmarks).means, [0.3]);
// Joined benchmarks (#904): columns scoring different records of one reviewed
// equivalent group share that benchmark; different groups do not share.
const joined = new Map([["hard", "gpqa"], ["easy", "gpqa"]]);
assert.deepEqual(
  models.modelSharedAverage([cells({ hard: 40 }), cells({ easy: 60 })], benchmarks, joined),
  { means: [40, 60], shared: ["gpqa"] },
);
assert.deepEqual(
  models.modelSharedAverage(
    [cells({ hard: 40 }), cells({ easy: 60 })],
    benchmarks,
    new Map([["hard", "g1"], ["easy", "g2"]]),
  ),
  { means: [null, null], shared: [] },
);
// Without the joined map the behaviour is unchanged.
assert.deepEqual(
  models.modelSharedAverage([cells({ hard: 40 }), cells({ easy: 60 })], benchmarks),
  { means: [null, null], shared: [] },
);
// Joined benchmarks compare group labels, not local indexes: index 0 is
// "cot" on "hard" and "plain" on "easy", so equal indexes must not share;
// the same protocol under different indexes must.
const labelled = new Map([
  ["hard", { ...pct, groups: ["cot", "plain"] }],
  ["easy", { ...pct, groups: ["plain", "cot"] }],
]);
assert.deepEqual(
  models.modelSharedAverage(
    [grouped({ hard: [40, 0] }), grouped({ easy: [60, 0] })],
    labelled,
    joined,
  ),
  { means: [null, null], shared: [] },
);
assert.deepEqual(
  models.modelSharedAverage(
    [grouped({ hard: [40, 1] }), grouped({ easy: [60, 0] })],
    labelled,
    joined,
  ),
  { means: [40, 60], shared: ["gpqa"] },
);
assert.equal(models.modelValueText(74.66, pct), "74.7%");
assert.equal(models.modelValueText(1577, benchmarks.get("elo")), "1,577 Elo");

// --- Matrix data, fallback, order. ------------------------------------------------
const record = (key, name, source = "llm_stats", scored = []) => ({
  key, slug: key.replace(":", "-"), name, source, categories: ["math"], scored_models: scored.map((n) => ({ name: n, date: "2026-01-01" })),
});
env.records = [
  record("llm-stats:arc-agi-3", "ARC-AGI-3", "llm_stats", ["Acme-2", "Beta-1"]),
  record("model-reports:arc_agi_3", "ARC-AGI-3", "model_reports", ["Acme-2"]),
  ...Array.from({ length: 8 }, (_, i) => record(`llm-stats:b${i}`, `B${i}`, "llm_stats", [`Acme-${i}`])),
  record("claire-radar:x", "X", "claire_radar"),
];
const payload = {
  schema_version: 1,
  benchmarks: [
    { key: "llm-stats:arc-agi-3", direction: "higher_is_better", multiplier: 100, percent: true, unit: "%" },
    { key: "model-reports:arc_agi_3", direction: "higher_is_better", multiplier: 1, percent: true, unit: "%" },
    ...Array.from({ length: 8 }, (_, i) => ({ key: `llm-stats:b${i}`, direction: "higher_is_better", multiplier: 100, percent: true, unit: "%" })),
  ],
  models: [
    { key: "beta-1", model: "Beta-1", organization: "Beta", dates: { llm_stats: ["2026-05-01", "model_announcement"] }, scores: [[0, 30]] },
    ...Array.from({ length: 8 }, (_, i) => ({
      key: `acme-${i}`, model: `Acme-${i}`, organization: "Acme",
      dates: i === 2
        ? { llm_stats: ["2026-03-01", "model_announcement"], model_reports: ["2026-02-15", "document_publication"] }
        : { llm_stats: [`2026-0${i + 1}-01`, "model_announcement"] },
      scores: i === 2 ? [[0, 50], [1, 48.5, 2], [2 + i, 70]] : [[2 + i, 60 + i]],
    })),
  ],
};
const matrix = models.modelMatrixModels(env.records, payload);
assert.equal(matrix.scored, true);
assert.equal(matrix.models.length, 9);
assert.deepEqual(matrix.models.find((model) => model.key === "acme-2").cells.get("model-reports:arc_agi_3"), { value: 48.5, count: 2, group: null });
const fallback = models.modelMatrixModels(env.records, null);
assert.equal(fallback.scored, false);
assert.deepEqual(fallback.models.find((model) => model.name === "Acme-2").cells.get("llm-stats:arc-agi-3"), { value: null, count: 1, group: null, date: "2026-01-01", precision: "" });
// Most benchmarks first (Acme-2 has three), then newest; or newest first.
assert.deepEqual(models.modelOrder(matrix.models).map((model) => model.key).slice(0, 3), ["acme-2", "acme-7", "acme-6"]);
assert.deepEqual(models.modelOrder(matrix.models, "newest").map((model) => model.key).slice(0, 3), ["acme-7", "acme-6", "acme-5"]);
const family = [
  { organization: "A", family: "M", configuration: "high", date: "2026-02-01", name: "M (high)", cells: new Map([["x", {}]]) },
  { organization: "A", family: "M", configuration: "", date: "2026-01-01", name: "M", cells: new Map([["x", {}]]) },
  { organization: "A", family: "N", configuration: "", date: "2026-01-15", name: "N", cells: new Map([["x", {}], ["y", {}]]) },
];
assert.deepEqual(models.modelOrder(family, "newest").map((model) => model.name), ["M", "M (high)", "N"]);
assert.deepEqual(models.modelOrder(family).map((model) => model.name), ["N", "M", "M (high)"]);
assert.deepEqual(models.modelLabCounts(matrix.models), [["Acme", 8], ["Beta", 1]]);

// modelMatrixTable (#1129 P1): the reviewed join reaches the live average --
// two models scoring different records of one equivalent group share it.
const joinedRecords = [
  record("llm-stats:gpqa", "GPQA", "llm_stats"),
  record("opencompass:1135", "GPQA", "opencompass"),
];
const joinedPayload = {
  schema_version: 1,
  benchmarks: [
    { key: "llm-stats:gpqa", direction: "higher_is_better", multiplier: 1, percent: true, unit: "%", joined: "gpqa" },
    { key: "opencompass:1135", direction: "higher_is_better", multiplier: 1, percent: true, unit: "%", joined: "gpqa" },
  ],
  models: [
    { key: "a", model: "A", organization: "Lab", dates: {}, scores: [[0, 40]] },
    { key: "b", model: "B", organization: "Lab", dates: {}, scores: [[1, 60]] },
  ],
};
const joinedMatrix = models.modelMatrixModels(joinedRecords, joinedPayload);
const joinedTable = models.modelMatrixTable(
  joinedMatrix.models, joinedMatrix,
  new Map(joinedRecords.map((entry) => [entry.key, entry])),
);
const joinedAverage = joinedTable.querySelector("tbody.models-average").textContent;
assert.match(joinedAverage, /over the 1 benchmarks all 2 models share, 0–100/);
assert.match(joinedAverage, /40/);
assert.match(joinedAverage, /60/);

// --- Rendering. ------------------------------------------------------------------
function reset(scores) {
  Object.assign(state, {
    view: "models", modelsLab: "", modelsQuery: "", modelsOffset: 0, modelsSharedOnly: false,
    modelsPanel: null, modelsMatrix: null, modelScores: scores, benchmarkIndex: env.records, benchmarkIndexLoaded: true,
  });
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const labButton = (lab) => byId("models-labs").querySelector(`button[data-lab="${lab}"]`);
const columnNames = () => byId("models-list").querySelectorAll("span.models-col-name").map((node) => node.textContent);

// Defect 1 (#862): after the lab data failed to load, the lab filter and
// paging stopped working, because the controls were bound after an early
// return. They are now bound first, and the page renders every scored model
// from the benchmark index with its lab unknown.
reset(undefined);
scoresResponse = { ok: false, json: async () => ({}) };
models.renderModels();
assert.equal(byId("models-older").listeners.click.length, 1); // bound while still loading
await tick();
await tick();
assert.equal(state.modelScores, null);
assert.match(byId("models-status").textContent, /could not be loaded/);
assert.equal(columnNames().length, 6);
byId("models-older").click();
assert.equal(state.modelsOffset, 6);
assert.equal(columnNames().length, 3); // 9 models, page two
labButton("__unrecorded__").click();
assert.equal(state.modelsLab, "__unrecorded__");
assert.equal(state.modelsOffset, 0);
assert.equal(columnNames().length, 6);

reset(payload);
// Same-name records keep their sources visible in the row label: Acme-2 has
// ARC-AGI-3 from LLM Stats and from a model report, the latter twice.
state.modelsQuery = "acme-2";
models.renderModels();
const labels = byId("models-list").querySelectorAll("span.models-source").map((node) => node.textContent);
assert(labels.includes("LLM Stats") && labels.includes("Model reports"));
assert.match(byId("models-list").textContent, /best of 2 settings/);
state.modelsQuery = "";
models.renderModels();
assert.match(byId("models-list").querySelector("tbody.models-average").textContent, /Shared-benchmark average/);
assert.equal(columnNames().length, 6);
assert.match(byId("models-list").querySelector("thead").textContent, /announced 2026-08-01/);

// Defect 2 (#862): "Show more" rebuilt the list and collapsed every expanded
// model. The matrix has no expandable rows; what a reader opens is a cell's
// side panel, and a re-render must keep it open while its model is shown.
// The panel reads scale and rows from the record's shard: a fraction declared
// out of 1 shows as a percentage, under a neutral heading.
shards.set("llm-stats-b7", { scores_by_source: { llm_stats: {
  series: { direction: "higher_is_better", declared_max: 1, score_summary: { display_multiplier: 100, raw_max: 0.67 } },
  rows: [{ model_name: "Acme-7", organization: "Acme", value: 0.67, reported_date: "2026-08-01", date_precision: "model_announcement", source: "llm_stats" }],
} } });
const cell = byId("models-list").querySelector('button.models-cell[data-model="acme-7"]');
cell.click();
await tick();
assert.match(byId("models-panel").textContent, /Scores for this model/);
// The panel says what each row's date is, as the columns do.
assert.match(byId("models-panel").textContent, /announced 2026-08-01/);
assert.match(byId("models-panel").textContent, /67%/);
assert.deepEqual(state.modelsPanel, { model: "acme-7", record: "llm-stats:b7" });
assert.equal(byId("models-panel").hidden, false);
assert.equal(document.activeElement, byId("models-panel-close"));
models.renderModels();
assert.deepEqual(state.modelsPanel, { model: "acme-7", record: "llm-stats:b7" });
assert.equal(byId("models-panel").hidden, false);
assert.equal(byId("models-list").querySelector('button.models-cell[data-model="acme-7"]').getAttribute("aria-pressed"), "true");
// The shared-only toggle hides a row the other columns lack, so it closes a
// panel open on that row.
byId("models-shared").dispatch("change", { target: { checked: true } });
assert.equal(state.modelsPanel, null);
assert.equal(byId("models-panel").hidden, true);
byId("models-shared").dispatch("change", { target: { checked: false } });
byId("models-list").querySelector('button.models-cell[data-model="acme-7"]').click();
// Paging past that model closes its panel instead of describing an off-page cell.
byId("models-older").click();
assert.equal(state.modelsPanel, null);
assert.equal(byId("models-panel").hidden, true);

// Defect 3 (#862): switching labs replaced every lab button, so the focused
// one was removed and keyboard focus was lost.
reset(payload);
models.renderModels();
const acme = labButton("Acme");
acme.focus();
acme.click();
assert.equal(state.modelsLab, "Acme");
assert.equal(labButton("Acme"), acme); // updated in place, not replaced
assert.equal(document.activeElement, acme);
assert.equal(acme.getAttribute("aria-pressed"), "true");
// When the list must be rebuilt (the seed's plain links), focus follows the
// selected lab rather than falling to the page.
const seedLink = new Node("a");
byId("models-labs").replaceChildren(seedLink);
seedLink.focus();
models.renderModels();
assert.equal(document.activeElement, labButton("Acme"));

// Search narrows by model name and returns to the first page.
reset(payload);
models.renderModels();
state.modelsOffset = 6;
byId("models-search").value = " acme-1 ";
byId("models-search").dispatch("input");
await new Promise((resolve) => setTimeout(resolve, 150));
assert.equal(state.modelsQuery, "acme-1");
assert.equal(state.modelsOffset, 0);
assert.deepEqual(columnNames(), ["Acme-1"]);
// One source: Acme-2 keeps only its model-report cell, and the sort and
// source menus reach the URL state.
reset(payload);
models.renderModels();
byId("models-source").dispatch("change", { target: { value: "model_reports" } });
assert.equal(state.modelsSource, "model_reports");
assert.deepEqual(columnNames(), ["Acme-2"]);
// The column shows the selected source's date and what it is.
assert.match(byId("models-list").querySelector("thead").textContent, /reported 2026-02-15/);
byId("models-source").dispatch("change", { target: { value: "" } });
byId("models-sort").dispatch("change", { target: { value: "newest" } });
assert.equal(columnNames()[0], "Acme-7");
// The chart ranks only runs in the selected score's comparable group: a run
// under another scaffold on the same record is listed for its own model, never
// ranked against this one.
reset(payload);
models.renderModels();
shards.set("llm-stats-b6", { scores_by_source: { llm_stats: {
  series: { direction: "higher_is_better", score_summary: { display_multiplier: 1, unit: "percent" } },
  rows: [
    { model_name: "Acme-6", organization: "Acme", value: 50, protocol: "scaffold A", comparable_group: "A" },
    { model_name: "Rival", organization: "Other", value: 90, protocol: "scaffold B", comparable_group: "B" },
    { model_name: "Peer", organization: "Other", value: 40, protocol: "scaffold A", comparable_group: "A" },
  ],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-6"]').click();
await tick();
const chart = byId("models-panel").querySelector("ol.models-panel-chart").textContent;
assert.match(chart, /Acme-6/);
assert.match(chart, /Peer/);
assert.doesNotMatch(chart, /Rival/);
assert.match(byId("models-panel").textContent, /Same setting only: scaffold A/);
// Switching labs with the panel open closes it, and focus stays on the lab
// button the reader pressed.
const acmeLab = labButton("Acme");
acmeLab.focus();
acmeLab.click();
assert.equal(state.modelsPanel, null);
assert.equal(byId("models-panel").hidden, true);
assert.equal(document.activeElement, acmeLab);

// A setting names its test version when it differs from the record.
reset(payload);
models.renderModels();
shards.set("llm-stats-b5", { scores_by_source: { llm_stats: {
  series: { direction: "higher_is_better", score_summary: { display_multiplier: 1, unit: "percent" } },
  rows: [
    { model_name: "Acme-5", organization: "Acme", value: 30, benchmark_id: "b5", instrument: "b5_3.0", protocol: "think max", comparable_group: "x" },
    { model_name: "Acme-5", organization: "Acme", value: 90, benchmark_id: "b5", instrument: "b5_2.1", protocol: "think max", comparable_group: "y" },
  ],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-5"]').click();
await tick();
assert.match(byId("models-panel").textContent, /b5_3\.0 · think max/);
assert.match(byId("models-panel").textContent, /Same setting only: b5_2\.1 · think max/);
// A source filter that drops the opened record closes the panel, even while
// its model stays on the page.
state.modelsQuery = "acme-2";
models.renderModels();
byId("models-list").querySelector('button.models-cell[data-model="acme-2"][data-record="model-reports:arc_agi_3"]').click();
byId("models-source").dispatch("change", { target: { value: "llm_stats" } });
assert.deepEqual(columnNames(), ["Acme-2"]);
assert.equal(state.modelsPanel, null);
assert.equal(byId("models-panel").hidden, true);
state.modelsSource = "";
state.modelsQuery = "";

// Paging is kept in the URL, so reload and Back restore the columns.
reset(payload);
models.renderModels();
const writes = env.urlWrites;
byId("models-older").click();
assert.equal(env.urlWrites, writes + 1);

// A source that splits one label into checkpoints gets one column each,
// labelled by its ID, and the panel lists only that checkpoint's rows.
const splitPayload = {
  ...payload,
  models: [
    ...payload.models,
    { key: "acme-9@old", model: "Acme-9", organization: "Acme", source_model_id: "acme-9-0513", dates: {}, scores: [[8, 88.7]] },
    { key: "acme-9@new", model: "Acme-9", organization: "Acme", source_model_id: "acme-9-0806", dates: {}, scores: [[8, 85.7]] },
  ],
};
reset(splitPayload);
state.modelsQuery = "acme-9";
models.renderModels();
assert.deepEqual(columnNames(), ["Acme-9", "Acme-9"]);
assert.match(byId("models-list").querySelector("thead").textContent, /acme-9-0513/);
shards.set("llm-stats-b6", { scores_by_source: { llm_stats: {
  series: { direction: "higher_is_better", score_summary: { display_multiplier: 1, unit: "percent" } },
  rows: [
    { model_name: "Acme-9", organization: "Acme", model_id: "acme-9-0513", value: 88.7 },
    { model_name: "Acme-9", organization: "Acme", model_id: "acme-9-0806", value: 85.7 },
  ],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-9@new"]').click();
await tick();
const mineList = byId("models-panel").querySelector("ul.models-panel-scores").textContent;
assert.match(mineList, /85\.7%/);
assert.doesNotMatch(mineList, /88\.7%/);
// The chart has one entry per checkpoint, and highlights this column's.
const entries = byId("models-panel").querySelector("ol.models-panel-chart").querySelectorAll("li");
assert.equal(entries.length, 2);
assert.match(entries.find((entry) => entry.className === "is-selected").textContent, /85\.7%/);
state.modelsQuery = "";

// Without model-scores.json, a source filter dates each model by that
// source's records only.
reset(null);
env.records[1].scored_models = [{ name: "Acme-2", date: "2025-12-01", date_precision: "document_publication" }];
state.modelsSource = "model_reports";
state.modelsSort = "newest";
models.renderModels();
assert.match(byId("models-list").querySelector("thead").textContent, /reported 2025-12-01/);
state.modelsSource = "";
state.modelsSort = "coverage";

// Without model-scores.json the panel still formats from the shard's scale.
reset(null);
state.modelsQuery = "acme-7";
models.renderModels();
const fallbackCell = byId("models-list").querySelector('button.models-cell[data-model="acme-7"]');
fallbackCell.click();
await tick();
assert.match(byId("models-panel").textContent, /67%/);
// The panel links only http(s) sources, draws lower-is-better bars so the
// best score is longest, and names split checkpoints in the chart.
reset(payload);
models.renderModels();
shards.set("llm-stats-b4", { scores_by_source: { llm_stats: {
  series: { direction: "lower_is_better", score_summary: { display_multiplier: 1 } },
  rows: [
    { model_name: "Acme-4", organization: "Acme", value: 9.76, source_url: "javascript:alert(1)", source_title: "bad" },
    { model_name: "Best", organization: "Other", value: 5.81, source_url: "https://example.org/r", source_title: "good" },
    { model_name: "Twin", organization: "Other", model_id: "twin-0513", value: 7 },
    { model_name: "Twin", organization: "Other", model_id: "twin-0806", value: 8 },
  ],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-4"]').click();
await tick();
const panelLinks = byId("models-panel").querySelectorAll("a").map((link) => link.getAttribute("href"));
assert(!panelLinks.some((href) => String(href).startsWith("javascript:")));
const bars = byId("models-panel").querySelector("ol.models-panel-chart").querySelectorAll("li");
const shareOf = (label) => Number(bars.find((bar) => bar.textContent.startsWith(label)).querySelector("span.models-panel-bar").getAttribute("style").split(":")[1]);
assert.equal(shareOf("Best"), 1);
assert(shareOf("Acme-4") < shareOf("Best"));
assert.match(byId("models-panel").textContent, /Lower is better: the longest bar is the lowest score\./);
const chartText = byId("models-panel").querySelector("ol.models-panel-chart").textContent;
assert.match(chartText, /Twin \(twin-0513\)/);
assert.match(chartText, /Twin \(twin-0806\)/);
// Every lower-is-better bar stays visible, ordered best to worst.
assert(shareOf("Acme-4") > 0 && shareOf("Twin (twin-0513)") > shareOf("Twin (twin-0806)"));
// Lower-is-better bars are the best score's ratio to each value, so the gap
// is drawn as large as the data has it: 5.81 vs 9.76 is 100% vs 60%.
assert.equal(shareOf("Acme-4"), Number((5.81 / 9.76).toFixed(3)));
const lowerBars = async (rows) => {
  shards.set("llm-stats-b4", { scores_by_source: { llm_stats: {
    series: { direction: "lower_is_better", score_summary: { display_multiplier: 1 } }, rows,
  } } });
  byId("models-list").querySelector('button.models-cell[data-model="acme-4"]').click();
  await tick();
  const items = byId("models-panel").querySelector("ol.models-panel-chart").querySelectorAll("li");
  return (label) => Number(items.find((bar) => bar.textContent.startsWith(label)).querySelector("span.models-panel-bar").getAttribute("style").split(":")[1]);
};
// Near-equal scores draw near-equal bars, not 100% vs 10%.
const nearEqual = await lowerBars([
  { model_name: "Acme-4", organization: "Acme", value: 5.82 },
  { model_name: "Best", organization: "Other", value: 5.81 },
]);
assert(nearEqual("Best") - nearEqual("Acme-4") < 0.01);
// A winning 0 has no ratio; the other bars stay visible rather than vanish.
const zeroBest = await lowerBars([
  { model_name: "Acme-4", organization: "Acme", value: 9.76 },
  { model_name: "Best", organization: "Other", value: 0 },
]);
assert.equal(zeroBest("Best"), 1);
assert(zeroBest("Acme-4") > 0);
// The note on direction comes after the chart.
const panelChildren = byId("models-panel").querySelector("div.models-panel-body").children;
assert(panelChildren.findIndex((child) => child.tagName === "OL") < panelChildren.findIndex((child) => /Lower is better/.test(child.textContent || "")));

// A label split across the corpus is named by ID even on a record where only
// one of its checkpoints reports.
reset(splitPayload);
state.modelsQuery = "acme-9";
models.renderModels();
shards.set("llm-stats-b6", { scores_by_source: { llm_stats: {
  series: { direction: "higher_is_better", score_summary: { display_multiplier: 1, unit: "percent" } },
  rows: [{ model_name: "Acme-9", organization: "Acme", model_id: "acme-9-0806", value: 85.7, source: "llm_stats" }],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-9@new"]').click();
await tick();
assert.match(byId("models-panel").querySelector("ol.models-panel-chart").textContent, /Acme-9 \(acme-9-0806\)/);
// The split is the source's: the same label from another source keeps its
// plain name, however that source keys its rows.
shards.set("llm-stats-b6", { scores_by_source: { model_reports: {
  series: { direction: "higher_is_better", score_summary: { display_multiplier: 1, unit: "percent" } },
  rows: [{ model_name: "Acme-9", organization: "Acme", model_id: "[\"Acme\",\"Acme-9\"]", value: 80, source: "model_reports" }],
} } });
byId("models-list").querySelector('button.models-cell[data-model="acme-9@new"]').click();
await tick();
assert.doesNotMatch(byId("models-panel").querySelector("ol.models-panel-chart").textContent, /\(\[/);
state.modelsQuery = "";

console.log("Models matrix, shared-benchmark average rules and the three #862 defects passed.");
