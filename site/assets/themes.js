import { searchCatalogMatches } from "./catalog-search.js";

// These upstream labels describe data quality, not benchmark capabilities.
const QUALITY_LABELS = new Set(["unsupported", "不支持"]);
const COMMON_CATEGORY_LIMIT = 12;
const UNCATEGORIZED = "__uncategorized__";

export function commonCategories(records) {
  const counts = new Map();
  for (const record of records) {
    for (const category of new Set(record.categories)) {
      if (!QUALITY_LABELS.has(category.trim().toLowerCase())) {
        counts.set(category, (counts.get(category) || 0) + 1);
      }
    }
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, COMMON_CATEGORY_LIMIT);
}

export function filterCatalog(records, query, category) {
  // Use the homepage's search over the whole corpus before category filtering,
  // so this page cannot invent different relevance scores or lose rare categories.
  const matches = query.trim() ? searchCatalogMatches(records, query)
    : records.map(record => ({record, missing: []}));
  return matches.filter(({record}) => !category || (category === UNCATEGORIZED
    ? record.categories.length === 0 : record.categories.includes(category)));
}

export function readCatalog(payload) {
  if (payload?.schema_version !== 1 || !Array.isArray(payload.benchmarks)
      || payload.count !== payload.benchmarks.length) throw new Error("Invalid catalog");
  const keys = new Set();
  const slugs = new Set();
  for (const record of payload.benchmarks) {
    if (!["key", "slug", "name", "source"].every(field =>
      typeof record?.[field] === "string" && record[field].trim())
      || !Array.isArray(record.categories)
      || !record.categories.every(value => typeof value === "string" && value.trim())
      || keys.has(record.key) || slugs.has(record.slug)) throw new Error("Invalid record");
    keys.add(record.key);
    slugs.add(record.slug);
  }
  return payload.benchmarks;
}

function cardFor(record) {
  const card = document.createElement("article");
  card.className = "theme-card";
  card.dataset.record = record.key;
  const title = document.createElement("a");
  title.className = "theme-card-title";
  title.href = `/benchmarks/${encodeURIComponent(record.slug)}/`;
  title.textContent = record.name;
  const meta = document.createElement("p");
  meta.className = "theme-card-meta";
  const sources = {llm_stats: "LLM Stats", model_reports: "Model reports",
    claire_radar: "Claire Radar", artificial_analysis: "Artificial Analysis",
    opencompass_hub: "OpenCompass Hub"};
  meta.textContent = `${sources[record.source] || record.source} · ${record.released || "Release date unknown"}`;
  card.append(title, meta);
  if (record.description) {
    const description = document.createElement("p");
    description.className = "theme-card-summary";
    description.textContent = record.description;
    card.append(description);
  }
  return card;
}

async function mount() {
  const query = document.getElementById("theme-query");
  const category = document.getElementById("theme-category");
  const grid = document.getElementById("theme-grid");
  const status = document.getElementById("theme-results");
  const empty = document.getElementById("theme-empty");
  const ledger = document.getElementById("theme-ledger");
  try {
    // Share the homepage's catalog URL and honor the host's HTTP cache policy.
    const response = await fetch("/data/benchmark-index.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const records = readCatalog(await response.json());
    const cards = new Map(records.map(record => [record.key, cardFor(record)]));
    category.append(new Option(`All categories (${records.length})`, ""));
    const menuCategories = commonCategories(records);
    for (const [name, count] of menuCategories) {
      category.append(new Option(`${name} (${count})`, name));
    }
    const uncategorized = records.filter(record => !record.categories.length).length;
    if (uncategorized) category.append(new Option(`Uncategorized (${uncategorized})`, UNCATEGORIZED));
    const sources = new Set(records.map(record => record.source));
    const allCategories = new Set(records.flatMap(record => record.categories));
    const browseCategories = [...allCategories]
      .filter(name => !QUALITY_LABELS.has(name.trim().toLowerCase())).length;
    ledger.textContent = `${records.length} benchmark records across ${sources.size} sources. `
      + `${uncategorized} uncategorized. No records omitted. Category counts may overlap. `
      + `${menuCategories.length} of ${browseCategories} browsing categories shown; `
      + `${browseCategories - menuCategories.length} additional categories remain searchable. `
      + `${allCategories.size - browseCategories} data-quality labels excluded from the menu. `
      + "Unsupported / 不支持 are data-quality labels, so they are not menu categories.";
    function render() {
      const matches = filterCatalog(records, query.value, category.value);
      grid.replaceChildren(...matches.map(({record}) => cards.get(record.key)));
      let text = `Showing ${matches.length} of ${records.length} benchmark records`;
      if (query.value.trim()) {
        const full = matches.filter(match => !match.missing.length).length;
        text += ` · ${full} match every word · ${matches.length - full} share some words`;
      }
      status.textContent = text;
      empty.hidden = matches.length > 0;
    }
    query.disabled = category.disabled = false;
    query.addEventListener("input", render);
    category.addEventListener("change", render);
    render();
    grid.removeAttribute("aria-busy");
  } catch (error) {
    grid.replaceChildren();
    grid.removeAttribute("aria-busy");
    status.textContent = "The full benchmark catalog could not be loaded. Reload this page to retry.";
    status.setAttribute("role", "alert");
    ledger.textContent = "Catalog unavailable; coverage could not be verified.";
    console.error("Category browser:", error);
  }
}

if (typeof document !== "undefined") mount();
