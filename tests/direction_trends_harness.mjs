// Print directionTrendRows for records read from stdin, using the production
// function from app.js, so the Python test can compare it with
// direction_trend_rows.
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const constants = source.match(/const DIRECTION_TREND_WEEKS = .*;\nconst DISCOVERY_SOURCE = .*;/)[0];
const { directionTrendRows, discoveryAnchor } = new Function(`${constants}\n${fn("dayNumber")}\n${fn("discoveryAnchor")}\n${fn("directionTrendRows")}\nreturn { directionTrendRows, discoveryAnchor };`)();
const { records, taxonomy, anchor, windows } = JSON.parse(readFileSync(0, "utf8"));
const models = windows.map((days) => directionTrendRows(records, taxonomy, anchor, days));
process.stdout.write(JSON.stringify({ anchor: discoveryAnchor(records), models }));
