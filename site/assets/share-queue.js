// The daily share queue (issue #1162), opened with ?share=queue.
//
// Daily X posting covers every card on the page: the top-3 summary, the
// briefing cards and the Today's radar cards. Each card already carries its
// caption, link and image (markShareable in app.js), so the queue lists what
// the page rendered rather than rebuilding it, and its scope is exactly the
// current page.
//
// A card counts as posted only once its published post URL is entered: an
// opened composer proves nothing. URLs live in localStorage so a reload keeps
// progress, and they import from and export to the posting log's CSV columns
// so another browser or an agent run does not post a card twice.

const STORE_KEY = "benchmark-radar.x-posts.v1";
const POST_URL = /^https:\/\/(?:www\.)?(?:x|twitter)\.com\/([A-Za-z0-9_]{1,15})\/status\/(\d+)/;
const LOG_COLUMNS = [
  "daily_date", "account", "card_type", "title", "source_url", "status",
  "post_url", "reply_url", "caption_status", "verified_on", "notes",
];
const KIND_LABELS = { summary: "Top 3", briefing: "Briefing", left: "Today's radar" };
const KIND_ORDER = { summary: 0, briefing: 1, left: 2 };

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

export function loadPosts(storage = window.localStorage) {
  try {
    return JSON.parse(storage.getItem(STORE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function savePosts(posts, storage = window.localStorage) {
  storage.setItem(STORE_KEY, JSON.stringify(posts));
}

export function postKey({ kind, day, source }) {
  return kind === "summary" ? `summary|${day}` : `${kind}|${source}`;
}

export function parsePostUrl(value) {
  const match = POST_URL.exec(String(value || "").trim());
  return match ? { url: `https://x.com/${match[1]}/status/${match[2]}`, account: match[1] } : null;
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') { cell += '"'; index += 1; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { row.push(cell); cell = ""; }
    else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += char;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((cells) => cells.some((value) => value.trim()));
}

// Posting-log rows with a post URL mark their cards as posted. Rows without
// a header are read in the log's column order.
export function importLog(text, posts) {
  const rows = parseCsv(text);
  const header = rows[0]?.includes("card_type") ? rows.shift() : LOG_COLUMNS;
  let added = 0;
  for (const cells of rows) {
    const row = Object.fromEntries(header.map((name, index) => [name, cells[index] || ""]));
    const parsed = parsePostUrl(row.post_url);
    if (!parsed || row.status !== "posted" || !KIND_LABELS[row.card_type]) continue;
    const key = postKey({ kind: row.card_type, day: row.daily_date, source: row.source_url });
    if (!posts[key]) added += 1;
    posts[key] = {
      post_url: parsed.url, account: parsed.account, card_type: row.card_type,
      daily_date: row.daily_date, title: row.title, source_url: row.source_url,
      verified_on: row.verified_on,
    };
  }
  return added;
}

export function exportLog(posts) {
  const lines = Object.values(posts).map((post) => [
    post.daily_date, post.account, post.card_type, post.title, post.source_url, "posted",
    post.post_url, "", "complete", post.verified_on, "Recorded in the share queue.",
  ].map(csvCell).join(","));
  return [LOG_COLUMNS.join(","), ...lines].join("\n");
}

function chicagoDate() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago" }).format(new Date());
}

function pageCards() {
  const seen = new Set();
  return [...document.querySelectorAll("[data-share-key]")]
    .filter((el) => !el.closest(".share-queue") && el.getClientRects().length)
    .map((el) => ({
      el,
      key: el.dataset.shareKey,
      kind: el.dataset.shareKind,
      day: el.dataset.shareDate,
      title: el.dataset.shareTitle,
      source: el.dataset.shareSource,
      caption: el.dataset.shareCaption,
      image: el.dataset.shareImage,
    }))
    .filter((card) => (seen.has(card.key) ? false : seen.add(card.key)))
    .sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind]);
}

let panel = null;

export function openShareQueue({ t = identity } = {}) {
  if (panel?.isConnected) {
    panel.show();
    return panel;
  }
  panel = node("dialog", { className: "share-queue", attrs: { "aria-labelledby": "share-queue-title" } });
  document.body.append(panel);
  let posts = loadPosts();
  let timer = 0;

  const render = () => {
    const cards = pageCards();
    for (const card of cards) {
      const post = posts[card.key];
      if (post) card.el.setAttribute("data-share-posted-url", post.post_url);
      else card.el.removeAttribute("data-share-posted-url");
    }
    const done = cards.filter((card) => posts[card.key]).length;
    const pageStatus = document.getElementById("today-page-status")?.textContent || "";
    const close = node("button", { className: "dialog-close", text: "×", attrs: { type: "button", "aria-label": t("Close") } });
    close.addEventListener("click", () => panel.close());

    const rows = cards.map((card) => queueRow(card, posts[card.key], t, {
      save(url) {
        const parsed = parsePostUrl(url);
        if (!parsed) return false;
        posts[card.key] = {
          post_url: parsed.url, account: parsed.account, card_type: card.kind,
          daily_date: card.day, title: card.title, source_url: card.source,
          verified_on: chicagoDate(),
        };
        savePosts(posts);
        render();
        return true;
      },
      undo() {
        delete posts[card.key];
        savePosts(posts);
        render();
      },
    }));

    const logBox = node("textarea", {
      className: "share-queue-log",
      attrs: { rows: "4", "aria-label": t("Posting log rows"), placeholder: t("Paste posting-log.csv rows here") },
    });
    const logStatus = node("p", { className: "share-card-status", attrs: { role: "status" } });
    const importButton = node("button", { className: "secondary-link", text: t("Import log"), attrs: { type: "button" } });
    importButton.addEventListener("click", () => {
      const added = importLog(logBox.value, posts);
      savePosts(posts);
      render();
      panel.querySelector(".share-queue-log-status").textContent = t("{count} posts imported.", { count: added });
    });
    const exportButton = node("button", { className: "secondary-link", text: t("Copy log rows"), attrs: { type: "button" } });
    exportButton.addEventListener("click", async () => {
      await navigator.clipboard.writeText(exportLog(posts));
      logStatus.textContent = t("Copied {count} rows.", { count: Object.keys(posts).length });
    });
    logStatus.classList.add("share-queue-log-status");

    panel.replaceChildren(
      close,
      node("h2", { className: "detail-title", text: t("Share queue"), attrs: { id: "share-queue-title" } }),
      node("p", { className: "share-queue-scope", text: t("Scope: this page only. {status}", { status: pageStatus }) }),
      node("p", {
        className: "share-queue-progress",
        text: t("{done} of {total} posted", { done, total: cards.length }),
      }),
      node("ol", { className: "share-queue-list" }, rows),
      node("details", { className: "share-queue-sync" }, [
        node("summary", { text: t("Posting log") }),
        logBox,
        node("div", { className: "share-card-actions" }, [importButton, exportButton]),
        logStatus,
      ]),
    );
  };

  // Cards render after data loads and again on paging or a date change, so
  // the queue follows the page instead of freezing what it saw first.
  const observer = new MutationObserver((records) => {
    if (records.every((record) => panel.contains(record.target))) return;
    clearTimeout(timer);
    timer = setTimeout(render, 150);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener("storage", (event) => {
    if (event.key !== STORE_KEY) return;
    posts = loadPosts();
    render();
  });
  render();
  panel.show();
  return panel;
}

function queueRow(card, post, t, { save, undo }) {
  const share = node("button", { className: "secondary-link share-card-primary", text: t("Share"), attrs: { type: "button" } });
  share.addEventListener("click", () => {
    card.el.querySelector("a, button")?.click();
  });
  const copy = node("button", { className: "secondary-link", text: t("Copy text"), attrs: { type: "button" } });
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(card.caption);
    copy.textContent = t("Copied");
    setTimeout(() => { copy.textContent = t("Copy text"); }, 1600);
  });

  let record;
  if (post) {
    const remove = node("button", { className: "secondary-link", text: t("Undo"), attrs: { type: "button" } });
    remove.addEventListener("click", undo);
    record = node("p", { className: "share-queue-posted" }, [
      node("span", { text: `${t("Posted")}: ` }),
      node("a", { text: post.post_url, attrs: { href: post.post_url, target: "_blank", rel: "noopener noreferrer" } }),
      remove,
    ]);
  } else {
    const input = node("input", {
      attrs: { type: "url", inputmode: "url", placeholder: "https://x.com/…/status/…", "aria-label": t("Published post URL for {title}", { title: card.title }) },
    });
    const mark = node("button", { className: "secondary-link", text: t("Mark posted"), attrs: { type: "button" } });
    const error = node("span", { className: "share-queue-error", attrs: { role: "status" } });
    mark.addEventListener("click", () => {
      if (!save(input.value)) error.textContent = t("Enter the published post URL.");
    });
    record = node("p", { className: "share-queue-record" }, [input, mark, error]);
  }

  return node("li", {
    className: `share-queue-item${post ? " is-posted" : ""}`,
    attrs: { "data-share-key": card.key, "data-share-kind": card.kind },
  }, [
    card.image ? node("img", { className: "share-queue-thumb", attrs: { src: card.image, alt: "", loading: "lazy", width: "120", height: "63" } }) : null,
    node("div", { className: "share-queue-body" }, [
      node("p", { className: "share-queue-kind", text: t(KIND_LABELS[card.kind] || card.kind) }),
      node("p", { className: "share-queue-title", text: card.title }),
      node("details", {}, [
        node("summary", { text: t("Caption") }),
        node("pre", { className: "share-queue-caption", text: card.caption }),
      ]),
      node("div", { className: "share-queue-actions" }, [share, copy]),
      record,
    ]),
  ]);
}
