// Draw a Today's radar item as a share card in the browser (issue #1019).
//
// About 99% of radar items have no catalog page and no pre-rendered card, and
// rendering ~460 images a day would fill the cards site within months. A radar
// item has no page of its own, so no crawler needs a hosted og:image for it:
// what a reader shares is the image file and the item's link. Drawing on a
// <canvas> when Share is pressed costs no storage and covers every past day.
//
// The layout copies render_card() in scripts/render_share_images.py, so a drawn
// card and a published daily card look like the same product. The colours and
// sizes below must match that script and scripts/generate_og_image.py;
// tests/test_radar_card.py fails when they drift apart.

export const CARD = {
  width: 1200,
  height: 630,
  margin: 64,
  background: "#FAFAFA",
  ink: "#1B2A4A",
  teal: "#2A7F8E",
  slate: "#6B7B8D",
  watermark: "benchmark-radar.org",
};

const SCALE = 1.3;
const TITLE_SIZE = 44;
const TITLE_LINES = 3;
const FACE = '"Avenir Next", Avenir, "Segoe UI", "Helvetica Neue", Arial, sans-serif';

// Every radar item is some mix of these, so naming them tells the reader
// nothing. The topical categories after them (agentic, multimodal) do.
const GENERIC_CATEGORIES = new Set(["benchmark", "evaluation", "dataset"]);

// These sources hold an owner handle, not an institution; the daily cards look
// the handle up before naming it, and a drawn card never guesses.
const HANDLE_SOURCES = new Set([
  "Hugging Face",
  "GitHub",
  "GitHub Organization",
  "GitHub Release",
  "Kaggle Dataset",
]);

function plain(value) {
  let text = String(value ?? "");
  // DataCite descriptions arrive as escaped HTML, sometimes escaped twice.
  for (let pass = 0; pass < 2; pass += 1) {
    text = text
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#0?39;/g, "'")
      .replace(/&nbsp;/g, " ")
      .replace(/&amp;/g, "&");
  }
  return text.replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).join(" ");
}

function unique(values) {
  const seen = new Set();
  const result = [];
  for (const value of values || []) {
    const text = plain(value);
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    result.push(text);
  }
  return result;
}

function names(values, limit) {
  const shown = values.slice(0, limit).join(", ");
  return values.length > limit ? `${shown} et al.` : shown;
}

function cardDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  if (!match) return "";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(match[2]) - 1];
  return month ? `${month} ${Number(match[3])}, ${match[1]}` : "";
}

// The facts a card shows, each read from the item. A fact the item lacks is
// left out; nothing is filled in.
export function cardFacts(item, { day = "", title = "" } = {}) {
  const topics = (item.categories || [])
    .map((name) => String(name).replace(/_/g, " "))
    .filter((name) => name && !GENERIC_CATEGORIES.has(name.toLowerCase()));
  const source = plain(item.source);
  const meta = [source, cardDay(item.published_at), ...topics.slice(0, 2)].filter(Boolean);
  return {
    label: ["Benchmark Radar", "Today's radar", cardDay(day)].filter(Boolean).join(" · "),
    title: plain(title || item.title),
    authors: unique(item.authors),
    affiliations: HANDLE_SOURCES.has(source) ? [] : unique(item.organizations),
    blurb: plain(item.summary),
    meta: meta.join(" · "),
  };
}

function font(ctx, size, bold = false) {
  ctx.font = `${bold ? "700" : "400"} ${size}px ${FACE}`;
}

// Cut ``text`` to ``width`` with an ellipsis when it does not fit.
function fit(ctx, text, width) {
  if (ctx.measureText(text).width <= width) return text;
  let low = 0;
  let high = text.length;
  while (low < high) {
    const middle = Math.floor((low + high + 1) / 2);
    if (ctx.measureText(`${text.slice(0, middle)}…`).width <= width) low = middle;
    else high = middle - 1;
  }
  return `${text.slice(0, low).replace(/[ ,·;:-]+$/, "")}…`;
}

function wrap(ctx, text, width, maxLines) {
  if (maxLines <= 0 || !text) return [];
  const words = text.split(" ");
  const lines = [];
  let current = "";
  for (let index = 0; index < words.length; index += 1) {
    const trial = `${current} ${words[index]}`.trim();
    if (ctx.measureText(trial).width <= width) {
      current = trial;
      continue;
    }
    if (current) lines.push(current);
    current = words[index];
    if (lines.length === maxLines - 1) {
      current = [current, ...words.slice(index + 1)].join(" ");
      break;
    }
  }
  if (current) lines.push(current);
  // Every line, not only the last: one "owner/repository" token can be wider
  // than the whole text area.
  return lines.slice(0, maxLines).map((line) => fit(ctx, line, width));
}

export function drawCard(ctx, facts) {
  const { width, height, margin } = CARD;
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  ctx.fillStyle = CARD.background;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = CARD.teal;
  ctx.fillRect(0, 0, 13, height);

  font(ctx, 24, true);
  ctx.fillStyle = CARD.teal;
  ctx.fillText(fit(ctx, facts.label, width - 2 * margin), margin, 40);

  const textWidth = width - 2 * margin;
  const bottom = height - 80;
  const body = Math.round(22 * SCALE);
  const step = Math.round(body * 1.33);
  let y = 96;
  font(ctx, TITLE_SIZE, true);
  ctx.fillStyle = CARD.ink;
  for (const line of wrap(ctx, facts.title, textWidth, TITLE_LINES)) {
    ctx.fillText(line, margin, y);
    y += Math.round(TITLE_SIZE * 1.27);
  }
  y += Math.round(6 * SCALE);
  if (facts.authors.length) {
    font(ctx, body + 1);
    ctx.fillStyle = CARD.ink;
    ctx.fillText(fit(ctx, names(facts.authors, 3), textWidth), margin, y);
    y += step + 2;
  }
  if (facts.affiliations.length) {
    font(ctx, body + 1, true);
    ctx.fillStyle = CARD.teal;
    ctx.fillText(fit(ctx, names(facts.affiliations, 2), textWidth), margin, y);
    y += step + 2;
  }
  y += Math.round(6 * SCALE);
  const metaSize = Math.round(19 * SCALE);
  const lines = Math.max(0, Math.floor((bottom - (metaSize + 8) - y) / step));
  font(ctx, body);
  ctx.fillStyle = CARD.slate;
  for (const line of wrap(ctx, facts.blurb, textWidth, lines)) {
    ctx.fillText(line, margin, y);
    y += step;
  }
  if (facts.meta) {
    font(ctx, metaSize);
    ctx.fillText(fit(ctx, facts.meta, textWidth), margin, y + 8);
  }

  font(ctx, 30, true);
  ctx.fillStyle = CARD.teal;
  ctx.textAlign = "right";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(CARD.watermark, width - margin, height - 40);
}

// The card as a PNG blob, drawn on a detached canvas.
export function cardBlob(facts) {
  const canvas = document.createElement("canvas");
  canvas.width = CARD.width;
  canvas.height = CARD.height;
  drawCard(canvas.getContext("2d"), facts);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("card not drawn"))), "image/png");
  });
}
