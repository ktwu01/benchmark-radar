const CATEGORY_COLORS = {
  benchmark: "#255ea8",
  evaluation: "#dc633f",
  dataset: "#4c948b",
  data_quality: "#c99327",
  agentic: "#756aa8",
};
const FALLBACK_COLORS = ["#756aa8", "#397f9a", "#a4576d", "#70833d"];
// A stable color per reporting organization, so the adoption frontier reads at a
// glance which organization moved the count (issue #178, HLE/harbor style).
// Unknown organizations fall back to a rotating palette rather than one gray,
// so a new entrant stays distinguishable while the known set stays stable.
const ORGANIZATION_COLORS = {
  OpenAI: "#4c9aff",
  Anthropic: "#e8995a",
  "Google DeepMind": "#4c948b",
  Meta: "#7fb0f5",
  DeepSeek: "#5aa7e8",
  Qwen: "#c99327",
  Mistral: "#f5a05a",
  xAI: "#8a7ec8",
  "Moonshot AI": "#a4576d",
  "Z.ai": "#6ab8a0",
};
const ORGANIZATION_FALLBACK_COLORS = ["#75a6c2", "#c27aa0", "#9aa05a", "#5aa08a", "#b08a4c"];
function organizationColor(organization) {
  const known = ORGANIZATION_COLORS[organization];
  if (known) return known;
  let hash = 0;
  for (const char of String(organization)) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return ORGANIZATION_FALLBACK_COLORS[hash % ORGANIZATION_FALLBACK_COLORS.length];
}
// A real brand glyph for each reporting organization, drawn inside the adoption
// circle and the org-key chip. Paths are the monochrome brand marks (24-unit
// viewBox) from the simple-icons set. OpenAI is absent there because OpenAI
// restricts use of its mark, so a six-petal rosette stands in for it; xAI has
// no published glyph, so a bold X marks it. The mark provides immediate brand
// recognition at a glance while the colored circle disambiguates any two whose
// glyphs read similarly at small size.
const ORGANIZATION_ICONS = {
  OpenAI: [
    "M11.90,12.0 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0M8.90,6.803847577293368 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0M2.90,6.803847577293368 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0M-0.10,12.0 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0M2.90,17.196152422706632 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0M8.90,17.196152422706632 a 6.1,6.1 0 1,0 12.20,0 a 6.1,6.1 0 1,0 -12.20,0",
  ],
  Anthropic: [
    "M17.3041 3.541h-3.6718l6.696 16.918H24Zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409Zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456Z",
  ],
  "Google DeepMind": [
    "M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z",
  ],
  Meta: [
    "M6.915 4.03c-1.968 0-3.683 1.28-4.871 3.113C.704 9.208 0 11.883 0 14.449c0 .706.07 1.369.21 1.973a6.624 6.624 0 0 0 .265.86 5.297 5.297 0 0 0 .371.761c.696 1.159 1.818 1.927 3.593 1.927 1.497 0 2.633-.671 3.965-2.444.76-1.012 1.144-1.626 2.663-4.32l.756-1.339.186-.325c.061.1.121.196.183.3l2.152 3.595c.724 1.21 1.665 2.556 2.47 3.314 1.046.987 1.992 1.22 3.06 1.22 1.075 0 1.876-.355 2.455-.843.542-.939.88-1.503 1.163-2.176.292-.779.46-1.63.46-2.414 0-2.72-.615-5.16-1.838-7.139l-1.235 2.182c-1.903 3.363-2.846 5.018-2.846 5.018-1.142 2.02-3.064 6.403-3.064 6.403-0.507.085-1.022.123-1.522.123-1.047 0-1.876-.049-2.435-.5-.497-.4-.764-.905-.87-1.5.14.05.3.09.45.13.52.22 1.17.26 1.83.26.675 0 1.38-.13 2.06-.5-.34-.3-.62-.66-.78-1.05-.46-1.1-.67-2.37-.67-3.63 0-2.38.4-4.9 1.3-6.85C4.9 5.06 5.8 4.03 6.915 4.03zm.003.553c-1.265 0-2.058.791-2.675 1.446-.307.327-.737.871-1.234 1.579l-1.02 1.566c-.757 1.163-1.882 3.017-2.837 4.338-1.191 1.649-1.81 1.817-2.486 1.817-.524 0-1.038-.237-1.383-.794-.263-.426-.464-1.13-.464-2.046 0-2.221.63-4.535 1.66-6.088.454-.687.964-1.226 1.533-1.533a2.264 2.264 0 0 1 1.088-.285zm13.232 1.5c-1.968 0-3.683 1.28-4.871 3.113-1.34 2.065-2.044 4.74-2.044 7.306 0 .706.07 1.369.21 1.973a6.624 6.624 0 0 0 .265.86 5.297 5.297 0 0 0 .371.761c.696 1.159 1.818 1.927 3.593 1.927 1.497 0 2.633-.671 3.965-2.444.76-1.012 1.145-1.626 2.664-4.32l.756-1.339.186-.325c.061.1.121.196.183.3l2.152 3.595c.724 1.21 1.665 2.556 2.47 3.314 1.046.987 1.992 1.22 3.06 1.22 1.075 0 1.876-.355 2.455-.843.542-.939.861-2.127.861-3.745 0-2.72-.681-5.357-2.084-7.45-1.282-1.912-2.957-2.93-4.716-2.93z",
  ],
  DeepSeek: [
    "M23.748 4.651c-.254-.124-.364.113-.512.233-.051.04-.094.09-.137.137-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.155-.708-.311-.955-.65-.172-.24-.219-.509-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.094.172.187.129.323-.082.28-.18.553-.266.833-.055.179-.137.218-.328.14a5.5 5.5 0 0 1-1.737-1.179c-.857-.828-1.631-1.743-2.597-2.46a12 12 0 0 0-.689-.47c-.985-.957.13-1.743.387-1.836.27-.098.094-.433-.778-.428-.872.003-1.67.295-2.687.685a3 3 0 0 1-.465.136 9.6 9.6 0 0 0-2.883-.101c-1.885.21-3.39 1.1-4.497 2.622C.082 8.776-.231 10.854.152 13.02c.403 2.284 1.568 4.175 3.36 5.653 1.857 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.132-.284 4.994-1.86.47.234.962.328 1.78.398.629.058 1.235-.031 1.705-.129.735-.155.684-.836.418-.961-2.155-1.004-1.682-.595-2.112-.926 1.095-1.295 2.768-3.598 3.284-6.733.05-.346.115-.834.108-1.114-.004-.171.035-.238.23-.257a4.2 4.2 0 0 0 1.545-.475c1.397-.763 1.96-2.016 2.093-3.517.02-.23-.004-.467-.247-.588M11.58 18.168c-2.088-1.642-3.101-2.183-3.52-2.16-.39.024-.32.472-.234.763.09.288.207.487.371.74.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.168-1.361-.801-2.5-1.86-3.301-3.306-.775-1.393-1.225-2.888-1.299-4.482-.02-.385.094-.522.477-.592a4.7 4.7 0 0 1 1.53-.038c2.131.311 3.946 1.264 5.467 2.774.868.86 1.525 1.887 2.202 2.89.72 1.066 1.494 2.082 2.48 2.915.348.291.626.513.892.677-.802.09-2.14.109-3.055-.615zm1.001-6.44a.306.306 0 0 1 .415-.287.3.3 0 0 1 .113.074.3.3 0 0 1 .086.214c0 .17-.136.307-.308.307a.303.303 0 0 1-.306-.307m3.11 1.596c-.2.081-.4.151-.591.16a1.25 1.25 0 0 1-.798-.254c-.274-.23-.47-.358-.551-.758a1.7 1.7 0 0 1 .015-.588c.07-.327-.007-.537-.238-.727-.188-.156-.426-.199-.689-.199a.6.6 0 0 1-.254-.078.253.253 0 0 1-.114-.358 1 1 0 0 1 .192-.21c.356-.202.767-.136 1.146.016.352.144.618.408 1.001.782.392.451.462.576.685.915.176.264.336.536.446.848.066.194-.02.353-.25.45",
  ],
  Qwen: [
    "M23.919 14.545 20.817 9.17l1.47-2.544a.56.56 0 0 0 0-.566l-1.633-2.83a.57.57 0 0 0-.49-.283h-6.207L12.487.402a.57.57 0 0 0-.49-.284H8.732a.56.56 0 0 0-.49.284L5.139 5.775h-2.94a.56.56 0 0 0-.49.284L.077 8.887a.56.56 0 0 0 0 .567L3.18 14.83l-1.47 2.545a.56.56 0 0 0 0 .566l1.634 2.83a.57.57 0 0 0 .49.283h6.205l1.47 2.545a.57.57 0 0 0 .49.284h3.266a.57.57 0 0 0 .49-.284l3.104-5.375h2.94a.57.57 0 0 0 .49-.283l1.634-2.828a.55.55 0 0 0-.004-.568M8.733.686l1.634 2.828-1.634 2.828H21.8L20.164 9.17H7.425L5.63 6.06Zm1.306 19.801-6.205-.002 1.634-2.83h3.265L2.201 6.344h3.267q3.182 5.517 6.367 11.032zm10.124-5.66L18.53 12l-6.532 11.315-1.634-2.83c2.129-3.673 4.25-7.351 6.373-11.028h3.592l3.102 5.374z",
  ],
  Mistral: [
    "M17.143 3.429v3.428h-3.429v3.429h-3.428V6.857H6.857V3.43H3.43v13.714H0v3.428h10.286v-3.428H6.857v-3.429h3.429v3.429h3.429v-3.429h3.428v3.429h-3.428v3.428H24v-3.428h-3.43V3.429z",
  ],
  xAI: [
    "M23 20.168 14.832 12 23 3.832 20.168 1 12 9.168 3.832 1 1 3.832 9.168 12 1 20.168 3.832 23 12 14.832 20.168 23Z",
  ],
  "Moonshot AI": [
    "m1.053 16.91 9.538 2.55a21 20.981 0 0 0 .06 2.031l5.956 1.592a12 11.99 0 0 1-15.554-6.172m-1.02-5.79 11.352 3.035a21 20.981 0 0 0-.469 2.01l10.817 2.89a12 11.99 0 0 1-1.845 2.004L.658 15.918a12 11.99 0 0 1-.625-4.796m1.593-5.146L13.573 9.17a21 20.981 0 0 0-1.01 1.874l11.297 3.02a21 20.981 0 0 1-.67 2.362l-11.55-3.087L.125 10.26a12 11.99 0 0 1 1.499-4.285ZM6.067 1.58l11.285 3.016a21 20.981 0 0 0-1.688 1.719l7.824 2.091a21 20.981 0 0 1 .513 2.664L2.107 5.218a12 11.99 0 0 1 3.96-3.638M21.68 4.866 7.222 1.003A12 11.99 0 0 1 21.68 4.866",
  ],
  "Z.ai": [
    "M12.606 1.806l-1.677 2.388c-0.258 0.374-0.697 0.606-1.161 0.606h-9.162V1.794C0.594 1.806 12.606 1.806 12.606 1.806zM24 1.806L9.6 22.206 0 22.206 14.4 1.806zM11.394 22.206l1.69-2.4c0.258-0.374 0.697-0.606 1.161-0.606h9.149v3.006H11.394z",
  ],
};
// An unknown organization gets a neutral spark; rare enough that a rotating
// color still carries the identity, and no glyph beats a wrong brand mark.
const ORGANIZATION_FALLBACK_ICON = "M12 2l2.1 6.9L21 11l-6.9 2.1L12 20l-2.1-6.9L3 11l6.9-2.1L12 2z";
function organizationIcon(organization) {
  return ORGANIZATION_ICONS[organization] || [ORGANIZATION_FALLBACK_ICON];
}

// Score points identify models, not just the companies that published them.
// Use model-family marks where the family has its own recognizable identity;
// otherwise the organization mark remains the honest fallback. The paths are
// monochrome 24-unit marks from Lobe Icons (MIT licensed).
const MODEL_FAMILY_ICONS = {
  Claude: [
    "M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z",
  ],
  Gemini: [
    "M20.616 10.835a14.147 14.147 0 01-4.45-3.001 14.111 14.111 0 01-3.678-6.452.503.503 0 00-.975 0 14.134 14.134 0 01-3.679 6.452 14.155 14.155 0 01-4.45 3.001c-.65.28-1.318.505-2.002.678a.502.502 0 000 .975c.684.172 1.35.397 2.002.677a14.147 14.147 0 014.45 3.001 14.112 14.112 0 013.679 6.453.502.502 0 00.975 0c.172-.685.397-1.351.677-2.003a14.145 14.145 0 013.001-4.45 14.113 14.113 0 016.453-3.678.503.503 0 000-.975 13.245 13.245 0 01-2.003-.678z",
  ],
  Grok: [
    "M9.27 15.29l7.978-5.897c.391-.29.95-.177 1.137.272.98 2.369.542 5.215-1.41 7.169-1.951 1.954-4.667 2.382-7.149 1.406l-2.711 1.257c3.889 2.661 8.611 2.003 11.562-.953 2.341-2.344 3.066-5.539 2.388-8.42l.006.007c-.983-4.232.242-5.924 2.75-9.383.06-.082.12-.164.179-.248l-3.301 3.305v-.01L9.267 15.292M7.623 16.723c-2.792-2.67-2.31-6.801.071-9.184 1.761-1.763 4.647-2.483 7.166-1.425l2.705-1.25a7.808 7.808 0 00-1.829-1A8.975 8.975 0 005.984 5.83c-2.533 2.536-3.33 6.436-1.962 9.764 1.022 2.487-.653 4.246-2.34 6.022-.599.63-1.199 1.259-1.682 1.925l7.62-6.815",
  ],
};

function modelIcon(model, organization) {
  const name = String(model || "");
  if (/\bclaude\b/i.test(name)) return MODEL_FAMILY_ICONS.Claude;
  if (/\bgemini\b/i.test(name)) return MODEL_FAMILY_ICONS.Gemini;
  if (/\bgrok\b/i.test(name)) return MODEL_FAMILY_ICONS.Grok;
  return organizationIcon(organization);
}

// Render one organization's brand glyph as SVG path elements inside a scaled
// group. The mark is a single path per organization (viewBox 0 0 24 24); the
// group transforms place it centred on (cx, cy) at `size` units across.
function iconGlyph(paths, cx, cy, size, className, color = null) {
  const scale = size / 24;
  const g = svgElement("g", {
    transform: `translate(${cx} ${cy}) scale(${scale}) translate(-12 -12)`,
    class: className,
    ...(color ? { style: `color: ${color}` } : {}),
    "aria-hidden": "true",
  });
  for (const d of paths) {
    g.append(svgElement("path", { d, fill: "currentColor" }));
  }
  return g;
}

function brandGlyph(organization, cx, cy, size, className) {
  return iconGlyph(organizationIcon(organization), cx, cy, size, className);
}

function modelGlyph(model, organization, cx, cy, size, className) {
  return iconGlyph(
    modelIcon(model, organization),
    cx,
    cy,
    size,
    className,
    organizationColor(organization),
  );
}
const ALL_DATES_PAGE_SIZE = 100;
// Snapshots recorded before SourceHealth.method existed carry no method
// field; this fills the gap for historical dates only (issue #174).
const LEGACY_SOURCE_COLLECTION_METHODS = {
  arxiv: "RSS",
  huggingface: "API",
  github: "API",
  openreview: "API",
  semantic_scholar: "API",
  github_releases: "API",
  first_party_feeds: "RSS/Atom",
  openalex: "API",
  brave: "API",
};

const byId = (id) => document.getElementById(id);

// Interface language. English is the truth inside this file: every UI string
// is emitted through t(), which returns the key unchanged until a zh entry
// exists below, so the default build stays byte-for-byte English and the
// dictionary is auditable against the code that renders each string.
const LANGS = ["en", "zh"];
const LANG_HTML = { en: "en", zh: "zh-CN" };
const LANG_STORAGE_KEY = "benchmark-radar:lang";

let lang = "en";

function getLang() {
  return lang;
}

function setLang(next) {
  lang = LANGS.includes(next) ? next : "en";
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(LANG_STORAGE_KEY, lang);
    }
  } catch (_) {
    // Storage can be unavailable (private browsing, some readers).
  }
  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.setAttribute("lang", LANG_HTML[lang]);
  }
}

function t(key, params) {
  let value = I18N[getLang()]?.[key] ?? key;
  if (params) {
    for (const [name, replacement] of Object.entries(params)) {
      value = value.replaceAll(`{${name}}`, String(replacement));
    }
  }
  return value;
}

// The day's GPT prose (briefing bullets, caveat, Q&A answers) is English by
// default. Under the Chinese interface the snapshot's zh rendering is
// preferred when the run produced it (issue #231); a day whose zh fields are
// absent falls back to English.
function l10nProse(en, zh) {
  return getLang() === "zh" && zh ? zh : en;
}

function initialLang() {
  const param = new URLSearchParams(window.location.search).get("lang");
  if (LANGS.includes(param)) return param;
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch (_) {
    // Storage can be unavailable (private browsing, some readers).
  }
  return "en";
}

// Static text in index.html is annotated with data-i18n / data-i18n-title /
// data-i18n-placeholder / data-i18n-aria slots keyed by this dictionary; the
// first pass captures the English default so a toggle back restores it exactly.
// Captured defaults that contain inline markup (<a>, <strong>, <em>...) are
// kept as live nodes rather than as a serialized string, so restoring a
// translated paragraph does not strip its link (serializing the captured nodes
// to a string for storage is forbidden project-wide).
const staticI18nMarkup = new Map();

function applyStaticI18n() {
  if (typeof document === "undefined") return;
  const table = I18N[getLang()] || {};
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    if (node.dataset.i18nEn === undefined) {
      node.dataset.i18nEn = node.textContent;
      if (node.querySelector("a,strong,em,code")) {
        staticI18nMarkup.set(node, node.cloneNode(true));
      }
    }
    const text = table[node.dataset.i18n];
    if (text !== undefined) {
      if (text.includes("<")) {
        node.replaceChildren();
        node.insertAdjacentHTML("afterbegin", text);
      } else {
        node.textContent = text;
      }
    } else if (staticI18nMarkup.has(node)) {
      node.replaceChildren(staticI18nMarkup.get(node).cloneNode(true));
    } else {
      node.textContent = node.dataset.i18nEn;
    }
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    if (node.dataset.i18nTitleEn === undefined) {
      node.dataset.i18nTitleEn = node.getAttribute("title") || "";
    }
    const text = table[node.dataset.i18nTitle];
    const resolved = text ?? node.dataset.i18nTitleEn;
    if (node.classList.contains("repo-badge")) {
      // Native title tooltips wait roughly a second before appearing. Header
      // utilities need immediate feedback, so CSS reads this attribute instead.
      node.setAttribute("data-tooltip", resolved);
      node.removeAttribute("title");
      if (!node.hasAttribute("aria-label")) node.setAttribute("aria-label", resolved);
    } else {
      node.setAttribute("title", resolved);
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    if (node.dataset.i18nPlaceholderEn === undefined) {
      node.dataset.i18nPlaceholderEn = node.getAttribute("placeholder") || "";
    }
    const text = table[node.dataset.i18nPlaceholder];
    node.setAttribute("placeholder", text ?? node.dataset.i18nPlaceholderEn);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    if (node.dataset.i18nAriaEn === undefined) {
      node.dataset.i18nAriaEn = node.getAttribute("aria-label") || "";
    }
    const text = table[node.dataset.i18nAria];
    node.setAttribute("aria-label", text ?? node.dataset.i18nAriaEn);
  });
}

function syncLangToggle() {
  const toggle = byId("lang-toggle");
  if (!toggle) return;
  const zh = getLang() === "zh";
  toggle.setAttribute("aria-pressed", String(zh));
  byId("lang-toggle-label").textContent = zh ? "EN" : "中";
  const titleKey = zh ? "Switch to English" : "Switch to Chinese (中文)";
  toggle.setAttribute("data-tooltip", t(titleKey));
  toggle.setAttribute("aria-label", t(titleKey));
  toggle.setAttribute("title", "");
}

function rerenderCurrentView() {
  if (!state.data) return;
  renderTodayDateOptions();
  if (state.view === "today") renderToday();
  if (state.view === "leaderboard") renderLeaderboard();
  if (state.view === "trends") renderTrends();
  if (state.view === "map") renderTrendMap();
  renderStaleBanner();
  renderBuildMeta();
}

function toggleLang() {
  setLang(getLang() === "zh" ? "en" : "zh");
  applyStaticI18n();
  syncLangToggle();
  rerenderCurrentView();
}

const I18N = {
  en: {},
  zh: {
    // --- Brackets and chrome -------------------------------------------------
    "Skip to content": "跳到主要内容",
    "Benchmark Radar": "Benchmark 雷达日报",
    "Subscribe to Benchmark Radar via RSS": "通过 RSS 订阅 Benchmark Radar",
    "Site utilities": "网站工具",
    "Switch to Chinese (中文)": "切换到中文",
    "Switch to English": "切换到英文",
    "Export the dataset": "导出数据集",
    "Get in touch · Email, WeChat, Discord": "联系我 · 邮件、微信、Discord",
    Data: "数据",
    Contact: "联系",
    "Support this repository": "支持这个仓库",
    "Open the repository and star it": "打开仓库并给个 Star",
    Star: "Star",
    "Fork this repository": "Fork 这个仓库",
    Fork: "Fork",
    "Open a new issue": "新建 Issue",
    Issues: "Issues",
    "Dashboard views": "仪表盘视图",
    Today: "今日",
    Leaderboard: "排行榜",
    Trends: "趋势",
    "Trend map": "趋势图",
    Rubric: "评分标准",
    "Daily briefing": "每日简报",
    "Questions for today": "今日问答",
    // The Q&A question strings are fixed (questions.py QUESTION_GROUPS) and
    // stored in English in every snapshot, so they are translated here against
    // the exact stored text rather than by a second server-side field (issue
    // #231). Group titles ship the same way.
    "What arrived": "今日新增",
    "What is still moving": "仍在变动",
    "What it means": "这意味着什么",
    "What benchmarks, datasets, or evaluation methods did the radar first see today?":
      "雷达今天首次看到了哪些基准、数据集或评估方法？",
    "Which of today's arrivals document how they score an answer?":
      "今天的哪些新增条目记录了它们如何给答案评分？",
    "Which artifacts the radar already tracked moved measurably, and over what span?":
      "雷达已跟踪的哪些条目出现了可测变动，跨度如何？",
    "Which of that movement is corroborated by more than one connector?":
      "其中哪些变动得到了不止一个数据源的印证？",
    "What should someone building or evaluating AI systems do differently today?":
      "构建或评估 AI 系统的人今天应该做哪些不同的选择？",
    "What does today's evidence fail to show, and what would change the reading?":
      "今天的证据未能说明什么，什么会改变这一解读？",
    Search: "搜索",
    "Title, summary, or source": "标题、摘要或来源",
    "Scan date": "扫描日期",
    Kind: "类型",
    Category: "类别",
    Source: "来源",
    Organization: "机构",
    Event: "事件",
    "Clear filters": "清除筛选",
    "Matching observations": "匹配结果",
    "Show more results": "显示更多结果",
    Sources: "来源",
    "Corpus totals": "语料统计",
    All: "全部",
    "view.today.matching": "匹配结果",
    // --- Leaderboard ---------------------------------------------------------
    "Model Card Adoption Rank": "模型卡采用排名",
    "Which benchmarks do model cards report?": "模型卡报告了哪些基准?",
    "How to read this evidence": "如何解读这些证据",
    "leaderboard.method.note1":
      "这是报告惯例的排名,不是基准质量排名。一张模型卡无论报告了多少种配置,对同一基准最多计为一次提及。",
    "leaderboard.method.note2":
      "部分模型卡把基准表做成图片发布,这些行是通过 OCR 转录的,转录结果可能出错。<a href=\"#leaderboard-cards-heading\">来源台账</a> 列出了每一条记录的基准和原始文档,以便逐条核对每个计数。",
    "Registry overview": "总览",
    "What the two layers say": "两层信息说了什么",
    "Stated findings": "明确结论",
    "Benchmarks to watch": "值得关注的基准",
    "Choose a reporting story": "选择一个报告故事",
    "leaderboard.navigator.note":
      "从能把新兴工具与成熟标准、饱和惯例区分开来的信号入手。",
    "Reporting over time": "随时间的变化",
    "Benchmark adoption frontier": "基准采用前沿",
    "All tracked benchmarks": "所有追踪的基准",
    "Frontier milestones": "前沿里程碑",
    "What would make this a true Pareto frontier?": "怎样才算真正的帕累托前沿?",
    "Benchmarks by model card adoption": "按模型卡采用排名的基准",
    "Benchmark name or alias": "基准名称或别名",
    Domain: "领域",
    "Benchmark released": "基准发布",
    "Audit the counts": "核对数量",
    "Model cards in the registry": "登记册中的模型卡",
    "Dashboard unavailable": "仪表盘不可用",
    "The validated data file could not be loaded.": "无法加载校验过的数据文件。",
    "Try refreshing, or inspect the latest daily Issue while the dashboard rebuilds.": "请尝试刷新,或在仪表盘重建时查看最新的每日 Issue。",
    "Open daily Issues ↗": "打开每日 Issue ↗",
    "error.note": "请尝试刷新,或在仪表盘重建时查看最新的每日 Issue。",
    "Open daily Issues": "打开每日 Issue ↗",
    "Select a node": "选择一个节点",
    "All dates": "所有日期",
    "frontier.explainer.tl1":
      "同一时间轴上有三条读数。每个橙色菱形标记一家机构首次报告该基准,这是唯一会抬高累计次数的事件。其下的地毯为每张有日期的模型卡放一个刻度,已被计数的机构之后发布的卡显示为灰色刻度,楼梯保持水平。没有发布日期的卡无法放在时间线上,从两条带中都缺席,但仍计入上面的总数。长而平稳的一段是在这个精选登记册中观察到的报告饱和,并非对基准分数饱和的判断。",
    "frontier.explainer.sub":
      "下面的分数轨道是另一条独立的读数:每个能从引文文档中逐字读到的数值,只在工具与协议完全一致时才相连。分数末端趋于平直通常意味着没有更新的数字可读,因此缺口被标出而不是用线穿过。",
    "leaderboard.filters.note":
      "每张模型卡对同一基准只计一次。一张在四个配置中报告 AIME 的卡,与只报告一次的卡计数相同,因此冗长的附录不能压过不同的供应商。机构可以打破平局:六个供应商报告同一计数是共同标准,只有一个供应商报告则是自家风格。",
    "leaderboard.ledger.note":
      "这是计算排名的精选来源列表。展开任意一张卡可看到其报告的全部基准,并按源文档的分组方式分组,以便我们的数据能逐行对照原文核查。",
    "pareto.readiness.summary": "怎样才算真正的帕累托前沿?",
    "pareto.readiness.note1":
      "可比的分数观测需要基准版本与划分、指标方向、模型、评测框架或脚手架、推理预算、成本或延迟、发布日期与来源。只有兼容的配置才能共享一个分数前沿;这个登记册目前存储的是提及次数,而不是这些测量值。",
    "pareto.readiness.note2":
      "有了这些观测数据,Harbor 风格视图可以把成本或延迟放在 x 轴、分数放在 y 轴,只连接不受支配的观测点,并用发布时间滑块揭示前沿如何移动。",
    "map.heading.note":
      "总览概括整个语料。关系画布包含每个工件及其关联的机构、来源与主题;选择一个节点会把它带进今天的筛选器。",
    "map.detail.note":
      "主题、来源和机构节点会设置对应的今日筛选器。工件节点会设置日期与标题搜索。",
    "trends.heading.note": "计数描述的是发现数量,不是科学质量。",
    "trends.daily.title": "每日证据与关注量",
    "trends.daily.note": "类别标签会有重叠。每个条形都是独立计数,不是堆叠总量的一部分。",
    "trends.releaseOnly": "仅看新发布",
    "trends.releaseOnly.note": "排除对已出现内容的更新式再公告记录。",
    Updated: "更新于",
    Unknown: "未知",
    // --- Metric nouns (singular/plural both map to the same zh noun) --------
    point: "分",
    points: "分",
    comment: "条评论",
    comments: "条评论",
    source: "个来源",
    sources: "个来源",
    "evidence record": "条证据",
    "model card": "张模型卡",
    "model cards": "张模型卡",
    "dated organization": "家过日期机构",
    "dated organizations": "家过日期机构",
    organization: "个机构",
    "repeat report": "次重复报告",
    "repeat reports": "次重复报告",
    benchmark: "个基准",
    benchmarks: "个基准",
    value: "个值",
    values: "个值",
    date: "个日期",
    dates: "个日期",
    domain: "个领域",
    domains: "个领域",
    artifact: "个工件",
    artifacts: "个工件",
    day: "天",
    days: "天",
    month: "个月",
    months: "个月",
    topic: "个主题",
    topics: "个主题",
    // --- Today / health ------------------------------------------------------
    "Evidence cited by GPT": "GPT 引用的证据",
    "Caveat: ": "注意: ",
    "No briefing was recorded for this day.": "这一天没有记录简报。",
    "No observations match these filters. Clear one or more filters to widen the view.":
      "没有符合条件的记录。清除一个或多个筛选条件以扩大范围。",
    "Evidence: ": "证据: ",
    "Attention: active": "关注度:活跃",
    "No categorized records in this scan.": "本次扫描没有分类记录。",
    "more categories": "更多类别",
    "None observed today": "今日无记录",
    "No records today": "今日无记录",
    "all ok": "全部正常",
    empty: "为空",
    "Active attention": "活跃关注度",
    "Evidence": "证据",
    new: "新增",
    active: "活跃",
    none: "无",
    result: "条结果",
    results: "条结果",
    evidence: "条证据",
    attention: "个关注信号",
    Show: "显示",
    more: "更多",
    remaining: "条剩余",
    flat: "持平",
    up: "上升",
    down: "下降",
    found: "已找到",
    failed: "失败",
    ok: "正常",
    "Attention ingest": "关注度采集",
    "Evidence ingest": "证据采集",
    "Producer report": "生产者报告",
    "Truncated at the record per-source limit": "在单项来源上限处被截断",
    "History begins": "历史始于",
    "At least two daily snapshots are required to calculate a trend": "计算趋势至少需要两个每日快照",
    Baseline: "基线",
    "active attention signals": "条活跃关注信号",
    "Two snapshots are available. The chart shows the first comparable daily change; broader trend language begins with three snapshots.":
      "已有两个快照。图表显示第一次可比较的日变化;更完整的趋势表述需要三个快照。",
    "Two snapshots are available, but their connector coverage or report limit differs, so the change between them is not comparable.":
      "已有两个快照,但两者的连接器覆盖范围或报告上限不同,因此它们之间的变化不可比较。",
    "Compared with": "与",
    "surfaced evidence is": "相比,已出现的证据",
    "active attention is": ",活跃关注度",
    "Biggest domain moves": "最大的领域变化",
    "used different connector coverage or a different report limit than": "使用了与",
    "so the two scans": "不同的连接器覆盖范围或报告上限,因此这两次扫描",
    "are not directly comparable. Counts are shown without a change figure.": "不可直接比较。计数将不附带变化数值显示。",
    "vs previous scan": "对比上次扫描",
    "not comparable": "不可比较",
    "recent daily average": "近期日平均",
    "not enough history": "历史不足",
    cumulative: "累计",
    "vs its average": "对比其平均值",
    "also updated (not counted above)": "另有更新(未计入上方)",
    "no change": "无变化",
    "New releases only. Re-announced updates are tracked separately.":
      "仅统计新发布。重新宣布的更新单独跟踪。",
    snapshots: "个快照",
    "category match": "个类别匹配",
    "category matches": "个类别匹配",
    // --- Questions -----------------------------------------------------------
    "In plain English: ": "用简单的话说: ",
    "Evidence is insufficient to answer this today.": "目前证据不足以回答这个问题。",
    "Takeaway: ": "要点: ",
    "Counter-view: ": "反面观点: ",
    "View analysis": "查看分析",
    "Answered by": "由",
    confidence: "置信度",
    in: "花费了",
    calls: "次调用",
    "input tokens": "输入 token",
    "output tokens": "输出 token",
    "every figure computed before the call and cited by ID": "所有数字都在调用前计算并通过 ID 引用",
    "OpenAI model": "OpenAI 模型",
    "GPT synthesis": "GPT 综合",
    "via OpenAI Responses API": "经由 OpenAI Responses API",
    "evidence records": "条证据记录",
    "history days injected": "天历史记录被注入",
    and: "和",
    "Evidence & briefing details": "证据与简报详情",
    "Briefing details": "简报详情",
    "Daily questions were not enabled for this run.": "本次运行未启用每日问答。",
    "Daily questions failed to generate": "每日问答生成失败",
    "No questions were answered for this day.": "这一天没有可回答的问题。",
    "Why it matters": "为什么重要",
    // --- Score blocks --------------------------------------------------------
    "Priority score": "优先度评分",
    Recommended: "推荐",
    "Recommended to review": "推荐复核",
    "Priority score meets this scan's": "本次扫描的优先度分数达到",
    " triage threshold; not an endorsement.": " 分诊阈值,并非背书。",
    "not an endorsement": "并非背书",
    "uncategorized": "未分类",
    "How is this scored?": "这个分数怎么来的?",
    "Not quality-scored": "未做质量评分",
    "This is a public attention signal. Its activity is shown separately from scientific evidence and priority.":
      "这是一个公开的关注度信号。它的活跃度与科学证据和优先度分开展示。",
    "Supporting submissions": "支撑提交",
    "Open primary artifact ↗": "打开主要工件 ↗",
    "Why surfaced": "为什么出现",
    "Open primary source ↗": "打开主要来源 ↗",
    "View matching observations →": "查看匹配记录 →",
    "Selected node": "已选节点",
    "Connected to": "连接到",
    "Paraphrased example": "转述示例",
    Scenario: "场景",
    "Evaluated artifact": "被评估的工件",
    "Comparison caveat": "对比注意事项",
    "Open official benchmark source ↗": "打开官方基准来源 ↗",
    "Benchmarks": "基准",
    // --- Trends --------------------------------------------------------------
    "Corpus rhythm": "语料节奏",
    "Signals over time": "随时间变化的信号",
    "Counts describe discovery volume, not scientific quality.": "计数描述的是发现量,不是科学质量。",
    "New by domain": "按领域的新内容",
    "Daily evidence and attention volume": "每日证据与关注度量",
    "Category tags overlap. Each bar is an independent count, not a part of a stacked total.":
      "类别标签有重叠。每个柱是独立计数,不是堆叠总量的组成部分。",
    "Releases only": "仅发布",
    "Excludes records re-announced as an update to something already surfaced.":
      "排除作为已出现内容的更新而再次宣布的记录。",
    "Daily ledger": "每日台账",
    "trends.ledger.note":
      "来源结构统计的是评分后的排序证据;抓取状态统计的是评分前的原始记录,所以一个来源可能正常却仍为空。",
    Date: "日期",
    "Coverage (UTC)": "覆盖范围 (UTC)",
    "Source mix": "来源结构",
    Categories: "类别",
    Events: "事件",
    Attention: "关注度",
    "Fetch health": "抓取状态",
    // --- Map ----------------------------------------------------------------
    "Cumulative corpus": "累计语料",
    "Artifacts and their context": "工件及其背景",
    "view.map.note":
      "总览概括了整个语料库。关系画布包含每一个工件以及与其相连的机构、来源和主题;选择节点即可将其带入今日筛选。",
    "Inspect a relationship": "检查一个关系",
    "view.map.detail.note": "主题、来源和机构节点会设置对应的今日筛选。工件节点会设置日期和标题搜索。",
    // --- Frontier / workbench -------------------------------------------------
    "Priority & evidence": "优先度与证据",
    "Early signal": "早期信号",
    "New & spreading": "新增且扩散中",
    "Established": "已确立",
    "Saturated reporting": "报告饱和",
    "View adoption frontier ↑": "查看采用前沿 ↑",
    "Show on the chart ↑": "在图表中显示 ↑",
    "Model cards": "模型卡",
    "Best on record": "历史最佳",
    "Headroom left": "剩余空间",
    "Readable values": "可读数值",
    "Supports: ": "支持: ",
    "Does not support: ": "不支持: ",
    "Readable score": "可读分数",
    Model: "模型",
    Adoption: "采用",
    "Open source record ↗": "打开来源记录 ↗",
    "Open source document ↗": "打开来源文档 ↗",
    "Read from": "读取自",
    "Cited by": "被引用",
    Instrument: "工具",
    Protocol: "协议",
    "new instrument": "新工具",
    "Not yet reported": "尚未报告",
    "not yet reported in these cards": "这些模型卡中尚未报告",
    "Reported by": "报告机构",
    "Benchmark home ↗": "基准主页 ↗",
    "Top cards": "头部模型卡",
    "Disclosure": "披露",
    "No benchmarks match these filters. Clear one or more filters to widen the view.":
      "没有符合条件的基准。清除一个或多个筛选条件以扩大范围。",
    "source documents": "来源文档",
    "Each document counts once per benchmark.": "每份文档对每个基准只计一次。",
    organizations: "机构",
    "The denominator for reporting breadth.": "衡量报告广度时的分母。",
    "Benchmarks tracked": "追踪的基准数",
    "Benchmarks reported at least once": "被报告至少一次的基准数",
    "The subset a ranked row can speak to.": "排名行所能覆盖的子集。",
    "New instruments": "新工具",
    "Benchmarks this document reports": "此文档报告的基准",
    "Last read by a human on": "人工最后读取于",
    "date unknown": "日期未知",
    "shown": "显示",
    "tracked": "追踪",
    "of": "共",
    // --- Export / contact -----------------------------------------------------
    "Benchmark Radar · data export": "Benchmark Radar · 数据导出",
    "Take the data with you": "把数据带走",
    "Download full dataset (JSON)": "下载全量数据集 (JSON)",
    "Download current view (CSV · {rows} rows)": "下载当前视图 (CSV · {rows} 行)",
    "Benchmark Radar": "Benchmark 雷达日报",
    "Get in touch": "联系我",
    Email: "邮件",
    WeChat: "微信",
    Discord: "Discord",
    // --- Remaining dynamic strings ------------------------------------------
    " on a": " 以",
    " scored records on": " 项已评分记录,以",
    " · current": " · 现行",
    " · superseded": " · 已取代",
    "(zoom)": "(缩放)",
    "(zoomed)": "(已缩放)",
    "A wrong row in the adoption ranking is a real bug. So is a connector that stopped collecting, or a benchmark you expected the radar to see.":
      "采用排行中的一行错误就是真实的 bug;连接器停止采集,或者一个你期待雷达发现的基准没有出现,同样是 bug。",
    "All domains": "所有领域",
    "All organizations": "所有机构",
    "Any release date": "任意发布日期",
    "Artifact nodes connected to topics, organizations, and discovery sources":
      "连接到主题、机构与发现来源的工件节点",
    Artifacts: "工件",
    "At least 80% of organizations in this curated registry report it; that is convention, not quality.":
      "该精选登记册中至少 80% 的机构报告了它;这是惯例,不是质量。",
    Authors: "作者",
    "Awaiting an independent second organization": "等待第二个独立机构",
    "Click the marker to pin these details": "点击标记以固定这些详情",
    "Click to pin record details": "点击固定记录详情",
    Comments: "评论",
    "Corpus coverage": "语料覆盖",
    "Dashed score connection": "虚线分数连接",
    "Discovery sources": "发现来源",
    "Doing related-work research, or hunting for a benchmark on a topic? This database aggregates every benchmark, evaluation, and dataset the radar has surfaced, and you can query it by topic, source, or organization before you export. The full corpus below is the same data the dashboard renders.":
      "在做相关工作研究,或想按主题查找基准?这个数据库汇总了雷达发现过的每一个基准、评测与数据集,可以在导出前按主题、来源或机构查询。下方的完整语料与仪表盘渲染的是同一份数据。",
    "Every benchmark this document puts in front of readers, counted once each. These are mentions, not scores: the source records the configuration, and this registry deliberately does not.":
      "此文档呈现给读者的每个基准,各计一次。这是提及次数,不是分数:来源记录了配置,而这个登记册刻意不记录。",
    "Every record matching at least one taxonomy category is retained. A score of":
      "只要匹配至少一个分类类别的记录都会被保留。达到分数",
    "First card from that organization": "该机构的第一张模型卡",
    "First reporting organization": "首个报告机构",
    "How priority is scored": "优先度如何评分",
    "Later card, organization already counted": "之后的模型卡,机构已计入",
    "Leaderboard (CSV)": "排行榜 (CSV)",
    "Most represented organizations": "出现最多的机构",
    "New organization": "新机构",
    "No benchmark is reported by a curated card yet.": "目前还没有精选模型卡报告任何基准。",
    "No corpus entities yet.": "还没有语料实体。",
    "No dated model-card mentions yet.": "还没有带日期的模型卡提及。",
    "No dated report": "没有日期记录",
    "No description published at the source.": "来源没有发布描述。",
    "No discovery sources yet.": "还没有发现来源。",
    "No further description beyond the preview above.": "除了上面的预览,没有更多描述。",
    "No organizations identified yet.": "还没有识别出机构。",
    "No score for this benchmark could be read verbatim from the cited documents, so the chart shows adoption only. An absent value is not a zero and not a plateau.":
      "引用的文档中读不到该基准的逐字分数,因此图表只显示采用情况。缺失的数值既不是零,也不是平台期。",
    "No source documents in the registry yet.": "登记册中还没有来源文档。",
    "No topics assigned yet.": "还没有分配主题。",
    "Not a verbatim benchmark item. This description paraphrases the official source; open it for exact tasks and protocol.":
      "不是逐字的基准条目。此描述转述自官方来源;请打开它以查看确切的题目与协议。",
    "Not a verbatim benchmark item. This is an illustrative format based on the recorded domain; use the official source for exact tasks and protocol.":
      "不是逐字的基准条目。这是根据记录领域生成的示例格式;请使用官方来源查看确切的题目与协议。",
    "Only one dated organization is visible so far. It is too early to infer a plateau.":
      "目前只看到一个有日期的机构。推断平台期还为时过早。",
    "Open public discussion ↗": "打开公开讨论 ↗",
    Organizations: "机构",
    "Pinned · click the marker again or press Escape to close": "已固定 · 再次点击标记或按 Escape 关闭",
    Priority: "优先度",
    "Priority is the weighted mean of four components, each measured on a 0 to":
      "优先度是四个维度的加权平均,每个维度都以 0 到",
    "Producer discovered": "发现者发现于",
    Published: "发布",
    "Radar first observed": "雷达首次观察到",
    "Read full card ↗": "阅读完整模型卡 ↗",
    Recency: "新鲜度",
    "Release date unrecorded": "未记录发布日期",
    Released: "发布于",
    "Released in the newest 18-month window and already reported by several independent organizations.":
      "在最近 18 个月的窗口内发布,且已被多个独立机构报告。",
    Relevance: "相关性",
    "Reported across multiple organizations, but not yet a corpus-wide convention in this registry.":
      "已被多个机构报告,但尚未成为本登记册中的语料级惯例。",
    "Reporting stage": "报告阶段",
    "Representative task shape": "代表性任务形态",
    "Rubric v": "评分标准 v",
    Score: "分数",
    Scored: "已评分",
    "Scores from the": "分数来自",
    "Scoring rubric v": "评分标准 v",
    "Show the first 18 benchmarks": "显示前 18 个基准",
    "Showing all": "显示全部",
    "Solid score connection": "实线分数连接",
    Submissions: "提交数",
    "The current rubric is v": "当前评分标准为 v",
    "This benchmark has no dated mentions.": "该基准没有带日期的提及。",
    "This historical scan used": "本次历史扫描采用了",
    "This record scores": "该记录得分",
    "This record was scored by rubric v": "该记录由评分标准 v",
    "Too early to infer a reporting plateau": "推断报告平台期为时尚早",
    "Topic coverage": "主题覆盖",
    Topics: "主题",
    "What this score does not claim": "这个分数的含义之外",
    "adoption trajectory": "采用轨迹",
    after: "之后",
    "an inclusion cutoff. Records below it were not retained.": "为纳入门槛。低于它的记录未被保留。",
    as: "作为",
    "author nodes summarized above and omitted from the canvas": "个作者节点已在上面汇总,并从画布中省略",
    "best on record": "历史最佳",
    by: "由",
    "cited by": "被引用",
    "connected only at one instrument and protocol": "仅在单一工具与协议连接",
    contributes: "贡献",
    "count unchanged": "计数不变",
    "cumulative count increases": "累计计数增加",
    "cumulative distinct organizations": "累计独立机构",
    "did not add a new organization to the frontier": "未向前沿新增机构",
    "distinct orgs": "独立机构",
    "first dated mention": "首次带日期的提及",
    "first readable score": "首个可读分数",
    "has only one dated reporting organization; it is too early to infer a plateau":
      "只有一个带日期的报告机构;推断平台期还为时过早",
    "here are third parties": "有第三方",
    "here is a third party": "有第三方",
    "last new organization": "最近新增机构",
    listed: "已列出",
    "no readable score in this window": "此窗口中无可读分数",
    "not yet reported": "尚未报告",
    "points to zero, the floor of this metric": "指向零,该指标的底线",
    protocol: "协议",
    "publication time": "发布时间",
    "quoting another vendor's figure, marked with a ring on the chart":
      "引用另一家供应商的数据,图表中以圆环标出",
    release: "发布",
    "release date unrecorded": "未记录发布日期",
    released: "发布于",
    "same instrument and protocol across organizations": "跨机构的相同工具与协议",
    "same instrument and protocol, one organization only": "单一机构,相同工具与协议",
    "scale. Every number below is read from the same definition the pipeline applies.":
      "的标尺。下面每个数字都按流程应用的同一套定义读取。",
    "still leaves one frontier step": "仍剩一个前沿台阶",
    "the previous frontier step": "前一个前沿台阶",
    "the tick under the jump": "跳变下方的刻度",
    to: "到",
    "to the total": "到总分",
    "two versions are not directly comparable, and past records are not rescored.":
      "两个版本不可直接比较,过去的记录不会重新评分。",
    weight: "权重",
    "with a dated card": "有日期的模型卡",
  },
};

const state = {
  data: null,
  view: "today",
  todayDate: "",
  q: "",
  kind: "",
  category: "",
  source: "",
  organization: "",
  event: "",
  entity: "",
  rubric: "",
  trendReleasedOnly: false,
  // Leaderboard filters carry their own prefixed keys so a shared permalink can
  // hold a Today filter and a Leaderboard filter at once without either view
  // silently reinterpreting the other's `category` or `organization`.
  lq: "",
  ldomain: "",
  lorg: "",
  lera: "",
  lfrontier: "",
  lfrontierExplicit: false,
  leaderboardShowAll: false,
  todayResultsKey: "",
  todayResultsLimit: ALL_DATES_PAGE_SIZE,
  observations: null,
};

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = String(options.text);
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([key, value]) => {
      if (value !== undefined && value !== null) node.setAttribute(key, String(value));
    });
  }
  children.filter(Boolean).forEach((child) => node.append(child));
  return node;
}

// Coalesce bursts of input (typing in a filter box) into a single trailing
// render, so the corpus is not re-filtered and the DOM rebuilt on every
// keystroke. Used by the filter panels that re-render their whole view.
function debounce(fn, waitMs = 80) {
  let timer = null;
  const debounced = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, waitMs);
  };
  debounced.flush = (...args) => {
    clearTimeout(timer);
    timer = null;
    fn(...args);
  };
  return debounced;
}

function svgElement(tag, attrs = {}, text = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text !== null) node.textContent = String(text);
  return node;
}

function replaceChildren(target, children) {
  target.replaceChildren(...children.filter(Boolean));
}

function formatDate(value, options = { dateStyle: "long" }) {
  if (!value) return t("Unknown");
  const withTime = value.length === 10 ? `${value}T00:00:00Z` : value;
  return new Intl.DateTimeFormat(getLang() === "zh" ? "zh" : "en", { timeZone: "UTC", ...options }).format(
    new Date(withTime),
  );
}

function shorten(value, max = 190) {
  if (!value) return "";
  const normalized = value.trim();
  if (normalized.length <= max) return normalized;
  const candidate = normalized.slice(0, max - 1).trimEnd();
  const lastSpace = candidate.lastIndexOf(" ");
  const cutoff = lastSpace >= Math.floor(max * 0.6)
    ? candidate.slice(0, lastSpace)
    : candidate;
  return `${cutoff.replace(/[,:;.!?-]+$/, "")}…`;
}

// Expanding a record whose teaser already ran most of the way through the
// description used to re-show that same opening text in full, which reads as
// "this just repeats what I already read" rather than as new information.
// Continuing from where the teaser was cut keeps the expanded view additive.
function summaryRemainder(fullText, teaser) {
  const trimmedFull = (fullText || "").trim();
  const teaserBody = teaser.replace(/…$/, "").trim();
  if (!trimmedFull.startsWith(teaserBody)) return trimmedFull;
  const rest = trimmedFull.slice(teaserBody.length).trim();
  return rest ? `…${rest}` : "";
}

function option(value, label, selected = false) {
  return element("option", {
    text: label,
    attrs: { value, ...(selected ? { selected: "" } : {}) },
  });
}

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  const requestedView = params.get("view");
  // Legacy Explorer permalinks resolve to the filterable Today list.
  state.view = ["trends", "map", "leaderboard"].includes(requestedView) ? requestedView : "today";
  state.todayDate = params.get("date") || "";
  state.q = params.get("q") || "";
  state.kind = params.get("kind") || "";
  state.category = params.get("category") || "";
  state.source = params.get("source") || "";
  state.organization = params.get("organization") || "";
  state.event = params.get("event") || "";
  state.entity = params.get("entity") || "";
  state.lq = params.get("lq") || "";
  state.ldomain = params.get("ldomain") || "";
  state.lorg = params.get("lorg") || "";
  state.lera = params.get("lera") || "";
  state.lfrontier = params.get("lfrontier") || "";
  state.lfrontierExplicit = Boolean(state.lfrontier);
  state.rubric = new URLSearchParams(window.location.hash.slice(1)).get("rubric") || "";
}

function writeUrl() {
  const params = new URLSearchParams();
  if (state.view !== "today") params.set("view", state.view);
  // Every filter below belongs to exactly one view, so only that view may write
  // it. Serializing all of them unconditionally is what leaked `lfrontier` onto
  // Today/Trends/Map links and `date` onto Leaderboard links (issue #123): the
  // reader would click "2026-07-31" and land on a URL carrying a leaderboard
  // selection that nothing on the page reads back.
  if (state.view === "today") {
    if (state.todayDate === "all") {
      params.set("date", "all");
    } else if (state.todayDate && state.todayDate !== state.data?.latest_date) {
      params.set("date", state.todayDate);
    }
    if (state.q) params.set("q", state.q);
    if (state.kind) params.set("kind", state.kind);
    if (state.category) params.set("category", state.category);
    if (state.source) params.set("source", state.source);
    if (state.organization) params.set("organization", state.organization);
    if (state.event) params.set("event", state.event);
  }
  if (state.view === "map" && state.entity) params.set("entity", state.entity);
  if (state.view === "leaderboard") {
    if (state.lq) params.set("lq", state.lq);
    if (state.ldomain) params.set("ldomain", state.ldomain);
    if (state.lorg) params.set("lorg", state.lorg);
    if (state.lera) params.set("lera", state.lera);
    // A benchmark auto-picked as the default is not the reader's choice, so it
    // stays out of the URL until they select one themselves.
    if (state.lfrontierExplicit && state.lfrontier) {
      params.set("lfrontier", state.lfrontier);
    }
  }
  const query = params.toString();
  // The rubric dialog is a hashtag, not a query param, so a shared link like
  // #rubric=2 reads as "jump to this section" rather than another filter.
  const hashParams = new URLSearchParams();
  if (state.rubric) hashParams.set("rubric", state.rubric);
  const hash = hashParams.toString();
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}${hash ? `#${hash}` : ""}`,
  );
}

function setView(view, update = true) {
  if (view !== "leaderboard" && selectedFrontierPoint) {
    clearFrontierPointSelection();
  }
  state.view = view;
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.id !== `${view}-view`;
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    if (button.dataset.view === view) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });
  if (update) writeUrl();
}

function selectFrontier(benchmarkId) {
  state.lfrontier = benchmarkId;
  state.lfrontierExplicit = true;
}

function categoryColor(category, index = 0) {
  return CATEGORY_COLORS[category] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

function dailySnapshot(date = state.todayDate) {
  return (
    state.data.days.find((day) => day.date === date) ||
    state.data.days[state.data.days.length - 1]
  );
}

function rubricFor(item = null) {
  const version = String(item?.score_version || state.data?.rubric?.scoring_version || 1);
  return state.data?.rubrics?.[version] || state.data?.rubric;
}

function scoreMax(item = null) {
  return Number(item?.score_max || rubricFor(item)?.score_max) || 4;
}

function scoreBlock(item) {
  const score = Number(item.total_score || 0);
  const max = scoreMax(item);
  const width = Math.max(0, Math.min(100, (score / max) * 100));
  const recommendationScore = Number(item.recommendation_score);
  const triagePrefix = t("Priority score meets this scan's");
  const triageSuffix = t(" triage threshold; not an endorsement.");
  const recommendationExplanation = Number.isFinite(recommendationScore)
    ? `${triagePrefix} ${recommendationScore.toFixed(0)}-point${triageSuffix}`
    : `${triagePrefix}${triageSuffix}`;
  const trackFill = element("span", {});
  const track = element("div", { className: "score-track" }, [trackFill]);
  trackFill.style.width = `${width}%`;
  // The label doubles as the way into the rubric. A number presented without
  // a reachable definition of how it was produced asks the reader to trust it
  // on faith, which is the opposite of what an evidence log is for.
  const explain = element("button", {
    className: "score-label score-explain",
    attrs: {
      type: "button",
      "aria-label": `${t("Priority score")} ${score.toFixed(2)} ${t("of")} ${max.toFixed(2)}. ${t("How is this scored?")}`,
    },
  }, [
    element("span", { text: t("Priority score") }),
    element("span", { className: "info-mark", text: "i", attrs: { "aria-hidden": "true" } }),
  ]);
  explain.addEventListener("click", (event) => {
    // The control lives inside a native <summary>; keep rubric access from
    // also toggling the row.
    event.preventDefault();
    event.stopPropagation();
    openRubric(item);
  });
  return element("div", { className: "score" }, [
    ...(item.recommended
      ? [
          element("span", {
            className: "recommendation-badge",
            text: t("Recommended"),
            attrs: {
              title: recommendationExplanation,
              "aria-label": `${t("Recommended to review")}. ${recommendationExplanation}`,
            },
          }),
        ]
      : []),
    element("div", { className: "score-value" }, [
      element("strong", { text: score.toFixed(2) }),
      element("span", { text: `/ ${max.toFixed(2)}` }),
    ]),
    track,
    explain,
  ]);
}

function pillBar(item) {
  const pills = [
    ...(item.watchlist
      ? [element("span", { className: "pill pill-watchlist", text: `★ ${item.watchlist}` })]
      : []),
    element("span", { className: "pill pill-source", text: item.source }),
    element("span", { className: "pill pill-event", text: item.event_kind }),
    ...(item.categories || []).map((category) =>
      element("span", { className: "pill", text: category.replaceAll("_", " ") }),
    ),
  ];
  if (!(item.categories || []).length) {
    pills.push(element("span", { className: "pill", text: t("uncategorized") }));
  }
  return element("div", { className: "pill-bar" }, pills);
}

function definition(label, value) {
  return element("div", {}, [
    element("dt", { text: label }),
    element("dd", { text: value }),
  ]);
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function validBriefingCitations(citations) {
  const seen = new Set();
  return (Array.isArray(citations) ? citations : []).flatMap((citation) => {
    const id = String(citation?.id || "");
    const href = safeHttpUrl(citation?.url);
    if (!/^E\d{3}$/.test(id) || !href || seen.has(id)) return [];
    seen.add(id);
    return [{
      id,
      href,
      title: String(citation?.title || id),
      source: String(citation?.source || "Primary source"),
    }];
  });
}

function briefingContent(line, citations) {
  const links = new Map(citations.map((citation) => [citation.id, citation]));

  const nodes = [];
  let cursor = 0;
  for (const match of String(line).matchAll(/\bE\d{3}\b/g)) {
    const citation = links.get(match[0]);
    if (!citation) continue;
    nodes.push(document.createTextNode(line.slice(cursor, match.index)));
    nodes.push(element("a", {
      className: "briefing-evidence-link",
      text: match[0],
      attrs: {
        href: citation.href,
        target: "_blank",
        rel: "noopener noreferrer",
        title: `Open evidence: ${citation.title}`,
        "aria-label": `${match[0]}: ${citation.title}`,
      },
    }));
    cursor = match.index + match[0].length;
  }
  nodes.push(document.createTextNode(line.slice(cursor)));
  return nodes;
}

// A briefing bullet is model prose of the form "The claim. Why it matters:
// the point. Evidence: E001, E002. High confidence." For a scan to meet the
// takeaway first and the support on demand, that one paragraph is split into a
// short head, an optional body, and a metadata line carrying the confidence and
// the source count. Bullets that do not follow the shape (older days) fall back
// to the whole line as the head with no body or meta.
function briefingParts(line) {
  let text = String(line).trim();
  let confidence = "";
  const confidenceMatch = text.match(/\b(High|Medium|Low|Moderate|Mixed)\s+confidence\.?\s*$/i);
  if (confidenceMatch) {
    confidence = confidenceMatch[1];
    text = text.slice(0, confidenceMatch.index).trim();
  }
  // Lift the trailing "Evidence: E001, E002." clause out of the prose in both
  // the split and the fallback shapes, so the IDs never stay in the running
  // sentences a scan of the findings has to wade through.
  const sources = (text.match(/\bE\d{3}\b/g) || []).length;
  text = text.replace(/\s*\.?\s*Evidence:\s*((?:E\d{3}\s*,\s*)*E\d{3})\.?\s*/i, "").trim();
  const whyIndex = text.search(/\bWhy it matters:\s*/i);
  if (whyIndex === -1) return { head: text, body: "", confidence, sources };
  const head = text.slice(0, whyIndex).trim();
  const body = text
    .slice(whyIndex + "Why it matters:".length)
    .trim();
  return { head, body, confidence, sources };
}

function briefingMeta(parts) {
  const chips = [];
  if (parts.confidence) {
    chips.push(element("span", {
      className: `briefing-chip briefing-chip-${parts.confidence.toLowerCase()}`,
      text: `${parts.confidence} ${t("confidence")}`,
    }));
  }
  if (parts.sources > 0) {
    chips.push(element("span", {
      className: "briefing-chip briefing-chip-sources",
      text: `${parts.sources} ${parts.sources === 1 ? t("source") : t("sources")}`,
    }));
  }
  if (!chips.length) return null;
  return element("p", { className: "briefing-insight-meta" }, chips);
}

function briefingInsight(line, citations) {
  const parts = briefingParts(line);
  const head = element("h3", { className: "briefing-insight-head" },
    briefingContent(parts.head || line, citations));
  // The body is the "why it matters" support under the head, and the evidence
  // clause was lifted out of it into the metadata chips by briefingParts.
  const body = parts.body
    ? element("p", { className: "briefing-insight-body" }, briefingContent(parts.body, citations))
    : null;
  return element("article", { className: "briefing-insight" }, [head, body, briefingMeta(parts)]);
}

function briefingProvenance(briefing) {
  if (briefing.generator !== "openai-responses") return null;
  const usage = briefing.usage || {};
  const input = briefing.input || {};
  return element("p", {
    className: "daily-briefing-meta",
    text: `${t("GPT synthesis")}: ${briefing.model || t("OpenAI model")} ${t("via OpenAI Responses API")} · ${Number(usage.input_tokens || 0).toLocaleString()} ${t("input tokens")} / ${Number(usage.output_tokens || 0).toLocaleString()} ${t("output tokens")} · ${Number(input.evidence_items || 0).toLocaleString()} ${t("evidence records")} ${t("and")} ${Number(input.history_days || 0).toLocaleString()} ${t("history days injected")}.`,
  });
}

function briefingEvidenceList(citations) {
  if (!citations.length) return null;
  return element("section", {
    className: "daily-briefing-evidence",
    attrs: { "aria-labelledby": "daily-briefing-evidence-heading" },
  }, [
    element("h3", {
      className: "daily-briefing-evidence-title",
      text: t("Evidence cited by GPT"),
      attrs: { id: "daily-briefing-evidence-heading" },
    }),
    element("ul", {}, citations.map((citation) =>
      element("li", {}, [
        element("a", {
          text: `${citation.id} — ${citation.title}`,
          attrs: {
            href: citation.href,
            target: "_blank",
            rel: "noopener noreferrer",
          },
        }),
        element("span", { text: ` (${citation.source})` }),
      ]))),
  ]);
}

function briefingDetails(briefing, citations) {
  const provenance = briefingProvenance(briefing);
  const caveatText = l10nProse(briefing.caveat, briefing.caveat_zh);
  const caveat = caveatText
    ? element("p", { className: "daily-briefing-caveat" }, [
        element("strong", { text: t("Caveat: ") }),
        document.createTextNode(String(caveatText)),
      ])
    : null;
  const evidence = briefingEvidenceList(citations);
  if (!provenance && !caveat && !evidence) return null;

  const label = citations.length
    ? `${t("Evidence & briefing details")} · ${citations.length.toLocaleString()} ${t("sources")}`
    : t("Briefing details");
  return element("details", { className: "daily-briefing-details" }, [
    element("summary", { text: label }),
    provenance,
    caveat,
    evidence,
  ]);
}

// The briefing is generated once per UTC day and stored in that day's snapshot,
// so a day can legitimately have none: it predates the feature, no API key was
// configured, or every pass over the day failed the call. Say which rather than
// leaving the reader with a heading above blank space.
function renderDailyBriefing(day) {
  const briefing = day.briefing || {};
  const enBullets = Array.isArray(briefing.bullets) ? briefing.bullets : [];
  const zhBullets = Array.isArray(briefing.bullets_zh) ? briefing.bullets_zh : [];
  const bullets = getLang() === "zh" && zhBullets.length ? zhBullets : enBullets;
  const citations = validBriefingCitations(briefing.citations);
  // A briefing carrying another day's date describes the wrong day, so it is
  // withheld rather than shown beside this date's listings.
  const usable = briefing.date === day.date ? bullets.filter((line) => line.trim()) : [];
  replaceChildren(
    byId("daily-briefing-body"),
    usable.length
      ? [
          // Model prose becomes a scannable insight block per bullet: a short
          // head (the takeaway), the "why it matters" support beneath it, and a
          // metadata line carrying confidence and source count instead of
          // paragraph-wide prose and mid-sentence evidence IDs.
          ...usable.map((line) => briefingInsight(line, citations)),
          briefingDetails(briefing, citations),
        ]
      : [
          element("p", {
            className: "empty-state",
            text: t("No briefing was recorded for this day."),
          }),
        ],
  );
}

// Statistic values are printed from the registry the answer cites, never from
// the model's prose, so a number reaches the page only if it was computed
// before the call. This mirrors report.py's `_format_stat_value` exactly.
function formatStatValue(stat) {
  const value = stat?.value;
  // `toLocaleString()` is not used: it rounds to three fraction digits, so a
  // registry value of 1234.56789 would reach the page as 1,234.568. Grouping is
  // applied to the integer part only, which matches Python's `f"{value:,}"` and
  // keeps the printed figure identical to the Markdown report's.
  let rendered;
  if (typeof value === "number" && Number.isFinite(value)) {
    const [whole, fraction] = String(value).split(".");
    // \B keeps the separator out of a leading "-", so -1234 groups as -1,234.
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    rendered = fraction ? `${grouped}.${fraction}` : grouped;
  } else {
    rendered = String(value ?? "");
  }
  const unit = String(stat?.unit || "").trim();
  if (unit && unit !== "count") rendered = `${rendered} ${unit}`;
  const window = String(stat?.window || "").trim();
  if (window && window !== "today") {
    // Spans already carry their own parentheses; do not nest another pair.
    rendered = window.endsWith(")") ? `${rendered} ${window}` : `${rendered} (${window})`;
  }
  return rendered;
}

function answerCitations(answer) {
  const stats = (Array.isArray(answer?.cited_stats) ? answer.cited_stats : []).map((stat) =>
    element("li", {}, [
      element("code", { className: "answer-stat-id", text: String(stat?.id || "") }),
      document.createTextNode(` ${String(stat?.label || "")}: `),
      element("strong", { text: formatStatValue(stat) }),
    ]),
  );
  // Same rule as the briefing: only an exact evidence ID with a safe http(s)
  // URL becomes a link, so a citation nobody can follow is not rendered as one.
  const evidence = validBriefingCitations(answer?.cited_evidence).map((citation) =>
    element("li", {}, [
      element("code", { className: "answer-stat-id", text: citation.id }),
      document.createTextNode(" "),
      element("a", {
        text: citation.title,
        attrs: {
          href: citation.href,
          target: "_blank",
          rel: "noopener noreferrer",
        },
      }),
      element("span", { text: ` (${citation.source})` }),
    ]),
  );
  if (!stats.length && !evidence.length) return null;
  return element("ul", { className: "answer-citations" }, [...stats, ...evidence]);
}

function answerBlock(answer) {
  const insufficient = answer?.sufficient_evidence === false;
  const confidence = String(answer?.confidence || "").trim();
  // The question, the confidence, and one line of signal are the decision the
  // reader came for; the explanation, its sources and the trade-offs back it
  // up but would otherwise take over the page if all shown at once. So the
  // answer is a native disclosure, collapsed by default, whose summary is the
  // compact take while its detail holds everything that supports it. Native
  // <details>/<summary> gives the reversible expand/re-collapse and keyboard
  // support (Tab to focus, Enter/Space to toggle) for free and stays collapsed
  // on load because no `open` attribute is rendered.
  const citations = answerCitations(answer);
  const sourceCount = validBriefingCitations(answer?.cited_evidence).length;
  const meta = element("p", { className: "answer-meta" }, [
    ...(confidence
      ? [
          element("span", {
            className: `pill pill-confidence pill-confidence-${confidence}`,
            text: `${confidence} ${t("confidence")}`,
          }),
        ]
      : []),
    ...(sourceCount
      ? [
          element("span", {
            className: "answer-source-count",
            text: `${sourceCount} ${sourceCount === 1 ? t("source") : t("sources")}`,
          }),
        ]
      : []),
  ]);
  const detail = element("div", { className: "answer-detail" }, [
    element("p", { className: "answer-plain" }, [
      element("em", { text: t("In plain English: ") }),
      document.createTextNode(l10nProse(String(answer?.plain_english || ""), answer?.plain_chinese)),
    ]),
    citations,
    // Stated on the answer rather than hidden in a tooltip: "the evidence does
    // not support an answer today" is a result, not a rendering failure.
    ...(insufficient
      ? [
          element("p", {
            className: "answer-insufficient",
            text: t("Evidence is insufficient to answer this today."),
          }),
        ]
      : []),
    element("p", { className: "answer-takeaway" }, [
      element("strong", { text: t("Takeaway: ") }),
      document.createTextNode(l10nProse(String(answer?.takeaway || ""), answer?.takeaway_zh)),
    ]),
    // The counter-view is the point of the format: an answer that only ever
    // confirms itself teaches a reader nothing about how much to trust it.
    element("p", { className: "answer-counter-view" }, [
      element("strong", { text: t("Counter-view: ") }),
      document.createTextNode(l10nProse(String(answer?.counter_view || ""), answer?.counter_view_zh)),
    ]),
  ]);
  return element("article", { className: "answer" }, [
    // Question first, confidence and sources as a de-emphasized metadata row
    // beneath it rather than pinned to the question's own line, so a scan of a
    // day's answers stays a scan of the questions themselves.
    element("h4", { className: "answer-question" }, [
      document.createTextNode(t(String(answer?.question || ""))),
    ]),
    element("p", { className: "answer-signal", text: l10nProse(String(answer?.signal || ""), answer?.signal_zh) }),
    meta,
    element("details", { className: "answer-disclosure" }, [
      element("summary", { className: "answer-disclosure-summary" }, [
        element("span", { className: "answer-disclosure-label", text: t("View analysis") }),
      ]),
      detail,
    ]),
  ]);
}

function questionsProvenance(questions) {
  if (questions.generator !== "openai-responses") return null;
  const usage = questions.usage || {};
  return element("p", {
    className: "daily-questions-meta",
    text: `${t("Answered by")} ${questions.model || t("OpenAI model")} ${t("in")} ${Number(questions.calls || 0).toLocaleString()} ${t("calls")} · ${Number(usage.input_tokens || 0).toLocaleString()} ${t("input tokens")} / ${Number(usage.output_tokens || 0).toLocaleString()} ${t("output tokens")} · ${t("every figure computed before the call and cited by ID")}.`,
  });
}

// The Q&A is opt-in and generated once per UTC day, so a day can legitimately
// have none: it predates the feature, was disabled, or the calls failed. The
// snapshot's `questions.status` says which, so the empty state names the
// actual reason instead of one generic message for all three.
function absentQuestionsMessage(questions) {
  const status = questions.status;
  if (status === "disabled") {
    return questions.reason || t("Daily questions were not enabled for this run.");
  }
  if (status === "error") {
    return `${t("Daily questions failed to generate")}: ${questions.reason || "unknown error"}.`;
  }
  return t("No questions were answered for this day.");
}

function renderDailyQuestions(day) {
  const questions = day.questions || {};
  const groups = Array.isArray(questions.groups) ? questions.groups : [];
  // A Q&A carrying another day's date answers questions about the wrong day,
  // so it is withheld rather than shown beside this date's listings.
  const usable = questions.date === day.date ? groups : [];
  const rendered = usable.flatMap((group) => {
    const answers = (Array.isArray(group?.answers) ? group.answers : []).map(answerBlock);
    if (!answers.length) return [];
    return [
      element("section", { className: "question-group" }, [
        element("h3", {
          className: "question-group-title",
          text: t(String(group?.title || "Questions")),
        }),
        ...answers,
      ]),
    ];
  });
  replaceChildren(
    byId("daily-questions-body"),
    rendered.length
      ? [
          // Without a certified comparison window, day-over-day differences may
          // be collection changes rather than field changes. Saying so up front
          // stops the answers below from reading as a trend claim.
          ...(questions.comparable === false
            ? [
                element("p", {
                  className: "daily-questions-caveat",
                  text: String(
                    questions.comparability_note ||
                      "No certified comparison window today, so these answers describe what was captured rather than how the field is trending.",
                  ),
                }),
              ]
            : []),
          ...rendered,
          questionsProvenance(questions),
        ]
      : [
          element("p", {
            className: "empty-state",
            text: absentQuestionsMessage(questions),
          }),
        ],
  );
}

function renderTodayDateOptions() {
  if (!state.data) return;
  replaceChildren(
    byId("today-date"),
    [
      option("all", t("All dates"), state.todayDate === "all"),
      ...[...state.data.facets.dates].reverse().map((date) =>
        option(date, formatDate(date, { dateStyle: "medium" }), date === state.todayDate),
      ),
    ],
  );
}

function renderBuildMeta() {
  if (!state.data) return;
  byId("build-meta").textContent = `${t("Updated")} ${formatDate(
    state.data.generated_at,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  )} UTC`;
}

function renderToday({ resultsOnly = false } = {}) {
  // Events are bound before the data file resolves (initialize), so a nav
  // click or filter keystroke in the load window must no-op, not throw.
  if (!state.data) return;
  const showingAllDates = state.todayDate === "all";
  const day = dailySnapshot(showingAllDates ? state.data.latest_date : state.todayDate);
  if (!day) return;
  byId("today-date").value = state.todayDate;

  if (!resultsOnly) {
    // The briefing and connector health describe one scan, not an archive-wide
    // result set. Hiding them in All dates mode keeps latest-day context from
    // appearing to explain observations collected across the full history.
    byId("daily-briefing").hidden = showingAllDates;
    byId("daily-questions").hidden = showingAllDates;
    byId("source-health-panel").hidden = showingAllDates;

    renderDailyBriefing(day);
    renderDailyQuestions(day);
    syncFilters();
  }
  const observations = filteredObservations();
  const resultsKey = [
    state.todayDate,
    state.q,
    state.kind,
    state.category,
    state.source,
    state.organization,
    state.event,
  ].join("\u0000");
  if (resultsKey !== state.todayResultsKey) {
    state.todayResultsKey = resultsKey;
    state.todayResultsLimit = ALL_DATES_PAGE_SIZE;
  }
  // A single busy scan can carry hundreds of observations. Bound every render,
  // not just the all-dates archive, so initial load and filter feedback never
  // have to build the entire card list before the reader can interact.
  const visibleObservations = observations.slice(0, state.todayResultsLimit);
  const remainingResults = observations.length - visibleObservations.length;
  const showMore = byId("today-show-more");
  showMore.hidden = remainingResults <= 0;
  showMore.textContent = remainingResults > 0
    ? `${t("Show")} ${Math.min(ALL_DATES_PAGE_SIZE, remainingResults)} ${t("more")} · ${remainingResults} ${t("remaining")}`
    : t("Show more results");
  const evidenceCount = observations.filter(
    (item) => item.observation_kind === "evidence",
  ).length;
  const attentionCount = observations.length - evidenceCount;
  byId("today-count").textContent =
    `${observations.length} ${observations.length === 1 ? t("result") : t("results")} · ` +
    `${evidenceCount} ${t("evidence")} · ${attentionCount} ${t("attention")}`;
  replaceChildren(
    byId("today-list"),
    visibleObservations.length
      ? visibleObservations.map(observationCard)
      : [
          element("p", {
            className: "empty-state",
            text: "No observations match these filters. Clear one or more filters to widen the view.",
          }),
        ],
  );

  if (resultsOnly) {
    writeUrl();
    return;
  }

  const healthEntries = [
    ...day.ingest_health.map((entry) => ({
      ...entry,
      layer: entry.kind === "attention" ? t("Attention ingest") : t("Evidence ingest"),
      method:
        entry.method ||
        (entry.ok ? LEGACY_SOURCE_COLLECTION_METHODS[entry.source] : "") ||
        "",
    })),
    ...day.producer_health.map((entry) => ({ ...entry, layer: t("Producer report") })),
  ];
  // Fetch plumbing is not what the reader came for, so the roster stays
  // collapsed to one line and the reader expands it on demand. The summary
  // still carries the failure count, so a gap is legible without opening the
  // panel: connector failures are usually long-lived and known, and
  // force-opening on every one of them buried the list beside it.
  const failedCount = healthEntries.filter((entry) => !entry.ok).length;
  byId("health-status").textContent = failedCount
    ? `${failedCount} ${t("of")} ${healthEntries.length} ${t("failed")}`
    : `${healthEntries.length} ${t("ok")}`;
  byId("health-status").classList.toggle("has-failure", failedCount > 0);
  // Absent on snapshots written before the cap was published, in which case no
  // count can be identified as truncated and all are shown as-is.
  const ingestCap = day.selection?.max_items_per_source ?? null;
  replaceChildren(
    byId("health-list"),
    healthEntries.map((entry) => {
      const children = [
        element("span", { className: `health-dot${entry.ok ? " ok" : ""}` }),
        element("span", {
          className: "health-name",
          text: entry.method
            ? `${entry.source} · ${entry.method} · ${entry.layer}`
            : `${entry.source} · ${entry.layer}`,
        }),
        element("span", {
          className: "health-count",
          // A source that returned exactly the per-source cap was truncated, so
          // the number is a ceiling. "300+ found" says that; "300 found" read as
          // a measured total.
          text: entry.ok
            ? entry.item_count
              ? `${entry.item_count}${entry.item_count === ingestCap ? "+" : ""} ${t("found")}`
              : t("empty")
            : t("failed"),
          ...(entry.item_count === ingestCap
            ? { attrs: { title: t("Truncated at the record per-source limit") } }
            : {}),
        }),
      ];
      if (entry.error) {
        children.push(element("p", { className: "health-detail", text: entry.error }));
      }
      return element("li", {}, children);
    }),
  );

  // How many distinct benchmarks/datasets/etc. the whole corpus has ever
  // surfaced, by category (issue #52). `topics` already counts each artifact
  // once across every source and day; this just makes that total legible
  // outside the trend map.
  const topics = state.data.corpus?.aggregates?.topics || [];
  const totalArtifacts = Number(state.data.corpus?.aggregates?.entity_types?.artifact || 0);
  byId("corpus-totals-status").textContent = `${totalArtifacts.toLocaleString()} ${t("artifacts")}`;
  replaceChildren(
    byId("corpus-totals-list"),
    [...topics]
      .sort((a, b) => b.entity_count - a.entity_count)
      .map((topic) =>
        element("li", {}, [
          element("span", {
            className: "health-name",
            text: topic.topic.replace(/_/g, " "),
          }),
          element("span", {
            className: "health-count",
            text: topic.entity_count.toLocaleString(),
          }),
        ]),
      ),
  );

  writeUrl();
}

function deltaText(value) {
  if (!value) return t("no change");
  return value > 0 ? `+${value}` : String(value);
}

function domainCard(category, trend, index) {
  const swatch = element("span", { className: "legend-swatch" });
  swatch.style.setProperty("--swatch", categoryColor(category, index));
  // A null delta means the previous scan used a different report limit, so the
  // two counts are not comparable and no change is claimed.
  const comparable = trend.delta !== null && trend.delta !== undefined;
  const delta = comparable ? Number(trend.delta) : 0;
  const rows = [
    [t("vs previous scan"), comparable ? deltaText(delta) : t("not comparable")],
    [
      t("recent daily average"),
      trend.baseline === null || trend.baseline === undefined
        ? t("not enough history")
        : Number(trend.baseline).toFixed(2),
    ],
    [t("cumulative"), Number(trend.cumulative || 0).toLocaleString()],
  ];
  if (trend.momentum !== null && trend.momentum !== undefined) {
    const percent = Math.round(Number(trend.momentum) * 100);
    rows.splice(2, 0, [t("vs its average"), `${percent > 0 ? "+" : ""}${percent}%`]);
  }
  const updatedOnly = Math.max(0, (trend.total_count || 0) - (trend.count || 0));
  if (updatedOnly) {
    rows.push([t("also updated (not counted above)"), updatedOnly.toLocaleString()]);
  }
  return element(
    "article",
    {
      className: `domain-card${!comparable ? "" : delta > 0 ? " is-up" : delta < 0 ? " is-down" : ""}`,
    },
    [
      element("div", { className: "domain-head" }, [
        swatch,
        element("h3", { text: category.replaceAll("_", " ") }),
      ]),
      element("p", {
        className: "domain-count",
        text: String(trend.count ?? 0),
        attrs: { title: t("New releases only. Re-announced updates are tracked separately.") },
      }),
      element(
        "dl",
        { className: "domain-stats" },
        rows.flatMap(([label, value]) => [
          element("dt", { text: label }),
          element("dd", { text: value }),
        ]),
      ),
    ],
  );
}

function renderDomainMetrics(day) {
  const grid = byId("domain-grid");
  if (!grid) return;
  const trends = day.category_trends || {};
  const entries = Object.entries(trends).sort(
    (a, b) => (b[1].count || 0) - (a[1].count || 0) || a[0].localeCompare(b[0]),
  );
  byId("domain-date").textContent = formatDate(day.date, { dateStyle: "medium" });
  replaceChildren(
    grid,
    entries.length
      ? entries.map(([category, trend], index) => domainCard(category, trend, index))
      : [
          element("p", {
            className: "empty-state",
            text: t("No categorized records in this scan."),
          }),
        ],
  );
}

function sameCollectionContext(a, b) {
  return (
    (a.selection || {}).report_limit === (b.selection || {}).report_limit &&
    JSON.stringify(a.coverage_signature || []) === JSON.stringify(b.coverage_signature || [])
  );
}

function coverageNote(day) {
  return (day.coverage_gaps || []).length
    ? ` Coverage is incomplete: ${day.coverage_gaps.join(", ")} failed.`
    : "";
}

function renderTrends() {
  if (!state.data) return;
  const categories = state.data.facets.categories;
  byId("trend-released-only").checked = state.trendReleasedOnly;
  replaceChildren(
    byId("trend-legend"),
    [
      ...categories.map((category, index) => {
        const swatch = element("span", { className: "legend-swatch" });
        swatch.style.setProperty("--swatch", categoryColor(category, index));
        return element("span", { className: "legend-item" }, [
          swatch,
          element("span", { text: `${t("Evidence")}: ${category.replaceAll("_", " ")}` }),
        ]);
      }),
      (() => {
        const swatch = element("span", { className: "legend-swatch attention-swatch" });
        return element("span", { className: "legend-item" }, [
          swatch,
          element("span", { text: t("Attention: active") }),
        ]);
      })(),
    ],
  );
  renderDomainMetrics(state.data.days[state.data.days.length - 1]);
  const dayCount = state.data.days.length;
  const trendMessage = byId("trend-message");
  const trendChart = byId("trend-chart");
  if (dayCount === 1) {
    const only = state.data.days[0];
    trendMessage.textContent =
      `${t("History begins")} ${formatDate(only.date)}. ${t("At least two daily snapshots are required to calculate a trend")}. ` +
      `${t("Baseline")}: ${only.evidence_count} ${t("evidence records")} ${t("and")} ${only.attention.active_count} ${t("active attention signals")}.`;
    trendChart.hidden = true;
  } else if (dayCount === 2) {
    trendMessage.textContent = sameCollectionContext(
      state.data.days[1],
      state.data.days[0],
    )
      ? t("Two snapshots are available. The chart shows the first comparable daily change; broader trend language begins with three snapshots.") +
        coverageNote(state.data.days[1])
      : t("Two snapshots are available, but their connector coverage or report limit differs, so the change between them is not comparable.");
    trendChart.hidden = false;
  } else {
    const latest = state.data.days[dayCount - 1];
    const previous = state.data.days[dayCount - 2];
    // Raising the report limit lifts every count at once. Announcing that as
    // movement would report a collection-policy change as a change in field,
    // so the same gate the domain cards use applies to this sentence.
    const comparable = sameCollectionContext(latest, previous);
    if (comparable) {
      const evidenceDelta = latest.evidence_count - previous.evidence_count;
      const attentionDelta = latest.attention.active_count - previous.attention.active_count;
      const direction = (value) =>
      value > 0 ? `${t("up")} ${value}` : value < 0 ? `${t("down")} ${Math.abs(value)}` : t("flat");
      const movers = Object.entries(latest.category_trends || {})
        .filter(([, trend]) => trend.delta)
        .sort((a, b) => Math.abs(b[1].delta) - Math.abs(a[1].delta))
        .slice(0, 2)
        .map(([category, trend]) => `${category.replaceAll("_", " ")} ${deltaText(trend.delta)}`);
      trendMessage.textContent =
        `${t("Compared with")} ${previous.date}, ${t("surfaced evidence is")} ${direction(evidenceDelta)} ${t("and")} ${t("active attention is")} ${direction(attentionDelta)}.` +
        (movers.length ? ` ${t("Biggest domain moves")}: ${movers.join(", ")}.` : "") +
        coverageNote(latest);
    } else {
      trendMessage.textContent =
        `${latest.date} ${t("used different connector coverage or a different report limit than")} ${previous.date}, ${t("so the two scans")} ` +
        t("are not directly comparable. Counts are shown without a change figure.");
    }
    trendChart.hidden = false;
  }
  const countsFor = (day) =>
    state.trendReleasedOnly ? day.category_counts_released : day.category_counts;
  const maxTotal = Math.max(
    1,
    ...state.data.days.map((day) =>
      Math.max(...Object.values(countsFor(day)), day.attention.active_count),
    ),
  );
  replaceChildren(
    byId("trend-chart"),
    state.data.days.map((day, dayIndex) => {
      const dayCounts = countsFor(day);
      const total = Object.values(dayCounts).reduce((sum, count) => sum + count, 0);
      const segments = categories.map((category, index) => {
        const segment = element("span", { className: "bar-segment" });
        segment.style.height = `${((dayCounts[category] || 0) / maxTotal) * 260}px`;
        segment.style.setProperty("--bar-color", categoryColor(category, index));
        return segment;
      });
      const attentionBar = element("span", { className: "attention-volume" });
      attentionBar.style.height = `${(day.attention.active_count / maxTotal) * 260}px`;
      const button = element("button", {
        className: "day-column",
        attrs: {
          type: "button",
          "aria-label": `${formatDate(day.date)}: ${total} overlapping evidence category matches across ${day.evidence_count} evidence records and ${day.attention.active_count} attention signals`,
        },
      }, [
        element("span", { className: "series-bars" }, [...segments, attentionBar]),
        element("span", { className: "day-label", text: day.date.slice(5) }),
      ]);
      const previous = state.data.days[dayIndex - 1];
      const show = () => {
        // Escape stays honoured until the pointer or focus leaves and returns,
        // so the card does not spring back while the column is still active.
        if (dismissedTooltipColumn === button) return;
        // Clear the previous column's description first: moving between columns
        // must never leave two triggers pointing at one card.
        hideDayTooltip();
        showDayTooltip(button, day, previous, dayCounts, categories);
      };
      button.showDayTooltip = show;
      button.addEventListener("pointerenter", show);
      button.addEventListener("focus", show);
      // Mixed pointer and keyboard use: leaving with the mouse must not close a
      // card the keyboard still owns, so hand it back to the focused column.
      // An Escape dismissal lifts only once the column is neither hovered nor
      // focused; otherwise taking the mouse off a focused column would undo the
      // dismissal and reopen the card the reader just closed.
      button.addEventListener("pointerleave", releaseDayTooltip);
      button.addEventListener("blur", releaseDayTooltip);
      button.addEventListener("click", () => {
        state.todayDate = day.date;
        setView("today");
        renderToday();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      return button;
    }),
  );
  hideDayTooltip();
  byId("snapshot-count").textContent = `${state.data.snapshot_count} ${t("snapshots")}`;
  replaceChildren(
    byId("trend-table"),
    [...state.data.days].reverse().map((day) => {
      const link = element("a", { text: day.date, attrs: { href: `?date=${day.date}` } });
      link.addEventListener("click", (event) => {
        event.preventDefault();
        state.todayDate = day.date;
        setView("today");
        renderToday();
      });
      return element("tr", {}, [
        element("td", {}, [link]),
        element("td", {
          text: `${formatDate(day.since, { dateStyle: "short", timeStyle: "short" })} → ${formatDate(day.generated_at, { dateStyle: "short", timeStyle: "short" })}`,
        }),
        element("td", { text: day.evidence_count }),
        element("td", { text: countMapText(day.source_counts) }),
        element("td", {
          text: countMapText(day.category_counts),
        }),
        element("td", { text: countMapText(day.event_kind_counts) }),
        element("td", {
          text: `${day.attention.new_count} ${t("new")} · ${day.attention.active_count} ${t("active")}`,
        }),
        element("td", { text: healthSummary(day.ingest_health) }),
      ]);
    }),
  );
}

// The chart exists to compare days, so the tooltip answers only what made this
// column this tall and whether that is up or down. Momentum, baselines, and
// cumulative totals stay on the domain cards rather than being repeated here.
const TOOLTIP_CATEGORY_LIMIT = 4;

// The column whose card is open, so a scroll or resize can re-place it, and the
// column Escape dismissed, so re-entering is required before it opens again.
let openTooltipColumn = null;
let dismissedTooltipColumn = null;

function showDayTooltip(column, day, previous, dayCounts, categories) {
  const tooltip = byId("day-tooltip");
  const total = Object.values(dayCounts).reduce((sum, count) => sum + count, 0);
  // A different report limit or connector set lifts every count at once, so the
  // same gate the headline sentence uses decides whether a delta is meaningful.
  const comparable = previous && sameCollectionContext(day, previous);
  const previousTotal = comparable
    ? Object.values(
        state.trendReleasedOnly
          ? previous.category_counts_released
          : previous.category_counts,
      ).reduce((sum, count) => sum + count, 0)
    : null;
  const ranked = categories
    .map((category, index) => ({
      category,
      count: dayCounts[category] || 0,
      color: categoryColor(category, index),
    }))
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count);
  const shown = ranked.slice(0, TOOLTIP_CATEGORY_LIMIT);
  const restCount = ranked
    .slice(TOOLTIP_CATEGORY_LIMIT)
    .reduce((sum, entry) => sum + entry.count, 0);

  const rows = shown.map((entry) => {
    const swatch = element("span", { className: "legend-swatch" });
    swatch.style.setProperty("--swatch", entry.color);
    return element("span", { className: "day-tooltip-row" }, [
      swatch,
      element("span", {
        className: "day-tooltip-name",
        text: entry.category.replaceAll("_", " "),
      }),
      element("span", { className: "day-tooltip-value", text: entry.count }),
    ]);
  });
  if (restCount) {
    rows.push(
      element("span", { className: "day-tooltip-row day-tooltip-rest" }, [
        element("span", {
          className: "day-tooltip-name",
          text: `+${ranked.length - shown.length} ${t("more categories")}`,
        }),
        element("span", { className: "day-tooltip-value", text: restCount }),
      ]),
    );
  }

  replaceChildren(tooltip, [
    element("span", { className: "day-tooltip-date", text: formatDate(day.date) }),
    element("span", {
      className: "day-tooltip-total",
      text:
        `${metricLabel(total, "category match", "category matches")}` +
        (previousTotal === null
          ? ""
          : total === previousTotal
            ? ` · ${t("flat")} vs ${previous.date.slice(5)}`
            : ` · ${deltaText(total - previousTotal)} vs ${previous.date.slice(5)}`),
    }),
    rows.length ? element("span", { className: "day-tooltip-rows" }, rows) : null,
    element("span", {
      className: "day-tooltip-attention",
      text: `${t("Active attention")}: ${day.attention.active_count}`,
    }),
  ]);

  tooltip.hidden = false;
  tooltip.setAttribute("aria-hidden", "false");
  // Point the trigger at the card while it is open. Without this the breakdown
  // is visual only: a screen reader on the focused column would never reach it.
  column.setAttribute("aria-describedby", tooltip.id);
  openTooltipColumn = column;
  positionDayTooltip(tooltip, column);
  // Tabbing to an off-screen column scrolls the chart after focus fires, which
  // would leave the card behind. Re-place it once that scrolling has settled.
  requestAnimationFrame(() => {
    if (openTooltipColumn === column && !tooltip.hidden) {
      positionDayTooltip(tooltip, column);
    }
  });
}

function positionDayTooltip(tooltip, column) {
  const frame = tooltip.parentElement;
  // Drop any narrowing a previous cramped placement applied, so every hover is
  // measured at the card's natural width.
  tooltip.style.maxWidth = "";
  const frameBox = frame.getBoundingClientRect();
  const columnBox = column.getBoundingClientRect();
  const width = tooltip.offsetWidth;
  const height = tooltip.offsetHeight;
  // Reads the live width, so a placement that narrows the card first still
  // clamps against its new size rather than the width measured on entry.
  const clampLeft = (value) =>
    Math.min(
      Math.max(value, 8),
      Math.max(frame.clientWidth - tooltip.offsetWidth - 8, 8),
    );
  // The bar stack is a fixed-height plotting box, so its own top says nothing
  // about how tall the rendered bars are. Measure the drawn segments instead.
  const drawn = [...column.querySelectorAll(".bar-segment, .attention-volume")]
    .map((bar) => bar.getBoundingClientRect())
    .filter((box) => box.height > 0);
  const barTop = drawn.length
    ? Math.min(...drawn.map((box) => box.top))
    : columnBox.bottom;
  const above = barTop - frameBox.top - height - 10;
  const center = columnBox.left - frameBox.left + columnBox.width / 2;
  if (above >= 0) {
    // There is room over the bar, so sit above it and stay centred.
    tooltip.style.left = `${clampLeft(center - width / 2)}px`;
    tooltip.style.top = `${above}px`;
    return;
  }
  // A tall bar leaves no headroom. Move beside the column rather than on top of
  // it, so the hovered bar the reader is inspecting is never covered.
  const gap = 12;
  const rightEdge = columnBox.right - frameBox.left + gap;
  const leftEdge = columnBox.left - frameBox.left - gap - width;
  const fitsRight = rightEdge + width <= frame.clientWidth - 8;
  const fitsLeft = leftEdge >= 8;
  const besideTop = () =>
    `${Math.max(
      Math.min(barTop - frameBox.top, frame.clientHeight - tooltip.offsetHeight - 8),
      8,
    )}px`;
  if (fitsRight || fitsLeft) {
    tooltip.style.left = `${clampLeft(fitsRight ? rightEdge : leftEdge)}px`;
    tooltip.style.top = besideTop();
    return;
  }
  // Neither side has room at the card's natural width. Narrow it to whichever
  // side has more space rather than letting it clamp back over the bar; the
  // card is capped in CSS, so this only ever shrinks it further.
  const roomRight = frame.clientWidth - 8 - rightEdge;
  const roomLeft = columnBox.left - frameBox.left - gap - 8;
  const useRight = roomRight >= roomLeft;
  tooltip.style.maxWidth = `${Math.max(Math.round(useRight ? roomRight : roomLeft), 120)}px`;
  tooltip.style.left = `${clampLeft(
    useRight ? rightEdge : columnBox.left - frameBox.left - gap - tooltip.offsetWidth,
  )}px`;
  tooltip.style.top = besideTop();
}

function hideDayTooltip() {
  const tooltip = byId("day-tooltip");
  if (!tooltip) return;
  tooltip.hidden = true;
  tooltip.setAttribute("aria-hidden", "true");
  openTooltipColumn = null;
  document
    .querySelectorAll("#trend-chart .day-column[aria-describedby]")
    .forEach((column) => column.removeAttribute("aria-describedby"));
}

// Escape closes the card without moving focus, so a reader who finds it in the
// way can clear it and keep their place in the column order.
function dismissDayTooltip() {
  if (!openTooltipColumn) return false;
  dismissedTooltipColumn = openTooltipColumn;
  hideDayTooltip();
  return true;
}

// The chart scrolls horizontally, so an open card has to follow its column. A
// column scrolled out of the viewport takes its card with it: on a narrow frame
// the card would otherwise stay pinned at the clamp edge, labelled with a day
// no longer on screen.
function repositionDayTooltip() {
  const tooltip = byId("day-tooltip");
  if (!tooltip || tooltip.hidden || !openTooltipColumn) return;
  const chart = byId("trend-chart");
  const columnBox = openTooltipColumn.getBoundingClientRect();
  const chartBox = chart.getBoundingClientRect();
  if (columnBox.right <= chartBox.left || columnBox.left >= chartBox.right) {
    hideDayTooltip();
    return;
  }
  positionDayTooltip(tooltip, openTooltipColumn);
}

// A pointer leaving, or focus moving on, closes the card only if no day column
// still holds focus. Otherwise the keyboard's card is restored. The check is
// deferred because blur fires before focus settles on the next element, and a
// pointerleave arrives before :hover has updated.
function releaseDayTooltip() {
  hideDayTooltip();
  requestAnimationFrame(() => {
    // An Escape dismissal outlives a pointer moving away: it lifts only once
    // its column is neither hovered nor focused, so taking the mouse off a
    // focused column cannot reopen the card the reader just closed.
    const dismissed = dismissedTooltipColumn;
    if (
      dismissed &&
      document.activeElement !== dismissed &&
      !dismissed.matches(":hover")
    ) {
      dismissedTooltipColumn = null;
    }
    const focused = document.activeElement;
    if (
      focused &&
      focused.classList &&
      focused.classList.contains("day-column") &&
      typeof focused.showDayTooltip === "function" &&
      byId("day-tooltip").hidden
    ) {
      focused.showDayTooltip();
    }
  });
}

function metricLabel(value, singular, plural = `${singular}s`) {
  const count = Number(value || 0);
  const noun = count === 1 ? t(singular) : t(plural);
  return `${count.toLocaleString()} ${noun}`;
}

function countMapText(values) {
  const entries = Object.entries(values || {});
  return entries.length
    ? entries
        .map(([name, count]) => `${name.replaceAll("_", " ")} ${count}`)
        .join(" · ")
    : t("none");
}

function healthSummary(entries) {
  // A source that returned nothing still succeeded. Only a failure is not ok,
  // and an empty run is reported alongside rather than counted as a fault.
  const total = entries.length;
  const ok = entries.filter((entry) => entry.ok).length;
  const empty = entries.filter((entry) => entry.ok && entry.item_count === 0).length;
  const base = ok === total ? t("all ok") : `${ok}/${total} ${t("ok")}`;
  return empty ? `${base} · ${empty} ${t("empty")}` : base;
}

function allObservations() {
  if (state.observations) return state.observations;
  const evidence = state.data.days.flatMap((day) =>
    day.evidence_items.map((item) => ({
      ...item,
      recommended:
        item.recommended ??
        (day.selection?.recommendation_score !== undefined &&
          Number(item.total_score || 0) >=
          Number(
            day.selection.recommendation_score,
          )),
      recommendation_score: day.selection?.recommendation_score,
      minimum_score: day.selection?.minimum_score,
      snapshot_date: day.date,
      observation_kind: "evidence",
    })),
  );
  const attention = state.data.days.flatMap((day) =>
    day.attention.observations.map((item) => ({
      ...item,
      snapshot_date: day.date,
      artifact_urls: item.primary_artifact_url ? [item.primary_artifact_url] : [],
      organizations: item.producer ? [item.producer] : [],
      observation_kind: "attention",
    })),
  );
  state.observations = [...evidence, ...attention].sort((a, b) => {
    const dateOrder = String(b.snapshot_date).localeCompare(String(a.snapshot_date));
    return dateOrder || Number(b.total_score || 0) - Number(a.total_score || 0);
  });
  return state.observations;
}

function populateSelect(target, values, label, selected) {
  replaceChildren(target, [
    option("", `All ${label}`),
    ...values.map((value) => option(value, value.replaceAll("_", " "), value === selected)),
  ]);
}

function syncFilters() {
  const observations = allObservations();
  populateSelect(
    byId("kind-filter"),
    state.data.facets.kinds,
    "kinds",
    state.kind,
  );
  populateSelect(
    byId("category-filter"),
    [...new Set(observations.flatMap((item) => item.categories || []))].sort(),
    "categories",
    state.category,
  );
  populateSelect(
    byId("source-filter"),
    [...new Set(observations.map((item) => item.source))].sort(),
    "sources",
    state.source,
  );
  populateSelect(
    byId("organization-filter"),
    [
      ...new Set(
        observations.flatMap((item) => item.organizations || []),
      ),
    ].sort(),
    "organizations",
    state.organization,
  );
  populateSelect(
    byId("event-filter"),
    [...new Set(observations.map((item) => item.event_kind))].sort(),
    "events",
    state.event,
  );
  byId("search-filter").value = state.q;
}

function filteredObservations() {
  const query = state.q.trim().toLowerCase();
  return allObservations().filter((item) => {
    const haystack = `${item.title} ${item.summary} ${item.source}`.toLowerCase();
    return (
      (state.todayDate === "all" || item.snapshot_date === state.todayDate) &&
      (!state.kind || item.observation_kind === state.kind) &&
      (!state.category || (item.categories || []).includes(state.category)) &&
      (!state.source || item.source === state.source) &&
      (!state.organization || (item.organizations || []).includes(state.organization)) &&
      (!state.event || item.event_kind === state.event) &&
      (!query || haystack.includes(query))
    );
  });
}

// When a record is supplied, the rubric is rendered with that record's own
// component scores beside each weight, so the reader can see the arithmetic
// that produced the total rather than a generic description of it.
// versionOverride opens a specific rubric version (e.g. from a #rubric=1
// deep link) without implying a record's own scores are being shown.
function openRubric(item = null, versionOverride = null) {
  const data = versionOverride
    ? state.data?.rubrics?.[String(versionOverride)] || rubricFor(item)
    : rubricFor(item);
  const dialog = byId("rubric-dialog");
  if (!data) return;
  clearFrontierPointSelection();
  const max = Number(data.score_max) || 4;
  const components = data.components || [];
  const contribution = (component) =>
    Number(item?.[`${component.key}_score`] || 0) * Number(component.weight || 0);

  // Two rubrics are in circulation on different scales (v1 tops out at 4, v2 at
  // 100). A dialog that says only "0 to 4" leaves a reader who has read the
  // README's 0-100 rubric unable to tell whether the number is wrong or simply
  // older, so the version is named rather than implied.
  const version = Number(data.scoring_version) || 1;
  const current = Number(state.data?.rubric?.scoring_version) || version;
  const isLegacy = version !== current;
  state.rubric = String(version);
  writeUrl();
  const header = [
    element("p", {
      className: "detail-source",
      text: `${t("Scoring rubric v")}${version}${isLegacy ? t(" · superseded") : t(" · current")}`,
    }),
    element("h2", {
      className: "detail-title rubric-title",
      text: t("How priority is scored"),
      attrs: { id: "rubric-title" },
    }),
    element("p", {
      className: "detail-summary",
      text:
        `${t("Priority is the weighted mean of four components, each measured on a 0 to")} ${max.toFixed(2)} ` +
        t("scale. Every number below is read from the same definition the pipeline applies."),
    }),
    ...(isLegacy
      ? [
          element("p", {
            className: "discovery-note",
            text:
              (item
                ? `${t("This record was scored by rubric v")}${version}${t(" on a")} 0 ${t("to")} ${max.toFixed(2)} scale. `
                : `${t("Rubric v")}${version}${t(" scored records on")} 0 ${t("to")} ${max.toFixed(2)} scale. `) +
              `${t("The current rubric is v")}${current}${t(" on a")} 0 ${t("to")} ` +
              `${(Number(state.data?.rubric?.score_max) || 100).toFixed(2)} scale. ${t("Scores from the")} ` +
              t("two versions are not directly comparable, and past records are not rescored."),
          }),
        ]
      : []),
    element("p", { className: "rubric-formula", text: data.formula }),
  ];

  if (item) {
    header.push(
      element("div", { className: "rubric-worked" }, [
        element("strong", { text: `${t("This record scores")} ${Number(item.total_score || 0).toFixed(2)}` }),
        element("p", {
          text: components
            .map(
              (component) =>
                `${component.weight.toFixed(2)} x ${Number(
                  item[`${component.key}_score`] || 0,
                ).toFixed(2)} ${component.label.toLowerCase()}`,
            )
            .join("  +  "),
        }),
      ]),
    );
  }

  const componentSections = components.map((component) =>
    element("section", { className: "rubric-component" }, [
      element("div", { className: "rubric-component-head" }, [
        element("h3", { text: component.label }),
        element("span", {
          className: "rubric-weight",
          text: `${t("weight")} ${component.weight.toFixed(2)}`,
        }),
      ]),
      element("p", { text: component.summary }),
      element(
        "ul",
        { className: "rubric-bands" },
        (component.bands || []).map((band) => element("li", { text: band })),
      ),
      item
        ? element("p", { className: "rubric-contribution" }, [
            element("span", {
              text:
                `${t("Scored")} ${Number(item[`${component.key}_score`] || 0).toFixed(2)}` +
                ` · ${t("contributes")} ${contribution(component).toFixed(2)} ${t("to the total")}`,
            }),
          ])
        : null,
    ]),
  );

  const limits =
    (data.limits || []).length
      ? element("section", { className: "rubric-limits" }, [
          element("h3", { text: t("What this score does not claim") }),
          element(
            "ul",
            {},
            data.limits.map((limit) => element("li", { text: limit })),
          ),
        ])
      : null;

  // Selection policy belongs to the record's scan, not its shared scoring
  // rubric version. Older v2 records were genuinely filtered at 40, while new
  // v2 records retain everything eligible and use 40 only for this badge.
  const selectedDay = dailySnapshot();
  const recommendationScore = item
    ? item.recommendation_score
    : selectedDay?.selection?.recommendation_score;
  const historicalMinimum = recommendationScore === undefined
    ? item
      ? item.minimum_score
      : selectedDay?.selection?.minimum_score
    : undefined;
  const cutoff =
    recommendationScore !== undefined && recommendationScore !== null
      ? element("p", {
          className: "discovery-note",
          text:
            `${t("Every record matching at least one taxonomy category is retained. A score of")} ` +
            `${Number(recommendationScore).toFixed(2)} ${t(
              "or above adds the Recommended badge; it does not control inclusion. Watchlisted artifacts are also retained.",
            )}`,
        })
      : historicalMinimum !== undefined && historicalMinimum !== null
        ? element("p", {
            className: "discovery-note",
            text:
              `${t("This historical scan used")} ${Number(historicalMinimum).toFixed(2)} ${t("as")} ` +
              t("an inclusion cutoff. Records below it were not retained."),
          })
        : null;

  replaceChildren(byId("rubric-content"), [
    ...header,
    ...componentSections,
    limits,
    cutoff,
    element("div", { className: "detail-links" }, [
      element("a", {
        className: "secondary-link",
        text: "Read the scoring code ↗",
        attrs: {
          href: "https://github.com/ktwu01/benchmark-radar/blob/main/src/benchmark_radar/rubric.py",
          target: "_blank",
          rel: "noopener noreferrer",
        },
      }),
    ]),
  ]);
  dialog.showModal();
}

function expandedRecord(item, teaser) {
  const isAttention = item.observation_kind === "attention";
  const primaryArtifact = item.primary_artifact_url || item.artifact_urls?.[0];
  const scoreEntries = isAttention
    ? [
        [
          t(item.source === "Hacker News" ? "HN points" : "Activity points"),
          Number(item.metrics?.points || 0).toLocaleString(),
        ],
        [t("Comments"), Number(item.metrics?.comments || 0).toLocaleString()],
        [t("Submissions"), Number(item.metrics?.submissions ?? 1).toLocaleString()],
        [t("Published"), formatDate(item.published_at, { dateStyle: "medium" })],
      ]
    : [
        [t("Priority"), Number(item.total_score || 0).toFixed(2)],
        [t("Relevance"), Number(item.relevance_score || 0).toFixed(2)],
        [t("Evidence"), Number(item.evidence_score || 0).toFixed(2)],
        [t("Recency"), Number(item.recency_score || 0).toFixed(2)],
        // Adoption is weighted into the total, so hiding it here left the
        // four shown components unable to explain the priority above them.
        [t("Adoption"), Number(item.adoption_score || 0).toFixed(2)],
      ];
  const rationale = element(
    "ul",
    { className: "rationale-list" },
    (item.rationale || []).map((reason) => element("li", { text: reason })),
  );
  const attentionNotice = isAttention
    ? element("div", { className: "attention-notice" }, [
        element("strong", { text: t("Not quality-scored") }),
        element("p", {
          text: "This is a public attention signal. Its activity is shown separately from scientific evidence and priority.",
        }),
      ])
    : null;
  const supporting =
    isAttention && item.supporting_observations?.length
      ? element("section", { className: "supporting-signals" }, [
          element("h3", { text: "Supporting submissions" }),
          element(
            "ul",
            {},
            item.supporting_observations.map((record) =>
              element("li", {}, [
                element("a", {
                  text: `${record.source || item.source} #${record.source_id}`,
                  attrs: {
                    href: safeHttpUrl(record.url),
                    target: "_blank",
                    rel: "noopener noreferrer",
                  },
                }),
                element("span", {
                  text: `${formatDate(record.published_at, { dateStyle: "medium" })} · ${metricLabel(record.metrics?.points, "point")} · ${metricLabel(record.metrics?.comments, "comment")}`,
                }),
              ]),
            ),
          ),
        ])
      : null;
  const links = element("div", { className: "detail-links" }, [
    ...(isAttention && safeHttpUrl(primaryArtifact)
      ? [
          element("a", {
            className: "primary-link",
            text: t("Open primary artifact ↗"),
            attrs: {
              href: safeHttpUrl(primaryArtifact),
              target: "_blank",
              rel: "noopener noreferrer",
            },
          }),
        ]
      : []),
    element("a", {
      className: isAttention ? "secondary-link" : "primary-link",
      text: isAttention
        ? t("Open public discussion ↗")
        : item.source === "Hugging Face"
          ? t("Read full card ↗")
          : t("Open primary source ↗"),
      attrs: { href: safeHttpUrl(item.url), target: "_blank", rel: "noopener noreferrer" },
    }),
  ]);
  return element("div", { className: "record-detail" }, [
    element("p", {
      className: "detail-source",
      text: `${item.source} · ${item.event_kind} · ${item.snapshot_date}`,
    }),
    element("p", {
      className: item.summary ? "detail-summary" : "detail-summary signal-nodesc",
      text: item.summary
        ? teaser
          ? summaryRemainder(item.summary, teaser) || t("No further description beyond the preview above.")
          : item.summary
        : t("No description published at the source."),
    }),
    attentionNotice,
    element(
      "dl",
      { className: "detail-grid" },
      scoreEntries.map(([label, value]) => definition(label, value)),
    ),
    element("h3", { text: t("Why surfaced") }),
    rationale,
    supporting,
    isAttention
      ? element("p", {
          className: "discovery-note",
          text:
            `${t("Producer discovered")} ${formatDate(item.discovered_at, { dateStyle: "medium", timeStyle: "short" })} UTC · ` +
            `${t("Radar first observed")} ${formatDate(item.observed_at, { dateStyle: "medium", timeStyle: "short" })} UTC`,
        })
      : null,
    links,
  ]);
}

function mapFilterFor(entity) {
  state.q = "";
  state.kind = "evidence";
  state.category = "";
  state.source = "";
  state.organization = "";
  state.event = "";
  if (entity.type === "artifact") {
    state.q = entity.label;
    state.todayDate = entity.last_seen_at;
  } else if (entity.type === "topic") {
    state.category = entity.id.replace(/^topic:/, "");
  } else if (entity.type === "source") {
    state.source = entity.label;
  } else if (entity.type === "organization") {
    state.organization = entity.label;
  }
}

function selectMapNode(entity, relatedEntities) {
  state.entity = entity.id;
  mapFilterFor(entity);
  const topicAggregate = (state.data.corpus.aggregates.topics || []).find(
    (entry) => `topic:${entry.topic}` === entity.id,
  );
  const stats = [
    definition("Type", entity.type),
    definition("First seen", formatDate(entity.first_seen_at, { dateStyle: "medium" })),
    definition("Last seen", formatDate(entity.last_seen_at, { dateStyle: "medium" })),
    definition("Observed days", Number(entity.seen_days?.length || 0).toLocaleString()),
    ...(entity.type === "artifact"
      ? [
          definition("Observations", Number(entity.observation_count || 0).toLocaleString()),
          definition(
            "Latest priority",
            entity.latest_score === null || entity.latest_score === undefined
              ? "not scored"
              : Number(entity.latest_score).toFixed(2),
          ),
        ]
      : []),
    ...(topicAggregate
      ? [
          definition("Artifact count", topicAggregate.entity_count),
          definition("Source breadth", topicAggregate.source_breadth),
          // The window is nominally 7 days but divides by the days actually
          // observed, so early in the archive "7-day" named a span that does
          // not exist yet. The label states the span that was measured.
          definition(
            `${
              state.data.corpus.aggregates.observed_window_days ??
              state.data.corpus.aggregates.window_days
            }-day velocity`,
            topicAggregate.velocity === null
              ? "needs a prior window"
              : `${topicAggregate.velocity >= 0 ? "+" : ""}${topicAggregate.velocity}/day`,
          ),
        ]
      : []),
  ];
  const viewResults = element("button", {
    className: "primary-link map-view-results",
    text: t("View matching observations →"),
    attrs: { type: "button" },
  });
  viewResults.addEventListener("click", () => {
    setView("today");
    renderToday();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  replaceChildren(byId("map-detail"), [
    element("p", { className: "eyebrow", text: t("Selected node") }),
    element("h2", { text: entity.label }),
    element("p", {
      text:
        entity.type === "artifact"
          ? "The corresponding date and exact title search are now set for Today."
          : `The ${entity.type} filter is now set for Today.`,
    }),
    element("dl", {}, stats),
    relatedEntities.length
      ? element("p", {
          className: "discovery-note",
          text: `${t("Connected to")} ${relatedEntities
            .slice(0, 8)
            .map((related) => related.label)
            .join(", ")}${relatedEntities.length > 8 ? "…" : ""}`,
        })
      : null,
    viewResults,
    safeHttpUrl(entity.url)
      ? element("a", {
          className: "primary-link",
          text: t("Open primary source ↗"),
          attrs: {
            href: safeHttpUrl(entity.url),
            target: "_blank",
            rel: "noopener noreferrer",
          },
        })
      : null,
  ]);
  writeUrl();
}

function rankedCounts(values, limit = 6) {
  return Object.entries(values || {})
    .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0) || a[0].localeCompare(b[0]))
    .slice(0, limit);
}

// Rows are `[label, value]`, or `[label, value, detail]` where detail is an
// array of `[name, url]` pairs naming the records the count is made of. A row
// with a detail becomes a disclosure; a row without one stays a plain line, so
// the Trend Map's callers are unaffected.
//
// The point is that a summary count should be checkable. "OpenAI: 5 cards" is a
// claim about five specific documents, and a reader who cannot see which five
// has to take the number on faith.
function insightDetailList(detail) {
  return element(
    "ul",
    { className: "insight-detail-list" },
    detail.map(([name, url]) =>
      element("li", {}, [
        safeHttpUrl(url)
          ? element("a", {
              className: "adopter-link",
              text: name,
              attrs: { href: safeHttpUrl(url), target: "_blank", rel: "noopener noreferrer" },
            })
          : element("span", { text: name }),
      ]),
    ),
  );
}

function mapInsightCard(title, entries, emptyText) {
  return element("article", { className: "map-insight-card" }, [
    element("h2", { text: title }),
    entries.length
      ? element(
          "ul",
          {},
          entries.map(([label, value, detail]) =>
            detail && detail.length
              ? element("li", { className: "insight-row-expandable" }, [
                  element("details", {}, [
                    element("summary", {}, [
                      element("span", { text: label }),
                      element("strong", { text: value }),
                    ]),
                    insightDetailList(detail),
                  ]),
                ])
              : element("li", {}, [
                  element("span", { text: label }),
                  element("strong", { text: value }),
                ]),
          ),
        )
      : element("p", { text: emptyText }),
  ]);
}

function renderMapInsights(corpus) {
  const aggregates = corpus.aggregates || {};
  const entityTypes = aggregates.entity_types || {};
  const topicEntries = (aggregates.topics || [])
    .sort(
      (a, b) =>
        Number(b.entity_count || 0) - Number(a.entity_count || 0) ||
        a.topic.localeCompare(b.topic),
    )
    .map((topic) => [
      topic.topic.replaceAll("_", " "),
      `${metricLabel(topic.entity_count, "artifact")} · ${metricLabel(
        topic.source_breadth,
        "source",
      )}`,
    ]);
  const sourceEntries = rankedCounts(aggregates.sources).map(([source, count]) => [
    source,
    metricLabel(count, "observation"),
  ]);
  const organizationEntries = rankedCounts(aggregates.organizations).map(
    ([organization, count]) => [organization, metricLabel(count, "observation")],
  );
  const coverageEntries = [
    [t("Artifacts"), Number(entityTypes.artifact || 0).toLocaleString()],
    [t("Organizations"), Number(entityTypes.organization || 0).toLocaleString()],
    [t("Authors"), Number(entityTypes.person || 0).toLocaleString()],
    [t("Discovery sources"), Number(entityTypes.source || 0).toLocaleString()],
    [t("Topics"), Number(entityTypes.topic || 0).toLocaleString()],
  ];
  replaceChildren(byId("map-insights"), [
    mapInsightCard(t("Corpus coverage"), coverageEntries, t("No corpus entities yet.")),
    mapInsightCard(t("Topic coverage"), topicEntries, t("No topics assigned yet.")),
    mapInsightCard(t("Discovery sources"), sourceEntries, t("No discovery sources yet.")),
    mapInsightCard(
      t("Most represented organizations"),
      organizationEntries,
      t("No organizations identified yet."),
    ),
  ]);
}

// --- Model Card Adoption Rank (issue #83) -----------------------------------
//
// Counts how many curated model cards report each benchmark. The count is per
// document, so a card reporting AIME in four configurations contributes the
// same single adoption as a card reporting it once. That is the whole reason
// this ranking is publishable while a score table is not: a mention survives
// every reasoning-budget and pass@k caveat that makes two reported scores
// incomparable.

// Cut points for the benchmark release-date filter. Chosen as era boundaries
// rather than rolling windows so a bookmarked URL keeps meaning the same thing
// next month: "?lera=2026" is always "released in 2026", never "the last N
// months". A benchmark with no recorded release date is excluded by any era
// filter, which is the honest outcome -- it cannot be placed on the timeline.
// "Released in 2026" is bounded at both ends. An open-ended lower bound would
// silently absorb 2027 benchmarks the moment one is added, contradicting both
// the label and the permalink promise. "2025 or later" says "or later" and is
// therefore correctly open-ended.
const LEADERBOARD_ERAS = [
  { value: "2026", label: "Released in 2026", from: "2026-01-01", to: "2027-01-01" },
  { value: "2025", label: "Released 2025 or later", from: "2025-01-01" },
  { value: "pre2024", label: "Released before 2024", to: "2024-01-01" },
];

function leaderboardEntries() {
  const board = state.data?.model_card_leaderboard;
  if (!board) return [];
  const query = state.lq.trim().toLowerCase();
  const era = LEADERBOARD_ERAS.find((candidate) => candidate.value === state.lera);
  return (board.entries || []).filter((entry) => {
    if (state.ldomain && entry.domain !== state.ldomain) return false;
    if (state.lorg && !(entry.organizations || []).includes(state.lorg)) return false;
    if (era) {
      // ISO dates compare correctly as strings, so no Date parsing is needed
      // and no timezone can shift a benchmark across a year boundary.
      if (!entry.released) return false;
      if (era.from && entry.released < era.from) return false;
      if (era.to && entry.released >= era.to) return false;
    }
    if (!query) return true;
    const haystack = [entry.name, entry.benchmark_id, ...(entry.aliases || [])]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function adoptionBar(entry, maxCount) {
  // The 2% floor keeps a single-card benchmark from rendering as an empty
  // track, but it must not apply to a zero: a visible bar beside a count of 0
  // contradicts the number it is supposed to encode.
  const width =
    maxCount && entry.card_count
      ? Math.max(2, Math.round((entry.card_count / maxCount) * 100))
      : 0;
  return element(
    "div",
    {
      className: "adoption-bar",
      attrs: {
        role: "img",
        "aria-label": `${metricLabel(entry.card_count, "model card")} of ${metricLabel(
          state.data.model_card_leaderboard.model_card_count,
          "model card",
        )}`,
      },
    },
    [
      element("span", {
        className: "adoption-bar-fill",
        attrs: { style: `width: ${width}%` },
      }),
    ],
  );
}

function frontierEvents(entry) {
  const seenOrganizations = new Set();
  return (entry.adopters || [])
    .filter((adopter) => adopter.published)
    .sort(
      (a, b) =>
        a.published.localeCompare(b.published) ||
        a.organization.localeCompare(b.organization) ||
        a.model.localeCompare(b.model),
    )
    .map((adopter) => {
      const advances = !seenOrganizations.has(adopter.organization);
      seenOrganizations.add(adopter.organization);
      return {
        ...adopter,
        advances,
        organizationCount: seenOrganizations.size,
      };
    });
}

function isNewBenchmark(entry, board) {
  if (!entry.released) return false;
  const latestPublished = (board.model_cards || [])
    .map((card) => card.published)
    .filter(Boolean)
    .sort()
    .at(-1);
  if (!latestPublished) return false;
  const cutoff = new Date(`${latestPublished}T00:00:00Z`);
  cutoff.setUTCDate(cutoff.getUTCDate() - 548);
  return new Date(`${entry.released}T00:00:00Z`) >= cutoff;
}

function frontierAdvances(entry) {
  return frontierEvents(entry).filter((event) => event.advances);
}

function frontierDefaultEntry(board) {
  const adopted = (board.entries || []).filter((entry) => entry.card_count > 0);
  const byNewestSignal = (a, b) =>
    (b.released || "").localeCompare(a.released || "") ||
    frontierAdvances(b).length - frontierAdvances(a).length ||
    a.name.localeCompare(b.name);
  // A one-point plot is technically recent but visually says nothing. Open on
  // the newest instrument that has already crossed three dated organizations;
  // the full select still makes every early signal reachable and shareable.
  const newSharedSignals = adopted.filter(
    (entry) => isNewBenchmark(entry, board) && frontierAdvances(entry).length >= 3,
  );
  if (newSharedSignals.length) return [...newSharedSignals].sort(byNewestSignal)[0];
  const sharedSignals = adopted.filter((entry) => frontierAdvances(entry).length >= 2);
  return [...(sharedSignals.length ? sharedSignals : adopted)].sort(byNewestSignal)[0];
}

function reportingStage(entry, board) {
  const advances = frontierAdvances(entry).length;
  const total = Number(board.organization_count || 0);
  if (advances < 2) {
    return {
      id: "early",
      label: t("Early signal"),
      description: t("Only one dated organization is visible so far. It is too early to infer a plateau."),
    };
  }
  if (total > 0 && advances / total >= 0.8) {
    return {
      id: "saturated",
      label: t("Saturated reporting"),
      description: t("At least 80% of organizations in this curated registry report it; that is convention, not quality."),
    };
  }
  if (isNewBenchmark(entry, board) && advances <= 4) {
    return {
      id: "emerging",
      label: t("New & spreading"),
      description: t("Released in the newest 18-month window and already reported by several independent organizations."),
    };
  }
  return {
    id: "established",
    label: t("Established"),
    description: t("Reported across multiple organizations, but not yet a corpus-wide convention in this registry."),
  };
}

const BENCHMARK_TASK_SHAPES = {
  apex_agents: {
    provenance: "Source-paraphrased task shape",
    title: "Cross-application professional deliverable",
    example:
      "Produce a professional work product across supplied files and applications for an investment-banking, consulting, or legal workflow.",
    scenario:
      "Complete a long-horizon assignment authored by investment bankers, management consultants, or corporate lawyers while navigating realistic files and tools.",
    artifact:
      "A professional deliverable graded against task-specific rubrics, reference outputs, files, and metadata.",
  },
  mcp_atlas: {
    provenance: "Source-paraphrased task shape",
    title: "Cross-server tool orchestration",
    example:
      "Investigate an open-source project's repository and official domain, then calculate the difference between two dates using the available repository and WHOIS tools.",
    scenario:
      "Infer the needed tools from a natural-language request, then orchestrate three to six calls across real MCP servers without being told which tools to use.",
    artifact:
      "A grounded answer scored against independently verifiable claims, with the tool trajectory retained for diagnostics.",
  },
  frontiercode: {
    provenance: "Source-paraphrased task shape",
    title: "Maintainer-grade production code change",
    example:
      "Implement a concise maintainer request in a production repository while following its testing, linting, style, and scope guidance.",
    scenario:
      "Infer maintainer intent from a deliberately concise task description and the repository's own contribution guidelines.",
    artifact:
      "A mergeable pull request graded for correctness, test quality, scope discipline, style, and codebase standards.",
  },
};

const TASK_SHAPES = {
  agent: {
    title: "Multi-step professional workflow",
    scenario:
      "Work through a realistic task that may require research, document handling, and tool calls before producing a graded deliverable.",
    artifact: "A final artifact plus the trajectory used to create it.",
  },
  coding_agent: {
    title: "Repository-level software task",
    scenario:
      "Inspect an existing codebase, diagnose a reported problem, edit the implementation, and satisfy executable checks.",
    artifact: "A code patch evaluated by tests and task-specific criteria.",
  },
  tool_use: {
    title: "Tool-selection episode",
    scenario:
      "Choose among available tools, form valid calls, combine returned evidence, and answer the user without inventing results.",
    artifact: "A tool-call trace and grounded final response.",
  },
  computer_use: {
    title: "Interactive computer task",
    scenario:
      "Navigate a visual interface, inspect changing state, and complete a goal through observable clicks and typed actions.",
    artifact: "A successful end state with an auditable interaction trace.",
  },
  coding: {
    title: "Executable programming problem",
    scenario:
      "Write or repair a program from a specification while accounting for hidden cases and runtime constraints.",
    artifact: "Source code scored against executable tests.",
  },
  reasoning: {
    title: "Structured reasoning question",
    scenario:
      "Resolve a question whose answer requires several linked deductions rather than direct factual recall.",
    artifact: "A selected or generated answer, sometimes with a rationale.",
  },
  math: {
    title: "Competition-style mathematics problem",
    scenario:
      "Derive a numerical or symbolic answer from a compact problem statement and verify the final result.",
    artifact: "A final answer, with evaluation focused on correctness.",
  },
  long_context: {
    title: "Long-document retrieval task",
    scenario:
      "Locate and connect evidence distributed across a long input while resisting nearby but irrelevant details.",
    artifact: "An answer grounded in the supplied context.",
  },
  multimodal: {
    title: "Visual-language question",
    scenario:
      "Inspect an image or document together with text and answer using evidence that is not available in either modality alone.",
    artifact: "A grounded textual answer or structured prediction.",
  },
  science: {
    title: "Scientific problem-solving task",
    scenario:
      "Apply domain knowledge and quantitative reasoning to a research-style question with a checkable answer.",
    artifact: "A conclusion supported by calculations or scientific evidence.",
  },
  knowledge: {
    title: "Broad-knowledge question",
    scenario:
      "Answer a question spanning academic and general domains while separating known facts from plausible distractors.",
    artifact: "A selected or short generated answer.",
  },
  instruction_following: {
    title: "Constraint-following prompt",
    scenario:
      "Produce a useful response while satisfying explicit format, content, and exclusion constraints at the same time.",
    artifact: "A response graded for both usefulness and constraint compliance.",
  },
};

function taskShape(entry) {
  return (
    BENCHMARK_TASK_SHAPES[entry.benchmark_id] || TASK_SHAPES[entry.domain] || {
      title: `${entry.domain.replaceAll("_", " ")} evaluation task`,
      scenario:
        "Complete a domain-specific prompt under the benchmark's published protocol and return the requested output.",
      artifact: "An answer or artifact evaluated by the benchmark's own metric.",
    }
  );
}

function renderBenchmarkNavigator(board) {
  const adopted = (board.entries || []).filter((entry) => entry.card_count > 0);
  const stageOrder = [
    ["emerging", t("New & spreading")],
    ["early", t("Early signal")],
    ["established", t("Established")],
    ["saturated", t("Saturated reporting")],
  ];
  const groups = stageOrder
    .map(([stageId, label]) => {
      const entries = adopted
        .filter((entry) => reportingStage(entry, board).id === stageId)
        .sort(
          (a, b) =>
            Number(b.benchmark_id === state.lfrontier) -
              Number(a.benchmark_id === state.lfrontier) ||
            (stageId === "emerging" || stageId === "early"
              ? (b.released || "").localeCompare(a.released || "")
              : frontierAdvances(b).length - frontierAdvances(a).length) ||
            (b.released || "").localeCompare(a.released || "") ||
            a.name.localeCompare(b.name),
        )
        .slice(0, stageId === "emerging" ? 4 : 3);
      if (!entries.length) return null;
      return element("section", { className: "benchmark-shortlist-group" }, [
        element("h3", { text: label }),
        element(
          "div",
          { className: "benchmark-shortlist-buttons" },
          entries.map((entry) => {
            const button = element("button", {
              className: "benchmark-shortlist-button",
              attrs: {
                type: "button",
                "aria-pressed": entry.benchmark_id === state.lfrontier ? "true" : "false",
              },
            }, [
              element("span", { text: entry.name }),
              element("small", {
                text: `${metricLabel(frontierAdvances(entry).length, "dated organization")}`,
              }),
            ]);
            button.addEventListener("click", () => {
              selectFrontier(entry.benchmark_id);
              renderAdoptionFrontier(board);
              writeUrl();
            });
            return button;
          }),
        ),
      ]);
    })
    .filter(Boolean);
  replaceChildren(byId("benchmark-shortlist"), groups);
}

function daysBetween(start, end) {
  if (!start || !end) return null;
  return Math.max(
    0,
    Math.round(
      (new Date(`${end}T00:00:00Z`) - new Date(`${start}T00:00:00Z`)) / 86_400_000,
    ),
  );
}

function renderFrontierMilestones(entry, events) {
  const advances = events.filter((event) => event.advances);
  const repeats = events.length - advances.length;
  const list = element(
    "ol",
    { className: "frontier-milestone-list" },
    advances.map((event, index) => {
      const previousDate = index ? advances[index - 1].published : entry.released;
      const elapsed = daysBetween(previousDate, event.published);
      return element("li", {}, [
        element("span", { className: "milestone-number", text: index + 1 }),
        element("div", {}, [
          element("p", {
            className: "milestone-date",
            text: `${formatDate(event.published, { dateStyle: "medium" })}${
              elapsed === null
                ? ""
                : ` · ${metricLabel(elapsed, "day")} ${t("after")} ${
                    index ? t("the previous frontier step") : t("release")
                  }`
            }`,
          }),
          element("a", {
            className: "milestone-source",
            text: event.organization,
            attrs: {
              href: safeHttpUrl(event.url),
              target: "_blank",
              rel: "noopener noreferrer",
            },
          }),
          element("span", { className: "milestone-model", text: event.model }),
        ]),
      ]);
    }),
  );
  replaceChildren(byId("frontier-milestones"), [
    entry.released
      ? element("p", {
          className: "milestone-release",
          text: `${t("Released")} ${formatDate(entry.released, { dateStyle: "medium" })}`,
        })
      : null,
    list,
    repeats
      ? element("p", {
          className: "milestone-repeat-note",
          text: `${metricLabel(repeats, "repeat report")} ${t("did not add a new organization to the frontier")}.`,
        })
      : null,
  ]);
}

function renderFrontierTaskPreview(entry) {
  const shape = taskShape(entry);
  replaceChildren(byId("frontier-task-preview"), [
    element("p", {
      className: "eyebrow",
      text: shape.provenance || t("Representative task shape"),
    }),
    element("h3", { text: shape.title, attrs: { id: "frontier-task-heading" } }),
    element("div", { className: "task-shape" }, [
      shape.example ? element("span", { text: t("Paraphrased example") }) : null,
      shape.example ? element("p", { text: shape.example }) : null,
      element("span", { text: t("Scenario") }),
      element("p", { text: shape.scenario }),
      element("span", { text: t("Evaluated artifact") }),
      element("p", { text: shape.artifact }),
    ]),
    element("p", {
      className: "task-shape-note",
      text: shape.provenance
        ? t("Not a verbatim benchmark item. This description paraphrases the official source; open it for exact tasks and protocol.")
        : t("Not a verbatim benchmark item. This is an illustrative format based on the recorded domain; use the official source for exact tasks and protocol."),
    }),
    entry.caveat
      ? element("div", { className: "frontier-caveat" }, [
          element("strong", { text: "Comparison caveat" }),
          element("p", { text: entry.caveat }),
        ])
      : null,
    safeHttpUrl(entry.url)
      ? element("a", {
          className: "frontier-source-link",
          text: t("Open official benchmark source ↗"),
          attrs: {
            href: safeHttpUrl(entry.url),
            target: "_blank",
            rel: "noopener noreferrer",
          },
        })
      : null,
  ]);
}

function sparseFrontier(entry, events) {
  const first = events.find((event) => event.advances);
  const repeatCount = Math.max(0, events.length - 1);
  return element(
    "div",
    {
      className: "frontier-sparse",
      attrs: {
        role: "img",
        "aria-label": `${entry.name} ${t("has only one dated reporting organization; it is too early to infer a plateau")}.`,
      },
    },
    [
      element("div", { className: "frontier-sparse-step is-complete" }, [
        element("span", { text: "01" }),
        element("strong", { text: t("Benchmark released") }),
        element("small", {
          text: entry.released
            ? formatDate(entry.released, { dateStyle: "medium" })
            : t("Release date unrecorded"),
        }),
      ]),
      element("div", { className: "frontier-sparse-step is-complete" }, [
        element("span", { text: "02" }),
        element("strong", { text: t("First reporting organization") }),
        element("small", {
          text: first
            ? `${first.organization} · ${formatDate(first.published, { dateStyle: "medium" })}`
            : t("No dated report"),
        }),
      ]),
      element("div", { className: "frontier-sparse-step is-awaiting" }, [
        element("span", { text: "03" }),
        element("strong", { text: t("Awaiting an independent second organization") }),
        element("small", {
          text: repeatCount
            ? `${metricLabel(repeatCount, "later repeat")} ${t("still leaves one frontier step")}`
            : t("Too early to infer a reporting plateau"),
        }),
      ]),
    ],
  );
}

// --- Score progression (issue #91) ------------------------------------------
//
// The saturation half of the panel. `benchmark_score_progression` carries only
// values read verbatim out of cited documents, grouped into series the join rule
// permits a line through: identical instrument AND identical protocol. Anything
// else stays an unconnected point, because two numbers taken under unstated and
// possibly different conditions are not a measurement of change.
//
// Under that rule this corpus yields very few multi-date runs, and most are one
// vendor reporting its own successive models. That is a real property of vendor
// reporting rather than something to engineer around, so the chart draws what
// exists and `evidence` states what it can support.

function scoreRecord(benchmarkId) {
  return state.data?.benchmark_score_progression?.benchmarks?.[benchmarkId] || null;
}

// The plotted band for a score axis. Percent metrics are NOT drawn 0-100: every
// value in this corpus sits in the upper half, so a full-height axis compresses
// the interesting movement into a sliver. The band is padded around the observed
// range instead, and the axis is labelled with its real bounds so a reader
// cannot mistake a zoomed axis for a full one.
function scoreBand(record) {
  const values = record.observations.map((observation) => observation.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = Math.max(2, (high - low) * 0.18);
  const bound = record.saturation.bound;
  return {
    low: bound === null ? low - pad : Math.max(0, low - pad),
    high: bound === null ? high + pad : Math.min(bound, high + pad),
  };
}

function scoreReadout(entry, record) {
  const saturation = record.saturation;
  const evidence = record.evidence;
  const rows = [
    element("div", { className: "score-readout-figure" }, [
      element("span", { text: t("Best on record") }),
      element("strong", {
        text: `${saturation.best_value}${record.unit === "percent" ? "%" : ""}`,
      }),
      element("small", {
        text: `${saturation.best_model} · ${saturation.best_organization} · ${formatDate(
          saturation.best_reported_at,
          { dateStyle: "medium" },
        )}`,
      }),
    ]),
  ];
  if (saturation.headroom !== null) {
    rows.push(
      element("div", { className: "score-readout-figure" }, [
        element("span", { text: t("Headroom left") }),
        element("strong", { text: `${saturation.headroom}` }),
        // On a lower-is-better metric the backend measures headroom to zero, not
        // to `bound`. Naming the bound in both cases would print "10 points to
        // the 100-point bound" for a score of 10, which is arithmetically false.
        element("small", {
          text:
            record.direction === "lower_is_better"
              ? t("points to zero, the floor of this metric")
              : t("points to the {bound}-point bound of this metric", {
                  bound: saturation.bound,
                }),
        }),
      ]),
    );
  }
  rows.push(
    element("div", { className: "score-readout-figure" }, [
      element("span", { text: t("Readable values") }),
      element("strong", { text: String(record.observation_count) }),
      element("small", {
        text: `${metricLabel(record.dated_observation_count, "date")} · ${metricLabel(
          record.comparable_series_count,
          "comparable run",
        )}`,
      }),
    ]),
  );

  return element("div", { className: "score-readout-inner" }, [
    element("div", { className: "score-readout-figures" }, rows),
    element("div", { className: `score-evidence score-evidence-${evidence.id}` }, [
      element("strong", { text: evidence.label }),
      element("p", {}, [
        element("span", { className: "score-evidence-yes", text: t("Supports: ") }),
        document.createTextNode(evidence.supports),
      ]),
      element("p", {}, [
        element("span", { className: "score-evidence-no", text: t("Does not support: ") }),
        document.createTextNode(evidence.does_not_support),
      ]),
    ]),
    record.third_party_count
      ? element("p", {
          className: "score-readout-note",
          // The verb has to agree with the count, not stay singular beside a
          // pluralized noun ("4 values here is a third party...").
          text: `${metricLabel(record.third_party_count, "value")} ${
            record.third_party_count === 1 ? t("here is a third party") : t("here are third parties")
          } ${t("quoting another vendor's figure, marked with a ring on the chart")}.`,
        })
      : null,
  ]);
}

function renderScoreReadout(entry) {
  const host = byId("frontier-score-readout");
  if (!host) return;
  const record = scoreRecord(entry.benchmark_id);
  if (!record) {
    replaceChildren(host, [
      element("p", {
        className: "score-readout-empty",
        text:
          t("No score for this benchmark could be read verbatim from the cited documents, so the chart shows adoption only. An absent value is not a zero and not a plateau."),
      }),
    ]);
    return;
  }
  replaceChildren(host, [scoreReadout(entry, record)]);
}

let selectedFrontierPoint = null;
let selectedFrontierDetails = null;
let describedFrontierPoint = null;
let selectedFrontierSourceVisited = false;

function frontierTooltip() {
  const tooltip = element("div", {
    className: "frontier-tooltip",
    attrs: {
      id: "frontier-tooltip",
      role: "tooltip",
      hidden: "",
      "aria-live": "polite",
    },
  });
  tooltip.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && selectedFrontierPoint) {
      event.preventDefault();
      const point = selectedFrontierPoint;
      point.focus();
      clearFrontierPointSelection();
      return;
    }
    if (event.key !== "Tab" || !event.target.matches(".frontier-tooltip-source")) return;
    if (event.shiftKey) {
      event.preventDefault();
      selectedFrontierPoint?.focus();
      return;
    }
    const points = [...byId("frontier-chart").querySelectorAll("[data-frontier-point]")];
    const next = points[points.indexOf(selectedFrontierPoint) + 1];
    if (next) {
      selectedFrontierSourceVisited = true;
      event.target.setAttribute("tabindex", "-1");
      event.preventDefault();
      next.focus();
    }
  });
  return tooltip;
}

function frontierTooltipContent(details, pinned) {
  return [
    element("span", { className: "frontier-tooltip-kind", text: details.kind }),
    element("strong", { className: "frontier-tooltip-title", text: details.title }),
    element(
      "dl",
      { className: "frontier-tooltip-details" },
      details.rows.flatMap(({ label, value }) => [
        element("dt", { text: label }),
        element("dd", { text: value }),
      ]),
    ),
    pinned && safeHttpUrl(details.url)
      ? element("a", {
          className: "frontier-tooltip-source",
          text: t("Open source record ↗"),
          attrs: {
            href: safeHttpUrl(details.url),
            target: "_blank",
            rel: "noopener noreferrer",
            tabindex: selectedFrontierSourceVisited ? "-1" : "0",
          },
        })
      : null,
    element("span", {
      className: "frontier-tooltip-hint",
      text: pinned
        ? t("Pinned · click the marker again or press Escape to close")
        : t("Click the marker to pin these details"),
    }),
  ];
}

function positionFrontierTooltip(tooltip, group) {
  const host = byId("frontier-chart");
  if (!host) return;
  const hostBox = host.getBoundingClientRect();
  const pointBox = group.getBoundingClientRect();
  const gap = 10;
  const centered = pointBox.left + pointBox.width / 2 - tooltip.offsetWidth / 2;
  const viewportMaxLeft = Math.max(8, window.innerWidth - tooltip.offsetWidth - 8);
  const minLeft = Math.max(8, Math.min(hostBox.left + 8, viewportMaxLeft));
  const maxLeft = Math.max(
    minLeft,
    Math.min(hostBox.right - tooltip.offsetWidth - 8, viewportMaxLeft),
  );
  const left = Math.max(minLeft, Math.min(centered, maxLeft));
  tooltip.style.left = `${left - hostBox.left}px`;

  const above = pointBox.top - tooltip.offsetHeight - gap;
  const below = pointBox.bottom + gap;
  const viewportMaxTop = Math.max(8, window.innerHeight - tooltip.offsetHeight - 8);
  const top =
    above >= 8
      ? above
      : below + tooltip.offsetHeight <= window.innerHeight - 8
        ? below
        : Math.max(8, Math.min(pointBox.top - tooltip.offsetHeight / 2, viewportMaxTop));
  tooltip.style.top = `${top - hostBox.top}px`;
}

function repositionFrontierTooltip() {
  const tooltip = byId("frontier-tooltip");
  if (!tooltip || tooltip.hidden || !describedFrontierPoint) return;
  positionFrontierTooltip(tooltip, describedFrontierPoint);
}

function showFrontierTooltip(group, details, { pinned = false } = {}) {
  const tooltip = byId("frontier-tooltip");
  if (!tooltip) return;
  replaceChildren(tooltip, frontierTooltipContent(details, pinned));
  tooltip.hidden = false;
  tooltip.classList.toggle("is-pinned", pinned);
  tooltip.setAttribute("role", pinned ? "dialog" : "tooltip");
  if (pinned) {
    tooltip.setAttribute("aria-label", `${details.kind} details`);
    tooltip.removeAttribute("aria-live");
  } else {
    tooltip.removeAttribute("aria-label");
    tooltip.setAttribute("aria-live", "polite");
  }
  if (describedFrontierPoint && describedFrontierPoint !== group) {
    describedFrontierPoint.removeAttribute("aria-describedby");
  }
  describedFrontierPoint = group;
  group.setAttribute("aria-describedby", tooltip.id);
  positionFrontierTooltip(tooltip, group);
}

function hideFrontierTooltip() {
  const tooltip = byId("frontier-tooltip");
  if (!tooltip) return;
  tooltip.hidden = true;
  tooltip.classList.remove("is-pinned");
  describedFrontierPoint?.removeAttribute("aria-describedby");
  describedFrontierPoint = null;
}

function clearFrontierPointSelection() {
  if (selectedFrontierPoint) {
    selectedFrontierPoint.classList.remove("is-selected");
    selectedFrontierPoint.setAttribute("aria-pressed", "false");
    selectedFrontierPoint.removeAttribute("aria-describedby");
  }
  selectedFrontierPoint = null;
  selectedFrontierDetails = null;
  selectedFrontierSourceVisited = false;
  hideFrontierTooltip();
}

function restoreSelectedFrontierPoint() {
  if (selectedFrontierPoint && selectedFrontierDetails) {
    const tooltip = byId("frontier-tooltip");
    if (
      tooltip?.classList.contains("is-pinned") &&
      describedFrontierPoint === selectedFrontierPoint
    ) {
      return;
    }
    showFrontierTooltip(selectedFrontierPoint, selectedFrontierDetails, { pinned: true });
  } else {
    hideFrontierTooltip();
  }
}

function makeFrontierPointInteractive(group, details) {
  let hovered = false;
  let focused = false;
  const show = () => {
    const tooltip = byId("frontier-tooltip");
    if (
      selectedFrontierPoint !== group &&
      tooltip?.contains(document.activeElement)
    ) {
      return;
    }
    showFrontierTooltip(group, details, { pinned: selectedFrontierPoint === group });
  };
  group.addEventListener("pointerenter", () => {
    hovered = true;
    show();
  });
  group.addEventListener("pointerleave", () => {
    hovered = false;
    if (focused) show();
    else restoreSelectedFrontierPoint();
  });
  group.addEventListener("focus", () => {
    focused = true;
    show();
  });
  group.addEventListener("blur", () => {
    focused = false;
    if (selectedFrontierPoint === group) {
      restoreSelectedFrontierPoint();
    } else if (hovered) {
      show();
    } else {
      restoreSelectedFrontierPoint();
    }
  });
  group.addEventListener("click", (event) => {
    event.stopPropagation();
    if (selectedFrontierPoint === group) {
      clearFrontierPointSelection();
      return;
    }
    clearFrontierPointSelection();
    selectedFrontierPoint = group;
    selectedFrontierDetails = details;
    group.classList.add("is-selected");
    group.setAttribute("aria-pressed", "true");
    showFrontierTooltip(group, details, { pinned: true });
    byId("frontier-tooltip").querySelector("a")?.focus();
  });
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      group.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    } else if (
      event.key === "Tab" &&
      event.shiftKey &&
      selectedFrontierPoint &&
      selectedFrontierSourceVisited
    ) {
      const points = [...byId("frontier-chart").querySelectorAll("[data-frontier-point]")];
      const next = points[points.indexOf(selectedFrontierPoint) + 1];
      if (group === next) {
        event.preventDefault();
        selectedFrontierSourceVisited = false;
        showFrontierTooltip(selectedFrontierPoint, selectedFrontierDetails, { pinned: true });
        byId("frontier-tooltip").querySelector("a")?.focus();
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      clearFrontierPointSelection();
    }
  });
}

// Dense runs cannot carry one independent 44px SVG rectangle per marker: those
// rectangles overlap and the last one in paint order hides its neighbours. A
// chart-level resolver gives every tap a 22px acquisition radius, then assigns an
// overlap to the geometrically nearest visible mark instead of DOM paint order.
function enableFrontierTouchTargets(svg) {
  svg.addEventListener("click", (event) => {
    // Keyboard activation dispatches a detail-0 click from the focused group and
    // must keep that explicit target. Pointer-generated clicks are resolved by
    // geometry even when their painted DOM target is a different overlapping mark.
    if (event.detail === 0) return;
    let nearest = null;
    let nearestDistance = Infinity;
    svg.querySelectorAll("[data-frontier-point]").forEach((group) => {
      const box = group.getBoundingClientRect();
      const distance = Math.hypot(
        event.clientX - (box.left + box.right) / 2,
        event.clientY - (box.top + box.bottom) / 2,
      );
      if (distance < nearestDistance) {
        nearest = group;
        nearestDistance = distance;
      }
    });
    const direct = event.target.closest("[data-frontier-point]");
    if (nearest && nearestDistance <= 22 && nearest !== direct) {
      event.preventDefault();
      event.stopPropagation();
      nearest.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }
  }, true);
}

// A legend keyed to the marks actually on the chart. The panel previously relied
// on the prose explainer to say what orange versus gray meant, which put the key
// several lines away from the thing it explains; issue #91 reports readers taking
// the two for equivalent kinds of point. Each entry names the mark AND what it
// does to the count, because "new organization" alone does not say that the other
// kind leaves the staircase flat.
// `sparse` suppresses the staircase and the rug in favour of the step list, so
// their legend entries are suppressed with them: a key describing marks that are
// not on screen is worse than no key, and many shipped benchmarks take that path.
function renderFrontierLegend(entry, record, { sparse = false } = {}) {
  const host = byId("frontier-legend");
  if (!host) return;
  const swatch = (className) => element("span", { className: `legend-swatch ${className}` });
  const items = sparse
    ? []
    : [
        ["legend-swatch-point", t("New organization"), t("cumulative count increases")],
        [
          "legend-swatch-tick-first",
          t("First card from that organization"),
          t("the tick under the jump"),
        ],
        [
          "legend-swatch-tick-repeat",
          t("Later card, organization already counted"),
          t("count unchanged"),
        ],
      ];
  if (record) {
    items.push([
      "legend-swatch-score",
      t("Readable score"),
      t("connected only at one instrument and protocol"),
    ]);
    if (record.series.some((series) => series.connectable && !series.single_organization)) {
      items.push([
        "legend-swatch-score-line",
        t("Solid score connection"),
        t("same instrument and protocol across organizations"),
      ]);
    }
    if (record.series.some((series) => series.connectable && series.single_organization)) {
      items.push([
        "legend-swatch-score-line-single-org",
        t("Dashed score connection"),
        t("same instrument and protocol, one organization only"),
      ]);
    }
  }
  replaceChildren(
    host,
    items.map(([className, label, effect]) =>
      element("span", { className: "frontier-legend-item" }, [
        swatch(className),
        element("strong", { text: label }),
        element("span", { text: effect }),
      ]),
    ),
  );
}

// The per-organization color key under the chart. Each reporting organization
// gets a small circular chip in its frontier color carrying its real brand
// glyph, so the reader can map a colored circle on the staircase back to a name
// without hovering (issue #178, HLE/harbor style). Built from the organizations
// that actually have a dated card on this benchmark, in first-report order.
function renderFrontierOrgKey(entry, events) {
  const host = byId("frontier-org-key");
  if (!host) return;
  const ordered = [];
  const seen = new Set();
  const dated = (entry.adopters || [])
    .filter((adopter) => adopter.published)
    .sort((a, b) => a.published.localeCompare(b.published));
  for (const adopter of dated) {
    if (seen.has(adopter.organization)) continue;
    seen.add(adopter.organization);
    ordered.push(adopter);
  }
  if (!ordered.length) {
    replaceChildren(host, []);
    return;
  }
  replaceChildren(
    host,
    ordered.map((adopter) => {
      const org = adopter.organization;
      const glyph = svgElement("svg", {
        viewBox: "0 0 24 24",
        class: "frontier-org-key-glyph",
        "aria-hidden": "true",
      });
      for (const d of organizationIcon(org)) {
        glyph.append(svgElement("path", { d, fill: "currentColor" }));
      }
      return element("span", { className: "frontier-org-key-item" }, [
        element(
          "span",
          {
            className: "frontier-org-key-chip",
            attrs: { style: `background: ${organizationColor(org)}` },
          },
          [glyph],
        ),
        element("span", { className: "frontier-org-key-name", text: org }),
      ]);
    }),
  );
}

// `sparse` means the adoption stepper is being rendered separately because it has
// fewer than two frontier advances. The score track still draws, on its own axis,
// so a thin adoption layer never hides a readable score.
function adoptionFrontierChart(entry, board, events, { sparse = false } = {}) {
  const datedCards = (board.model_cards || []).filter((card) => card.published);
  const record = scoreRecord(entry.benchmark_id);
  // `events` may be empty when only the score track is being drawn, so both
  // bounds are computed from whatever dates exist rather than indexing into it.
  const startText = [entry.released, events[0]?.published, record?.first_reported_at]
    .filter(Boolean)
    .sort()[0];
  // Symmetric with `startText`: the range has to cover the score track as well
  // as the adoption track, or a score dated after the newest card -- reachable
  // when a card carries a later `revised` date -- lands outside the viewBox and
  // is silently clipped. Both ends therefore consider both layers.
  const endText = [
    events.length ? datedCards.map((card) => card.published).sort().at(-1) : null,
    events.at(-1)?.published,
    record?.last_reported_at,
  ]
    .filter(Boolean)
    .sort()
    .at(-1);
  const start = new Date(`${startText}T00:00:00Z`).getTime();
  const rawEnd = new Date(`${endText}T00:00:00Z`).getTime();
  const end = Math.max(rawEnd, start + 86_400_000);
  // A narrower viewBox on a narrow viewport. `width: 100%` scales height with
  // width, so a 920-unit box at 390px CSS pixels rendered the whole chart about
  // 90px tall and the staircase became unreadable. Halving the coordinate width
  // lets the same content scale up rather than being squashed; distorting the
  // aspect ratio instead would stretch the axis text illegibly.
  const narrow = typeof window !== "undefined" && window.innerWidth <= 760;
  const width = narrow ? 520 : 920;
  // The score band is only reserved when there is a score to draw. A benchmark
  // with no readable value gets the original single-plot height rather than an
  // empty lower half, which would read as "scores went to zero here".
  const band = record ? scoreBand(record) : null;
  const scoreHeight = record ? 132 : 0;
  const bandGap = record ? 34 : 0;
  // The left margin widens when a score band is present: its axis label is a
  // metric name ("resolved", "pass@1") rather than the fixed "organizations
  // reporting", and a 52px gutter clipped the longer ones at the viewBox edge.
  const margin = { top: 32, right: 20, bottom: 62, left: record ? 68 : 52 };
  const plotWidth = width - margin.left - margin.right;
  // The adoption plot collapses to nothing when its stepper is drawn separately,
  // so the SVG carries no empty region where the step line would have been.
  const plotHeight = sparse ? 0 : 370 - margin.top - margin.bottom;
  // The card rug: one tick per model card, on its own band under the staircase.
  // Repeat cards used to be plotted *on* the count axis at the running total,
  // which put a marker at a height the card did not cause -- a card that changed
  // nothing sat at the same y as the advance that did. Worse, several cards
  // sharing a date stacked into each other and occluded the numbers. Giving card
  // events their own band separates "how many organizations by this date" from
  // "when were the cards published", which is the whole confusion in issue #91.
  const rugHeight = sparse || !events.length ? 0 : 26;
  const rugGap = rugHeight ? 12 : 0;
  const height =
    margin.top + plotHeight + rugGap + rugHeight + bandGap + scoreHeight + margin.bottom;
  const rugTop = margin.top + plotHeight + rugGap;
  const maxOrganizations = Math.max(1, Number(board.organization_count || 0));
  const x = (date) =>
    margin.left +
    ((new Date(`${date}T00:00:00Z`).getTime() - start) / (end - start)) * plotWidth;
  const y = (count) => margin.top + plotHeight - (count / maxOrganizations) * plotHeight;
  // The score plot sits below the adoption plot and shares its x scale, which is
  // the whole point: the two readings are only comparable if a vertical line
  // through the chart means one date in both.
  const scoreTop = margin.top + plotHeight + rugGap + rugHeight + bandGap;
  // Better is always up. `direction` exists in the schema precisely so a metric
  // where lower wins (an edit distance, an error rate) does not render its
  // improvements as a downward slope; consulting it here is what makes the axis
  // mean "better" rather than "larger".
  const scoreDescends = record?.direction === "lower_is_better";
  const scoreY = (value) => {
    if (!band || band.high <= band.low) return scoreTop + scoreHeight / 2;
    const fraction = (value - band.low) / (band.high - band.low);
    const fromFloor = scoreDescends ? 1 - fraction : fraction;
    return scoreTop + scoreHeight - fromFloor * scoreHeight;
  };
  const advances = events.filter((event) => event.advances);

  const svg = svgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    // A group rather than an image: image descendants are presentational in the
    // accessibility tree, which would hide the interactive marker buttons.
    role: "group",
    "aria-label":
      (events.length
        ? `${entry.name} reporting adoption over time. ${advances.length} of ` +
          `${board.organization_count} organizations have a dated report.`
        : `${entry.name} readable scores over time. No mention of it carries a date, so no ` +
          "adoption timeline is shown.") +
      (record
        ? ` ${events.length ? "Below it, " : ""}${metricLabel(
            record.observation_count,
            "readable score",
          )} from ${formatDate(record.first_reported_at, { dateStyle: "medium" })} to ` +
          `${formatDate(record.last_reported_at, { dateStyle: "medium" })}, best ` +
          `${record.saturation.best_value}.`
        : " No readable score for this benchmark."),
  });
  // The adoption plot. Skipped entirely when its stepper is rendered separately:
  // a step line with fewer than two advances says nothing a reader can use.
  if (!sparse) {
    const tickStep = Math.max(1, Math.ceil(maxOrganizations / 5));
    const tickValues = new Set([0, maxOrganizations]);
    for (let count = tickStep; count < maxOrganizations; count += tickStep) {
      tickValues.add(count);
    }
    for (const count of [...tickValues].sort((a, b) => a - b)) {
      const yPosition = y(count);
      svg.append(
        svgElement("line", {
          x1: margin.left,
          y1: yPosition,
          x2: width - margin.right,
          y2: yPosition,
          class: "frontier-grid",
        }),
      );
      svg.append(
        svgElement(
          "text",
          { x: margin.left - 12, y: yPosition + 4, "text-anchor": "end", class: "frontier-tick" },
          count,
        ),
      );
    }

    let path = `M ${x(startText)} ${y(0)}`;
    for (const event of advances) {
      path += ` H ${x(event.published)} V ${y(event.organizationCount)}`;
    }
    path += ` H ${x(endText)}`;
    svg.append(svgElement("path", { d: path, class: "frontier-line" }));

    // Diamonds at the jumps, and only at the jumps. The marker number is gone: it
    // restated the y-axis value the marker already sits at, and a digit inside a
    // circle reads as a record id, so readers took the staircase for a numbered
    // list of points rather than a cumulative count.
    for (const event of advances) {
      const pointX = x(event.published);
      const pointY = y(event.organizationCount);
      const group = svgElement("g", {
        class: "frontier-point frontier-point-advance",
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "data-frontier-point": "",
        "aria-label":
          `${event.organization} first reported it ${formatDate(event.published, {
            dateStyle: "medium",
          })} with ${event.model}, taking the count to ${event.organizationCount}. ` +
          "Click to pin record details.",
      });
      const r = 8;
      const orgColor = organizationColor(event.organization);
      group.append(
        svgElement("circle", {
          cx: pointX,
          cy: pointY,
          r,
          style: `fill: ${orgColor}`,
          class: "frontier-point-face",
        }),
      );
      group.append(brandGlyph(event.organization, pointX, pointY, r * 1.6, "frontier-point-glyph"));
      makeFrontierPointInteractive(group, {
        kind: "New organization",
        title: `${event.organization} · ${event.model}`,
        rows: [
          { label: "Organization", value: event.organization },
          { label: "Model", value: event.model },
          {
            label: "Date",
            value: formatDate(event.published, { dateStyle: "medium" }),
          },
          {
            label: "Adoption",
            value: `First report · cumulative count ${event.organizationCount}`,
          },
          {
            label: "Source",
            value: String(event.document_type || "model card").replaceAll("_", " "),
          },
        ],
        url: event.url,
      });
      svg.append(group);
    }
  }

  // The card rug. Every card gets exactly one tick, so a date carrying several
  // cards shows several ticks side by side instead of a pile of circles on the
  // staircase. Orange marks a first report, gray a later card from an
  // organization already counted.
  if (rugHeight) {
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: rugTop + rugHeight / 2,
        x2: width - margin.right,
        y2: rugTop + rugHeight / 2,
        class: "card-rug-baseline",
      }),
    );
    // Tick positions are allocated across every card at once, not per date. Two
    // earlier versions were wrong in the same way at different scales: x(date)
    // alone overpainted cards sharing a date, and fanning each date independently
    // then pushed those ticks into a *neighbouring* date's -- on shipped GPQA
    // Diamond at the narrow viewBox a fanned 2026-02-11 tick landed 0.04 units
    // from the 2026-02-16 tick, inside a 2.5-unit stroke, so one still vanished
    // and swallowed the other's hover target. One-day-apart pairs collided at
    // desktop width too.
    //
    // So this is a single left-to-right sweep that keeps every tick at least a
    // stroke-width apart, then shifts the whole run back by half its total drift
    // to keep the group centred on the dates it represents. Ticks stay in date
    // order and no two can occupy the same pixel, which is the guarantee the rug
    // exists to make; a tick may sit a fraction of a unit off its exact date, and
    // that is the honest trade, since a hidden card is a lost observation while a
    // 3px nudge is not.
    const MIN_TICK_GAP = 3.5;
    const positions = [];
    let previous = -Infinity;
    for (const event of events) {
      const ideal = x(event.published);
      const placed = Math.max(ideal, previous + MIN_TICK_GAP);
      positions.push(placed);
      previous = placed;
    }
    const drift = positions.length ? positions[positions.length - 1] - x(events[events.length - 1].published) : 0;
    const shift = drift / 2;
    for (const [index, event] of events.entries()) {
      const tickX = positions[index] - shift;
      const group = svgElement("g", {
        class: `card-rug-tick${event.advances ? " card-rug-tick-first" : " card-rug-tick-repeat"}`,
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "data-frontier-point": "",
        "aria-label":
          `${event.organization}, ${event.model}, ${formatDate(event.published, {
            dateStyle: "medium",
          })}` +
          (event.advances
            ? ", first report from this organization"
            : ", later card from an organization already counted"),
      });
      // A first report gets a full-height tick, a repeat a short one, so the two
      // are distinguishable without relying on colour alone.
      const halfHeight = event.advances ? rugHeight / 2 : rugHeight / 4;
      group.append(
        svgElement("line", {
          x1: tickX,
          y1: rugTop + rugHeight / 2 - halfHeight,
          x2: tickX,
          y2: rugTop + rugHeight / 2 + halfHeight,
        }),
      );
      makeFrontierPointInteractive(group, {
        kind: event.advances ? "First report card" : "Repeat report card",
        title: `${event.organization} · ${event.model}`,
        rows: [
          { label: "Organization", value: event.organization },
          { label: "Model", value: event.model },
          {
            label: "Date",
            value: formatDate(event.published, { dateStyle: "medium" }),
          },
          {
            label: "Adoption",
            value: event.advances
              ? `First report · cumulative count ${event.organizationCount}`
              : `Later card · cumulative count unchanged at ${event.organizationCount}`,
          },
          {
            label: "Source",
            value: String(event.document_type || "model card").replaceAll("_", " "),
          },
        ],
        url: event.url,
      });
      svg.append(group);
    }
    svg.append(
      svgElement(
        "text",
        {
          x: 17,
          y: rugTop + rugHeight / 2,
          transform: `rotate(-90 17 ${rugTop + rugHeight / 2})`,
          "text-anchor": "middle",
          class: "frontier-axis-label",
        },
        "cards",
      ),
    );
  }

  if (record) {
    // Band bounds, not 0-100: every value in this corpus sits in the upper part
    // of its scale, so the axis is zoomed and says so on both ticks.
    for (const value of [band.high, band.low]) {
      const yPosition = scoreY(value);
      svg.append(
        svgElement("line", {
          x1: margin.left,
          y1: yPosition,
          x2: width - margin.right,
          y2: yPosition,
          class: "frontier-grid",
        }),
      );
      svg.append(
        svgElement(
          "text",
          {
            x: margin.left - 12,
            y: yPosition + 4,
            "text-anchor": "end",
            class: "frontier-tick",
          },
          Number(value.toFixed(1)),
        ),
      );
    }

    // One polyline per comparable series, and only for series the join rule
    // permits a line through. A series confined to one date draws no line: its
    // points are a comparison table from one document, and connecting them
    // would turn a single publication into an apparent trend.
    for (const series of record.series) {
      if (!series.connectable) continue;
      const points = series.points
        .map((point) => `${x(point.reported_at)},${scoreY(point.value)}`)
        .join(" ");
      svg.append(
        svgElement("polyline", {
          points,
          class: `score-line${series.single_organization ? " score-line-single-org" : ""}`,
        }),
      );
    }

    // The best-on-record marker. Drawn as a horizontal rule rather than a point
    // because it is a fact about the whole corpus to date, not about one date.
    const bestY = scoreY(record.saturation.best_value);
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: bestY,
        x2: width - margin.right,
        y2: bestY,
        class: "score-best-line",
      }),
    );
    svg.append(
      svgElement(
        "text",
        { x: width - margin.right, y: bestY - 6, "text-anchor": "end", class: "score-best-label" },
        `${t("best on record")} ${record.saturation.best_value}`,
      ),
    );

    for (const observation of record.observations) {
      const source = (board.model_cards || []).find(
        (card) => card.model_card_id === observation.source_id,
      );
      const sourceLabel = source
        ? `${source.organization} · ${source.model} (${String(
            source.document_type || t("model card"),
          ).replaceAll("_", " ")})`
        : observation.source_id.replaceAll("_", " ");
      const group = svgElement("g", {
        class: `score-point${observation.reported_by ? " score-point-third-party" : ""}`,
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "data-frontier-point": "",
        "aria-label":
          `${observation.value} ${record.metric} ${t("by")} ${observation.model} ` +
          `(${observation.organization}), ${formatDate(observation.reported_at, {
            dateStyle: "medium",
          })}, ${t("protocol")} ${observation.protocol}` +
          (observation.reported_by ? `, ${t("cited by")} ${observation.reported_by}` : "") +
          `. ${t("Click to pin record details")}.`,
      });
      const pointX = x(observation.reported_at);
      const pointY = scoreY(observation.value);
      group.append(
        svgElement("circle", {
          cx: pointX,
          cy: pointY,
          r: 9,
          class: "score-point-face",
        }),
      );
      if (observation.reported_by) {
        group.append(
          svgElement("circle", {
            cx: pointX,
            cy: pointY,
            r: 12,
            class: "score-point-citation-ring",
          }),
        );
      }
      group.append(
        modelGlyph(
          observation.model,
          observation.organization,
          pointX,
          pointY,
          14,
          "score-point-glyph",
        ),
      );
      makeFrontierPointInteractive(group, {
        kind: t("Readable score"),
        title: `${observation.organization} · ${observation.model}`,
        rows: [
          { label: t("Organization"), value: observation.organization },
          { label: t("Model"), value: observation.model },
          {
            label: t("Date"),
            value: formatDate(observation.reported_at, { dateStyle: "medium" }),
          },
          {
            label: t("Score"),
            value: `${observation.value}${record.unit === "percent" ? "%" : ` ${record.unit}`} ${record.metric}`,
          },
          { label: t("Instrument"), value: observation.instrument },
          { label: t("Protocol"), value: observation.protocol },
          { label: t("Source"), value: sourceLabel },
          { label: t("Read from"), value: observation.read_from.replaceAll("_", " ") },
          ...(observation.reported_by
            ? [{ label: t("Cited by"), value: observation.reported_by }]
            : []),
        ],
        url: source?.url,
      });
      svg.append(group);
    }

    // The reading gap. Scores in this corpus stop well before mentions do, and
    // an unmarked flat tail is exactly what invites "saturated" as the
    // explanation when "nothing newer could be read" is the actual one.
    //
    // Drawn on the plot floor, carrying no y-value. An earlier version put this
    // line at the best-on-record height, which asserted that value at a date
    // where nothing was recorded -- and on shipped data the best often predates
    // the last observation (AIME, SWE-bench Verified, MMLU-Redux, IFEval), so it
    // manufactured a flat tail out of missing data. That is the exact failure
    // this marker exists to prevent, so the span is now purely horizontal: it
    // says "no reading here", not "the reading stayed at N".
    // Bounded by the newest dated mention of *this* benchmark, not by the newest
    // card in the registry. An unrelated vendor's recent document is not evidence
    // that this benchmark went unread: shipped Arena-Hard and Aider Polyglot have
    // no adopter newer than their last score, so ending at the global date drew a
    // long gap that nothing about those benchmarks supported.
    const lastMention = events
      .map((event) => event.published)
      .filter(Boolean)
      .sort()
      .at(-1);
    const lastScoreX = x(record.last_reported_at);
    const endX = x(
      lastMention && lastMention > record.last_reported_at ? lastMention : record.last_reported_at,
    );
    if (endX - lastScoreX > 24) {
      const floorY = scoreTop + scoreHeight;
      svg.append(
        svgElement("line", {
          x1: lastScoreX,
          y1: floorY,
          x2: endX,
          y2: floorY,
          class: "score-gap-line",
        }),
      );
      // Ticks at both ends so the span reads as a bounded interval on the time
      // axis rather than as a series that happens to sit at the floor.
      for (const edge of [lastScoreX, endX]) {
        svg.append(
          svgElement("line", {
            x1: edge,
            y1: floorY - 5,
            x2: edge,
            y2: floorY + 5,
            class: "score-gap-line",
          }),
        );
      }
      svg.append(
        svgElement(
          "text",
          {
            x: (lastScoreX + endX) / 2,
            y: scoreTop + scoreHeight + 18,
            "text-anchor": "middle",
            class: "score-gap-label",
          },
          t("no readable score in this window"),
        ),
      );
    }

    svg.append(
      svgElement(
        "text",
        {
          x: 17,
          y: scoreTop + scoreHeight / 2,
          transform: `rotate(-90 17 ${scoreTop + scoreHeight / 2})`,
          "text-anchor": "middle",
          class: "frontier-axis-label",
        },
        // The zoom marker is never dropped. An earlier version omitted it on
        // narrow viewports and justified that by saying the readout states the
        // band bounds -- it does not; the bounds appear only as the two axis
        // ticks. Removing it left small screens with no indication that the axis
        // is magnified, which is the one thing about this band a reader must not
        // misjudge. Abbreviated instead, so it still fits the rotated label.
        narrow ? `${record.metric} ${t("(zoom)")}` : `${record.metric} ${t("(zoomed)")}`,
      ),
    );
  }

  const releaseX = entry.released ? x(entry.released) : x(startText);
  svg.append(
    svgElement("line", {
      x1: releaseX,
      y1: margin.top,
      // Spans both plots when a score band exists, so the release date reads as
      // one moment in the benchmark's life rather than as two unrelated marks.
      x2: releaseX,
      y2: record ? scoreTop + scoreHeight : rugTop + rugHeight,
      class: "frontier-release-line",
    }),
  );
  svg.append(
    svgElement(
      "text",
      { x: releaseX + 8, y: margin.top + 14, class: "frontier-release-label" },
      entry.released
        ? t("release")
        : events.length
          ? t("first dated mention")
          : t("first readable score"),
    ),
  );
  for (const [date, anchor] of [
    [startText, "start"],
    [endText, "end"],
  ]) {
    svg.append(
      svgElement(
        "text",
        { x: x(date), y: height - 28, "text-anchor": anchor, class: "frontier-tick" },
        formatDate(date, { month: "short", year: "numeric" }),
      ),
    );
  }
  if (!sparse) {
    svg.append(
      svgElement(
        "text",
        {
          x: 15,
          y: margin.top + plotHeight / 2,
          transform: `rotate(-90 15 ${margin.top + plotHeight / 2})`,
          "text-anchor": "middle",
          class: "frontier-axis-label",
        },
        // Named for what the axis counts. "Organizations reporting" invited the
        // reading that a repeat card adds to it; "cumulative distinct" says in the
        // label itself that a second card from a counted vendor moves nothing.
        // Shortened on a narrow viewport, where the rotated full text is longer
        // than the plot is tall and would be clipped at the viewBox edge.
        narrow ? t("distinct orgs") : t("cumulative distinct organizations"),
      ),
    );
  }
  svg.append(
    svgElement(
      "text",
      { x: margin.left + plotWidth / 2, y: height - 7, "text-anchor": "middle", class: "frontier-axis-label" },
      t("publication time"),
    ),
  );
  enableFrontierTouchTargets(svg);
  return svg;
}

// The score track alone, for a benchmark whose every mention is undated. Delegates
// to the same renderer with no adoption events rather than duplicating the score
// geometry: two implementations of one axis would be free to disagree about the
// join rule, which is the one thing this chart must not do.
function scoreOnlyChart(entry, board) {
  return adoptionFrontierChart(
    entry,
    // `organization_count` is only read for the adoption axis, which is suppressed
    // here. Keep the real card roster so score tooltips can resolve their source
    // labels and links even when no dated adoption event can be drawn.
    board,
    [],
    { sparse: true },
  );
}

function clearAdoptionFrontier(message) {
  clearFrontierPointSelection();
  byId("frontier-stage").textContent = "";
  replaceChildren(byId("frontier-summary"), []);
  replaceChildren(byId("frontier-milestones"), []);
  replaceChildren(byId("frontier-task-preview"), []);
  replaceChildren(byId("frontier-score-readout"), []);
  replaceChildren(byId("frontier-legend"), []);
  // The org color key is rendered only by the populated path; leaving a stale
  // key from a previously selected benchmark behind an empty chart would
  // present colors no marker carries.
  replaceChildren(byId("frontier-org-key"), []);
  replaceChildren(byId("frontier-chart"), [
    element("p", { className: "empty-state", text: message }),
  ]);
}

function renderAdoptionFrontier(board) {
  const adopted = (board.entries || []).filter((entry) => entry.card_count > 0);
  const defaultEntry = frontierDefaultEntry(board);
  if (!adopted.length || !defaultEntry) {
    clearAdoptionFrontier(t("No dated model-card mentions yet."));
    return;
  }
  if (!adopted.some((entry) => entry.benchmark_id === state.lfrontier)) {
    state.lfrontier = defaultEntry.benchmark_id;
    state.lfrontierExplicit = false;
  }
  replaceChildren(byId("frontier-benchmark"), [
    ...[...adopted]
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((entry) =>
        option(entry.benchmark_id, entry.name, entry.benchmark_id === state.lfrontier),
      ),
  ]);
  renderBenchmarkNavigator(board);

  const entry = adopted.find((candidate) => candidate.benchmark_id === state.lfrontier);
  byId("frontier-heading").textContent = `${entry.name} ${t("adoption trajectory")}`;
  const events = frontierEvents(entry);
  if (!events.length) {
    // No dated mention means no adoption timeline can be drawn. The score
    // reading is independent of that, though: the registry permits a card
    // without a `published` date, and clearing the panel outright would hide
    // every readable score because the *other* layer had no usable date. So the
    // score track still draws, on its own, with the points and comparable series
    // intact rather than reduced to the aggregate readout.
    clearAdoptionFrontier(t("This benchmark has no dated mentions."));
    const record = scoreRecord(entry.benchmark_id);
    renderFrontierLegend(entry, record, { sparse: true });
    if (record) {
      replaceChildren(byId("frontier-chart"), [scoreOnlyChart(entry, board), frontierTooltip()]);
    }
    renderScoreReadout(entry);
    return;
  }

  const frontier = events.filter((event) => event.advances);
  const lastAdvance = frontier.at(-1);
  const stage = reportingStage(entry, board);
  const stageElement = byId("frontier-stage");
  stageElement.className = `frontier-stage frontier-stage-${stage.id}`;
  stageElement.textContent = `${t("Reporting stage")} · ${stage.label}`;
  replaceChildren(byId("frontier-summary"), [
    element("strong", { text: entry.name }),
    // "23 cards · 10 of 10 dated organizations" read as one ratio about a single
    // quantity. They are two different counts, so they are now named separately.
    //
    // The organization count is qualified as "dated" when some card carries no
    // publication date: `card_count` includes those cards but `frontier` cannot,
    // so an unqualified "distinct organizations" beside the card total would imply
    // the two were counted over the same set of documents.
    element("span", {
      text:
        `${metricLabel(entry.card_count, "model card")} · ` +
        `${metricLabel(frontier.length, "distinct organization")}` +
        ((entry.adopters || []).some((adopter) => !adopter.published) ? ` ${t("with a dated card")}` : ""),
    }),
    element("span", {
      text: `${t("last new organization")} ${formatDate(lastAdvance.published, { dateStyle: "medium" })}`,
    }),
    element("span", { className: "frontier-stage-description", text: stage.description }),
  ]);
  // A single-advance adoption step line says nothing visually, which is why the
  // sparse stepper replaces it. The score track is a separate reading though, so
  // when one exists it is still drawn: dropping it would hide real data because a
  // *different* layer was thin.
  const sparse = frontier.length < 2;
  const scored = Boolean(scoreRecord(entry.benchmark_id));
  renderFrontierLegend(entry, scoreRecord(entry.benchmark_id), { sparse });
  renderFrontierOrgKey(entry, events);
  clearFrontierPointSelection();
  replaceChildren(byId("frontier-chart"), [
    sparse ? sparseFrontier(entry, events) : null,
    sparse && !scored ? null : adoptionFrontierChart(entry, board, events, { sparse }),
    sparse && !scored ? null : frontierTooltip(),
  ]);
  // Rendered for every benchmark, including those whose adoption is too sparse
  // to plot: the score reading is a separate question from the adoption reading,
  // and a benchmark with one adopter can still have a readable score.
  renderScoreReadout(entry);
  renderFrontierMilestones(entry, events);
  renderFrontierTaskPreview(entry);
}

// --- Stated findings (issue #91) --------------------------------------------
//
// The issue's third point: the project kept adding charts while the real gap --
// surfacing insight -- stayed open. Every sentence here is derived in Python by
// `insights.build_insights`, where it is tested, rather than phrased in the
// browser. This function only lays them out.
//
// A finding carries its own evidence line, and clicking one moves the chart to
// the benchmark it is about, so a claim is never more than one interaction away
// from the data behind it.

const FINDING_LABELS = {
  adopted_without_scores: "Adopted, unscored",
  stale_scores: "Reading coverage",
  closing_headroom: "Closing headroom",
  fast_gain: "Fast gain",
  third_party_only: "Third-party only",
};

function findingCard(finding, board) {
  const children = [
    element("div", { className: "finding-head" }, [
      element("span", {
        className: `finding-kind finding-kind-${finding.kind}`,
        text: FINDING_LABELS[finding.kind] || finding.kind,
      }),
      element("h3", { text: finding.headline }),
    ]),
    element("p", { className: "finding-detail", text: finding.detail }),
    element("p", { className: "finding-evidence" }, [
      element("span", { text: "Evidence" }),
      document.createTextNode(finding.evidence),
    ]),
  ];

  // Corpus-scope findings carry no benchmark_id, so there is nothing to focus.
  const target = finding.benchmark_id
    ? (board.entries || []).find((entry) => entry.benchmark_id === finding.benchmark_id)
    : null;
  if (target) {
    const jump = element("button", {
      className: "secondary-link finding-jump",
      text: `Show ${target.name} on the chart ↑`,
      attrs: { type: "button" },
    });
    jump.addEventListener("click", () => {
      selectFrontier(target.benchmark_id);
      renderAdoptionFrontier(board);
      writeUrl();
      byId("adoption-frontier").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    children.push(jump);
  }

  return element("article", { className: "finding-card" }, children);
}

function renderBenchmarkFindings(board) {
  const panel = byId("benchmark-findings");
  if (!panel) return;
  const insights = state.data?.benchmark_insights;
  // Hidden entirely rather than shown empty. An empty findings panel reads as
  // "we looked and the field is uneventful", which is a claim this corpus is not
  // in a position to make.
  if (!insights || !insights.findings?.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  byId("findings-count").textContent = metricLabel(insights.finding_count, "finding");
  byId("findings-measures").textContent = insights.measures || "";
  byId("findings-limits").textContent = `Does not measure: ${insights.does_not_measure}`;
  replaceChildren(
    byId("findings-list"),
    insights.findings.map((finding) => findingCard(finding, board)),
  );
}

function modelCardLabelCounts(board) {
  const labelCounts = new Map();
  for (const card of board.model_cards || []) {
    const key = `${card.organization} · ${card.model}`;
    labelCounts.set(key, (labelCounts.get(key) || 0) + 1);
  }
  return labelCounts;
}

function cardLabel(card, labelCounts) {
  const base = `${card.organization} · ${card.model}`;
  return labelCounts.get(base) > 1
    ? `${base} (${String(card.document_type).replaceAll("_", " ")})`
    : base;
}

function leaderboardRow(entry) {
  const board = state.data.model_card_leaderboard;
  const maxCount = board.entries?.[0]?.card_count || 0;
  const labelCounts = modelCardLabelCounts(board);
  const header = element("summary", { className: "record-summary" }, [
    element("span", {
      className: "signal-rank",
      text: String(entry.rank).padStart(2, "0"),
    }),
    element("div", { className: "record-heading" }, [
      element("div", { className: "signal-meta" }, [
        element("span", { text: entry.domain.replaceAll("_", " ") }),
        // A benchmark in the registry that no curated card reports is a real
        // observation, not an empty row: it says the benchmark is discussed
        // without yet being adopted in vendor reporting. Say that, rather than
        // showing a bare "0 organizations of 8".
        entry.card_count
          ? element("span", {
              text: `${metricLabel(entry.organization_count, "organization")} of ${
                board.organization_count
              }`,
            })
          : element("span", { text: "not yet reported in these cards" }),
        // The instrument's own age, which the adoption count deliberately does
        // not encode: a 2020 benchmark with 9 cards and a 2026 benchmark with 9
        // cards are very different findings about vendor reporting.
        entry.released
          ? element("span", {
              text: `released ${formatDate(entry.released, { dateStyle: "medium" })}`,
            })
          : null,
      ]),
      element("h3", { text: entry.name }),
      // The caveat is part of the row, not a footnote. A ranking that puts a
      // saturated benchmark near the top without saying so is misleading in
      // exactly the direction issue #83 warns about.
      entry.caveat ? element("p", { className: "signal-tldr", text: entry.caveat }) : null,
    ]),
    element("div", { className: "score" }, [
      element("div", { className: "score-value" }, [
        element("strong", { text: String(entry.card_count) }),
        element("span", { text: `/ ${board.model_card_count}` }),
      ]),
      adoptionBar(entry, maxCount),
      element("p", { className: "score-label", text: t("Model cards") }),
    ]),
  ]);

  const adopters = element(
    "ul",
    { className: "adopter-list" },
    (entry.adopters || []).map((adopter) =>
      element("li", {}, [
        // A plain text link, not the .primary-link call-to-action button: a
        // twelve-row roster of dark blocks reads as twelve competing actions
        // rather than as one list of sources.
        element("a", {
          className: "adopter-link",
          text: cardLabel(adopter, labelCounts),
          attrs: {
            href: safeHttpUrl(adopter.url),
            target: "_blank",
            rel: "noopener noreferrer",
          },
        }),
        element("span", {
          className: "adopter-meta",
          text: `${String(adopter.document_type).replaceAll("_", " ")}${
            adopter.published ? ` · ${formatDate(adopter.published, { dateStyle: "medium" })}` : ""
          }`,
        }),
      ]),
    ),
  );

  const isNew = isNewBenchmark(entry, board);
  if (isNew) {
    header.querySelector(".signal-meta").prepend(
      element("span", { className: "benchmark-new-badge", text: t("new instrument") }),
    );
  }

  const frontierButton = element("button", {
    className: "secondary-link frontier-jump",
    text: t("View adoption frontier ↑"),
    attrs: { type: "button" },
  });
  frontierButton.addEventListener("click", () => {
    selectFrontier(entry.benchmark_id);
    renderAdoptionFrontier(board);
    writeUrl();
    byId("adoption-frontier").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  return element("details", { className: `record-card${isNew ? " benchmark-new" : ""}` }, [
    header,
    element("div", { className: "record-detail" }, [
      element("h3", { text: t("Reported by") }),
      adopters,
      frontierButton,
      safeHttpUrl(entry.url)
        ? element("a", {
            className: "primary-link",
            text: t("Benchmark home ↗"),
            attrs: { href: safeHttpUrl(entry.url), target: "_blank", rel: "noopener noreferrer" },
          })
        : null,
    ]),
  ]);
}

function renderLeaderboardFilters(board) {
  // Every domain present in the ranking, not board.domains: that summary counts
  // only adopted benchmarks, so a domain whose benchmarks are all unadopted
  // would be listed in the table with no way to filter to it.
  const domains = [...new Set((board.entries || []).map((entry) => entry.domain))].sort();
  replaceChildren(byId("leaderboard-domain"), [
    option("", t("All domains"), !state.ldomain),
    ...domains.map((domain) =>
      option(domain, domain.replaceAll("_", " "), domain === state.ldomain),
    ),
  ]);
  const organizations = Object.keys(board.organizations || {}).sort();
  replaceChildren(byId("leaderboard-organization"), [
    option("", t("All organizations"), !state.lorg),
    ...organizations.map((organization) =>
      option(organization, organization, organization === state.lorg),
    ),
  ]);
  replaceChildren(byId("leaderboard-era"), [
    option("", t("Any release date"), !state.lera),
    ...LEADERBOARD_ERAS.map((era) => option(era.value, era.label, era.value === state.lera)),
  ]);
  if (byId("leaderboard-search").value !== state.lq) {
    byId("leaderboard-search").value = state.lq;
  }
}

function renderLeaderboard() {
  const board = state.data?.model_card_leaderboard;
  const navButton = document.querySelector('[data-view="leaderboard"]');
  // A checkout without the curated registry publishes no ranking. Hiding the
  // nav entry is the honest response: offering a tab that opens an empty page
  // reads as a broken feature rather than as absent data.
  if (!board) {
    if (navButton) navButton.hidden = true;
    return;
  }
  if (navButton) navButton.hidden = false;

  byId("leaderboard-measures").textContent = board.measures || "";
  renderLeaderboardFilters(board);
  renderBenchmarkFindings(board);
  renderAdoptionFrontier(board);

  const topEntries = (board.entries || []).filter((entry) => entry.card_count > 0);

  const newEntries = (board.entries || []).filter((entry) => isNewBenchmark(entry, board));
  const newSharedSignals = newEntries.filter((entry) => frontierAdvances(entry).length >= 3);
  // Each registry-overview count is a claim about specific records, so every
  // tile opens to the itemized evidence behind its number (issue #183). They
  // are native <details>/<summary>: collapsed on load, visible by the marker,
  // expandable and re-collapsible with the same control.
  const labelCounts = modelCardLabelCounts(board);
  const allCards = [...(board.model_cards || [])].sort(
    (a, b) =>
      Number(!a.published) - Number(!b.published) ||
      (b.published || "").localeCompare(a.published || "") ||
      String(a.organization).localeCompare(String(b.organization)) ||
      String(a.model).localeCompare(String(b.model)),
  );
  const evidenceDisclosure = (stat, items, emptyText) =>
    element("details", { className: "evidence-stat evidence-disclosure" }, [
      element("summary", { className: "evidence-stat-summary" }, [
        element("strong", { text: Number(stat.value || 0).toLocaleString() }),
        element("span", { text: stat.label }),
        element("small", { text: stat.detail }),
      ]),
      items.length
        ? element("ul", { className: "evidence-detail-list" }, items)
        : element("p", { className: "evidence-detail-empty", text: emptyText }),
    ]);
  const modelCardLine = (card) =>
    element("li", {}, [
      safeHttpUrl(card.url)
        ? element("a", {
            className: "adopter-link",
            text: cardLabel(card, labelCounts),
            attrs: { href: safeHttpUrl(card.url), target: "_blank", rel: "noopener noreferrer" },
          })
        : element("span", { className: "insight-item-name", text: cardLabel(card, labelCounts) }),
      element("span", {
        className: "insight-item-meta",
        text: `${String(card.document_type).replaceAll("_", " ")}${
          card.published ? ` · ${formatDate(card.published, { dateStyle: "medium" })}` : ""
        }`,
      }),
    ]);
  const benchmarkLine = (entry, meta) =>
    element("li", {}, [
      safeHttpUrl(entry.url)
        ? element("a", {
            className: "adopter-link",
            text: entry.name,
            attrs: { href: safeHttpUrl(entry.url), target: "_blank", rel: "noopener noreferrer" },
          })
        : element("span", { className: "insight-item-name", text: entry.name }),
      meta
        ? element("span", { className: "insight-item-meta", text: meta })
        : entry.released
          ? element("span", {
              className: "insight-item-meta",
              text: `${t("released")} ${formatDate(entry.released, { dateStyle: "medium" })}`,
            })
          : null,
    ]);
  // `board.domains` counts only adopted benchmarks, so it would understate the
  // spread of everything tracked. Count the distinct domains across all
  // entries, matching how the filter options are built, so the tracked tile's
  // breadth claim never collides with the adopted-only figure.
  const domainCount = new Set((board.entries || []).map((entry) => entry.domain)).size;
  replaceChildren(byId("leaderboard-insights"), [
    evidenceDisclosure(
      { value: board.model_card_count, label: t("source documents"), detail: t("Each document counts once per benchmark.") },
      allCards.map(modelCardLine),
      t("No source documents in the registry yet."),
    ),
    evidenceDisclosure(
      { value: board.organization_count, label: t("organizations"), detail: t("The denominator for reporting breadth.") },
      Object.entries(board.organizations || {})
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([organization, count]) =>
          element("li", {}, [
            element("details", { className: "insight-nested" }, [
              element("summary", { className: "insight-nested-summary" }, [
                element("span", { className: "insight-item-name", text: organization }),
                element("span", {
                  className: "insight-item-meta",
                  text: metricLabel(Number(count || 0), "card"),
                }),
              ]),
              element(
                "ul",
                { className: "evidence-detail-list" },
                allCards
                  .filter((card) => card.organization === organization)
                  .map(modelCardLine),
              ),
            ]),
          ]),
        ),
      "No organizations in the registry yet.",
    ),
    evidenceDisclosure(
      {
        value: board.benchmark_count,
        label: t("Benchmarks tracked"),
        detail: t("across {domains}{listed}.", {
          domains: metricLabel(domainCount, "domain"),
          listed: board.entries.length ? ` · ${metricLabel(board.entries.length, "benchmark")} ${t("listed")}` : "",
        }),
      },
      (board.entries || []).map((entry) =>
        benchmarkLine(
          entry,
          entry.card_count ? metricLabel(entry.card_count, "model card") : t("not yet reported"),
        ),
      ),
      "No benchmarks tracked yet.",
    ),
    evidenceDisclosure(
      { value: topEntries.length, label: t("Benchmarks reported at least once"), detail: t("The subset a ranked row can speak to.") },
      topEntries.map((entry) => benchmarkLine(entry, metricLabel(entry.card_count, "model card"))),
      t("No benchmark is reported by a curated card yet."),
    ),
    element("details", { className: "evidence-thesis evidence-thesis-disclosure" }, [
      element("summary", { className: "evidence-thesis-summary" }, [
        element("strong", { text: t("New instruments") }),
        element("span", {
          text: t(" · {count} released in the newest 18-month window already appear across three or more dated organizations. Follow their trajectories before reading the raw rank.", {
            count: metricLabel(newSharedSignals.length, "benchmark"),
          }),
        }),
      ]),
      element(
        "ul",
        { className: "evidence-detail-list" },
        [...newSharedSignals]
          .sort(
            (a, b) =>
              (b.released || "").localeCompare(a.released || "") ||
              a.name.localeCompare(b.name),
          )
          .map((entry) => benchmarkLine(entry, metricLabel(entry.card_count, "model card"))),
      ),
    ]),
  ]);

  const entries = leaderboardEntries();
  const filtersActive = Boolean(state.lq || state.ldomain || state.lorg || state.lera);
  const visibleEntries =
    filtersActive || state.leaderboardShowAll ? entries : entries.slice(0, 18);
  byId("leaderboard-count").textContent = filtersActive
    ? `${metricLabel(entries.length, "benchmark")} ${t("of")} ${board.entries.length}`
    : `${visibleEntries.length} ${t("shown")} · ${board.entries.length} ${t("tracked")}`;
  replaceChildren(
    byId("leaderboard-list"),
    visibleEntries.length
      ? visibleEntries.map(leaderboardRow)
      : [
          element("p", {
            className: "empty-state",
            text: t("No benchmarks match these filters. Clear one or more filters to widen the view."),
          }),
        ],
  );
  const showAllButton = byId("leaderboard-show-all");
  showAllButton.hidden = filtersActive || entries.length <= 18;
  showAllButton.textContent = state.leaderboardShowAll
    ? t("Show the first 18 benchmarks")
    : t("Show all {count} benchmarks", { count: entries.length });

  const cards = board.model_cards || [];
  byId("leaderboard-cards-count").textContent = metricLabel(cards.length, "document");
  replaceChildren(byId("leaderboard-cards"), cards.map(modelCardRow));
}

// The reverse direction of the registry's dual link, rendered as a disclosure so
// a reader can audit one card against its source document. The forward direction
// (a benchmark, expanded to its adopters) answers "who reports this?"; this
// answers "what did this card report?", which is the question you need when
// checking our data against the ground-truth PDF or blog post. Both are built
// from the same edge set in `adoption_rank`, so what is listed here is exactly
// what that card contributes to every count in the table above.
function modelCardRow(card) {
  const benchmarks = card.reported_benchmarks || [];
  // `record-summary-unranked` selects the three-column grid: these rows carry no
  // rank number, unlike the ranked benchmark rows above.
  const summary = element("summary", { className: "record-summary record-summary-unranked" }, [
    element("div", { className: "record-heading" }, [
      element("div", { className: "signal-meta" }, [
        element("span", { text: card.organization }),
        element("span", { text: String(card.document_type).replaceAll("_", " ") }),
        element("span", {
          text: card.published
            ? formatDate(card.published, { dateStyle: "medium" })
            : t("date unknown"),
        }),
      ]),
      element("h3", { text: card.model }),
    ]),
    element("div", { className: "score" }, [
      element("div", { className: "score-value" }, [
        element("strong", { text: String(card.benchmark_count) }),
      ]),
      element("p", { className: "score-label", text: t("Benchmarks") }),
    ]),
  ]);

  // Grouped by domain because that is how the source documents are laid out:
  // a card's own tables are sectioned into reasoning, coding, agentic and
  // multimodal blocks, so grouping the same way keeps a side-by-side check
  // against the PDF a matter of reading down one column.
  const byDomain = new Map();
  for (const benchmark of benchmarks) {
    if (!byDomain.has(benchmark.domain)) byDomain.set(benchmark.domain, []);
    byDomain.get(benchmark.domain).push(benchmark);
  }

  const groups = [...byDomain.entries()].map(([domain, items]) =>
    element("div", { className: "card-benchmark-group" }, [
      element("h4", { text: domain.replaceAll("_", " ") }),
      element(
        "ul",
        { className: "adopter-list" },
        items.map((benchmark) =>
          element("li", {}, [
            safeHttpUrl(benchmark.url)
              ? element("a", {
                  className: "adopter-link",
                  text: benchmark.name,
                  attrs: {
                    href: safeHttpUrl(benchmark.url),
                    target: "_blank",
                    rel: "noopener noreferrer",
                  },
                })
              : element("span", { className: "adopter-link", text: benchmark.name }),
            element("span", {
              className: "adopter-meta",
              text: benchmark.released
                ? `${t("released")} ${formatDate(benchmark.released, { dateStyle: "medium" })}`
                : t("release date unrecorded"),
            }),
          ]),
        ),
      ),
    ]),
  );

  return element("details", { className: "record-card" }, [
    summary,
    element("div", { className: "record-detail" }, [
      element("h3", { text: t("Benchmarks this document reports") }),
      element("p", {
        className: "section-note",
        text: t("Every benchmark this document puts in front of readers, counted once each. These are mentions, not scores: the source records the configuration, and this registry deliberately does not."),
      }),
      ...groups,
      element("a", {
        className: "primary-link",
        text: t("Open source document ↗"),
        attrs: { href: safeHttpUrl(card.url), target: "_blank", rel: "noopener noreferrer" },
      }),
      card.retrieved_at
        ? element("p", {
            className: "adopter-meta",
            text: `${t("Last read by a human on")} ${formatDate(card.retrieved_at, {
              dateStyle: "medium",
            })}`,
          })
        : null,
    ]),
  ]);
}

function renderTrendMap() {
  if (!state.data) return;
  const corpus = state.data.corpus;
  if (!corpus) return;
  const entityById = new Map(corpus.entities.map((entity) => [entity.id, entity]));
  const selectedFromUrl = entityById.get(state.entity);
  const artifacts = corpus.entities
    .filter((entity) => entity.type === "artifact")
    .sort(
      (a, b) =>
        Number(b.latest_score || 0) - Number(a.latest_score || 0) ||
        Number(b.observation_count || 0) - Number(a.observation_count || 0) ||
        a.label.localeCompare(b.label),
    );
  const artifactOrder = new Map(
    artifacts.map((entity, index) => [entity.id, index]),
  );
  const artifactIds = new Set(artifacts.map((entity) => entity.id));
  const visibleEdges = corpus.edges.filter(
    (edge) =>
      artifactIds.has(edge.source) &&
      ["HAS_TOPIC", "RELEASED_BY", "FOUND_VIA"].includes(edge.type),
  );
  const visibleIds = new Set([
    ...artifactIds,
    ...visibleEdges.flatMap((edge) => [edge.source, edge.target]),
  ]);
  if (
    selectedFromUrl &&
    ["topic", "organization", "source"].includes(selectedFromUrl.type)
  ) {
    visibleIds.add(selectedFromUrl.id);
  }
  const visibleEntities = [...visibleIds]
    .map((id) => entityById.get(id))
    .filter(Boolean);
  const typeOrder = ["source", "organization", "artifact", "topic"];
  const xByType = { source: 110, organization: 350, artifact: 650, topic: 1010 };
  const groups = Object.fromEntries(
    typeOrder.map((type) => [
      type,
      visibleEntities
        .filter((entity) => entity.type === type)
        .sort((a, b) =>
          type === "artifact"
            ? artifactOrder.get(a.id) - artifactOrder.get(b.id)
            : a.label.localeCompare(b.label),
        ),
    ]),
  );
  const rowSpacing = 36;
  const height = Math.max(
    560,
    groups.artifact.length * rowSpacing + 120,
  );
  const positions = new Map();
  typeOrder.forEach((type) => {
    groups[type].forEach((entity, index) => {
      const y =
        type === "artifact"
          ? 70 + index * rowSpacing
          : groups[type].length === 1
            ? height / 2
            : 70 + (index * (height - 140)) / (groups[type].length - 1);
      positions.set(entity.id, { x: xByType[type], y });
    });
  });

  const svg = svgElement("svg", {
    viewBox: `0 0 1200 ${height}`,
    width: "1200",
    height,
    // role="group" rather than role="img": the map contains interactive
    // marker nodes, and ARIA makes descendants of role="img" presentational,
    // hiding every node from assistive tech. Same choice the adoption
    // frontier documents for its marker buttons.
    role: "group",
    "aria-label": t("Artifact nodes connected to topics, organizations, and discovery sources"),
  });
  typeOrder.forEach((type) => {
    svg.append(
      svgElement(
        "text",
        {
          x: xByType[type],
          y: 30,
          "text-anchor": "middle",
          class: "map-column-label",
        },
        `${type}s`,
      ),
    );
  });
  visibleEdges.forEach((edge) => {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) return;
    svg.append(
      svgElement("line", {
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        class: "map-edge",
      }),
    );
  });
  visibleEntities.forEach((entity) => {
    const position = positions.get(entity.id);
    if (!position) return;
    const group = svgElement("g", {
      class: `map-node map-node-${entity.type}`,
      transform: `translate(${position.x} ${position.y})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${entity.type}: ${entity.label}`,
    });
    group.append(svgElement("circle", { r: entity.type === "artifact" ? 8 : 6 }));
    group.append(
      svgElement(
        "text",
        { x: 14, y: 4 },
        shorten(entity.label, entity.type === "artifact" ? 38 : 24),
      ),
    );
    const related = visibleEdges
      .filter((edge) => edge.source === entity.id || edge.target === entity.id)
      .map((edge) => entityById.get(edge.source === entity.id ? edge.target : edge.source))
      .filter(Boolean);
    const select = () => selectMapNode(entity, related);
    group.addEventListener("click", select);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select();
      }
    });
    svg.append(group);
  });
  renderMapInsights(corpus);
  replaceChildren(byId("map-canvas"), [svg]);
  const authorCount = Number(corpus.aggregates?.entity_types?.person || 0);
  byId("map-summary").textContent =
    `${t("Showing all")} ${artifacts.length.toLocaleString()} ${t("artifacts")} · ` +
    `${groups.organization.length.toLocaleString()} ${t("organizations")} · ` +
    `${groups.source.length.toLocaleString()} ${t("sources")} · ${groups.topic.length.toLocaleString()} ${t("topics")}` +
    (authorCount
      ? ` · ${authorCount.toLocaleString()} ${t("author nodes summarized above and omitted from the canvas")}`
      : "");
  if (selectedFromUrl) {
    const related = corpus.edges
      .filter(
        (edge) => edge.source === selectedFromUrl.id || edge.target === selectedFromUrl.id,
      )
      .map((edge) =>
        entityById.get(
          edge.source === selectedFromUrl.id ? edge.target : edge.source,
        ),
      )
      .filter(Boolean);
    selectMapNode(selectedFromUrl, related);
  }
}

function attentionActivity(item) {
  return element("div", { className: "attention-activity" }, [
    element("strong", { text: metricLabel(item.metrics?.points, "point") }),
    element("span", { text: metricLabel(item.metrics?.comments, "comment") }),
    element("span", { text: metricLabel(item.metrics?.submissions ?? 1, "submission") }),
  ]);
}

function observationCard(item, index) {
  const isAttention = item.observation_kind === "attention";
  const metadata = isAttention
    ? element("div", { className: "signal-meta" }, [
        element("span", { className: "attention-badge", text: t("attention") }),
        element("span", { text: `${item.source} · ${item.event_kind}` }),
      ])
    : pillBar(item);
  const summary = (item.summary || "").trim()
    ? shorten(item.summary)
    : t("No description published at the source.");
  const header = element("summary", { className: "record-summary" }, [
    element("span", {
      className: "signal-rank",
      text: String(index + 1).padStart(2, "0"),
    }),
    element("div", { className: "record-heading" }, [
      metadata,
      element("h3", { text: item.title }),
      ...(item.watchlist && item.watchlist_note
        ? [element("p", { className: "signal-tldr", text: item.watchlist_note })]
        : []),
      element("p", {
        className: item.summary ? "" : "signal-nodesc",
        text: isAttention
          ? `${summary} · ${metricLabel(item.metrics?.points, "point")}`
          : summary,
      }),
    ]),
    isAttention ? attentionActivity(item) : scoreBlock(item),
  ]);
  return element(
    "details",
    {
      className: `record-card${isAttention ? " attention-card" : ""}`,
    },
    [header, expandedRecord(item, (item.summary || "").trim() ? summary : "")],
  );
}

const CONTACT_EMAIL = "ktwu01@gmail.com";
const WECHAT_ID = "ktwu001";
const DISCORD_ID = "ktwu01";

const BRAND_ICON_PATHS = {
  email: "M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm9 6.9L4.2 6h15.6L12 11.9Zm-8 6.6V8.9l8 5.9 8-5.9v9.6H4Z",
  wechat:
    "M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05a6.127 6.127 0 0 1-.253-1.72c0-3.571 3.437-6.467 7.678-6.467.233 0 .463.013.694.031C17.02 4.792 13.205 2.188 8.69 2.188Zm-2.6 4.408c.654 0 1.184.517 1.184 1.154 0 .637-.53 1.154-1.184 1.154-.654 0-1.184-.517-1.184-1.154 0-.637.53-1.154 1.184-1.154Zm5.51 0c.654 0 1.184.517 1.184 1.154 0 .637-.53 1.154-1.184 1.154-.654 0-1.184-.517-1.184-1.154 0-.637.53-1.154 1.184-1.154Zm7.835 3.124c-3.858 0-6.984 2.667-6.984 5.957 0 3.29 3.126 5.957 6.984 5.957.848 0 1.663-.146 2.418-.408a.622.622 0 0 1 .516.07l1.371.802a.235.235 0 0 0 .12.039.213.213 0 0 0 .208-.213c0-.052-.02-.102-.035-.153l-.28-1.067a.426.426 0 0 1 .153-.479c1.359-1.111 2.2-2.707 2.2-4.548 0-3.29-3.126-5.957-6.984-5.957Zm-3.865 3.594c.55 0 .996.435.996.971 0 .537-.446.972-.996.972-.55 0-.996-.435-.996-.972 0-.536.446-.971.996-.971Zm7.729 0c.55 0 .996.435.996.971 0 .537-.446.972-.996.972-.55 0-.996-.435-.996-.972 0-.536.446-.971.996-.971Z",
  discord:
    "M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 0 0 .0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 0 0-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 0 1-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 0 1 .0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 0 1 .0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 0 1-.0066.1276 12.2986 12.2986 0 0 1-1.873.8914.0766.0766 0 0 0-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 0 0 .0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 0 0 .0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286ZM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0957 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189Zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0957 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z",
};

function brandIcon(name) {
  const svg = svgElement("svg", {
    viewBox: "0 0 24 24",
    class: "brand-icon",
    "aria-hidden": "true",
  });
  svg.appendChild(svgElement("path", { d: BRAND_ICON_PATHS[name] }));
  return svg;
}

function observationsToCsv(observations) {
  const columns = [
    "date",
    "kind",
    "title",
    "summary",
    "source",
    "event_kind",
    "categories",
    "organizations",
    "url",
    "score",
  ];
  const escape = (value) => {
    const text = String(value ?? "");
    // Quotes and separators force quoting; a leading =, +, -, or @ is also
    // quoted so a scraped cell cannot execute as a spreadsheet formula.
    const mustQuote = /[",\n\r]/.test(text) || /^[=+\-@]/.test(text);
    return mustQuote ? `"${text.replaceAll('"', '""')}"` : text;
  };
  const rows = observations.map((item) =>
    [
      item.snapshot_date,
      item.observation_kind,
      escape(item.title),
      escape(item.summary || ""),
      escape(item.source),
      escape(item.event_kind),
      escape((item.categories || []).join("; ")),
      escape((item.organizations || []).join("; ")),
      escape(item.url || item.primary_artifact_url || ""),
      Number(item.total_score || 0).toFixed(2),
    ].join(","),
  );
  return [columns.join(","), ...rows].join("\r\n");
}

function downloadText(filename, text, mimeType = "text/plain") {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// The export dialog (issue #193) does two things at once: it states the
// usecase that makes this more than a dump, and it puts one-click downloads
// behind a single control. The usecase is the reason the site exists for a
// reader doing related-work research: find every benchmark on a topic, or take
// the whole corpus with you. The JSON link and the client-side CSV are both
// derived from the same in-memory data the dashboard renders, so an export can
// never disagree with the screen it came from.
function openExport() {
  const dialog = byId("export-dialog");
  if (!state.data) return;
  const filtered = filteredObservations();
  replaceChildren(byId("export-content"), [
    element("p", { className: "detail-source", text: t("Benchmark Radar · data export") }),
    element("h2", {
      className: "detail-title export-title",
      text: t("Take the data with you"),
      attrs: { id: "export-title" },
    }),
    element("p", {
      className: "detail-summary",
      text: t("Doing related-work research, or hunting for a benchmark on a topic? This database aggregates every benchmark, evaluation, and dataset the radar has surfaced, and you can query it by topic, source, or organization before you export. The full corpus below is the same data the dashboard renders."),
    }),
    element("div", { className: "export-actions" }, [
      element("a", {
        className: "primary-link",
        text: t("Download full dataset (JSON)"),
        attrs: { href: "data/radar.json", download: "benchmark-radar.json" },
      }),
      element("button", {
        className: "secondary-link export-csv-button",
        text: t("Download current view (CSV · {rows} rows)", { rows: filtered.length }),
        attrs: { type: "button" },
      }),
      element("a", {
        className: "secondary-link",
        text: t("Leaderboard (CSV)"),
        attrs: { href: "data/leaderboard.csv", download: "leaderboard.csv" },
      }),
    ]),
    element("p", {
      className: "discovery-note",
      text: t("{observations} observations across {snapshots} daily snapshots.", {
        observations: allObservations().length,
        snapshots: state.data.snapshot_count,
      }),
    }),
  ]);
  byId("export-content")
    .querySelector(".export-csv-button")
    .addEventListener("click", () => {
      downloadText(
        `benchmark-radar-${state.todayDate === "all" ? "all" : state.todayDate}.csv`,
        observationsToCsv(filtered),
        "text/csv;charset=utf-8",
      );
    });
  dialog.showModal();
}

// The contact dialog (issue #191) keeps every reach-out channel in one place:
// email, WeChat, and Discord. The header badge (issue #213) merged the two
// separate WeChat and Discord buttons into a single Contact control that
// opens this dialog, so a reader lands on a choice rather than being launched
// out of the page on a guess.
function openContact() {
  const dialog = byId("contact-dialog");
  replaceChildren(byId("contact-content"), [
    element("p", { className: "detail-source", text: "Benchmark Radar" }),
    element("h2", {
      className: "detail-title contact-title",
      text: t("Get in touch"),
      attrs: { id: "contact-title" },
    }),
    element("p", {
      className: "detail-summary",
      text: t("A wrong row in the adoption ranking is a real bug. So is a connector that stopped collecting, or a benchmark you expected the radar to see."),
    }),
    element("ul", { className: "contact-list" }, [
      element("li", {}, [
        element("span", { className: "contact-label" }, [
          brandIcon("email"),
          element("strong", { text: t("Email") }),
        ]),
        element("a", {
          className: "contact-value",
          text: CONTACT_EMAIL,
          attrs: { href: `mailto:${CONTACT_EMAIL}` },
        }),
      ]),
      element("li", {}, [
        element("span", { className: "contact-label" }, [
          brandIcon("wechat"),
          element("strong", { text: t("WeChat") }),
        ]),
        element("span", { className: "contact-value", text: `ID ${WECHAT_ID}` }),
      ]),
      element("li", {}, [
        element("span", { className: "contact-label" }, [
          brandIcon("discord"),
          element("strong", { text: t("Discord") }),
        ]),
        element("span", { className: "contact-value", text: `ID ${DISCORD_ID}` }),
      ]),
    ]),
  ]);
  dialog.showModal();
}

// Filter keystrokes only rebuild the bounded result list. Briefing, questions,
// health, and corpus totals do not change while a reader types.
const scheduleTodayRender = debounce(() => renderToday({ resultsOnly: true }));

// Same for the leaderboard, which re-sorts the registry and rewrites the URL
// on every keystroke otherwise.
const scheduleLeaderboardRender = debounce(() => {
  renderLeaderboard();
  writeUrl();
});

function bindEvents() {
  const langToggle = byId("lang-toggle");
  if (langToggle) langToggle.addEventListener("click", toggleLang);
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
      if (button.dataset.view === "today") renderToday();
      if (button.dataset.view === "leaderboard") renderLeaderboard();
      if (button.dataset.view === "trends") renderTrends();
      if (button.dataset.view === "map") renderTrendMap();
    });
  });
  // Reads every control rather than the event target, so the <select>
  // "input"-before-"change" ordering that broke the Scan date picker (issue
  // #43) cannot write a stale value back over the reader's pick here: whichever
  // event arrives first, all three values come from the DOM as it stands now.
  byId("leaderboard-filters").addEventListener("input", () => {
    state.lq = byId("leaderboard-search").value;
    state.ldomain = byId("leaderboard-domain").value;
    state.lorg = byId("leaderboard-organization").value;
    state.lera = byId("leaderboard-era").value;
    scheduleLeaderboardRender();
  });
  byId("leaderboard-clear").addEventListener("click", () => {
    state.lq = "";
    state.ldomain = "";
    state.lorg = "";
    state.lera = "";
    state.leaderboardShowAll = false;
    byId("leaderboard-search").value = "";
    renderLeaderboard();
    writeUrl();
  });
  byId("leaderboard-show-all").addEventListener("click", () => {
    state.leaderboardShowAll = !state.leaderboardShowAll;
    renderLeaderboard();
    byId("leaderboard-table-heading").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  byId("frontier-benchmark").addEventListener("change", (event) => {
    selectFrontier(event.target.value);
    renderAdoptionFrontier(state.data.model_card_leaderboard);
    writeUrl();
  });
  byId("today-date").addEventListener("change", (event) => {
    state.todayDate = event.target.value;
    renderToday();
  });
  byId("today-show-more").addEventListener("click", () => {
    state.todayResultsLimit += ALL_DATES_PAGE_SIZE;
    renderToday({ resultsOnly: true });
  });
  byId("trend-released-only").addEventListener("change", (event) => {
    state.trendReleasedOnly = event.target.checked;
    renderTrends();
  });
  // An open hover card is positioned against the chart, so any scroll or resize
  // that moves its column has to move it too.
  byId("trend-chart").addEventListener("scroll", repositionDayTooltip, {
    passive: true,
  });
  window.addEventListener("resize", repositionDayTooltip);
  window.addEventListener("resize", repositionFrontierTooltip);
  window.addEventListener("scroll", repositionFrontierTooltip, { passive: true });
  // The frontier chart picks its viewBox width from the viewport, so crossing the
  // 760px breakpoint has to redraw it. Without this a page loaded wide and then
  // narrowed (or a rotated phone) keeps the 920-unit box until some unrelated
  // rerender, and the CSS min-height only letterboxes the collapsed chart rather
  // than fixing it. Re-rendered only on an actual crossing, not on every resize
  // event, since redrawing every SVG mid-drag would be wasteful.
  let wasNarrow = window.innerWidth <= 760;
  window.addEventListener("resize", () => {
    const isNarrow = window.innerWidth <= 760;
    if (isNarrow === wasNarrow) return;
    wasNarrow = isNarrow;
    const board = state.data?.model_card_leaderboard;
    if (board) renderAdoptionFrontier(board);
  });
  document.addEventListener("keydown", (event) => {
    // A <dialog>'s native Escape-close is the keydown's default action (its
    // `cancel` event), so preventDefault() below would swallow the first
    // Escape while a dialog is open. Yield to the dialog when one is up.
    if (
      event.key === "Escape" &&
      selectedFrontierPoint &&
      !document.querySelector("dialog[open]")
    ) {
      clearFrontierPointSelection();
      event.preventDefault();
      return;
    }
    // Do not swallow Escape unless a card is actually open to close.
    if (event.key === "Escape" && dismissDayTooltip()) event.preventDefault();
  });
  byId("filters").addEventListener("input", (event) => {
    // The Scan date select has its own dedicated change handler above. A
    // <select> fires "input" before "change", and this bubbled "input"
    // reaching here would call renderToday() with the still-stale
    // state.todayDate, which then writes the OLD date back onto the
    // control and clobbers the user's just-made selection.
    if (event.target === byId("today-date")) return;
    state.q = byId("search-filter").value;
    state.kind = byId("kind-filter").value;
    state.category = byId("category-filter").value;
    state.source = byId("source-filter").value;
    state.organization = byId("organization-filter").value;
    state.event = byId("event-filter").value;
    scheduleTodayRender();
  });
  // Both filter panels are <form>s whose state lives in the URL query we
  // build ourselves. Enter in a search field would otherwise trigger an
  // implicit GET that submits only the named controls, dropping `view` and
  // reloading the reader into Today from whichever panel they were using.
  document.querySelectorAll("#filters, #leaderboard-filters").forEach((form) => {
    form.addEventListener("submit", (event) => event.preventDefault());
  });
  byId("clear-filters").addEventListener("click", () => {
    state.todayDate = "all";
    state.q = "";
    state.kind = "";
    state.category = "";
    state.source = "";
    state.organization = "";
    state.event = "";
    renderToday();
  });
  byId("rubric-close").addEventListener("click", () => byId("rubric-dialog").close());
  byId("rubric-dialog").addEventListener("click", (event) => {
    if (event.target === byId("rubric-dialog")) byId("rubric-dialog").close();
  });
  // Fires for every close path (button, backdrop click, Esc), so #rubric is
  // cleared from the URL no matter how the reader dismisses the dialog.
  byId("rubric-dialog").addEventListener("close", () => {
    state.rubric = "";
    writeUrl();
  });
  // Reachable without a record in hand, for a reader who wants the method
  // before they trust any single row.
  byId("rubric-nav").addEventListener("click", () => openRubric());
  byId("badge-export").addEventListener("click", openExport);
  byId("badge-contact").addEventListener("click", openContact);
  byId("export-close").addEventListener("click", () => byId("export-dialog").close());
  byId("export-dialog").addEventListener("click", (event) => {
    if (event.target === byId("export-dialog")) byId("export-dialog").close();
  });
  byId("contact-close").addEventListener("click", () => byId("contact-dialog").close());
  byId("contact-dialog").addEventListener("click", (event) => {
    if (event.target === byId("contact-dialog")) byId("contact-dialog").close();
  });
}

const REPO_SLUG = "ktwu01/benchmark-radar";

// The visible badge reads "★ Star 12", which a screen reader would announce as
// a bare statistic. The accessible name states the action and keeps the count
// as context, so the control sounds like the invitation it is.
const BADGE_ACTIONS = {
  "badge-stars": (count) => t("Star this repository on GitHub. {count} stars", { count }),
  "badge-forks": (count) => t("Fork this repository on GitHub. {count} forks", { count }),
  "badge-issues": (count) => t("Open a new issue on GitHub. {count} issues open", { count }),
};

function setBadgeCount(id, value) {
  const badge = byId(id);
  const node = badge?.querySelector("[data-count]");
  if (!node) return;
  const count = Number(value || 0).toLocaleString();
  node.textContent = count;
  badge.setAttribute("aria-label", BADGE_ACTIONS[id](count));
}

async function renderRepoBadges() {
  // Counts are decoration: the badges link out and stay usable if this fails,
  // so a rate-limited API must never surface as an error state.
  try {
    const response = await fetch(`https://api.github.com/repos/${REPO_SLUG}`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) return;
    const repo = await response.json();
    setBadgeCount("badge-stars", repo.stargazers_count);
    setBadgeCount("badge-forks", repo.forks_count);
    // open_issues_count includes pull requests, so building the count from it
    // overstates how many issues are actually open. Ask search for issues only,
    // and leave the badge blank if that fails rather than showing the inflated
    // number.
    const issues = await fetch(
      `https://api.github.com/search/issues?q=${encodeURIComponent(
        `repo:${REPO_SLUG} is:issue is:open`,
      )}&per_page=1`,
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (issues.ok) {
      setBadgeCount("badge-issues", (await issues.json()).total_count);
    }
  } catch (error) {
    console.debug("Repository badge counts unavailable", error);
  }
}

// Two scheduled runs a day (issue #44), roughly 6h apart; a gap past 30h
// means both the scheduled run and its same-day retry were missed.
const STALE_AFTER_HOURS = 30;

function renderStaleBanner() {
  const banner = byId("stale-banner");
  const latestDay = state.data.days[state.data.days.length - 1];
  const generatedAt = new Date(state.data.generated_at);
  const ageHours = (Date.now() - generatedAt.getTime()) / 3_600_000;
  const degraded = !latestDay.required_coverage_complete;
  if (ageHours <= STALE_AFTER_HOURS && !degraded) {
    banner.hidden = true;
    banner.textContent = "";
    banner.classList.remove("stale-banner-degraded");
    return;
  }
  const parts = [];
  if (ageHours > STALE_AFTER_HOURS) {
    parts.push(
      t("Latest snapshot is from {date} UTC ({hours}h ago) — the scheduled run may have failed.", {
        date: formatDate(state.data.generated_at, {
          dateStyle: "medium",
          timeStyle: "short",
        }),
        hours: Math.floor(ageHours),
      }),
    );
  }
  if (degraded) {
    parts.push(
      t("Required source failures on {date}: {gaps}.", {
        date: latestDay.date,
        gaps: latestDay.required_coverage_gaps.join(", "),
      }),
    );
  }
  banner.textContent = parts.join(" ");
  banner.classList.toggle("stale-banner-degraded", degraded);
  banner.hidden = false;
}

async function initialize() {
  setLang(initialLang());
  applyStaticI18n();
  syncLangToggle();
  readUrl();
  bindEvents();
  // Independent of the data file, so badges still render on an error state.
  renderRepoBadges();
  try {
    // radar.json is ~34MB and regenerated once a day. Let the browser cache
    // it (GitHub Pages serves conditional headers, so a repeat visit reuses
    // the cached copy and revalidates rather than re-downloading the whole
    // corpus). cache: "no-store" forced a full re-download every load, which
    // was the dominant part of the page's slow first interaction (issue #222).
    const response = await fetch("data/radar.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (
      state.data.schema_version !== 2 ||
      !Array.isArray(state.data.days) ||
      !state.data.days.length
    ) {
      throw new Error("No compatible snapshots");
    }
    if (state.todayDate !== "all" && !state.data.facets.dates.includes(state.todayDate)) {
      state.todayDate = state.data.latest_date;
    }
    renderTodayDateOptions();
    // A permalink to ?view=leaderboard on a build without the curated registry
    // has nothing to show, so fall back to Today rather than opening a blank
    // section behind a navigation entry that has no data.
    if (state.view === "leaderboard" && !state.data.model_card_leaderboard) {
      state.view = "today";
    }
    setView(state.view, false);

    // Rendering all four views up front made the reader wait for charts and
    // thousands of hidden nodes. Build only the requested view; the navigation
    // handlers render another view when the reader opens it.
    if (state.view === "today") renderToday();
    if (state.view === "leaderboard") renderLeaderboard();
    if (state.view === "trends") renderTrends();
    if (state.view === "map") renderTrendMap();

    renderBuildMeta();
    renderStaleBanner();
    if (state.rubric && state.data.rubrics?.[state.rubric]) {
      openRubric(null, state.rubric);
    }
  } catch (error) {
    document.querySelectorAll(".view").forEach((section) => {
      section.hidden = true;
    });
    byId("error-state").hidden = false;
    console.error(error);
  }
}

initialize();
