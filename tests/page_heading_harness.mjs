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
// Each utility sheet: a dialog and the title its renderer writes as an h2.
const sheets = {};
for (const page of ["cli", "cite", "rubric"]) {
  const holder = { heading: heading("h2", { class: `detail-title ${page}-title`, id: `${page}-title` }, page) };
  holder.heading.section = holder;
  sheets[page] = { dialog: { open: false }, holder };
}
globalThis.document = {
  querySelectorAll: (selector) => (selector === ".view" ? sections : []),
  createElement: (tag) => new El(tag),
  getElementById(id) {
    const page = id.replace(/-(dialog|title)$/, "");
    if (!sheets[page]) return null;
    return id.endsWith("-dialog") ? sheets[page].dialog : sheets[page].holder.heading;
  },
};
const utilityTitles = source.match(/const UTILITY_TITLES = .*;/)[0];
const { syncPageHeading } = new Function(
  `const byId = (id) => document.getElementById(id);\n${utilityTitles}\n` +
    `${["viewHeading", "retagHeading", "syncPageHeading"].map(fn).join("\n")}\nreturn { syncPageHeading };`,
)();

function h1s() {
  return [
    ...sections.filter((s) => s.heading.tagName === "H1").map((s) => s.id),
    ...Object.entries(sheets).filter(([, s]) => s.holder.heading.tagName === "H1").map(([page]) => `${page}-title`),
  ];
}

function open(id) {
  for (const s of sections) s.hidden = s.id !== id;
  syncPageHeading();
  assert.deepEqual(h1s(), [id]);
}

function openSheet(page) {
  for (const [name, sheet] of Object.entries(sheets)) sheet.dialog.open = name === page;
  syncPageHeading();
  assert.deepEqual(h1s(), page ? [`${page}-title`] : h1s().slice(0, 1));
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

// /cli/, /cite/, /rubric/: the open sheet's title holds the h1, then hands it back.
openSheet("cli");
assert.equal(sheets.cli.holder.heading.getAttribute("class"), "detail-title cli-title");
openSheet("cite");
assert.equal(sheets.cli.holder.heading.tagName, "H2");
openSheet("rubric");
openSheet(null);
assert.deepEqual(h1s(), ["today-view"]);
open("library-view");
openSheet("cli");
openSheet(null);
assert.deepEqual(h1s(), ["library-view"]);
console.log("page heading harness: ok");
