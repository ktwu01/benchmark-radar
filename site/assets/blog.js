// Client behavior for the generated blog pages.
//
// The chrome around the reading pane is extracted from site/index.html at
// build time, so this script lights up exactly the bits the dashboard's
// app.js would have handled — with the same visible contracts: the language
// toggle flips title, glyph, and aria-pressed; the repository Star badge fills
// its count from the same GitHub endpoint; the footer share control uses
// navigator.share with a clipboard fallback; and the chrome itself translates
// from the same reviewed I18N table app.js uses, baked into the page at build
// time as #chrome-i18n.
//
// The body's language blocks stay a pure visibility change and never a fetch.
// Pages without a stored translation ship no toggle at all: a control that
// switches to identical text is broken, and translating here would publish
// text nobody reviewed.
//
// The stored preference is shared with the dashboard under the same key, so a
// reader who chose 中文 there keeps it here. Only an explicit click writes to
// it. Falling back to English on an untranslated brief must not quietly reset
// the preference the reader set somewhere else.
const LANG_STORAGE_KEY = "benchmark-radar:lang";
const LANGS = ["en", "zh"];

function savedLanguage() {
  const param = new URLSearchParams(window.location.search).get("lang");
  if (LANGS.includes(param)) return param;
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch (_) {
    // Storage can be unavailable in private browsing and text-only readers.
  }
  return "en";
}

let chromeI18N = null;
try {
  const baked = document.getElementById("chrome-i18n");
  if (baked) chromeI18N = JSON.parse(baked.textContent);
} catch (error) {
  console.error("Failed to parse #chrome-i18n payload:", error);
}
function t(key, params) {
  let value = (document.documentElement.lang === "zh-CN" ? chromeI18N?.[key] : null) ?? key;
  if (params) {
    for (const [name, replacement] of Object.entries(params)) {
      value = value.replaceAll(`{${name}}`, String(replacement));
    }
  }
  return value;
}

// The same three passes app.js applies, including the repo-badge tooltip
// contract: a data-i18n-title on a badge becomes the CSS-rendered
// data-tooltip instead of the browser's delayed native title.
function applyChromeI18n() {
  if (!chromeI18N) return;
  const zh = document.documentElement.lang === "zh-CN";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    if (node.dataset.i18nEn === undefined) {
      node.dataset.i18nEn = node.textContent;
    }
    node.textContent = zh ? (chromeI18N[node.dataset.i18n] ?? node.dataset.i18nEn) : node.dataset.i18nEn;
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    if (node.dataset.i18nTitleEn === undefined) {
      node.dataset.i18nTitleEn = node.getAttribute("title") || "";
    }
    const resolved = zh ? (chromeI18N[node.dataset.i18nTitle] ?? node.dataset.i18nTitleEn) : node.dataset.i18nTitleEn;
    if (node.classList.contains("repo-badge")) {
      if (zh) {
        node.setAttribute("data-tooltip", resolved);
        node.removeAttribute("title");
        if (!node.hasAttribute("aria-label")) node.setAttribute("aria-label", resolved);
      } else {
        node.removeAttribute("data-tooltip");
        node.setAttribute("title", resolved);
      }
    } else {
      node.setAttribute("title", resolved);
    }
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    if (node.dataset.i18nAriaEn === undefined) {
      node.dataset.i18nAriaEn = node.getAttribute("aria-label") || "";
    }
    const resolved = zh ? (chromeI18N[node.dataset.i18nAria] ?? node.dataset.i18nAriaEn) : node.dataset.i18nAriaEn;
    node.setAttribute("aria-label", resolved);
  });
}

function showLanguage(language, { remember = false } = {}) {
  const hasZh = Boolean(document.querySelector('[data-lang-content="zh"]'));
  document.querySelectorAll("[data-lang-content]").forEach((node) => {
    if (node.dataset.langContent === "zh") {
      node.hidden = language !== "zh";
    } else if (node.dataset.langContent === "en") {
      node.hidden = language === "zh" && hasZh;
    }
  });
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  applyChromeI18n();
  const toggle = document.getElementById("lang-toggle");
  if (toggle) {
    const zh = language === "zh";
    const titleKey = zh ? "Switch to English" : "Switch to Chinese (中文)";
    toggle.setAttribute("aria-pressed", String(zh));
    toggle.setAttribute("aria-label", t(titleKey));
    toggle.setAttribute("data-tooltip", t(titleKey));
    toggle.setAttribute("title", "");
    const label = document.getElementById("lang-toggle-label");
    if (label) label.textContent = zh ? "EN" : "中";
  }
  if (!remember) return;
  try {
    localStorage.setItem(LANG_STORAGE_KEY, language);
  } catch (_) {
    // The page still switches even when preference storage is unavailable.
  }
}

const langToggle = document.getElementById("lang-toggle");
if (langToggle) {
  langToggle.addEventListener("click", () => {
    const current = document.documentElement.lang === "zh-CN" ? "zh" : "en";
    showLanguage(current === "zh" ? "en" : "zh", { remember: true });
  });
}
showLanguage(savedLanguage());

// Repository star count. Mirrors app.js's renderStarCount: a rate-limited API
// must never surface as an error because the GitHub link still works blank.
const REPO_SLUG = "ktwu01/benchmark-radar";

function setStarCount(value) {
  const badge = document.getElementById("badge-stars");
  const node = badge?.querySelector("[data-count]");
  if (!node) return;
  const count = Number(value || 0).toLocaleString();
  node.textContent = count;
  badge.setAttribute("aria-label", t("Star this repository on GitHub. {count} stars", { count }));
}

async function renderStarCount() {
  try {
    const response = await fetch(`https://api.github.com/repos/${REPO_SLUG}`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) return;
    const repo = await response.json();
    setStarCount(repo.stargazers_count);
  } catch (error) {
    console.debug("Repository star count unavailable", error);
  }
}
renderStarCount();

// The footer's share control, same behavior as the dashboard's.
const shareButton = document.getElementById("share-radar");
if (shareButton) {
  shareButton.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const shareData = {
      title: document.title,
      text: "Share Benchmark Radar",
      url: window.location.href,
    };
    try {
      if (navigator.share) await navigator.share(shareData);
      else await navigator.clipboard.writeText(shareData.url);
      button.textContent = "Copied";
      setTimeout(() => {
        button.textContent = "Share";
      }, 1600);
    } catch (error) {
      if (error?.name !== "AbortError") console.error(error);
    }
  });
}

// The section nav scrolls horizontally on narrow screens, and Blog is its last
// item, so on a phone the reader lands on a brief with the active tab parked
// off the right edge. Nudging it into view keeps the "you are here" state
// visible; the dashboard needs no equivalent because its default view is the
// leftmost item.
const activeNav = document.querySelector('.view-nav [aria-current="page"]');
if (activeNav?.scrollIntoView) {
  activeNav.scrollIntoView({ block: "nearest", inline: "nearest" });
}
