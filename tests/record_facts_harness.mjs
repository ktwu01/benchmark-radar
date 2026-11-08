// Execute the real metadata helpers from app.js so the test proves missing
// versus zero behavior rather than matching implementation source strings.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "..", "site", "assets", "app.js"), "utf8");
const start = source.indexOf("const RECORD_METRIC_LABELS");
const end = source.indexOf("\nfunction safeHttpUrl", start);
if (start < 0 || end < 0) throw new Error("Record metadata helpers not found");

globalThis.t = (value) => value;
globalThis.getLang = () => "en";
globalThis.formatDate = (value) => `date:${value}`;
globalThis.document = { createTextNode: (text) => ({ text }) };
globalThis.element = (tag, props = {}, children = []) => ({ tag, props, children });
const harness = `${source.slice(start, end)}
globalThis.__recordFactEntries = recordFactEntries;
globalThis.__recordDateEntries = recordDateEntries;
globalThis.__recordFacts = recordFacts;
globalThis.__cardTierClass = cardTierClass;
globalThis.__publishedDateNote = publishedDateNote;`;
new Function(harness)();

const reportedItem = {
  organizations: ["OpenAI"],
  authors: ["Alice", "Bob", "Carol"],
  metrics: { stars: 0, forks: null },
};
const reported = globalThis.__recordFactEntries(reportedItem);
const unreported = globalThis.__recordFactEntries({
  authors: ["Deyao Hong"],
  metrics: {},
});
// A GitHub record whose connector left organizations empty still names its
// owner, because the card title no longer shows it.
const slugOwner = globalThis.__recordFactEntries({
  title: "NVIDIA-NeMo/Gym",
  organizations: [],
  metrics: {},
});
const dates = globalThis.__recordDateEntries({
  published_at: "2026-08-24T17:59:04Z",
  updated_at: "2026-08-25T17:59:04Z",
});
const datesWithBasis = globalThis.__recordDateEntries({
  published_at: "2026-10-27T02:01:03Z",
  updated_at: "2026-10-27T02:01:03Z",
  published_basis: "created",
  published_source_value: "2026-10-31",
});
// Issue #1016: a record dated by its deposition's created time says so next
// to Published, with the uploader's value as given; any other basis is silent.
const publishedNote = {
  replaced: globalThis.__publishedDateNote({
    published_basis: "created",
    published_source_value: "2026-10-31",
  }),
  replacedBareYear: globalThis.__publishedDateNote({
    published_basis: "created",
    published_source_value: "2027",
  }),
  noSourceValue: globalThis.__publishedDateNote({ published_basis: "created" }),
  normal: globalThis.__publishedDateNote({
    published_basis: "publication_date",
    published_source_value: "2026-07-27",
  }),
  unknown: globalThis.__publishedDateNote({}),
};
const rendered = globalThis.__recordFacts(reportedItem);
// Issue #994: each published count tints the card light gold past its first
// threshold and strong gold past its second.
const tiers = Object.fromEntries(
  [
    ["downloads_282271", { metrics: { downloads: 282271 } }],
    ["downloads_10000", { metrics: { downloads: 10000 } }],
    ["downloads_5000", { metrics: { downloads: 5000 } }],
    ["downloads_1000", { metrics: { downloads: 1000 } }],
    ["stars_1001", { metrics: { stars: 1001 } }],
    ["stars_101", { metrics: { stars: 101 } }],
    ["stars_100", { metrics: { stars: 100 } }],
    ["likes_7746", { metrics: { likes: 7746 } }],
    ["likes_150", { metrics: { likes: 150 } }],
    ["upvotes_660", { metrics: { upvotes: 660 } }],
    ["votes_1500", { metrics: { votes: 1500 } }],
    ["citations_120", { metrics: { citations: 120 } }],
    ["stars_50_downloads_5000", { metrics: { stars: 50, downloads: 5000 } }],
    ["release_repo_stars", { source: "GitHub Release", metrics: { stars: 3000, downloads: 70 } }],
    ["views_only", { metrics: { views: 38306, forks: 5000 } }],
    ["none", { metrics: {} }],
  ].map(([key, item]) => [key, globalThis.__cardTierClass(item)]),
);

console.log(
  JSON.stringify({
    reported,
    slug_owner: slugOwner,
    unreported,
    dates,
    dates_with_basis: datesWithBasis,
    published_note: publishedNote,
    tiers,
    rendered: {
      tag: rendered.tag,
      className: rendered.props.className,
      role: rendered.props.attrs.role,
      ariaLabel: rendered.props.attrs["aria-label"],
    },
  }),
);
