// Keep captions complete even when the image layout abbreviates names or prose.
import { cardFacts } from "./radar-card.js";

const HOME = "https://benchmark-radar.org";
const unique = (values) => [...new Set((values || []).filter(Boolean))];
// Domain-like text is not an X handle. Keep genuine handles such as @ktwu01.
const postText = (text) => text.split(/(https?:\/\/\S+)/g)
  .map((part, index) => index % 2 ? part : part
    .replace(/([\w.+-]+)@([\w.-]+\.[a-z]{2,})/gi, "$1 at $2")
    .replace(/(^|\s)@(?=[\w.-]+\.[a-z]{2,}\b)/gi, "$1"))
  .join("");
const join = (parts) => postText(parts.filter(Boolean).join("\n\n"));
const sourceUrl = (value) => {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? value : "";
  } catch { return ""; }
};
const creators = (card) => [
  unique(card.authors).join(", "),
  unique(card.affiliations).join("; "),
].filter(Boolean).join("\n");

export function radarCaption({ item, title, card = null, pageUrl = "" }) {
  const facts = cardFacts(item, { title });
  const people = unique([...facts.authors, ...(card?.authors || [])]);
  const byline = facts.byline.startsWith("By ") ? facts.byline : "";
  const affiliations = unique([...facts.affiliations, ...(card?.affiliations || []), card?.publisher]);
  const summary = facts.blurb || "No description published at the source.";
  return join([
    facts.title,
    [byline, people.join(", "), affiliations.join("; ")].filter(Boolean).join("\n"),
    card?.title && card.title !== facts.title ? card.title : "",
    summary,
    card?.blurb && !summary.includes(card.blurb) ? card.blurb : "",
    sourceUrl(item.url) && !summary.includes(item.url) ? `Source: ${item.url}` : "",
    sourceUrl(pageUrl) && pageUrl !== item.url && pageUrl !== HOME ? pageUrl : "",
    HOME,
  ]);
}

export function briefingCaption({ card, finding = "", implication = "", sources = [] }) {
  return join([
    card.title,
    creators(card),
    finding || card.blurb,
    finding && card.blurb && !finding.includes(card.blurb) ? card.blurb : "",
    implication ? `Why it matters: ${implication}` : "",
    unique([card.url, ...sources].map(sourceUrl)).map((url) => `Source: ${url}`).join("\n"),
    HOME,
  ]);
}

export function summaryCaption({ day, cards }) {
  const selected = cards.slice(0, 3);
  return join([
    `Top ${selected.length} AI benchmarks on Benchmark Radar · ${day}`,
    ...selected.map((card, index) => [
      `${index + 1}. ${card.title}`,
      creators(card),
      card.blurb,
      sourceUrl(card.url),
    ].filter(Boolean).join("\n")),
    HOME,
  ]);
}
