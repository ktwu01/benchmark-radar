import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test } from "node:test";

const source = readFileSync("site/assets/clarity.js", "utf8");
const key = "benchmark-radar:analytics-consent";

function page({ storage = new Map(), blocked = false, writeBlocked = false, cookies = new Map(), reset = true, hostname = "benchmark-radar.org", search = "" } = {}) {
  const nodes = new Map();
  const listeners = {};
  const scripts = [];
  const calls = [];
  let recording = false;
  let reloads = 0;
  const localStorage = {
    getItem(k) { if (blocked) throw Error("blocked"); return storage.get(k) ?? null; },
    setItem(k, v) { if (blocked || writeBlocked) throw Error("blocked"); storage.set(k, v); },
    removeItem(k) { if (blocked) throw Error("blocked"); storage.delete(k); },
  };
  const privacy = { append(node) { nodes.set("reset", node); } };
  const document = {
    body: { append(node) { nodes.set(node.id, node); } },
    addEventListener(type, fn) { listeners[`document:${type}`] = fn; },
    dispatchEvent(event) { listeners[`document:${event.type}`]?.(event); },
    getElementById(id) { return nodes.get(id); },
    querySelector(selector) {
      return selector === ".privacy-note" ? privacy : (reset ? {} : nodes.get("reset"));
    },
    createElement() {
      return { dataset: {}, setAttribute() {}, addEventListener(type, fn) { this[type] = fn; },
        remove() { nodes.delete(this.id); } };
    },
    getElementsByTagName() { return [{ parentNode: { insertBefore(node) { scripts.push(node); } } }]; },
    set cookie(value) {
      const name = value.split("=")[0];
      const domain = /Domain=([^;]+)/.exec(value)?.[1] ?? "host";
      if (value.includes("Max-Age=0")) cookies.delete(`${name}:${domain}`);
    },
  };
  const window = {
    localStorage, location: { hostname, search, reload() { recording = false; reloads += 1; } },
    addEventListener(type, fn) { listeners[type] = fn; },
  };
  runInNewContext(source, { window, document, URLSearchParams, Event: class { constructor(type) { this.type = type; } } });
  function loadSdk() {
    const queued = [...(window.clarity.q ?? [])];
    window.clarity = (...args) => {
      calls.push(args);
      if (args[0] === "start") recording = true;
      if (args[0] === "stop") recording = false;
    };
    recording = true;
    for (const args of queued) window.clarity(...args);
  }
  return {
    window, scripts, calls, nodes, cookies, loadSdk,
    get recording() { return recording; },
    get reloads() { return reloads; },
    choose(value) {
      if (!nodes.has("analytics-consent")) this.reopen();
      nodes.get("analytics-consent").click({ target: { closest: () => ({ dataset: { consent: value } }) } });
    },
    reopen() {
      listeners["document:click"]({ target: { closest: () => ({}) }, preventDefault() {} });
    },
    restore() { listeners.pageshow?.({ persisted: true }); },
    sync(changedKey = key, storageArea = localStorage) {
      listeners.storage?.({ key: changedKey, storageArea });
    },
  };
}

test("fresh and declined visits never request the tag", () => {
  const fresh = page();
  assert.ok(fresh.nodes.has("analytics-consent"));
  fresh.choose("denied");
  assert.equal(fresh.scripts.length, 0);
  assert.ok(!fresh.nodes.has("analytics-consent"));
  const denied = page({ storage: new Map([[key, "denied"]]) });
  assert.equal(denied.scripts.length, 0);
  assert.ok(!denied.nodes.has("analytics-consent"));
});

test("local previews and copied deployments never send production analytics", () => {
  for (const hostname of ["localhost", "127.0.0.1", "::1", "fork.github.io", "benchmark-radar.org.example.com"]) {
    const tab = page({ hostname, storage: new Map([[key, "granted"]]) });
    assert.equal(tab.scripts.length, 0, hostname);
    assert.ok(!tab.nodes.has("analytics-consent"), hostname);
  }
});

test("the maintainer opt-out overrides an old grant and persists on later visits", () => {
  const storage = new Map([[key, "granted"]]);
  const tab = page({ storage, search: "?analytics=off" });
  assert.equal(tab.scripts.length, 0);
  assert.equal(storage.get(key), "denied");
  assert.ok(!tab.nodes.has("analytics-consent"));
  const later = page({ storage });
  assert.equal(later.scripts.length, 0);
  assert.ok(!later.nodes.has("analytics-consent"));
});

test("accept loads one tag and grants analytics only; withdrawal stops; reaccept restarts", () => {
  const storage = new Map();
  const tab = page({ storage });
  tab.choose("granted");
  assert.equal(tab.scripts.length, 1);
  assert.match(tab.scripts[0].src, /^https:\/\/www\.clarity\.ms\/tag\//);
  tab.loadSdk();
  assert.equal(tab.recording, true);
  assert.equal(tab.calls[0][0], "consentv2");
  assert.equal(tab.calls[0][1].analytics_Storage, "granted");
  assert.equal(tab.calls[0][1].ad_Storage, "denied");
  tab.choose("denied");
  assert.equal(tab.recording, false);
  assert.ok(tab.calls.some(([command, value]) => command === "consent" && value === false));
  assert.equal(tab.reloads, 1);
  const restored = page({ storage });
  assert.equal(restored.scripts.length, 0);
  restored.choose("granted");
  restored.loadSdk();
  assert.equal(restored.recording, true);
  assert.equal(restored.scripts.length, 1);
});

test("stored opt-in starts without another prompt", () => {
  const tab = page({ storage: new Map([[key, "granted"]]) });
  assert.equal(tab.scripts.length, 1);
  assert.ok(!tab.nodes.has("analytics-consent"));
});

test("decline clears legacy cookies at host and parent domains without loading Clarity", () => {
  const cookies = new Map();
  for (const name of ["_clck", "_clsk", "unrelated"]) {
    for (const domain of ["host", "benchmark-radar.org", "org"]) {
      cookies.set(`${name}:${domain}`, "old");
    }
  }
  const tab = page({ cookies });
  tab.choose("denied");
  assert.deepEqual([...cookies.keys()], ["unrelated:host", "unrelated:benchmark-radar.org", "unrelated:org"]);
  assert.equal(tab.scripts.length, 0);
});

test("withdrawal stops even when storage is blocked", () => {
  const tab = page({ blocked: true });
  tab.choose("granted");
  tab.loadSdk();
  tab.choose("denied");
  assert.equal(tab.recording, false);
});

test("withdrawal before the SDK arrives discards the pending runtime", () => {
  const tab = page();
  tab.choose("granted");
  tab.choose("denied");
  assert.equal(tab.reloads, 1);
  // A navigation discards the pending script, so the next document never loads it.
  const restored = page({ storage: new Map([[key, "denied"]]) });
  assert.equal(restored.scripts.length, 0);
});

test("withdrawal and storage clearing stop other tabs", () => {
  const storage = new Map([[key, "granted"]]);
  const first = page({ storage });
  const other = page({ storage });
  first.loadSdk();
  other.loadSdk();
  first.choose("denied");
  other.sync();
  assert.equal(first.recording, false);
  assert.equal(other.recording, false);
  assert.ok(!other.nodes.has("analytics-consent"));
  assert.equal(other.reloads, 1);
  storage.set(key, "granted");
  const restored = page({ storage });
  restored.loadSdk();
  storage.clear();
  restored.sync(null);
  assert.equal(restored.recording, false);
  assert.equal(restored.reloads, 1);
  const cleared = page({ storage });
  assert.ok(cleared.nodes.has("analytics-consent"));
});

test("unrelated storage events do not alter consent", () => {
  const storage = new Map([[key, "granted"]]);
  const tab = page({ storage });
  tab.loadSdk();
  storage.set(key, "denied");
  tab.sync("unrelated");
  tab.sync(key, {});
  assert.equal(tab.recording, true);
});

test("entry points without a reset button gain a working control", () => {
  const tab = page({ reset: false, storage: new Map([[key, "denied"]]) });
  assert.equal(tab.nodes.get("reset").textContent, "Change analytics choice");
  tab.reopen();
  assert.ok(tab.nodes.has("analytics-consent"));
});


test("restoring a cached page honors withdrawal that happened while away", () => {
  const storage = new Map([[key, "granted"]]);
  const tab = page({ storage });
  tab.loadSdk();
  storage.set(key, "denied");
  tab.restore();
  assert.equal(tab.recording, false);
});


test("withdrawal removes a readable old grant when saving denial exceeds quota", () => {
  const storage = new Map([[key, "granted"]]);
  const tab = page({ storage, writeBlocked: true });
  tab.loadSdk();
  tab.choose("denied");
  assert.equal(tab.recording, false);
  assert.equal(tab.reloads, 1);
  assert.equal(storage.has(key), false);
  const restored = page({ storage, writeBlocked: true });
  assert.equal(restored.scripts.length, 0);
});
