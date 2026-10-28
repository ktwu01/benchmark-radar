// Exercise the actual prompt and share modules, with independent browser states.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const shareSource = readFileSync("site/assets/share-card.js", "utf8");
const key = "benchmark-radar:star-prompt:v1";
let sequence = 0;

class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.listeners = {};
    this.isConnected = false;
  }
  setAttribute(key, value) { this.attrs[key] = value; }
  append(...nodes) {
    for (const node of nodes) { node.isConnected = true; this.children.push(node); }
  }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  remove() { this.removed = true; this.isConnected = false; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  click() { return this.listeners.click?.({ target: this }); }
  find(predicate) {
    if (predicate(this)) return this;
    for (const child of this.children) {
      const match = child.find?.(predicate);
      if (match) return match;
    }
  }
}

async function load({ store = {}, lang = "en", blocked = false, consent = true, failure = null } = {}) {
  const events = [];
  const body = new Node("body");
  const storage = {
    getItem(name) { if (blocked) throw Error("blocked"); return store[name] ?? null; },
    setItem(name, value) { if (blocked) throw Error("blocked"); store[name] = String(value); },
  };
  globalThis.document = {
    body, documentElement: { lang },
    createElement: (tag) => new Node(tag),
    querySelectorAll: () => [],
    querySelector: () => null,
  };
  globalThis.window = {
    localStorage: storage, location: { origin: "https://benchmark-radar.org" },
    ...(consent ? { clarity: (kind, name) => events.push([kind, name]) } : {}),
    ClipboardItem: true,
  };
  globalThis.ClipboardItem = class { constructor(data) { this.data = data; } };
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: {
    clipboard: {
      async write(items) {
        if (failure === "clipboard") throw Error("clipboard denied");
        await Promise.all(Object.values(items[0].data));
      },
      async writeText() { if (failure === "clipboard") throw Error("clipboard denied"); },
    },
  } });
  globalThis.fetch = async () => ({
    ok: failure !== "fetch", status: failure === "fetch" ? 404 : 200,
    blob: async () => new Blob(["card"], { type: "image/png" }),
  });
  const promptUrl = new URL(`../site/assets/star-prompt.js?case=${++sequence}`, import.meta.url).href;
  const { starPrompt } = await import(promptUrl);
  const shareModule = shareSource.replace('"./star-prompt.js"', JSON.stringify(promptUrl));
  const { openBenchmarkShare } = await import(`data:text/javascript;base64,${Buffer.from(shareModule).toString("base64")}`);
  return { starPrompt, openBenchmarkShare, events, store, body };
}

const first = await load();
let closed = 0;
const prompt = first.starPrompt("save", () => { closed += 1; });
assert(prompt);
assert.equal(first.store[key], "save");
const [, link, dismiss] = prompt.children;
assert.equal(link.attrs.href, "https://github.com/ktwu01/benchmark-radar");
assert.equal(link.attrs.rel, "noopener");
assert.deepEqual(first.events, [["event", "star_prompt_shown_save"]]);
link.click();
assert(prompt.removed);
assert.equal(closed, 1);
assert.deepEqual(first.events.at(-1), ["event", "star_prompt_click_save"]);
assert.equal(first.starPrompt("cite"), null);
assert.equal((await load({ store: first.store })).starPrompt("card_download"), null);

const blocked = await load({ blocked: true });
assert(blocked.starPrompt("cite"));
assert.equal(blocked.starPrompt("card_download"), null);
const denied = await load({ consent: false });
assert(denied.starPrompt("card_copy_link"));
assert.deepEqual(denied.events, []);

const triggers = ["subscribe", "cite", "save", "card_copy_image", "card_copy_link", "card_download"];
for (const trigger of triggers) {
  const page = await load({ lang: "zh-CN" });
  const translated = page.starPrompt(trigger);
  assert.match(translated.children[0].textContent, /[\u4e00-\u9fff]/);
  assert.equal(translated.children[1].textContent, "★ 在 GitHub 上点 Star");
  assert.equal(translated.children[2].attrs["aria-label"], "关闭");
  translated.children[2].click();
  assert(translated.removed);
  assert.equal(page.starPrompt("save"), null);
}

const cases = [
  ["Copy image", "card_copy_image"],
  ["Copy link", "card_copy_link"],
  ["Download", "card_download"],
];
for (const [label, trigger] of cases) {
  const page = await load();
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  assert.equal(page.store[key], undefined, "opening Share never spends the prompt budget");
  await page.body.find((node) => node.textContent === label).click();
  assert.equal(page.store[key], trigger);
  assert(page.body.find((node) => node.className === "star-prompt"));
  assert.equal(page.starPrompt("save"), null, "card and app actions share the same module state");
  assert.deepEqual(page.events, [["event", `star_prompt_shown_${trigger}`]]);
}

const earlier = await load();
earlier.starPrompt("subscribe");
earlier.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
await earlier.body.find((node) => node.textContent === "Copy link").click();
assert.equal(earlier.events.length, 1, "an earlier app prompt suppresses the card prompt");
assert(!earlier.body.find((node) => node.className === "star-prompt"));

const left = await load();
let finishCopy;
navigator.clipboard.writeText = () => new Promise((resolve) => { finishCopy = resolve; });
left.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
const copying = left.body.find((node) => node.textContent === "Copy link").click();
left.body.find((node) => node.tag === "dialog").close();
finishCopy();
await copying;
assert.equal(left.store[key], undefined, "a hidden dialog must not consume the prompt");

// A denied clipboard or missing card must leave the budget for a later action.
for (const [label, failure] of [["Copy link", "clipboard"], ["Copy image", "clipboard"], ["Download", "fetch"]]) {
  const page = await load({ failure });
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  const originalError = console.error;
  console.error = () => {};
  try { await page.body.find((node) => node.textContent === label).click(); }
  finally { console.error = originalError; }
  assert.equal(page.store[key], undefined);
  assert.deepEqual(page.events, []);
  assert(page.starPrompt("save"));
}

assert.match(readFileSync("site/assets/app.js", "utf8"), /import \{ starPrompt \} from "\.\/star-prompt.js"/);
console.log("star prompt and card actions harness ok");
