// Executes the latest-releases renderer (issue #530) against the fixture the
// seed tests share, on a minimal DOM, and prints what it drew as JSON: the
// rows with their disclosure bodies, the method note, the empty state and its
// way out, the loading, failed and absent-window messages, and which rows stay
// open across a redraw. The Python test compares the rows and the note with
// the seeds app_seeds.py writes, so the two can never disagree silently.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
// app.js imports its brand-mark resolvers from glyphs.js; `new Function`
// cannot take an import statement, so the module is inlined (as the other
// render harnesses do) and the real source runs otherwise unchanged.
const glyphs = readFileSync(join(here, "..", "site", "assets", "glyphs.js"), "utf8")
  .replace(/^export \{[\s\S]*?\};$/m, "");
const source =
  glyphs +
  readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8").replace(
    /^import \{[\s\S]*?\} from "\.\/glyphs\.js";$/m,
    "",
  );

const allNodes = [];

class StubNode {
  constructor(tag) {
    this.tag = tag;
    this.className = "";
    this.children = [];
    this.attributes = {};
    this._text = "";
    this.hidden = false;
    allNodes.push(this);
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return this.children.length
      ? this.children.map((child) => child.textContent).join("")
      : this._text;
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
  }
  getAttribute(key) {
    return key in this.attributes ? this.attributes[key] : null;
  }
  hasAttribute(key) {
    return key in this.attributes;
  }
  removeAttribute(key) {
    delete this.attributes[key];
  }
  get open() {
    return "open" in this.attributes;
  }
  set open(value) {
    if (value) this.attributes.open = "";
    else delete this.attributes.open;
  }
  get dataset() {
    const out = {};
    for (const [key, value] of Object.entries(this.attributes)) {
      if (key.startsWith("data-")) {
        out[key.slice(5).replace(/-(\w)/g, (_m, c) => c.toUpperCase())] = value;
      }
    }
    return out;
  }
  append(child) {
    this.children.push(child);
  }
  replaceChildren(...children) {
    this.children = children;
    this._text = "";
  }
  addEventListener() {}
  descendants() {
    return this.children.flatMap((child) =>
      child instanceof StubNode ? [child, ...child.descendants()] : [],
    );
  }
  querySelectorAll(selector) {
    return this.descendants().filter((node) => matches(node, selector));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  getContext() {
    return null;
  }
}

class StubText {
  constructor(value) {
    this.tag = "#text";
    this.children = [];
    this.attributes = {};
    this._text = String(value);
  }
  get textContent() {
    return this._text;
  }
}

// The selectors the renderer uses: a tag, an attribute, or both.
function matches(node, selector) {
  const parsed = selector.match(/^([a-z]*)(?:\[([\w-]+)\])?$/);
  if (!parsed) return false;
  const [, tag, attribute] = parsed;
  if (tag && node.tag !== tag) return false;
  if (attribute && !(attribute in node.attributes)) return false;
  return Boolean(tag || attribute);
}

const registry = new Map();
globalThis.document = {
  createElement: (tag) => new StubNode(tag),
  createElementNS: (_ns, tag) => new StubNode(tag),
  createTextNode: (value) => new StubText(value),
  getElementById: (id) => {
    if (!registry.has(id)) registry.set(id, new StubNode("div"));
    return registry.get(id);
  },
  addEventListener: () => {},
  querySelectorAll: (selector) => allNodes.filter((node) => matches(node, selector)),
  querySelector: () => null,
};
globalThis.window = {
  addEventListener: () => {},
  location: { origin: "https://benchmark-radar.org", pathname: "/", search: "", hash: "" },
  history: { state: null, pushState() {}, replaceState() {} },
  matchMedia: () => ({ matches: false, addEventListener() {} }),
};
const fetchCalls = [];
let fetchBehaviour = () => new Promise(() => {});
globalThis.fetch = (path) => {
  fetchCalls.push(String(path));
  return fetchBehaviour(path);
};
const errors = [];
console.error = (error) => errors.push(String(error?.message || error));

// The window and mode controls the page ships; the renderer syncs their
// pressed state through document.querySelectorAll.
function control(attribute, value, pressed) {
  const button = document.createElement("button");
  button.setAttribute(attribute, value);
  button.setAttribute("aria-pressed", String(pressed));
  return button;
}
const windowControls = ["7d", "30d", "90d"].map((key) => control("data-lwindow", key, key === "30d"));
const modeControls = ["latest", "adoption"].map((key) => control("data-lmode", key, key === "latest"));

// Bootstrapping runs on load and stalls on the never-settling fetch above.
// The export follows the source so `const state` is initialised by then.
new Function(
  `${source}\nglobalThis.__render = { state, renderLatestReleases, syncLeaderboardMode, stateNeedsFullData, setLang };`,
)();
const R = globalThis.__render;

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}
// Serialized the way app_seeds.py writes markup: class first, then the
// attributes in the order element() set them, text escaped like html.escape.
function html(node) {
  if (node.tag === "#text") return esc(node._text);
  const attrs = node.className ? [` class="${esc(node.className)}"`] : [];
  for (const [key, value] of Object.entries(node.attributes)) attrs.push(` ${key}="${esc(value)}"`);
  const inner = node.children.length ? node.children.map(html).join("") : esc(node._text);
  return `<${node.tag}${attrs.join("")}>${inner}</${node.tag}>`;
}
const inner = (node) => node.children.map(html).join("") || esc(node._text);
const byId = (id) => document.getElementById(id);

function snapshot() {
  return {
    list: inner(byId("latest-releases-list")),
    info: inner(byId("latest-releases-info")),
    empty: inner(byId("latest-releases-empty")),
    emptyHidden: byId("latest-releases-empty").hidden,
    note: byId("latest-releases-note").textContent,
    window: byId("latest-releases-window").textContent,
    pressedWindows: windowControls.filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.dataset.lwindow),
    pressedModes: modeControls.filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.dataset.lmode),
    latestHidden: byId("latest-releases").hidden,
    adoptionHidden: byId("leaderboard-adoption").hidden,
    fetchCalls: fetchCalls.splice(0),
  };
}
const openRows = () =>
  byId("latest-releases-list").querySelectorAll("details[open]").map((d) => d.dataset.artifact);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const payload = JSON.parse(readFileSync(process.argv[2], "utf8"));
const state = R.state;
state.view = "leaderboard";
state.lmode = "latest";
state.lwindow = "";
state.fullDataLoaded = false;
state.data = { schema_version: 2, days: [{}], latest_releases_leaderboard: payload };
const out = {};

R.syncLeaderboardMode();
R.renderLatestReleases();
out.default = snapshot();

// Open the first row, redraw, and the same row is still open.
byId("latest-releases-list").children[0].children[0].open = true;
out.openBefore = openRows();
R.renderLatestReleases();
out.openAfter = openRows();

state.lmode = "adoption";
R.syncLeaderboardMode();
out.adoption = { latestHidden: byId("latest-releases").hidden, adoptionHidden: byId("leaderboard-adoption").hidden, pressedModes: snapshot().pressedModes };
state.lmode = "latest";
R.syncLeaderboardMode();

state.lwindow = "7d";
R.renderLatestReleases();
out.empty7d = snapshot();

// A window the bootstrap did not carry: the corpus is fetched; when that
// fails the reader is told, when it has loaded without the window too.
out.needsFullData = {};
state.lwindow = "90d";
out.needsFullData.missingWindow = R.stateNeedsFullData();
state.lmode = "adoption";
out.needsFullData.adoption = R.stateNeedsFullData();
state.lmode = "latest";
state.lwindow = "30d";
out.needsFullData.loadedWindow = R.stateNeedsFullData();
state.lwindow = "90d";
state.view = "today";
out.needsFullData.otherView = R.stateNeedsFullData();
state.view = "leaderboard";
state.fullDataLoaded = true;
out.needsFullData.fullLoaded = R.stateNeedsFullData();
state.fullDataLoaded = false;

fetchBehaviour = () => Promise.reject(new Error("HTTP 404"));
R.renderLatestReleases();
out.failed90d = { ...snapshot(), errorsBefore: errors.length };
await tick();
await tick();
out.failed90d.after = snapshot().empty;
out.failed90d.errors = errors.splice(0);

state.fullDataLoaded = true;
R.renderLatestReleases();
out.missing90d = snapshot();
state.fullDataLoaded = false;

fetchBehaviour = () => new Promise(() => {});
R.renderLatestReleases();
out.loading90d = snapshot();
await tick();
out.loading90d.after = snapshot().empty;

// Adoption mode reads no release window, and stateNeedsFullData skips the
// corpus for it, so the renderer must not fetch it either to fill a section
// syncLeaderboardMode has hidden.
state.lmode = "adoption";
state.lwindow = "90d";
state.fullDataLoaded = false;
// The previous scenario left a never-settling corpus request in flight, and
// ensureFullData dedupes on it. Clearing it is what makes a fetch here
// observable, so this probe fails when the guard is removed.
state.fullDataPromise = null;
fetchBehaviour = () => new Promise(() => {});
R.syncLeaderboardMode();
snapshot();
R.renderLatestReleases();
out.adoption90d = { ...snapshot(), needsFullData: R.stateNeedsFullData() };
state.lmode = "latest";
R.syncLeaderboardMode();

state.lwindow = "";
R.setLang("zh");
R.renderLatestReleases();
out.zh = snapshot();
R.setLang("en");

// The bootstrap trims a window the engine did not publish to an empty stub
// (snapshots.py): no bounds, so no method note, and the empty state's way out.
payload.windows["90d"] = {};
state.lwindow = "90d";
R.renderLatestReleases();
out.stub90d = snapshot();

console.log(JSON.stringify(out));
