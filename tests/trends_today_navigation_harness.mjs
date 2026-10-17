import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8");

class StubNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = { setProperty() {} };
    this.classList = { toggle() {}, add() {}, remove() {} };
    this.hidden = false;
    this.open = false;
    this.checked = false;
    this.value = "";
    this._text = "";
    this.listeners = {};
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return this.children.length ? this.children.map((child) => child.textContent || "").join("") : this._text;
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
  }
  removeAttribute(key) {
    delete this.attributes[key];
  }
  append(...children) {
    this.children.push(...children.filter(Boolean));
  }
  replaceChildren(...children) {
    this.children = children.filter(Boolean);
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  async dispatch(type, event = {}) {
    for (const listener of this.listeners[type] || []) await listener(event);
  }
  querySelectorAll() {
    return [];
  }
  querySelector() {
    return null;
  }
  matches() {
    return false;
  }
}

const registry = new Map();
const node = (tag = "div") => {
  return new StubNode(tag);
};
const getNode = (id) => {
  if (!registry.has(id)) registry.set(id, node("div"));
  return registry.get(id);
};
const todayTab = node("button");
todayTab.dataset.view = "today";

function updateLocation(_state, _title, url) {
  const parsed = new URL(url, "https://benchmark-radar.org");
  Object.assign(window.location, {
    pathname: parsed.pathname, search: parsed.search, hash: parsed.hash,
  });
}

globalThis.document = {
  createElement: node,
  createElementNS: (_namespace, tag) => node(tag),
  createTextNode: (value) => ({ textContent: String(value) }),
  getElementById: getNode,
  querySelectorAll: (selector) => selector === "[data-view]" ? [todayTab] : [],
  querySelector: () => null,
  addEventListener() {},
};
globalThis.window = {
  history: { pushState: updateLocation, replaceState: updateLocation },
  location: { pathname: "/trends/", search: "", hash: "" },
  addEventListener() {},
  scrollTo() {},
};
globalThis.byId = getNode;
globalThis.getLang = () => "en";
globalThis.t = (value) => value;
globalThis.formatDate = (value) => String(value);
globalThis.countMapText = (value) => JSON.stringify(value || {});
globalThis.healthSummary = () => "";
globalThis.sourceMixCell = () => node("span");
globalThis.zeroItemSources = () => [];
globalThis.renderSourceGapNote = () => {};
globalThis.hideDayTooltip = () => {};
globalThis.showDayTooltip = () => {};
globalThis.toggleLang = () => {};

let releaseFullResponse;
globalThis.fetch = (path) => {
  // Trends also reads the catalog index for its research-direction table
  // (#420); an empty catalog keeps that table out of this navigation test.
  if (path === "/data/benchmark-index.json") {
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ benchmarks: [] }) });
  }
  if (path !== "/data/radar.json") throw new Error(`Unexpected fetch path: ${path}`);
  return new Promise((resolve) => {
    releaseFullResponse = () => resolve({
      ok: true,
      status: 200,
      json: async () => ({
        schema_version: 2,
        latest_date: "2026-09-05",
        days: [
          { date: "2026-07-23", evidence_items: [], attention: { observations: [] } },
          { date: "2026-08-20", evidence_items: [], attention: { observations: [] } },
          { date: "2026-09-05", evidence_items: [], attention: { observations: [] } },
        ],
        facets: { dates: ["2026-07-23", "2026-08-20", "2026-09-05"], categories: [] },
        corpus: { entities: [], edges: [], aggregates: {} },
      }),
    });
  });
};

const start = source.indexOf("const state = {");
const end = source.indexOf("\nasync function initialize()", start);
if (start < 0 || end < 0) throw new Error("Dashboard logic not found in app.js");
const dashboardSource = source.slice(start, end).replace(
  "function renderToday(",
  "function renderToday_unused(",
);
const harness = `${dashboardSource}
globalThis.renderToday = () => {
  state.todayRenderedDate = state.todayDate;
  writeUrl();
};
globalThis.__harness = {
  state,
  renderTrends,
  ensureFullData,
  bindEvents,
};
`;
new Function(harness)();

const { state, renderTrends, ensureFullData, bindEvents } = globalThis.__harness;
// Use the production event handlers so the test also checks which user
// actions invalidate a pending selection, without manually advancing a token.
bindEvents();
const initialData = {
  schema_version: 2,
  latest_date: "2026-09-05",
  snapshot_count: 3,
  days: ["2026-07-23", "2026-08-20", "2026-09-05"].map((date) => (
    {
      date,
      evidence_count: 1,
      category_counts: {},
      category_counts_released: {},
      event_kind_counts: {},
      attention: { active_count: 0, new_count: 0, observations: [] },
      category_trends: {},
      ingest_health: [],
      selection: {},
    }
  )),
  facets: { dates: ["2026-07-23", "2026-08-20", "2026-09-05"], categories: [] },
  corpus: { aggregates: {} },
};
const scenarios = [];
for (const entry of ["column", "table"]) {
  for (const action of ["none", "today", "2026-08-20", "30d", "60d", "all", "search", "clear"]) {
    Object.assign(state, {
      data: structuredClone(initialData), view: "trends", todayDate: "2026-09-05",
      todayRenderedDate: "2026-09-05", fullDataLoaded: false, trendsDataLoaded: true,
      fullDataPromise: null, observations: null, q: "",
    });
    releaseFullResponse = null;
    renderTrends();
    const trigger = entry === "column"
      ? getNode("trend-chart").children[0]
      : getNode("trend-table").children.at(-1).children[0].children[0];
    await trigger.dispatch("click", { preventDefault() {} });
    if (!releaseFullResponse) throw new Error("Historical click did not start the full-data request");

    let selection;
    if (action === "today") {
      selection = todayTab.dispatch("click");
    } else if (action === "search") {
      const search = getNode("search-filter");
      search.value = "benchmark";
      selection = getNode("filters").dispatch("input", { target: search });
    } else if (action === "clear") {
      selection = getNode("clear-filters").dispatch("click");
    } else if (action !== "none") {
      const datePicker = getNode("today-date");
      datePicker.value = action;
      selection = datePicker.dispatch("change", { target: datePicker });
    }
    const selectedBeforeResponse = state.todayDate;
    releaseFullResponse();
    await Promise.all([selection, ensureFullData()]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    scenarios.push({
      entry, action, selectedBeforeResponse, dateAfterResponse: state.todayDate,
      urlAfterResponse: window.location.pathname + window.location.search,
    });
  }
}
console.log(JSON.stringify({ scenarios }));
