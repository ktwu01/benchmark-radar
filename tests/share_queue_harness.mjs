// The share queue's record keeping (issue #1162): a card is posted only with a
// real post URL, and posting-log rows round-trip so no card is posted twice.
import assert from "node:assert/strict";

const queue = await import("../site/assets/share-queue.js");

assert.equal(queue.parsePostUrl("https://x.com/compose/post"), null);
assert.equal(queue.parsePostUrl("not a url"), null);
assert.deepEqual(queue.parsePostUrl("https://twitter.com/ktwu01/status/2119301152999141831?s=20"), {
  url: "https://x.com/ktwu01/status/2119301152999141831",
  account: "ktwu01",
});

// Left-panel and briefing cards match by type and source on any date; a
// summary matches by its day.
assert.equal(queue.postKey({ kind: "briefing", day: "2026-11-07", source: "https://a.org" }), "briefing|https://a.org");
assert.equal(queue.postKey({ kind: "summary", day: "2026-11-07", source: "" }), "summary|2026-11-07");

const log = [
  "daily_date,account,card_type,title,source_url,status,post_url,reply_url,caption_status,verified_on,notes",
  '2026-11-07,ktwu01,briefing,"A, with comma",https://a.org,posted,https://x.com/ktwu01/status/1,,complete,2026-11-08,ok',
  "2026-11-07,ktwu01,summary,Top 3,,posted,https://x.com/ktwu01/status/2,,complete,2026-11-08,ok",
  "2026-11-07,ktwu01,left,Pending card,https://b.org,pending,,,not_posted,,",
  "2026-11-07,ktwu01,left,Bad url,https://c.org,posted,https://example.org/1,,complete,,",
].join("\n");
const posts = {};
assert.equal(queue.importLog(log, posts), 2);
assert.deepEqual(Object.keys(posts).sort(), ["briefing|https://a.org", "summary|2026-11-07"]);
assert.equal(posts["briefing|https://a.org"].title, "A, with comma");

const again = {};
assert.equal(queue.importLog(queue.exportLog(posts), again), 2);
assert.deepEqual(again, posts);
console.log("share queue harness ok");
