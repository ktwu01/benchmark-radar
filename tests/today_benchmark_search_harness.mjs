// Issue #863: Today must explain partial candidates just like Saturation.
// Execute the production renderer and search helpers; stub only DOM creation.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { searchCatalog, searchCatalogMatches } from "../site/assets/catalog-search.js";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const nodes = new Map();
const byId = (id) => {
  if (!nodes.has(id)) nodes.set(id, { hidden: false, textContent: "", children: [] });
  return nodes.get(id);
};
// The homepage reads the compact search index (#1305); the full catalog is
// used only once another view has loaded it.
const state = {
  q: "protein structure prediction",
  benchmarkIndex: null,
  benchmarkIndexLoaded: false,
  benchmarkSearchRecords: [],
  benchmarkSearchLoaded: true,
};
const names = ["searchBenchmarkIndex", "fullMatchSlugs", "partialMatchNote", "renderTodayBenchmarks"];
const render = new Function("state", "byId", "replaceChildren", "searchCatalog", "searchCatalogMatches", "benchmarkResultRow", "t", `
  ${source.match(/const BENCHMARK_SEARCH_LIMIT = .*;/)[0]}
  let benchmarkIndexRerenderQueued = true;
  let fullMatchCache = { records: null, query: "", slugs: new Set() };
  ${names.map(fn).join("\n")}
  return renderTodayBenchmarks;
`)(state, byId, (node, children) => { node.children = children; }, searchCatalog, searchCatalogMatches,
  (record) => record, (text, values = {}) => Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)), text,
  ),
);
const record = (slug, name) => ({ slug, key: `test:${slug}`, name, source: "test" });
const full = record("full", "Protein structure prediction");
const partial = [record("protein", "Protein folding"), record("structure", "Structure analysis")];
const note = () => byId("today-benchmarks-note").textContent;

state.benchmarkSearchRecords = partial;
assert.equal(render(), 2);
assert.equal(byId("today-benchmarks").hidden, false);
assert.match(note(), /No benchmark matches every word; these share only some/);

state.benchmarkSearchRecords = [full, ...partial];
assert.equal(render(), 3);
assert.match(note(), /1 match every word · 2 share only some/);

state.benchmarkSearchRecords = [full];
assert.equal(render(), 1);
assert.doesNotMatch(note(), /share only some/);

// Counts describe all candidates, not only the first 50 rendered rows.
state.benchmarkSearchRecords = [full, ...Array.from({ length: 50 }, (_, i) => record(`p${i}`, `Protein ${i}`))];
assert.equal(render(), 51);
assert.equal(byId("today-benchmarks-results").children.length, 50);
assert.match(note(), /Showing 50 of 51 registry records/);
assert.match(note(), /1 match every word · 50 share only some/);

// A failed/pending catalog must not inherit the previous query's match note.
state.benchmarkSearchRecords = null;
assert.equal(render(), 0);
assert.equal(note(), "The benchmark catalog could not be loaded.");
state.benchmarkSearchRecords = [];
state.benchmarkSearchLoaded = false;
assert.equal(render(), "pending");
assert.equal(note(), "Still checking the benchmark registry…");
state.benchmarkSearchLoaded = true;
assert.equal(render(), 0);
assert.equal(byId("today-benchmarks").hidden, true);
state.q = "";
assert.equal(render(), 0);
assert.equal(byId("today-benchmarks").hidden, true);
assert.deepEqual(byId("today-benchmarks-results").children, []);
// A failed load that Refresh reset is requested again: the latch that stops
// one request per keystroke is released once the load settles.
{
  let requests = 0;
  const retryState = { q: "protein", benchmarkIndex: null, benchmarkIndexLoaded: false,
    benchmarkSearchRecords: null, benchmarkSearchLoaded: false };
  const retry = new Function("state", "byId", "replaceChildren", "searchCatalog", "searchCatalogMatches",
    "benchmarkResultRow", "t", "loadBenchmarkSearch", "renderToday", `
    ${source.match(/const BENCHMARK_SEARCH_LIMIT = .*;/)[0]}
    let benchmarkIndexRerenderQueued = false;
    let fullMatchCache = { records: null, query: "", slugs: new Set() };
    ${names.map(fn).join("\n")}
    return renderTodayBenchmarks;
  `)(retryState, byId, (node, children) => { node.children = children; }, searchCatalog, searchCatalogMatches,
    (record) => record, (text) => text, () => { requests += 1; return Promise.resolve(null); }, () => {});
  retry();
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(retryState.benchmarkSearchLoaded, true);
  // What refreshData does to a failed compact load.
  retryState.benchmarkSearchLoaded = false;
  retry();
  assert.equal(requests, 2);
}

// A full catalog another view loaded answers with the same records.
state.q = "protein structure prediction";
state.benchmarkSearchRecords = [];
state.benchmarkIndex = [full, ...partial];
state.benchmarkIndexLoaded = true;
assert.equal(render(), 3);
assert.match(note(), /1 match every word · 2 share only some/);
console.log("Today search distinguishes full and partial candidates without changing ranking.");
