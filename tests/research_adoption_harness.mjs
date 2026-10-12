import assert from "node:assert/strict";
import { loadDashboardSource } from "./load_dashboard_source.mjs";

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attributes = {}; this._text = ""; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(""); }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; this._text = ""; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener() {}
  querySelector(selector) { return walk(this).find((node) => node.className === selector.slice(1)); }
}
const nodes = new Map();
const byId = (id) => {
  if (!nodes.has(id)) nodes.set(id, new Node("div"));
  return nodes.get(id);
};
globalThis.document = {
  createElement: (tag) => new Node(tag), getElementById: byId,
  documentElement: { lang: "en" }, addEventListener() {}, querySelectorAll: () => [],
};
globalThis.window = { addEventListener() {}, location: { pathname: "/", search: "", hash: "" } };
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
const source = loadDashboardSource().replace(/^initialize\(\);$/m, "");
const R = new Function(`${source}
  // These independent score/release widgets are outside the adoption regression.
  syncLeaderboardMode = renderLatestReleases = initBenchmarkSearch = syncScoreFilters =
    renderBenchmarkSkyline = renderScoreRanking = syncLeaderboardNav = renderBenchmarkFindings = () => {};
  scoreRankingRows = () => [];
  return { state, renderLeaderboard, leaderboardEntries, catalogDocumentBoard, renderLeaderboardTop };
`)();
const benchmark = (id, tags) => ({ slug: id, tags, name: id });
R.state.benchmarkIndex = [
  benchmark("safety", ["safety"]), benchmark("unknown-score", ["safety"]),
  benchmark("mixed", ["safety", "coding_agent"]), benchmark("coding", ["coding"]),
];
const ref = (id, domain = "testing") => ({ benchmark_id: id, name: id, domain });
const documents = [
  { id: "shared", source: "model_reports", organization: "Shared", title: "Shared report", benchmarks: [ref("safety"), ref("mixed"), ref("coding")] },
  { id: "safety-doc", source: "model_reports", organization: "Safety publisher", title: "Safety report", benchmarks: [ref("safety"), ref("mixed")] },
  { id: "code-doc", source: "model_reports", organization: "Code publisher", title: "Code report", benchmarks: [ref("coding")] },
];
const entry = (id, rank, ids) => ({
  ...ref(id), rank, document_ids: ids, document_count: ids.length,
  organizations: ids.map((id) => documents.find((doc) => doc.id === id).organization),
  organization_count: ids.length,
});
R.state.catalogDocuments = {
  documents, document_count: 3, benchmark_count: 4,
  organizations: { Shared: 1, "Safety publisher": 1, "Code publisher": 1 },
  entries: [entry("safety", 1, ["shared", "safety-doc"]), entry("mixed", 2, ["shared", "safety-doc"]),
    entry("coding", 3, ["shared", "code-doc"]), entry("unknown-score", 4, [])],
};
R.state.data = {};
R.state.lq = R.state.ldomain = R.state.lorg = R.state.lera = "";
R.state.lscore = 70;
R.state.leaderboardShowAll = true;
const rowNames = () => byId("leaderboard-list").children.map((row) =>
  walk(row).find((node) => node.tag === "h3")?.textContent);
const topNames = () => walk(byId("leaderboard-top-list"))
  .filter((node) => node.className === "leaderboard-top-name").map((node) => node.textContent);
const counts = () => byId("leaderboard-insights").children.slice(0, 4).map((tile) =>
  walk(tile).find((node) => node.tag === "strong").textContent);

R.state.researchField = "safety";
R.renderLeaderboard();
assert.deepEqual(rowNames(), ["safety", "mixed", "unknown-score"], "field scope reaches the full table, including unscored records");
assert.deepEqual(topNames(), ["safety", "mixed"]);
assert.deepEqual(counts(), ["2", "2", "3", "2"], "documents and organizations count once in the selected field");
assert.equal(byId("leaderboard-count").textContent, "3 benchmarks of 3");
assert.equal(byId("leaderboard-cards-count").textContent, "2 documents");
assert(!byId("leaderboard-cards").textContent.includes("coding"), "shared documents list only the field's benchmark references");
assert(byId("leaderboard-list").textContent.includes("/ 2"), "row denominators match the scoped document count");
assert(walk(byId("leaderboard-list")).some((node) => node.attributes["aria-label"] === "2 source documents of 2 source documents"));

R.state.lq = "coding";
assert.deepEqual(R.leaderboardEntries(), [], "table search intersects the field scope");
R.state.lq = "";
R.state.researchField = "agents";
R.state.researchSub = "Coding agents";
R.renderLeaderboard();
assert.deepEqual(rowNames(), ["mixed"], "overlapping fields and directions use the same scope");
assert.deepEqual(counts(), ["2", "2", "1", "1"]);
R.renderLeaderboardTop(R.catalogDocumentBoard());
assert.deepEqual(topNames(), ["mixed"], "expanding the top list also keeps the field scope");

R.state.researchField = "other";
R.state.researchSub = "";
R.renderLeaderboard();
assert.deepEqual(R.leaderboardEntries(), []);
assert.deepEqual(counts(), ["0", "0", "0", "0"]);
assert.equal(byId("leaderboard-cards-count").textContent, "0 documents");

R.state.researchField = "all";
R.renderLeaderboard();
assert.deepEqual(rowNames(), ["safety", "mixed", "coding", "unknown-score"], "All research restores every source record");
assert.deepEqual(topNames(), ["safety", "mixed", "coding"]);
assert.deepEqual(counts(), ["3", "3", "4", "3"]);
assert.equal(byId("leaderboard-count").textContent, "4 shown · 4 tracked");
assert.equal(byId("leaderboard-cards-count").textContent, "3 documents");
assert(byId("leaderboard-cards").textContent.includes("coding"));
assert.equal(R.catalogDocumentBoard().entries.length, 4, "scoping never mutates the full catalog board");
console.log("Research adoption scope regression passed");
