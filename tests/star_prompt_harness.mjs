// Exercise the actual prompt and share modules, with independent browser states.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const shareSource = readFileSync("site/assets/share-card.js", "utf8");
const key = "benchmark-radar:star-prompt:v1";
let sequence = 0;
const drawnCardStub = `data:text/javascript,${encodeURIComponent(
  'export const cardFacts = () => ({}); export const cardBlob = async () => new Blob(["card"], { type: "image/png" });',
)}`;

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
  const shareModule = shareSource.replace('"./star-prompt.js"', JSON.stringify(promptUrl))
    .replace('"./share-caption.js"', JSON.stringify(new URL("../site/assets/share-caption.js", import.meta.url).href))
    // The canvas drawing needs a browser; a card drawn on demand is a blob here.
    .replace('"./radar-card.js"', JSON.stringify(drawnCardStub));
  const shares = await import(`data:text/javascript;base64,${Buffer.from(shareModule).toString("base64")}`);
  return { starPrompt, ...shares, events, store, body };
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
  ["Copy benchmark link", "card_copy_link"],
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
await earlier.body.find((node) => node.textContent === "Copy benchmark link").click();
assert.equal(earlier.events.length, 1, "an earlier app prompt suppresses the card prompt");
assert(!earlier.body.find((node) => node.className === "star-prompt"));

const left = await load();
let finishCopy;
navigator.clipboard.writeText = () => new Promise((resolve) => { finishCopy = resolve; });
left.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
const copying = left.body.find((node) => node.textContent === "Copy benchmark link").click();
left.body.find((node) => node.tag === "dialog").close();
finishCopy();
await copying;
assert.equal(left.store[key], undefined, "a hidden dialog must not consume the prompt");

// A denied clipboard or missing card must leave the budget for a later action.
for (const [label, failure] of [["Copy benchmark link", "clipboard"], ["Copy image", "clipboard"], ["Download", "fetch"]]) {
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

// #1068: X's post link cannot attach a file, so Post on X copies the card on the
// same click and says to paste it; the link itself still opens X.
const hintOf = (page) => page.body.find((node) => node.className === "share-card-hint");
const noteOf = (page) => page.body.find((node) => node.className === "share-card-note");
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
{
  const page = await load();
  let written = null;
  navigator.clipboard.write = async (items) => {
    written = await Promise.all(Object.values(items[0].data));
  };
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  const x = page.body.find((node) => node.textContent === "Post on X ↗");
  assert(x, "one plain main action");
  assert.equal(x.tag, "a");
  assert.match(x.attrs.href, /^https:\/\/x\.com\/intent\/post\?/);
  assert.equal(x.attrs.target, "_blank");
  assert.equal(noteOf(page).textContent, "Copies the card image and opens X in a new window.",
    "the note says what the click does before X's tab covers the dialog");
  assert(hintOf(page).hidden, "the hint waits for the click");
  x.click();
  await tick();
  assert(written && written[0] instanceof Blob, "the card image reaches the clipboard");
  assert(noteOf(page).hidden);
  assert.equal(hintOf(page).hidden, false);
  assert.equal(hintOf(page).textContent, "X is open in a new window. Press Ctrl+V in X to add the image.");
}
{
  // Only Apple devices paste with Cmd.
  const page = await load();
  Object.defineProperty(navigator, "platform", { configurable: true, value: "MacIntel" });
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  page.body.find((node) => node.textContent === "Post on X ↗").click();
  await tick();
  assert.equal(hintOf(page).textContent, "X is open in a new window. Press ⌘V in X to add the image.");
}
{
  // A touch screen has no shortcut: the hint says tap and hold.
  const page = await load();
  window.matchMedia = (query) => ({ matches: query === "(pointer: coarse)" });
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  page.body.find((node) => node.textContent === "Post on X ↗").click();
  await tick();
  assert.equal(hintOf(page).textContent,
    "X is open in a new window. In X, tap and hold, then choose Paste to add the image.");
  delete window.matchMedia;
}
{
  const page = await load({ failure: "clipboard" });
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  page.body.find((node) => node.textContent === "Post on X ↗").click();
  await tick();
  assert.equal(hintOf(page).textContent,
    "X is open in a new window. The image was not copied. Download it, then attach it in X.");
}
{
  // A card that failed to load keeps its notice and does not promise a copy.
  const page = await load();
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  const image = page.body.find((node) => node.className === "share-card-image");
  image.listeners.error();
  const status = page.body.find((node) => node.className === "share-card-status");
  const notice = status.textContent;
  assert.equal(noteOf(page).textContent, "Opens X in a new window with the full text.");
  page.body.find((node) => node.textContent === "Post on X ↗").click();
  await tick();
  assert.equal(status.textContent, notice);
  assert.match(notice, /not ready yet/);
  assert.equal(hintOf(page).textContent, "X is open in a new window.");
}

{
  // The card fails while the copy is still pending: its notice stays.
  const page = await load();
  let rejectCopy;
  navigator.clipboard.write = () => new Promise((_, reject) => { rejectCopy = reject; });
  page.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  page.body.find((node) => node.textContent === "Post on X ↗").click();
  page.body.find((node) => node.className === "share-card-image").listeners.error();
  const status = page.body.find((node) => node.className === "share-card-status");
  const notice = status.textContent;
  rejectCopy(new Error("card 404"));
  await tick();
  assert.equal(status.textContent, notice);
  assert.equal(hintOf(page).textContent, "X is open in a new window.");
}

// One main action and four tools; Share… belongs to phones.
{
  const toolLabels = (page) => page.body
    .find((node) => node.className === "share-card-actions").children.map((node) => node.textContent);
  const desktop = await load();
  Object.defineProperty(navigator, "share", { configurable: true, value: async () => {} });
  desktop.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  assert.deepEqual(toolLabels(desktop), ["Copy text", "Copy image", "Download", "Copy benchmark link"],
    "a desktop browser with navigator.share still shows four tools");
  const phone = await load();
  Object.defineProperty(navigator, "share", { configurable: true, value: async () => {} });
  window.matchMedia = (query) => ({ matches: query === "(pointer: coarse)" });
  phone.openBenchmarkShare({ slug: "test-bench", name: "Test Bench" });
  assert.deepEqual(toolLabels(phone),
    ["Copy text", "Copy image", "Download", "Copy benchmark link", "Share…"]);
  assert(phone.body.find((node) => node.textContent === "Post on X ↗"), "Post on X stays the main action");
  delete navigator.share;
  delete window.matchMedia;
}

// The link button names what it copies.
{
  const labelFor = async (pageUrl) => {
    const page = await load();
    page.openRadarShare({ item: { title: "A", source: "Hugging Face" }, title: "A", pageUrl,
      image: "https://example.org/card.png" });
    return page.body.find((node) => node.className === "share-card-actions").children.at(-1).textContent;
  };
  assert.equal(await labelFor("https://benchmark-radar.org/benchmarks/gpqa/"), "Copy benchmark link");
  assert.equal(await labelFor("https://huggingface.co/datasets/owner/name"), "Copy source link");
  const day = await load();
  day.openDailyShare({ name: "Card", image: "https://example.org/card.png", caption: "Caption", day: "2026-11-07" });
  assert.equal(day.body.find((node) => node.className === "share-card-actions").children.at(-1).textContent,
    "Copy page link");
}

// Agents read the caption, link and image from the open dialog.
{
  const page = await load();
  page.openDailyShare({ name: "Card", image: "https://example.org/card.png", caption: "Full caption", day: "2026-11-07" });
  await tick();
  const dialog = page.body.find((node) => node.tag === "dialog");
  assert.equal(dialog.attrs["data-share-caption"], "Full caption");
  assert.equal(dialog.attrs["data-share-link"], "https://benchmark-radar.org/?date=2026-11-07");
  assert.equal(dialog.attrs["data-share-image"], "https://example.org/card.png");
}
{
  // A card drawn on demand is a blob URL: it is named while the dialog is open
  // and cleared once the blob is revoked.
  const page = await load();
  page.openRadarShare({ item: { title: "A", source: "Hugging Face" }, title: "A", pageUrl: "https://huggingface.co/x" });
  await new Promise((resolve) => setTimeout(resolve, 50));
  const dialog = page.body.find((node) => node.tag === "dialog");
  assert.match(dialog.attrs["data-share-image"], /^blob:/);
  dialog.listeners.close();
  assert.equal(dialog.attrs["data-share-image"], "");
}

assert.match(readFileSync("site/assets/app.js", "utf8"), /import \{ starPrompt \} from "\.\/star-prompt.js"/);

// #1162: the actual X handoff and copy fallback contain every caption field.
{
  const { radarCaption, briefingCaption, summaryCaption } = await import("../site/assets/share-caption.js");
  const card = {
    title: "Full benchmark", authors: ["Ada Lovelace", "Grace Hopper", "Alan Turing", "Fourth Author"],
    affiliations: ["First University", "Second Institute", "Third Lab"],
    blurb: "The complete image blurb.", url: "https://example.org/paper?a=1&b=2",
  };
  const item = { title: "owner/full-benchmark", source: "Hugging Face", organizations: ["owner"],
    url: "https://example.org/dataset", summary: "A long description. ".repeat(60) + "Final sentence preserved." };
  const radar = radarCaption({ item, title: "Full Benchmark", card });
  assert(radar.includes("By owner"));
  assert(radar.includes(item.summary.trim()));
  assert(radar.includes(card.blurb));
  const briefing = briefingCaption({ card, finding: "Finding with https://example.org/evidence.",
    implication: "Complete implication.", sources: ["https://example.org/extra"] });
  assert(briefing.includes("Why it matters: Complete implication."));
  assert(briefing.split("\n").includes("Source: https://example.org/extra"));
  assert(briefing.includes(card.blurb), "a revised finding retains the immutable PNG blurb");
  const summary = summaryCaption({ day: "2026-11-07", cards: [card, { ...card, title: "Second" },
    { ...card, title: "Third" }, { ...card, title: "Not on summary" }] });
  assert(summary.includes("3. Third"));
  assert(!summary.includes("Not on summary"));
  assert(summaryCaption({ day: "2026-11-07", cards: [card] }).startsWith("Top 1 AI benchmarks"));
  for (const caption of [radar, briefing, summary]) {
    for (const name of [...card.authors, ...card.affiliations]) assert(caption.includes(name));
    const page = await load();
    if (caption === radar) page.openRadarShare({ item, title: "Full Benchmark", card,
      day: "2026-11-07", image: "https://example.org/card.png", pageUrl: item.url });
    else page.openDailyShare({ name: card.title, image: "https://example.org/card.png", caption, day: "2026-11-07" });
    const link = page.body.find((node) => node.textContent === "Post on X ↗");
    const url = new URL(link.attrs.href);
    assert.equal(url.searchParams.get("text"), caption, "the intent preserves the entire caption, including URL encoding");
    assert.equal(url.searchParams.get("url"), null, "the site link is not appended twice");
    let copied;
    navigator.clipboard.writeText = async (text) => { copied = text; };
    await page.body.find((node) => node.textContent === "Copy text").click();
    assert.equal(copied, caption);
    const notice = page.body.find((node) => node.textContent?.includes("X Premium may be required"));
    assert(notice.hidden, "X details stay hidden until Post on X is clicked");
    link.click();
    assert.equal(notice.hidden, false);
  }
  assert(!radarCaption({ item: { title: "Sparse", source: "arXiv" } }).includes("undefined"));
  const neutralized = radarCaption({ item: { title: "Contact", summary: "Write energea@energeatech.com, @example-sandbox.dev, or @ktwu01." } });
  assert(neutralized.includes("energea at energeatech.com"));
  assert(neutralized.includes(" example-sandbox.dev"));
  assert(neutralized.includes("@ktwu01"));
  const contactUrl = "https://example.org/report?contact=author@example.org";
  assert(radarCaption({ item: { title: "URL", url: contactUrl } }).includes(`Source: ${contactUrl}`));
  assert(!briefingCaption({ card: { title: "Invalid", url: "javascript:alert(1)" } }).includes("javascript:"));
}
// Exercise the app's metadata handoff, including a search hit without its day.
{
  const app = readFileSync("site/assets/app.js", "utf8");
  const start = app.indexOf("function radarShareButton(");
  const source = app.slice(start, app.indexOf("\n}\n", start) + 2)
    .replace('await import("./share-card.js")', '({ openRadarShare: capture })');
  let captured;
  const make = new Function("element", "shareIcon", "t", "shareCardFor", "safeHttpUrl", "window", "capture", `return (${source});`);
  const element = (tag, props, children) => Object.assign(new Node(tag), { props, children });
  const daily = { title: "Daily image", authors: ["Published Creator"] };
  for (const [item, published, expected] of [
    [{}, daily, daily],
    [{ share_card: daily, snapshot_date: "2026-11-04" }, null, daily],
    [{ catalog_card: { title: "Catalog", authors: ["Catalog Creator"] } }, null, null],
  ]) {
    const share = make(element, () => null, (v) => v, () => published, (v) => v,
      { location: { href: "https://benchmark-radar.org" } }, (args) => { captured = args; });
    const control = share(item, { date: "2026-11-07" }, "Display title", "https://example.org/card.png");
    await control.children[0].listeners.click({ preventDefault() {}, stopPropagation() {} });
    assert.equal(captured.card, expected || item.catalog_card);
    assert.equal(captured.day, item.snapshot_date || "2026-11-07");
  }
  // A failed module load must retain the old image fallback; modifier clicks stay native.
  const controlStart = app.indexOf("function shareControl(");
  const controlSource = app.slice(controlStart, app.indexOf("function briefingShare(", controlStart))
    .replace('import("./share-card.js")', 'Promise.reject(new Error("chunk missing"))')
    .replace('import("./share-caption.js")', 'Promise.resolve({})');
  let fallback;
  const safeHttpSource = app.slice(app.indexOf("function safeHttpUrl("), app.indexOf("\n}\n", app.indexOf("function safeHttpUrl(")) + 2);
  const makeControl = new Function("element", "shareIcon", "t", "window",
    `${safeHttpSource}\nreturn (${controlSource});`);
  const control = makeControl(
    element, () => null, (v) => v, { location: { assign: (url) => { fallback = url; } } },
  )("https://example.org/card.png", "Bench", "Share card", { day: "2026-11-07", card: daily });
  // A non-http(s) image never becomes a link the fallback could navigate to.
  assert.equal(makeControl(element, () => null, (v) => v, { location: { assign() {
    throw new Error("must not navigate");
  } } })("javascript:alert(1)", "Bench", "Share card", { day: "2026-11-07", card: daily }), null);
  let prevented = false;
  await control.children[0].listeners.click({ metaKey: true, preventDefault() { prevented = true; } });
  assert.equal(prevented, false);
  const originalError = console.error;
  console.error = () => {};
  try { await control.children[0].listeners.click({ preventDefault() { prevented = true; } }); }
  finally { console.error = originalError; }
  assert.equal(prevented, true);
  assert.equal(fallback, "https://example.org/card.png");
}
console.log("star prompt and card actions harness ok");
