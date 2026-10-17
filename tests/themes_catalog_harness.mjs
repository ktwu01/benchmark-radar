import {readFileSync} from "node:fs";
import {commonCategories, filterCatalog, readCatalog} from "../site/assets/themes.js";
import {searchCatalogMatches} from "../site/assets/catalog-search.js";
const {payload, queries = [], category = "", bootError = false, httpStatus = 200} = JSON.parse(readFileSync(0, "utf8"));
if (bootError) {
  const nodes = new Map();
  for (const id of ["theme-query", "theme-category", "theme-grid", "theme-results", "theme-empty", "theme-ledger"]) {
    nodes.set(id, {disabled: true, textContent: "Loading…", children: ["old content"],
      replaceChildren(...children) {this.children = children;},
      removeAttribute() {}, setAttribute(name, value) {this[name] = value;}});
  }
  globalThis.document = {getElementById: id => nodes.get(id)};
  globalThis.fetch = async () => ({ok: httpStatus === 200, status: httpStatus,
    json: async () => payload});
  await import("../site/assets/themes.js?bootstrap-check");
  await new Promise(setImmediate);
  console.log(JSON.stringify({status: nodes.get("theme-results").textContent,
    role: nodes.get("theme-results").role, ledger: nodes.get("theme-ledger").textContent,
    cards: nodes.get("theme-grid").children.length,
    disabled: nodes.get("theme-query").disabled}));
} else try {
  const records = readCatalog(payload);
  console.log(JSON.stringify({
    keys: filterCatalog(records, "", "").map(({record}) => record.key),
    categories: commonCategories(records),
    queries: queries.map(query => ({
      query,
      actual: filterCatalog(records, query, category).map(({record}) => record.key),
      homepage: searchCatalogMatches(records, query).filter(({record}) => !category
        || record.categories.includes(category)).map(({record}) => record.key),
    })),
  }));
} catch (error) {
  console.log(JSON.stringify({error: error.message}));
}
