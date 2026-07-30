const CATEGORY_COLORS = {
  benchmark: "#255ea8",
  evaluation: "#dc633f",
  dataset: "#4c948b",
  data_quality: "#c99327",
  agentic: "#756aa8",
};
const FALLBACK_COLORS = ["#756aa8", "#397f9a", "#a4576d", "#70833d"];

const byId = (id) => document.getElementById(id);
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
  if (!value) return "Unknown";
  const withTime = value.length === 10 ? `${value}T00:00:00Z` : value;
  return new Intl.DateTimeFormat("en", { timeZone: "UTC", ...options }).format(
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
  state.view = ["trends", "map"].includes(requestedView) ? requestedView : "today";
  state.todayDate = params.get("date") || "";
  state.q = params.get("q") || "";
  state.kind = params.get("kind") || "";
  state.category = params.get("category") || "";
  state.source = params.get("source") || "";
  state.organization = params.get("organization") || "";
  state.event = params.get("event") || "";
  state.entity = params.get("entity") || "";
  state.rubric = new URLSearchParams(window.location.hash.slice(1)).get("rubric") || "";
}

function writeUrl() {
  const params = new URLSearchParams();
  if (state.view !== "today") params.set("view", state.view);
  if (state.todayDate && state.todayDate !== state.data?.latest_date) {
    params.set("date", state.todayDate);
  }
  if (state.q) params.set("q", state.q);
  if (state.kind) params.set("kind", state.kind);
  if (state.category) params.set("category", state.category);
  if (state.source) params.set("source", state.source);
  if (state.organization) params.set("organization", state.organization);
  if (state.event) params.set("event", state.event);
  if (state.view === "map" && state.entity) params.set("entity", state.entity);
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
      "aria-label": `Priority score ${score.toFixed(2)} of ${max.toFixed(2)}. How is this scored?`,
    },
  }, [
    element("span", { text: "Priority score" }),
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
    pills.push(element("span", { className: "pill", text: "uncategorized" }));
  }
  return element("div", { className: "pill-bar" }, pills);
}

function definition(label, value) {
  return element("div", {}, [
    element("dt", { text: label }),
    element("dd", { text: value }),
  ]);
}

function renderToday() {
  const day = dailySnapshot();
  if (!day) return;
  state.todayDate = day.date;
  byId("today-date").value = day.date;

  syncFilters();
  const observations = filteredObservations();
  const evidenceCount = observations.filter(
    (item) => item.observation_kind === "evidence",
  ).length;
  const attentionCount = observations.length - evidenceCount;
  byId("today-count").textContent =
    `${observations.length} result${observations.length === 1 ? "" : "s"} · ` +
    `${evidenceCount} evidence · ${attentionCount} attention`;
  replaceChildren(
    byId("today-list"),
    observations.length
      ? observations.map(observationCard)
      : [
          element("p", {
            className: "empty-state",
            text: "No observations match these filters. Clear one or more filters to widen the view.",
          }),
        ],
  );

  const healthEntries = [
    ...day.ingest_health.map((entry) => ({ ...entry, layer: "Radar ingest" })),
    ...day.producer_health.map((entry) => ({ ...entry, layer: "Producer report" })),
  ];
  // Fetch plumbing is not what the reader came for, so the roster collapses to
  // one line. It opens itself only when a connector failed, which is the one
  // case where the panel explains a gap in the list beside it.
  const failedCount = healthEntries.filter((entry) => !entry.ok).length;
  byId("health-status").textContent = failedCount
    ? `${failedCount} of ${healthEntries.length} failed`
    : `${healthEntries.length} ok`;
  byId("health-status").classList.toggle("has-failure", failedCount > 0);
  byId("health-panel-details").open = failedCount > 0;
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
          text: `${entry.source} · ${entry.layer}`,
        }),
        element("span", {
          className: "health-count",
          // A source that returned exactly the per-source cap was truncated, so
          // the number is a ceiling. "300+ found" says that; "300 found" read as
          // a measured total.
          text: entry.ok
            ? entry.item_count
              ? `${entry.item_count}${entry.item_count === ingestCap ? "+" : ""} found`
              : "empty"
            : "failed",
          ...(entry.item_count === ingestCap
            ? { attrs: { title: `Truncated at the ${ingestCap}-record per-source limit` } }
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
  byId("corpus-totals-status").textContent = `${totalArtifacts.toLocaleString()} artifacts`;
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
  if (!value) return "no change";
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
    ["vs previous scan", comparable ? deltaText(delta) : "not comparable"],
    [
      "recent daily average",
      trend.baseline === null || trend.baseline === undefined
        ? "not enough history"
        : Number(trend.baseline).toFixed(2),
    ],
    ["cumulative", Number(trend.cumulative || 0).toLocaleString()],
  ];
  if (trend.momentum !== null && trend.momentum !== undefined) {
    const percent = Math.round(Number(trend.momentum) * 100);
    rows.splice(2, 0, ["vs its average", `${percent > 0 ? "+" : ""}${percent}%`]);
  }
  const updatedOnly = Math.max(0, (trend.total_count || 0) - (trend.count || 0));
  if (updatedOnly) {
    rows.push(["also updated (not counted above)", updatedOnly.toLocaleString()]);
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
        attrs: { title: "New releases only. Re-announced updates are tracked separately." },
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
            text: "No categorized records in this scan.",
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
          element("span", { text: `Evidence: ${category.replaceAll("_", " ")}` }),
        ]);
      }),
      (() => {
        const swatch = element("span", { className: "legend-swatch attention-swatch" });
        return element("span", { className: "legend-item" }, [
          swatch,
          element("span", { text: "Attention: active" }),
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
      `History begins ${formatDate(only.date)}. At least two daily snapshots are required to calculate a trend. ` +
      `Baseline: ${only.evidence_count} evidence records and ${only.attention.active_count} active attention signals.`;
    trendChart.hidden = true;
  } else if (dayCount === 2) {
    trendMessage.textContent = sameCollectionContext(
      state.data.days[1],
      state.data.days[0],
    )
      ? "Two snapshots are available. The chart shows the first comparable daily change; broader trend language begins with three snapshots." +
        coverageNote(state.data.days[1])
      : "Two snapshots are available, but their connector coverage or report limit differs, so the change between them is not comparable.";
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
      const direction = (value) => (value > 0 ? `up ${value}` : value < 0 ? `down ${Math.abs(value)}` : "flat");
      const movers = Object.entries(latest.category_trends || {})
        .filter(([, trend]) => trend.delta)
        .sort((a, b) => Math.abs(b[1].delta) - Math.abs(a[1].delta))
        .slice(0, 2)
        .map(([category, trend]) => `${category.replaceAll("_", " ")} ${deltaText(trend.delta)}`);
      trendMessage.textContent =
        `Compared with ${previous.date}, surfaced evidence is ${direction(evidenceDelta)} and active attention is ${direction(attentionDelta)}.` +
        (movers.length ? ` Biggest domain moves: ${movers.join(", ")}.` : "") +
        coverageNote(latest);
    } else {
      trendMessage.textContent =
        `${latest.date} used different connector coverage or a different report limit than ${previous.date}, so the two scans ` +
        "are not directly comparable. Counts are shown without a change figure.";
    }
    trendChart.hidden = false;
  }
  const countsFor = (day) =>
    state.trendReleasedOnly ? day.category_counts_released : day.category_counts;
  const maxTotal = Math.max(
    1,
    ...state.data.days.map((day) =>
      Math.max(
        Object.values(countsFor(day)).reduce((sum, count) => sum + count, 0),
        day.attention.active_count,
      ),
    ),
  );
  replaceChildren(
    byId("trend-chart"),
    state.data.days.map((day) => {
      const dayCounts = countsFor(day);
      const total = Object.values(dayCounts).reduce((sum, count) => sum + count, 0);
      const segments = categories.map((category, index) => {
        const segment = element("span", {
          className: "bar-segment",
          attrs: { title: `${category.replaceAll("_", " ")}: ${dayCounts[category] || 0}` },
        });
        segment.style.height = `${((dayCounts[category] || 0) / maxTotal) * 260}px`;
        segment.style.setProperty("--bar-color", categoryColor(category, index));
        return segment;
      });
      const attentionBar = element("span", {
        className: "attention-volume",
        attrs: { title: `Active attention: ${day.attention.active_count}` },
      });
      attentionBar.style.height = `${(day.attention.active_count / maxTotal) * 260}px`;
      const button = element("button", {
        className: "day-column",
        attrs: {
          type: "button",
          "aria-label": `${formatDate(day.date)}: ${total} evidence category matches across ${day.evidence_count} evidence records and ${day.attention.active_count} attention signals`,
        },
      }, [
        element("span", { className: "series-bars" }, [
          element("span", { className: "bar-stack" }, segments),
          attentionBar,
        ]),
        element("span", { className: "day-label", text: day.date.slice(5) }),
      ]);
      button.addEventListener("click", () => {
        state.todayDate = day.date;
        setView("today");
        renderToday();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      return button;
    }),
  );
  byId("snapshot-count").textContent = `${state.data.snapshot_count} snapshots`;
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
          text: `${day.attention.new_count} new · ${day.attention.active_count} active`,
        }),
        element("td", { text: healthSummary(day.ingest_health) }),
      ]);
    }),
  );
}

function metricLabel(value, singular, plural = `${singular}s`) {
  const count = Number(value || 0);
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

function countMapText(values) {
  const entries = Object.entries(values || {});
  return entries.length
    ? entries
        .map(([name, count]) => `${name.replaceAll("_", " ")} ${count}`)
        .join(" · ")
    : "none";
}

function healthSummary(entries) {
  // A source that returned nothing still succeeded. Only a failure is not ok,
  // and an empty run is reported alongside rather than counted as a fault.
  const total = entries.length;
  const ok = entries.filter((entry) => entry.ok).length;
  const empty = entries.filter((entry) => entry.ok && entry.item_count === 0).length;
  const base = ok === total ? "all ok" : `${ok}/${total} ok`;
  return empty ? `${base} · ${empty} empty` : base;
}

function allObservations() {
  const evidence = state.data.days.flatMap((day) =>
    day.evidence_items.map((item) => ({
      ...item,
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
  return [...evidence, ...attention].sort((a, b) => {
    const dateOrder = String(b.snapshot_date).localeCompare(String(a.snapshot_date));
    return dateOrder || Number(b.total_score || 0) - Number(a.total_score || 0);
  });
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
      item.snapshot_date === state.todayDate &&
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
      text: `Scoring rubric v${version}${isLegacy ? " · superseded" : " · current"}`,
    }),
    element("h2", {
      className: "detail-title rubric-title",
      text: "How priority is scored",
      attrs: { id: "rubric-title" },
    }),
    element("p", {
      className: "detail-summary",
      text:
        `Priority is the weighted mean of four components, each measured on a 0 to ${max.toFixed(2)} ` +
        "scale. Every number below is read from the same definition the pipeline applies.",
    }),
    ...(isLegacy
      ? [
          element("p", {
            className: "discovery-note",
            text:
              (item
                ? `This record was scored by rubric v${version} on a 0 to ${max.toFixed(2)} scale. `
                : `Rubric v${version} scored records on a 0 to ${max.toFixed(2)} scale. `) +
              `The current rubric is v${current} on a 0 to ` +
              `${(Number(state.data?.rubric?.score_max) || 100).toFixed(2)} scale. Scores from the ` +
              "two versions are not directly comparable, and past records are not rescored.",
          }),
        ]
      : []),
    element("p", { className: "rubric-formula", text: data.formula }),
  ];

  if (item) {
    header.push(
      element("div", { className: "rubric-worked" }, [
        element("strong", { text: `This record scores ${Number(item.total_score || 0).toFixed(2)}` }),
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
          text: `weight ${component.weight.toFixed(2)}`,
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
                `Scored ${Number(item[`${component.key}_score`] || 0).toFixed(2)}` +
                ` · contributes ${contribution(component).toFixed(2)} to the total`,
            }),
          ])
        : null,
    ]),
  );

  const limits =
    (data.limits || []).length
      ? element("section", { className: "rubric-limits" }, [
          element("h3", { text: "What this score does not claim" }),
          element(
            "ul",
            {},
            data.limits.map((limit) => element("li", { text: limit })),
          ),
        ])
      : null;

  const cutoff =
    data.minimum_score !== undefined && data.minimum_score !== null
      ? element("p", {
          className: "discovery-note",
          text:
            `A record is reported only if it matches at least one taxonomy category and ` +
            `scores ${Number(data.minimum_score).toFixed(2)} or above, or if it names a ` +
            "watchlisted artifact, which is published regardless of score.",
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
          item.source === "Hacker News" ? "HN points" : "Activity points",
          Number(item.metrics?.points || 0).toLocaleString(),
        ],
        ["Comments", Number(item.metrics?.comments || 0).toLocaleString()],
        ["Submissions", Number(item.metrics?.submissions ?? 1).toLocaleString()],
        ["Published", formatDate(item.published_at, { dateStyle: "medium" })],
      ]
    : [
        ["Priority", Number(item.total_score || 0).toFixed(2)],
        ["Relevance", Number(item.relevance_score || 0).toFixed(2)],
        ["Evidence", Number(item.evidence_score || 0).toFixed(2)],
        ["Recency", Number(item.recency_score || 0).toFixed(2)],
        // Adoption is weighted into the total, so hiding it here left the
        // four shown components unable to explain the priority above them.
        ["Adoption", Number(item.adoption_score || 0).toFixed(2)],
      ];
  const rationale = element(
    "ul",
    { className: "rationale-list" },
    (item.rationale || []).map((reason) => element("li", { text: reason })),
  );
  const attentionNotice = isAttention
    ? element("div", { className: "attention-notice" }, [
        element("strong", { text: "Not quality-scored" }),
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
                    href: record.url,
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
    ...(isAttention && primaryArtifact
      ? [
          element("a", {
            className: "primary-link",
            text: "Open primary artifact ↗",
            attrs: {
              href: primaryArtifact,
              target: "_blank",
              rel: "noopener noreferrer",
            },
          }),
        ]
      : []),
    element("a", {
      className: isAttention ? "secondary-link" : "primary-link",
      text: isAttention
        ? "Open public discussion ↗"
        : item.source === "Hugging Face"
          ? "Read full card ↗"
          : "Open primary source ↗",
      attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
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
          ? summaryRemainder(item.summary, teaser) || "No further description beyond the preview above."
          : item.summary
        : "No description published at the source.",
    }),
    attentionNotice,
    element(
      "dl",
      { className: "detail-grid" },
      scoreEntries.map(([label, value]) => definition(label, value)),
    ),
    element("h3", { text: "Why surfaced" }),
    rationale,
    supporting,
    isAttention
      ? element("p", {
          className: "discovery-note",
          text:
            `Producer discovered ${formatDate(item.discovered_at, { dateStyle: "medium", timeStyle: "short" })} UTC · ` +
            `Radar first observed ${formatDate(item.observed_at, { dateStyle: "medium", timeStyle: "short" })} UTC`,
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
    text: "View matching observations →",
    attrs: { type: "button" },
  });
  viewResults.addEventListener("click", () => {
    setView("today");
    renderToday();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  replaceChildren(byId("map-detail"), [
    element("p", { className: "eyebrow", text: "Selected node" }),
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
          text: `Connected to ${relatedEntities
            .slice(0, 8)
            .map((related) => related.label)
            .join(", ")}${relatedEntities.length > 8 ? "…" : ""}`,
        })
      : null,
    viewResults,
    entity.url
      ? element("a", {
          className: "primary-link",
          text: "Open primary source ↗",
          attrs: {
            href: entity.url,
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

function mapInsightCard(title, entries, emptyText) {
  return element("article", { className: "map-insight-card" }, [
    element("h2", { text: title }),
    entries.length
      ? element(
          "ul",
          {},
          entries.map(([label, value]) =>
            element("li", {}, [
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
    ["Artifacts", Number(entityTypes.artifact || 0).toLocaleString()],
    ["Organizations", Number(entityTypes.organization || 0).toLocaleString()],
    ["Authors", Number(entityTypes.person || 0).toLocaleString()],
    ["Discovery sources", Number(entityTypes.source || 0).toLocaleString()],
    ["Topics", Number(entityTypes.topic || 0).toLocaleString()],
  ];
  replaceChildren(byId("map-insights"), [
    mapInsightCard("Corpus coverage", coverageEntries, "No corpus entities yet."),
    mapInsightCard("Topic coverage", topicEntries, "No topics assigned yet."),
    mapInsightCard("Discovery sources", sourceEntries, "No discovery sources yet."),
    mapInsightCard(
      "Most represented organizations",
      organizationEntries,
      "No organizations identified yet.",
    ),
  ]);
}

function renderTrendMap() {
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
    role: "img",
    "aria-label": "Artifact nodes connected to topics, organizations, and discovery sources",
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
    `Showing all ${artifacts.length.toLocaleString()} artifacts · ` +
    `${groups.organization.length.toLocaleString()} organizations · ` +
    `${groups.source.length.toLocaleString()} sources · ${groups.topic.length.toLocaleString()} topics` +
    (authorCount
      ? ` · ${authorCount.toLocaleString()} author nodes summarized above and omitted from the canvas`
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
        element("span", { className: "attention-badge", text: "attention" }),
        element("span", { text: `${item.source} · ${item.event_kind}` }),
      ])
    : pillBar(item);
  const summary = (item.summary || "").trim()
    ? shorten(item.summary)
    : "No description published at the source.";
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

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
      if (button.dataset.view === "today") renderToday();
      if (button.dataset.view === "trends") renderTrends();
      if (button.dataset.view === "map") renderTrendMap();
    });
  });
  byId("today-date").addEventListener("change", (event) => {
    state.todayDate = event.target.value;
    renderToday();
  });
  byId("trend-released-only").addEventListener("change", (event) => {
    state.trendReleasedOnly = event.target.checked;
    renderTrends();
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
    renderToday();
  });
  byId("clear-filters").addEventListener("click", () => {
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
}

const REPO_SLUG = "ktwu01/benchmark-radar";

// The visible badge reads "★ Star 12", which a screen reader would announce as
// a bare statistic. The accessible name states the action and keeps the count
// as context, so the control sounds like the invitation it is.
const BADGE_ACTIONS = {
  "badge-stars": (count) => `Star this repository on GitHub. ${count} stars`,
  "badge-forks": (count) => `Fork this repository on GitHub. ${count} forks`,
  "badge-issues": (count) => `Open a new issue on GitHub. ${count} issues open`,
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
      `Latest snapshot is from ${formatDate(state.data.generated_at, {
        dateStyle: "medium",
        timeStyle: "short",
      })} UTC (${Math.floor(ageHours)}h ago) — the scheduled run may have failed.`,
    );
  }
  if (degraded) {
    parts.push(
      `Required source failures on ${latestDay.date}: ` +
        `${latestDay.required_coverage_gaps.join(", ")}.`,
    );
  }
  banner.textContent = parts.join(" ");
  banner.classList.toggle("stale-banner-degraded", degraded);
  banner.hidden = false;
}

async function initialize() {
  readUrl();
  bindEvents();
  // Independent of the data file, so badges still render on an error state.
  renderRepoBadges();
  try {
    const response = await fetch("data/radar.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (
      state.data.schema_version !== 2 ||
      !Array.isArray(state.data.days) ||
      !state.data.days.length
    ) {
      throw new Error("No compatible snapshots");
    }
    if (!state.data.facets.dates.includes(state.todayDate)) {
      state.todayDate = state.data.latest_date;
    }
    replaceChildren(
      byId("today-date"),
      [...state.data.facets.dates]
        .reverse()
        .map((date) =>
          option(date, formatDate(date, { dateStyle: "medium" }), date === state.todayDate),
        ),
    );
    renderToday();
    renderTrends();
    renderTrendMap();
    setView(state.view, false);
    byId("build-meta").textContent = `Updated ${formatDate(state.data.generated_at, {
      dateStyle: "medium",
      timeStyle: "short",
    })} UTC`;
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
