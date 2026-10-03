// Executes the dashboard's stale-banner renderer against a fixture shaped
// exactly like radar.json, and prints the resulting banner DOM as JSON for
// the Python test to assert on. This mirrors the briefing harness: source
// assertions alone cannot tell "renders an actions row" from "mentions the
// word Contact", so the renderer is run for real against a minimal DOM.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
// app.js imports its brand-mark resolvers from glyphs.js (issue #261), and
// `new Function` below cannot take an import statement. Inlining the module
// and dropping the import keeps the harness evaluating the real source rather
// than a copy: the same text runs here and in the browser, minus the two lines
// that only differ in how the file is loaded.
const glyphs = readFileSync(join(here, "..", "site", "assets", "glyphs.js"), "utf8").replace(
  /^export \{[\s\S]*?\};$/m,
  "",
);
const research = readFileSync(join(here, "..", "site", "assets", "fields.js"), "utf8")
  .replace(/^export /gm, "") + "\nconst researchFields = fields;\n";
const source =
  research + glyphs +
  readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8").replace(
    /^import \{[\s\S]*?\} from "\.\/glyphs\.js";$/m,
    "",
  );

class StubNode {
  constructor(tag) {
    this.tag = tag;
    this.className = "";
    this.children = [];
    this.attributes = {};
    this._text = "";
    this.hidden = false;
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
  get classList() {
    const node = this;
    const names = () => node.className.split(/\s+/).filter(Boolean);
    return {
      contains: (name) => names().includes(name),
      add(name) {
        if (!names().includes(name)) node.className = [...names(), name].join(" ");
      },
      remove(name) {
        node.className = names().filter((existing) => existing !== name).join(" ");
      },
      toggle(name, force) {
        const has = names().includes(name);
        const want = force === undefined ? !has : Boolean(force);
        const next = names().filter((existing) => existing !== name);
        if (want) next.push(name);
        node.className = next.join(" ");
        return want;
      },
    };
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  addEventListener() {}
  querySelectorAll() {
    return [];
  }
  querySelector() {
    return null;
  }
}

class StubText {
  constructor(value) {
    this.tag = "#text";
    this.children = [];
    this.attributes = {};
    this.className = "";
    this._text = String(value);
  }
  get textContent() {
    return this._text;
  }
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
  querySelectorAll: () => [],
  querySelector: () => null,
};
// pathname included because the app reads the view off it: a location
// without one is not a location any browser would hand you.
globalThis.window = {
  addEventListener: () => {},
  location: { pathname: "/", search: "", hash: "" },
};
globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
};

// Default fetch never resolves, like a reader whose lookup is slow: the banner
// must already be correct with its fallback href while the deep-link upgrade
// is still in flight. `--resolve-failure` swaps in a resolving GitHub response
// for the failed-run lookup only; every other request (the page's own radar.json
// boot fetch included) keeps hanging so the harness stays in control of state.
const RUNS_LOOKUP =
  "https://api.github.com/repos/ktwu01/benchmark-radar/actions/workflows/daily-radar.yml/runs";
if (process.argv.includes("--resolve-failure")) {
  globalThis.fetch = (url) =>
    String(url).startsWith(RUNS_LOOKUP)
      ? Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              workflow_runs: [
                { html_url: "https://github.com/ktwu01/benchmark-radar/actions/runs/32439770574" },
              ],
            }),
        })
      : new Promise(() => {});
} else {
  globalThis.fetch = () => new Promise(() => {});
}

// The export line goes after the source: `state` is a top-level const in
// app.js, so referencing it before the source body would hit its TDZ.
const harness = `${source}\nglobalThis.__render = { renderStaleBanner, setLang, getLang, state };`;
new Function(harness)();

const lang = process.argv[3] && process.argv[3] !== "--resolve-failure" ? process.argv[3] : "";
if (lang) globalThis.__render.setLang(lang);

const fixtureArg = process.argv[2];
const fixturePath =
  fixtureArg && fixtureArg !== "--resolve-failure"
    ? fixtureArg
    : join(here, "fixtures", "stale_radar.json");
globalThis.__render.state.data = JSON.parse(readFileSync(fixturePath, "utf8"));
globalThis.__render.renderStaleBanner();

function walk(node) {
  return {
    tag: node.tag,
    className: node.className || "",
    hidden: Boolean(node.hidden),
    href: node.attributes?.href || "",
    text: node.textContent,
    children: (node.children || []).map(walk),
  };
}

// The deep-link upgrade resolves asynchronously after the banner renders; let
// the microtask queue (and the stubbed fetch) settle before printing.
setTimeout(() => {
  console.log(JSON.stringify(walk(document.getElementById("stale-banner")), null, 2));
}, 20);
