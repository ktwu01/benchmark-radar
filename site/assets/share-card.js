// Share any benchmark as an image card (issue #671).
//
// Every catalog benchmark has a 1200x630 card at /cards/<slug>.png, which
// scripts/render_share_images.py draws during the Pages build, so the card
// deploys with the page that names it. src/benchmark_radar/cards.py says why
// it is served from the site's own host.
// This module only fetches the card a reader asked for. A benchmark whose card
// is missing still shares its link. A Today's radar item has no hosted card
// unless the daily briefing picked it, so its card is drawn on demand by
// radar-card.js (issue #1019).
//
// The dashboard imports this on demand when a reader presses Share, and the
// static /benchmarks/<slug>/ pages load it to wake their hidden Share button,
// so nothing here runs or renders until a reader asks for it.

import { starPrompt } from "./star-prompt.js";
import { radarCaption } from "./share-caption.js";

export const CARDS_URL = "/cards";

const SAFE_SLUG = /^[a-z0-9][a-z0-9_-]*$/;

export function benchmarkCardUrl(slug) {
  return SAFE_SLUG.test(slug || "") ? `${CARDS_URL}/${slug}.png` : "";
}

export function benchmarkPageUrl(slug, origin = window.location.origin) {
  return `${origin}/benchmarks/${slug}/`;
}

const identity = (text, values = {}) =>
  text.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ""));

function node(tag, props = {}, children = []) {
  const el = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  for (const [key, value] of Object.entries(attrs || {})) el.setAttribute(key, value);
  for (const child of children) if (child) el.append(child);
  return el;
}

let dialog = null;
// Counts openings of the shared dialog, so a slow card can tell it was replaced.
let openings = 0;

function ensureDialog() {
  if (dialog?.isConnected) return dialog;
  dialog = node("dialog", {
    className: "share-card-dialog",
    attrs: { "aria-labelledby": "share-card-title" },
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.body.append(dialog);
  return dialog;
}

// One request per opened card, shared by Share, Copy and Download.
function cardBlob(url) {
  let pending = null;
  return () => {
    pending ||= fetch(url, { mode: "cors" }).then((response) => {
      if (!response.ok) throw new Error(`card ${response.status}`);
      return response.blob();
    });
    return pending;
  };
}

function flash(button, label, done) {
  button.textContent = done;
  setTimeout(() => { button.textContent = label; }, 1600);
}

const coarsePointer = () => Boolean(window.matchMedia?.("(pointer: coarse)")?.matches);

// How to paste the card into X. A touch screen has no shortcut, and only Apple
// computers paste with Cmd.
function pasteHint(t) {
  if (coarsePointer()) return t("X is open in a new window. In X, tap and hold, then choose Paste to add the image.");
  const platform = navigator.userAgentData?.platform || navigator.platform || navigator.userAgent || "";
  const key = /Mac/i.test(platform) ? "⌘V" : "Ctrl+V";
  return t("X is open in a new window. Press {key} in X to add the image.", { key });
}

// A desktop browser such as Safari also offers navigator.share, and its system
// menu only added a sixth control to choose from. Phones and tablets have a
// coarse pointer and a share sheet worth opening.
function hasShareSheet() {
  return Boolean(navigator.share) && coarsePointer();
}

// The link button names what it copies. One label for three different links
// (a benchmark page, a day of the radar, a source) left readers guessing.
function linkLabel(pageUrl, t) {
  let url;
  try {
    url = new URL(pageUrl, window.location.origin);
  } catch {
    return t("Copy source link");
  }
  if (url.host !== "benchmark-radar.org" && url.host !== window.location.host) {
    return t("Copy source link");
  }
  return /^\/benchmarks\/[^/]+\/?$/.test(url.pathname) ? t("Copy benchmark link") : t("Copy page link");
}

export function openBenchmarkShare({ slug, name, t = identity }) {
  const imageUrl = benchmarkCardUrl(slug);
  if (!imageUrl) return;
  openShareDialog({
    name,
    pageUrl: benchmarkPageUrl(slug),
    imageSrc: imageUrl,
    getBlob: cardBlob(imageUrl),
    fileName: `benchmark-radar-${slug}.png`,
    missing: t("This benchmark's card is not ready yet. You can still share its link."),
    t,
  });
}

function fileSlug(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "card";
}

// A Today's radar item (issue #1019). An item the daily pipeline published a
// card for shares that card; any other item gets one drawn in the browser from
// the facts it holds. The link is the item's own source, because a radar item
// has no page here.
export function openRadarShare({ item, day = "", title, image = "", pageUrl, card = null, t = identity }) {
  const name = title || item.title || "";
  const caption = radarCaption({ item, title: name, card, pageUrl });
  const fileName = `benchmark-radar-${day ? `${day}-` : ""}${fileSlug(name)}.png`;
  if (image) {
    openShareDialog({
      name,
      caption,
      pageUrl,
      imageSrc: image,
      getBlob: cardBlob(image),
      fileName,
      missing: t("This card could not be loaded. You can still share its link."),
      t,
    });
    return;
  }
  let pending = null;
  const getBlob = () => {
    pending ||= import("./radar-card.js").then(({ cardBlob: draw, cardFacts }) =>
      draw(cardFacts(item, { day, title: name })),
    );
    return pending;
  };
  openShareDialog({
    name,
    caption,
    pageUrl,
    imageSrc: getBlob().then((blob) => URL.createObjectURL(blob)),
    getBlob,
    fileName,
    missing: t("This card could not be drawn here. You can still share its link."),
    t,
  });
}

export function openDailyShare({ name, image, caption, day, t = identity }) {
  openShareDialog({
    name, caption,
    pageUrl: `https://benchmark-radar.org/?date=${day}`,
    imageSrc: image,
    getBlob: cardBlob(image),
    fileName: `benchmark-radar-${day}-${fileSlug(name)}.png`,
    missing: t("This card could not be loaded. You can still share its link."),
    t,
  });
}

// The dialog behind every Share button: the card, one main action (Post on X),
// then the smaller ways to take the card elsewhere. ``imageSrc`` is a URL or a
// promise of one; ``getBlob`` returns the same image as a blob for Share, Copy
// image and Download.
function openShareDialog({ name, pageUrl, caption = "", imageSrc, getBlob: blob, fileName, missing, t = identity }) {
  const title = t("{name} on Benchmark Radar", { name });
  const fullText = caption || `${title}\n\n${pageUrl}`;
  const host = ensureDialog();
  // Agents read the caption and link here instead of working out which of the
  // buttons to press. The dialog is reused, so each open overwrites them.
  host.setAttribute("data-share-caption", fullText);
  host.setAttribute("data-share-link", pageUrl);
  host.setAttribute("data-share-image", "");
  const opening = ++openings;

  const status = node("p", { className: "share-card-status", attrs: { role: "status" } });
  const image = node("img", {
    className: "share-card-image",
    attrs: {
      alt: t("Share card for {name}", { name }),
      width: "1200",
      height: "630",
      decoding: "async",
    },
  });
  const imageActions = [];
  // ``icon`` names a share-card-tool-* class; styles.css draws it as a mask, so
  // the button's own text stays the label that flash() swaps.
  const action = (label, onClick, { needsImage = true, promptTrigger, icon } = {}) => {
    const button = node("button", { className: `secondary-link share-card-tool share-card-tool-${icon}`, text: label, attrs: { type: "button" } });
    button.addEventListener("click", async () => {
      try {
        await onClick(button);
        // Failed copies/download fetches never spend the shared prompt budget.
        if (promptTrigger && host.open) {
          const prompt = starPrompt(promptTrigger);
          if (prompt) host.append(prompt);
        }
      } catch (error) {
        if (error?.name === "AbortError") return;
        console.error(error);
        status.textContent = t("That did not work here. Copy the text instead.");
      }
    });
    if (needsImage) imageActions.push(button);
    return button;
  };

  // Copy text, Copy image, Download and the link, in that order; Share… ends the
  // row on phones only.
  const buttons = [];
  buttons.push(action(t("Copy text"), async (button) => {
    await navigator.clipboard.writeText(fullText);
    flash(button, t("Copy text"), t("Copied"));
  }, { needsImage: false, icon: "text" }));
  if (navigator.clipboard?.write && window.ClipboardItem) {
    buttons.push(action(t("Copy image"), async (button) => {
      // Safari only allows the write while the click is still active, so the
      // item takes the pending blob rather than waiting for it first.
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob() })]);
      flash(button, t("Copy image"), t("Copied"));
    }, { promptTrigger: "card_copy_image", icon: "image" }));
  }
  buttons.push(action(t("Download"), async () => {
    // A download attribute is ignored across origins, so save a local copy.
    const href = URL.createObjectURL(await blob());
    const link = node("a", { attrs: { href, download: fileName } });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }, { promptTrigger: "card_download", icon: "download" }));
  const copyLabel = linkLabel(pageUrl, t);
  buttons.push(action(copyLabel, async (button) => {
    await navigator.clipboard.writeText(pageUrl);
    flash(button, copyLabel, t("Copied"));
  }, { needsImage: false, promptTrigger: "card_copy_link", icon: "link" }));
  if (hasShareSheet()) {
    // share() must run while the tap still counts as user activation, which a
    // slow fetch outlasts. The card is fetched as the dialog opens and shared
    // only once it is here; until then, or without file sharing, the link goes.
    let file = null;
    blob()
      .then((data) => { file = new File([data], fileName, { type: "image/png" }); })
      .catch(() => {});
    buttons.push(action(t("Share…"), async () => {
      const payload = { title, text: fullText };
      if (file && navigator.canShare?.({ files: [file] })) payload.files = [file];
      await navigator.share(payload);
    }, { needsImage: false, icon: "share" }));
  }

  const post = new URL("https://x.com/intent/post");
  post.searchParams.set("text", fullText);
  // X's post link carries text and a URL but never a file (#1068). So the card
  // goes to the clipboard on the same click, and the reader pastes it into the
  // post. The write starts before the link opens X's tab: browsers allow it only
  // while this page has focus and the click still counts as user activation.
  // X opens in a new window that covers this dialog, so the note says what the
  // click does before it happens, and the hint says what to do once X is open.
  const canCopyCard = Boolean(navigator.clipboard?.write && window.ClipboardItem);
  const note = node("p", {
    className: "share-card-note",
    text: canCopyCard
      ? t("Copies the card image and opens X in a new window.")
      : t("Opens X in a new window with the full text."),
  });
  const hint = node("p", { className: "share-card-hint", attrs: { role: "status" } });
  const lengthNotice = node("p", { className: "share-card-help", text: t("Long caption: X Premium may be required. The full text is preserved.") });
  hint.hidden = true;
  lengthNotice.hidden = true;
  const postOnX = node("a", {
    className: "secondary-link share-card-primary",
    text: t("Post on X ↗"),
    attrs: { href: post.href, target: "_blank", rel: "noopener noreferrer" },
  });
  postOnX.addEventListener("click", () => {
    note.hidden = true;
    hint.hidden = false;
    hint.textContent = t("X is open in a new window.");
    lengthNotice.hidden = [...fullText].length <= 280;
    // A missing card keeps its own notice; there is nothing to copy or download.
    if (image.hidden) return;
    const notCopied = () => t("X is open in a new window. The image was not copied. Download it, then attach it in X.");
    if (!canCopyCard) {
      hint.textContent = notCopied();
      return;
    }
    navigator.clipboard
      .write([new ClipboardItem({ "image/png": blob() })])
      .then(() => {
        hint.textContent = pasteHint(t);
      })
      .catch(() => {
        // The card may have failed while the copy was pending; keep its notice.
        if (!image.hidden) hint.textContent = notCopied();
      });
  });

  const unavailable = () => {
    image.hidden = true;
    for (const button of imageActions) button.hidden = true;
    note.textContent = t("Opens X in a new window with the full text.");
    status.textContent = missing;
  };
  image.addEventListener("error", unavailable);
  Promise.resolve(imageSrc).then((src) => {
    image.src = src;
    // The dialog is reused, so a card still drawing when the reader opens
    // another must not write its image over the newer card's attributes.
    if (opening === openings) host.setAttribute("data-share-image", src);
    if (src.startsWith("blob:")) {
      // A drawn card is a blob URL that dies with the dialog, so the attribute
      // goes with it rather than naming an address that no longer loads.
      host.addEventListener("close", () => {
        URL.revokeObjectURL(src);
        if (opening === openings) host.setAttribute("data-share-image", "");
      }, { once: true });
    }
  }, unavailable);

  const close = node("button", {
    className: "dialog-close",
    text: "×",
    attrs: { type: "button", "aria-label": t("Close") },
  });
  close.addEventListener("click", () => host.close());
  host.replaceChildren(
    close,
    node("p", { className: "detail-source", text: "Benchmark Radar" }),
    node("h2", {
      className: "detail-title",
      text: t("Share {name}", { name }),
      attrs: { id: "share-card-title" },
    }),
    image,
    postOnX,
    note,
    hint,
    lengthNotice,
    status,
    node("div", { className: "share-card-actions" }, buttons),
  );
  if (!host.open) host.showModal();
}

// Static benchmark pages ship the button hidden, so a reader without
// JavaScript never meets a control that does nothing.
function wakeStaticButtons() {
  for (const button of document.querySelectorAll("[data-share-benchmark]")) {
    button.hidden = false;
    button.addEventListener("click", () =>
      openBenchmarkShare({ slug: button.dataset.shareBenchmark, name: button.dataset.name }),
    );
  }
}

if (typeof document !== "undefined" && document.querySelector?.("[data-share-benchmark]")) {
  wakeStaticButtons();
}
