// Executes the dashboard's daily Q&A renderer against a fixture shaped exactly
// like `questions.py` writes into a snapshot, and prints the resulting text and
// link targets as JSON for the Python test to assert on.
//
// Source assertions alone cannot tell "the function renders the answer" apart
// from "the function mentions the word answer", and this Q&A is the one part of
// the page whose whole value is that every number on it is traceable. So the
// renderer is run for real against a minimal DOM rather than grepped.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8");

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
globalThis.window = { addEventListener: () => {}, location: { search: "", hash: "" } };
// Bootstrap fetches radar.json on load. This harness renders a fixture instead,
// so the request is stubbed to a never-settling promise: letting it reject would
// print an unhandled rejection that has nothing to do with what is under test.
globalThis.fetch = () => new Promise(() => {});

// The module runs bootstrapping code on load. Function declarations hoist, so
// the export is placed at the TOP of the harness: it then captures the render
// helpers before any bootstrap statement can throw on a browser-only API.
const harness =
  `globalThis.__render = { renderDailyQuestions, formatStatValue, setLang, getLang };\n${source}`;
// A bootstrap failure is NOT swallowed. The stubs above cover every browser API
// app.js touches on load, so a throw here means the real script would break in a
// browser too, and a renderer test that still passed would be hiding it.
new Function(harness)();

// A caller may pass "zh" as a third argument to exercise the Chinese rendering
// (issue #231); default stays English.
const lang = process.argv[3];
if (lang) globalThis.__render.setLang(lang);

// A caller may pass a different fixture to exercise an absent or stale Q&A.
const fixturePath = process.argv[2] || join(here, "fixtures", "daily_questions.json");
const day = JSON.parse(readFileSync(fixturePath, "utf8"));
globalThis.__render.renderDailyQuestions(day);

function walk(node) {
  return {
    tag: node.tag,
    className: node.className || "",
    href: node.attributes?.href || "",
    attributes: node.attributes || {},
    text: node.textContent,
    children: (node.children || []).map(walk),
  };
}

console.log(JSON.stringify(walk(document.getElementById("daily-questions-body")), null, 2));
