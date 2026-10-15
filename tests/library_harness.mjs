// Execute the Library's production filter, sort and saved-list functions with
// small inputs, without a browser.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const constants = [
  source.match(/const LIBRARY_UNCLASSIFIED = .*;/)[0],
  source.match(/const LIBRARY_SAVED_KEY = .*;/)[0],
  source.match(/let librarySavedMemory = null;/)[0],
  source.match(/const LIBRARY_FOLLOWED_KEY = .*;/)[0],
  source.match(/let libraryFollowedMemory = null;/)[0],
].join("\n");
const names = ["librarySavedSlugs", "setLibrarySaved", "libraryFollowedDirections", "setLibraryFollowed", "libraryInFollowed", "libraryInDirection", "codePointCompare", "libraryCompare", "libraryMatches", "libraryRows", "libraryDirectionCounts"];
const record = (slug, name, released, categories, documents = 0) => ({
  slug, key: `k:${slug}`, name, released,
  library_direction: categories ? { primary: categories[0], categories } : null,
  evidence_summary: { document_count: documents },
});
const withStars = (row, stars, gain) => ({ ...row, attention_signals: { github_stars: stars, github_stars_30d: gain, as_of: "2026-10-14" } });
const state = {
  benchmarkIndex: [
    record("a", "Alpha", "2026-01-02", ["math"], 1),
    record("b", "Beta", "2026-03-04", ["math", "science"], 5),
    record("c", "Gamma", null, null, 2),
  ],
  libraryQuery: "", libraryDirection: "", librarySort: "latest", librarySaved: false, libraryFollowing: false,
};
let store = {};
const storage = {
  getItem: (key) => (key in store ? store[key] : null),
  setItem: (key, value) => { store[key] = String(value); },
};
globalThis.window = { localStorage: storage };
const lib = new Function("state", "searchBenchmarkIndex", `${constants}\n${names.map(fn).join("\n")}\nreturn {${names.join(",")}};`)(
  state, (records, query) => records.filter((row) => row.name.toLowerCase().includes(query.toLowerCase())),
);

// Newest first; an undated record is listed last, never dropped.
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["b", "a", "c"]);
state.librarySort = "documented";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["b", "c", "a"]);
state.librarySort = "name";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["a", "b", "c"]);

// A secondary direction counts, and unclassified records have their own entry.
state.libraryDirection = "science";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["b"]);
state.libraryDirection = "unclassified";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["c"]);
state.libraryDirection = "";
const counts = lib.libraryDirectionCounts();
assert.equal(counts.get(""), 3);
assert.equal(counts.get("math"), 2);
assert.equal(counts.get("unclassified"), 1);

// A query keeps the search's own order instead of the sort.
state.libraryQuery = "a";
state.librarySort = "latest";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["a", "b", "c"]);
state.libraryQuery = "";

// Saved benchmarks persist per browser, and the saved filter narrows the list.
lib.setLibrarySaved("k:c", true);
assert.deepEqual([...lib.librarySavedSlugs()], ["k:c"]);
state.librarySaved = true;
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["c"]);
lib.setLibrarySaved("k:c", false);
assert.deepEqual(lib.libraryRows(), []);
state.librarySaved = false;

// Corrupt storage reads as an empty list instead of breaking the page.
store = { "benchmark-radar:saved-keys:v1": "{not json" };
assert.equal(lib.librarySavedSlugs().size, 0);
// Blocked storage: the click still sticks for the rest of the visit, because a
// reread of the blocked store would otherwise undo the star immediately.
globalThis.window = { get localStorage() { throw new Error("blocked"); } };
assert.equal(lib.librarySavedSlugs().size, 0);
lib.setLibrarySaved("a", true);
assert.deepEqual([...lib.librarySavedSlugs()], ["a"]);
lib.setLibrarySaved("b", true);
lib.setLibrarySaved("a", false);
assert.deepEqual([...lib.librarySavedSlugs()], ["b"]);

// Ties on a release date break by code point, not locale, so app_seeds.py can
// reproduce the live first page exactly.
const tied = [record("z", "beta", "2026-01-01"), record("y", "Alpha", "2026-01-01"), record("x", "alpha", "2026-01-01")];
assert.deepEqual(tied.sort(lib.libraryCompare("latest")).map((row) => row.slug), ["y", "x", "z"]);
// Star sorts: observed values first, records with no observation after.
globalThis.window = { localStorage: storage };
store = {};
state.benchmarkIndex = [
  withStars(record("a", "Alpha", "2026-01-02", ["math"]), 10, 1),
  withStars(record("b", "Beta", "2026-03-04", ["science"]), 50, null),
  record("c", "Gamma", null, null),
];
state.librarySort = "stars";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["b", "a", "c"]);
state.librarySort = "stars30";
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["a", "b", "c"]);

// Followed directions narrow the list to records filed under any of them.
lib.setLibraryFollowed("science", true);
state.libraryFollowing = true;
assert.deepEqual(lib.libraryRows().map((row) => row.slug), ["b"]);
state.libraryFollowing = false;

// A write that fails and a later one that succeeds: storage holds the list
// again, so the stale in-memory copy must not win (review on #861). The
// blocked-storage case above left an in-memory list; a successful write
// clears it first.
lib.setLibrarySaved("b", false);
assert.deepEqual([...lib.librarySavedSlugs()], JSON.parse(store["benchmark-radar:saved-keys:v1"]));
let failNext = true;
globalThis.window = { localStorage: {
  getItem: storage.getItem,
  setItem: (key, value) => { if (failNext) { failNext = false; throw new Error("quota"); } store[key] = String(value); },
} };
lib.setLibrarySaved("k:x", true);
assert.deepEqual([...lib.librarySavedSlugs()], ["k:x"]);
lib.setLibrarySaved("k:x", false);
assert.deepEqual([...lib.librarySavedSlugs()], []);
console.log("Library filters, sorts, saved list and followed directions passed.");
