// Share any benchmark as an image card (issue #671).
//
// Every catalog benchmark has a 1200x630 card at /cards/<slug>.png, which
// scripts/render_share_images.py draws during the Pages build, so the card
// deploys with the page that names it. src/benchmark_radar/cards.py says why
// it is served from the site's own host.
// This module only fetches the card a reader asked for. A benchmark whose card
// is missing still shares its link.
//
// The dashboard imports this on demand when a reader presses Share, and the
// static /benchmarks/<slug>/ pages load it to wake their hidden Share button,
// so nothing here runs or renders until a reader asks for it.

import { starPrompt } from "./star-prompt.js";

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

export function openBenchmarkShare({ slug, name, t = identity }) {
  const imageUrl = benchmarkCardUrl(slug);
  if (!imageUrl) return;
  const pageUrl = benchmarkPageUrl(slug);
  const title = t("{name} on Benchmark Radar", { name });
  const blob = cardBlob(imageUrl);
  const host = ensureDialog();

  const status = node("p", { className: "share-card-status", attrs: { role: "status" } });
  const image = node("img", {
    className: "share-card-image",
    attrs: {
      src: imageUrl,
      alt: t("Share card for {name}", { name }),
      width: "1200",
      height: "630",
      decoding: "async",
    },
  });
  const imageActions = [];
  const action = (label, onClick, { needsImage = true, promptTrigger } = {}) => {
    const button = node("button", { className: "secondary-link", text: label, attrs: { type: "button" } });
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
        status.textContent = t("That did not work here. Copy the link instead.");
      }
    });
    if (needsImage) imageActions.push(button);
    return button;
  };

  const buttons = [];
  if (navigator.share) {
    // share() must run while the tap still counts as user activation, which a
    // slow fetch outlasts. The card is fetched as the dialog opens and shared
    // only once it is here; until then, or without file sharing, the link goes.
    let file = null;
    blob()
      .then((data) => { file = new File([data], `${slug}.png`, { type: "image/png" }); })
      .catch(() => {});
    buttons.push(action(t("Share…"), async () => {
      const payload = { title, text: title, url: pageUrl };
      if (file && navigator.canShare?.({ files: [file] })) payload.files = [file];
      await navigator.share(payload);
    }, { needsImage: false }));
  }
  if (navigator.clipboard?.write && window.ClipboardItem) {
    buttons.push(action(t("Copy image"), async (button) => {
      // Safari only allows the write while the click is still active, so the
      // item takes the pending blob rather than waiting for it first.
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob() })]);
      flash(button, t("Copy image"), t("Copied"));
    }, { promptTrigger: "card_copy_image" }));
  }
  buttons.push(action(t("Download"), async () => {
    // A download attribute is ignored across origins, so save a local copy.
    const href = URL.createObjectURL(await blob());
    const link = node("a", { attrs: { href, download: `benchmark-radar-${slug}.png` } });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }, { promptTrigger: "card_download" }));
  buttons.push(action(t("Copy link"), async (button) => {
    await navigator.clipboard.writeText(pageUrl);
    flash(button, t("Copy link"), t("Copied"));
  }, { needsImage: false, promptTrigger: "card_copy_link" }));
  const post = new URL("https://x.com/intent/post");
  post.searchParams.set("text", title);
  post.searchParams.set("url", pageUrl);
  buttons.push(node("a", {
    className: "secondary-link",
    text: t("Post on X ↗"),
    attrs: { href: post.href, target: "_blank", rel: "noopener noreferrer" },
  }));

  image.addEventListener("error", () => {
    image.hidden = true;
    for (const button of imageActions) button.hidden = true;
    status.textContent = t("This benchmark's card is not ready yet. You can still share its link.");
  });

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
