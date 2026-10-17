// Execute the Models view's production document functions without a browser.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const constants = [
  source.match(/const MODEL_DOCUMENT_TYPES = .*;/)[0],
  source.match(/const MODEL_UNRECORDED = .*;/)[0],
].join("\n");
const names = ["modelDocuments", "modelFirstMentions", "modelIdentity", "preferredModelName", "modelCatalog", "modelLabCounts"];
const bench = (id) => ({ benchmark_id: id, name: id.toUpperCase() });
const doc = (id, organization, published, benchmarks, type = "model_card") => ({
  id, organization, published, document_type: type, benchmarks: benchmarks.map(bench),
});
const state = {
  catalogDocuments: {
    documents: [
      doc("a1", "Acme", "2025-01-01", ["mmlu", "aime"]),
      doc("a2", "Acme", "2026-01-01", ["aime", "swe"]),
      doc("b1", "Beta", "2026-02-01", ["mmlu"]),
      doc("x", "Acme", "2026-03-01", ["leader"], "benchmark_leaderboard"),
      doc("u", "Acme", null, ["hle"]),
    ],
  },
};
const models = new Function("state", `${constants}\n${names.map(fn).join("\n")}\nreturn {${names.join(",")}};`)(state);

// Leaderboard pages are not model documents; newest first, undated last.
const documents = models.modelDocuments();
assert.deepEqual(documents.map((d) => d.id), ["b1", "a2", "a1", "u"]);

const firsts = models.modelFirstMentions(documents);
// A lab's first document has nothing earlier to compare with.
assert.deepEqual([...firsts.get("a1")], []);
// New to the lab, not to the corpus: Beta's first MMLU is not "new" because it
// is Beta's first document, and Acme's second card marks only SWE.
assert.deepEqual([...firsts.get("a2")], ["swe"]);
assert.deepEqual([...firsts.get("b1")], []);
// An undated document never claims a first.
assert.deepEqual([...firsts.get("u")], []);

// The page's population is every scored model in the catalog, from every
// source; the lab comes from the registry by exact name, never guessed.
const records = [
  { key: "r1", source: "llm_stats", scored_models: [{ name: "Acme-1", date: "2026-01-01" }, { name: "Mystery", date: "2026-03-01" }] },
  { key: "r2", source: "artificial_analysis", scored_models: [{ name: "Acme-1", date: "2026-02-01" }] },
  { key: "r3", source: "claire_radar" },
];
// One display name under two labs keeps both identities: a score names only
// the model, so it is listed under each lab and counted once overall.
const registry = { models: [
  { model: "Acme-1", organization: "Acme" },
  { model: "Acme-1", organization: "Acme Labs" },
] };
const catalog = models.modelCatalog(records, registry);
assert.equal(catalog.scoredRecords, 2);
assert.deepEqual(catalog.models.map((model) => [model.name, model.organizations, model.records.length, model.latest]), [
  ["Mystery", ["__unrecorded__"], 1, "2026-03-01"],
  ["Acme-1", ["Acme", "Acme Labs"], 2, "2026-02-01"],
]);
assert.deepEqual([...catalog.models[1].sources].sort(), ["artificial_analysis", "llm_stats"]);
// Unrecorded models stay listed, after every named lab.
assert.deepEqual(models.modelLabCounts(catalog.models), [["Acme", 1], ["Acme Labs", 1], ["__unrecorded__", 1]]);
// Case-only spellings are one model, named as the registry names it, and a
// record reported under both spellings counts once.
const spelled = models.modelCatalog([
  { key: "r1", source: "llm_stats", scored_models: [{ name: "MiniMax M1 40K", date: "2026-01-01" }] },
  { key: "r1", source: "llm_stats", scored_models: [{ name: "MiniMax M1 40k", date: "2026-01-02" }] },
  { key: "r2", source: "llm_stats", scored_models: [{ name: "MiniMax M1 40k", date: "2026-01-03" }] },
], { models: [{ model: "MiniMax M1 40K", organization: "MiniMax" }] });
assert.deepEqual(spelled.models.map((model) => [model.name, model.organizations, model.records.length]), [
  ["MiniMax M1 40K", ["MiniMax"], 2],
]);
console.log("Models documents, first mentions, scored-model catalog and labs passed.");
