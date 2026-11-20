// Issue #1305: the homepage ranks registry records from benchmark-search.json.
// The same queries must return the same records, in the same order, as the
// full catalog does through the same production ranking.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { searchCatalogMatches } from "../site/assets/catalog-search.js";

const [indexPath, searchPath] = process.argv.slice(2);
const source = readFileSync("site/assets/app.js", "utf8");
const start = source.indexOf("function decodeBenchmarkSearch(");
const decodeBenchmarkSearch = new Function(
  `${source.slice(start, source.indexOf("\n}\n", start) + 2)}\nreturn decodeBenchmarkSearch;`,
)();

const full = JSON.parse(readFileSync(indexPath, "utf8")).benchmarks;
const compact = decodeBenchmarkSearch(JSON.parse(readFileSync(searchPath, "utf8")));
assert.equal(compact.length, full.length);

const queries = [
  "mmlu", "swe-bench", "gpt", "math", "code", "agent", "protein structure prediction",
  "humanity's last exam", "terminal-bench", "多模态", "reasoning benchmark", "a", "zzzzq",
  "long context retrieval", "medical", "arc", "gsm8k", "vision language", "opencompass",
];
for (const query of queries) {
  const view = (records) => searchCatalogMatches(records, query)
    .map((match) => `${match.record.slug}:${match.missing.join(",")}`);
  assert.deepEqual(view(compact), view(full), query);
}
console.log(`benchmark-search.json ranks ${queries.length} queries exactly like the full catalog.`);
