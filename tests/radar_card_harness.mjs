// Draw fixture radar items with the production radar-card.js against a fake
// 2D context, and check the card holds only the facts each item has (#1019).
import assert from "node:assert/strict";
import { CARD, cardFacts, drawCard } from "../site/assets/radar-card.js";

function context() {
  const calls = [];
  const ctx = {
    font: "",
    fillStyle: "",
    textAlign: "left",
    textBaseline: "top",
    fillRect() {},
    // Wide enough that long titles wrap; the real font is narrower.
    measureText(text) {
      const size = Number(/(\d+)px/.exec(this.font)?.[1] || 10);
      return { width: [...text].length * size * 0.55 };
    },
    fillText(text, x, y) {
      calls.push({ text, x, y, font: this.font, fill: this.fillStyle, align: this.textAlign });
    },
  };
  return { ctx, calls };
}

const full = {
  title: "LongBench-Agent: A Benchmark for Long-Horizon Terminal Agents Across Many Realistic Multi-Step Tasks",
  source: "arXiv",
  published_at: "2026-11-03T05:00:00+00:00",
  categories: ["benchmark", "evaluation", "agentic", "multi_modal", "coding"],
  authors: ["Ada Lovelace", "Alan Turing", "Ada Lovelace", "Grace Hopper", "Edsger Dijkstra"],
  organizations: ["MIT", "Stanford University", "CMU"],
  summary: "We  introduce a\nbenchmark. ".repeat(20),
};
const facts = cardFacts(full, { day: "2026-11-03" });
assert.equal(facts.label, "Benchmark Radar · Today's radar · Nov 3, 2026");
assert.deepEqual(facts.authors, ["Ada Lovelace", "Alan Turing", "Grace Hopper", "Edsger Dijkstra"]);
assert.deepEqual(facts.affiliations, ["MIT", "Stanford University", "CMU"]);
assert.equal(facts.meta, "arXiv · Nov 3, 2026 · agentic · multi modal");
assert(facts.blurb.startsWith("We introduce a benchmark. We introduce"));
// Reported results with angle brackets survive whole (SemVerBench, 2026-09-12).
const semver = "Pins requests>=2.0,<3 and checks the resolver picks numpy>1.2 for every case.";
assert.equal(cardFacts({ title: "SemVerBench", summary: semver }).blurb, semver);

const drawn = context();
drawCard(drawn.ctx, facts);
const texts = drawn.calls.map((call) => call.text);
for (const call of drawn.calls) {
  assert(!/undefined|null|NaN/.test(call.text), call.text);
  if (call.align === "left") {
    const width = drawn.ctx.measureText.call({ font: call.font }, call.text).width;
    assert(call.x + width <= CARD.width - CARD.margin + 0.5, `overflows: ${call.text}`);
  }
}
const watermark = drawn.calls.at(-1);
assert.equal(watermark.text, "benchmark-radar.org");
assert.equal(watermark.align, "right");
assert.equal(watermark.x, CARD.width - CARD.margin);
assert.equal(watermark.fill, CARD.teal);
assert.equal(texts[0], facts.label);
assert(texts.includes("Ada Lovelace, Alan Turing, Grace Hopper et al."));
assert(texts.includes("MIT, Stanford University et al."));
const titleLines = drawn.calls.filter((call) => call.font.includes("700 44px"));
assert(titleLines.length >= 2 && titleLines.length <= 3);
const meta = drawn.calls.find((call) => call.text === facts.meta);
assert(meta, "meta line drawn");
const body = drawn.calls.filter((call) => call.font.includes("400 29px"));
assert(body.length > 0);
assert(body.every((call) => call.y < meta.y), "summary stays above the meta line");
assert(meta.y + 25 <= CARD.height - 80 + 8, "meta line stays inside the card body");

// An item with almost nothing: no author, owner-handle source, no summary.
const sparse = cardFacts(
  { title: "owner/" + "x".repeat(200), source: "Hugging Face", organizations: ["openai"] },
  { day: "" },
);
assert.deepEqual(sparse.authors, []);
assert.deepEqual(sparse.affiliations, [], "an owner handle is not an institution");
assert.equal(sparse.blurb, "");
assert.equal(sparse.meta, "Hugging Face");
assert.equal(sparse.label, "Benchmark Radar · Today's radar");
const thin = context();
drawCard(thin.ctx, sparse);
assert.deepEqual(
  thin.calls.map((call) => call.text).filter((text) => !text.endsWith("…")),
  [sparse.label, "Hugging Face", "benchmark-radar.org"],
);
const cut = thin.calls.find((call) => call.text.endsWith("…"));
assert(cut, "a token wider than the card is cut with an ellipsis");

// The card keeps CJK text; the browser font has the glyphs DejaVu lacks.
assert.equal(cardFacts({ title: "中文基准 Bench" }).title, "中文基准 Bench");
console.log("radar card harness: ok");
