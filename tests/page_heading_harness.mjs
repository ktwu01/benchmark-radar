// Run app.js's production heading sync against a small fake DOM: switching
// views without a reload must leave exactly one h1, in the open view (#945).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}

class El {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.attributes = [];
    this.childNodes = [];
    this.section = null;
  }
  setAttribute(name, value) {
    const found = this.attributes.find((attr) => attr.name === name);
    if (found) found.value = value;
    else this.attributes.push({ name, value });
  }
  getAttribute(name) {
    return this.attributes.find((attr) => attr.name === name)?.value ?? null;
  }
  append(...nodes) {
    this.childNodes.push(...nodes);
  }
  replaceWith(node) {
    node.section = this.section;
    this.section.heading = node;
  }
}

function heading(tag, attrs, text) {
  const node = new El(tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  node.append(text);
  return node;
}

function section(id, node, hidden) {
  const result = {
    id,
    hidden,
    heading: node,
    querySelector(selector) {
      const h = this.heading;
      if (selector.startsWith(":scope")) {
        return h.getAttribute("class") === "visually-hidden" ? h : null;
      }
      return selector === `#${h.getAttribute("id")}` ? h : null;
    },
  };
  node.section = result;
  return result;
}

const sections = [
  section("today-view", heading("h1", { class: "visually-hidden", "data-i18n": "Search" }, "Search"), false),
  section("library-view", heading("h2", { id: "library-heading", class: "library-heading view-title" }, "Library"), true),
  section("saturation-view", heading("h2", { id: "saturation-heading", class: "view-title" }, "Saturation"), true),
  section("map-view", heading("h2", { id: "map-heading", class: "view-title" }, "What we found"), true),
];
globalThis.document = {
  querySelectorAll: (selector) => (selector === ".view" ? sections : []),
  createElement: (tag) => new El(tag),
};
const { syncPageHeading } = new Function(
  `${["viewHeading", "retagHeading", "syncPageHeading"].map(fn).join("\n")}\nreturn { syncPageHeading };`,
)();

function open(id) {
  for (const s of sections) s.hidden = s.id !== id;
  syncPageHeading();
  const h1s = sections.filter((s) => s.heading.tagName === "H1");
  assert.deepEqual(h1s.map((s) => s.id), [id]);
}

open("library-view");
const library = sections[1].heading;
assert.equal(library.getAttribute("id"), "library-heading");
assert.equal(library.getAttribute("class"), "library-heading view-title");
assert.deepEqual(library.childNodes, ["Library"]);
assert.equal(sections[0].heading.tagName, "H2");
assert.equal(sections[0].heading.getAttribute("class"), "visually-hidden");

open("map-view");
open("saturation-view");
open("today-view");
assert.deepEqual(sections[0].heading.childNodes, ["Search"]);
console.log("page heading harness: ok");
