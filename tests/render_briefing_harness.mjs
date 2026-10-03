// Executes the dashboard's daily-briefing renderer against a fixture shaped
// exactly like `briefing.py` writes into a snapshot, and prints the resulting
// DOM tree as JSON for the Python test to assert on. This mirrors the Q&A
// harness: source assertions alone cannot tell "renders insight blocks" from
// "mentions the word insight", so the renderer is run for real against a
// minimal DOM rather than grepped.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
// app.js imports its brand-mark resolvers from glyphs.js (issue #261), and
// `new Function` below cannot take an import statement. Inlining the module
// and dropping the import keeps the harness evaluating the real source rather
// than a copy: the same text runs here and in the browser, minus the two lines
// that only differ in how the file is loaded.
const glyphs = readFileSync(join(here, "..", "site", "assets", "glyphs.js"), "utf8")
  .replace(/^export \{[\s\S]*?\};$/m, "");
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
  setAttribute(key, value) {
    this.attributes[key] = String(value);
  }
  append(child) {
    this.children.push(child);
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
  getContext() {
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
globalThis.fetch = () => new Promise(() => {});

const harness =
  `globalThis.__render = { renderDailyBriefing, setLang, getLang };\n${source}`;
new Function(harness)();

// A caller may pass "zh" as a third argument to exercise the Chinese rendering
// (issue #231); default stays English.
const lang = process.argv[3];
if (lang) globalThis.__render.setLang(lang);

const fixturePath = process.argv[2] || join(here, "fixtures", "daily_briefing.json");
const day = JSON.parse(readFileSync(fixturePath, "utf8"));
globalThis.__render.renderDailyBriefing(day);

function walk(node) {
  return {
    tag: node.tag,
    className: node.className || "",
    href: node.attributes?.href || "",
    text: node.textContent,
    children: (node.children || []).map(walk),
  };
}

console.log(JSON.stringify(walk(document.getElementById("daily-briefing-body")), null, 2));