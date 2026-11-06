// Execute the real saturationIndexFact helper from app.js so the test proves
// the dashboard detail shows the study's stated index, as stated, rather
// than matching implementation source strings.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8");
const start = source.indexOf("function saturationIndexFact");
const end = source.indexOf("\n}\n", start);
if (start < 0 || end < 0) throw new Error("saturationIndexFact not found");

globalThis.t = (value) => value;
const harness = `${source.slice(start, end + 3)}\nglobalThis.__saturationIndexFact = saturationIndexFact;`;
new Function(harness)();

const stated = globalThis.__saturationIndexFact({
  source_metadata: {
    benchmark_saturation: {
      saturation_index: "0.916397111",
      saturation_index_interpreted: "Very high",
    },
  },
});
const indexOnly = globalThis.__saturationIndexFact({
  source_metadata: { benchmark_saturation: { saturation_index: "0.5" } },
});
const unannotated = globalThis.__saturationIndexFact({ source_metadata: {} });
const noMetadata = globalThis.__saturationIndexFact({});

console.log(JSON.stringify({ stated, indexOnly, unannotated, noMetadata }));
