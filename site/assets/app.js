const CATEGORY_COLORS = {
  benchmark: "#255ea8",
  evaluation: "#dc633f",
  dataset: "#4c948b",
  data_quality: "#c99327",
};
const FALLBACK_COLORS = ["#756aa8", "#397f9a", "#a4576d", "#70833d"];

const byId = (id) => document.getElementById(id);
const state = {
  data: null,
  external: [],
  view: "today",
  date: "",
  q: "",
  category: "",
  source: "",
  event: "",
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
  return value.length > max ? `${value.slice(0, max).trim()}…` : value;
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
  state.view = ["today", "trends", "explorer"].includes(requestedView)
    ? requestedView
    : "today";
  state.date = params.get("date") || "";
  state.q = params.get("q") || "";
  state.category = params.get("category") || "";
  state.source = params.get("source") || "";
  state.event = params.get("event") || "";
}

function writeUrl() {
  const params = new URLSearchParams();
  if (state.view !== "today") params.set("view", state.view);
  if (state.date && state.date !== state.data?.latest_date) params.set("date", state.date);
  if (state.q) params.set("q", state.q);
  if (state.category) params.set("category", state.category);
  if (state.source) params.set("source", state.source);
  if (state.event) params.set("event", state.event);
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
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

function dailySnapshot(date = state.date) {
  return (
    state.data.days.find((day) => day.date === date) ||
    state.data.days[state.data.days.length - 1]
  );
}

function scoreBlock(item) {
  const score = Number(item.total_score || 0);
  const width = Math.max(0, Math.min(100, (score / 4) * 100));
  const trackFill = element("span", {
    attrs: { style: `--score:${width}%` },
  });
  const track = element("div", { className: "score-track" }, [trackFill]);
  track.style.setProperty("--score", `${width}%`);
  trackFill.style.width = `${width}%`;
  return element("div", { className: "score" }, [
    element("div", { className: "score-value" }, [
      element("strong", { text: score.toFixed(2) }),
      element("span", { text: "/ 4.00" }),
    ]),
    track,
    element("div", { className: "score-label", text: "Priority score" }),
  ]);
}

function signalCard(item, index) {
  const title = element("a", {
    text: item.title,
    attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
  });
  const categories = (item.categories || []).join(" · ") || "uncategorized";
  return element("article", { className: "signal-card" }, [
    element("div", { className: "signal-rank", text: String(index + 1).padStart(2, "0") }),
    element("div", {}, [
      element("div", {
        className: "signal-meta",
        text: `${item.source} · ${item.event_kind} · ${categories}`,
      }),
      element("h3", {}, [title]),
      element("p", { text: shorten(item.summary) }),
      element("div", {
        className: "signal-meta",
        text: (item.rationale || []).join(" · "),
      }),
    ]),
    scoreBlock(item),
  ]);
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
  state.date = day.date;
  byId("today-date").value = day.date;
  byId("scan-count").textContent = day.item_count;
  byId("scan-dial").style.setProperty(
    "--coverage",
    `${Math.min(92, Math.max(14, day.item_count * 2.4))}%`,
  );
  byId("briefing-date").textContent = formatDate(day.date);
  const failed = day.health.filter((entry) => !entry.ok);
  byId("briefing-copy").textContent = failed.length
    ? `${failed.length} source${failed.length === 1 ? "" : "s"} reported a coverage gap. Comparisons should be read with that limitation.`
    : "All configured sources reported successfully for this scan.";
  replaceChildren(byId("briefing-stats"), [
    definition("Window start", formatDate(day.since, { dateStyle: "medium" })),
    definition("Sources", new Set(day.items.map((item) => item.source)).size),
    definition("Categories", Object.keys(day.category_counts).length),
  ]);
  byId("today-count").textContent = `${day.item_count} records`;
  replaceChildren(
    byId("today-list"),
    day.items.map((item, index) => signalCard(item, index)),
  );

  const healthy = day.health.filter((entry) => entry.ok).length;
  byId("health-summary").textContent = `${healthy}/${day.health.length} healthy`;
  replaceChildren(
    byId("health-list"),
    day.health.map((entry) => {
      const children = [
        element("span", { className: `health-dot${entry.ok ? " ok" : ""}` }),
        element("span", { className: "health-name", text: entry.source }),
        element("span", { className: "health-count", text: `${entry.item_count} found` }),
      ];
      if (entry.error) {
        children.push(element("p", { className: "health-detail", text: entry.error }));
      }
      return element("li", {}, children);
    }),
  );
  writeUrl();
}

function renderTrends() {
  const categories = state.data.facets.categories;
  replaceChildren(
    byId("trend-legend"),
    categories.map((category, index) => {
      const swatch = element("span", { className: "legend-swatch" });
      swatch.style.setProperty("--swatch", categoryColor(category, index));
      return element("span", { className: "legend-item" }, [
        swatch,
        element("span", { text: category.replaceAll("_", " ") }),
      ]);
    }),
  );
  const maxTotal = Math.max(
    1,
    ...state.data.days.map((day) =>
      Object.values(day.category_counts).reduce((sum, count) => sum + count, 0),
    ),
  );
  replaceChildren(
    byId("trend-chart"),
    state.data.days.map((day) => {
      const total = Object.values(day.category_counts).reduce((sum, count) => sum + count, 0);
      const segments = categories.map((category, index) => {
        const segment = element("span", {
          className: "bar-segment",
          attrs: { title: `${category.replaceAll("_", " ")}: ${day.category_counts[category] || 0}` },
        });
        segment.style.height = `${((day.category_counts[category] || 0) / maxTotal) * 260}px`;
        segment.style.setProperty("--bar-color", categoryColor(category, index));
        return segment;
      });
      const button = element("button", {
        className: "day-column",
        attrs: {
          type: "button",
          "aria-label": `${formatDate(day.date)}: ${total} category matches across ${day.item_count} items`,
        },
      }, [
        element("span", { className: "bar-stack" }, segments),
        element("span", { className: "day-label", text: day.date.slice(5) }),
      ]);
      button.addEventListener("click", () => {
        state.date = day.date;
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
      const healthy = day.health.filter((entry) => entry.ok).length;
      const link = element("a", { text: day.date, attrs: { href: `?date=${day.date}` } });
      link.addEventListener("click", (event) => {
        event.preventDefault();
        state.date = day.date;
        setView("today");
        renderToday();
      });
      return element("tr", {}, [
        element("td", {}, [link]),
        element("td", { text: day.item_count }),
        element("td", {
          text: Object.entries(day.category_counts)
            .map(([name, count]) => `${name.replaceAll("_", " ")} ${count}`)
            .join(" · "),
        }),
        element("td", { text: `${healthy}/${day.health.length} sources` }),
      ]);
    }),
  );
}

function normalizeExternal(observation, feed) {
  const published = observation.published_at || observation.discovered_at || feed.generated_at;
  return {
    source: observation.source || feed.producer,
    source_id: observation.source_id || observation.id,
    title: observation.title,
    url: observation.url,
    published_at: published,
    summary: observation.summary || "",
    event_kind: observation.event_kind || "discussed",
    authors: observation.authors || [],
    artifact_urls: observation.primary_artifact_url ? [observation.primary_artifact_url] : [],
    metrics: observation.metrics || {},
    categories: observation.categories || [],
    evidence_score: 0,
    relevance_score: 0,
    recency_score: 0,
    adoption_score: 0,
    total_score: 0,
    rationale: observation.rationale || ["Public attention signal; not quality evidence"],
    snapshot_date: (observation.discovered_at || published).slice(0, 10),
    observation_kind: "attention",
  };
}

function safeHttpUrl(value) {
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol);
  } catch {
    return false;
  }
}

async function loadExternalFeeds() {
  try {
    const configResponse = await fetch("data/feeds.json", { cache: "no-store" });
    if (!configResponse.ok) throw new Error("feed configuration unavailable");
    const config = await configResponse.json();
    const settled = await Promise.allSettled(
      (config.feeds || []).map(async (entry) => {
        const response = await fetch(entry.url, { cache: "no-store" });
        if (!response.ok) throw new Error(`${entry.name}: HTTP ${response.status}`);
        const feed = await response.json();
        if (feed.schema_version !== 1 || !Array.isArray(feed.observations)) {
          throw new Error(`${entry.name}: incompatible public feed`);
        }
        return feed.observations
          .filter(
            (observation) =>
              observation &&
              typeof observation.title === "string" &&
              safeHttpUrl(observation.url),
          )
          .map((observation) => normalizeExternal(observation, feed));
      }),
    );
    state.external = settled
      .filter((result) => result.status === "fulfilled")
      .flatMap((result) => result.value);
    const failures = settled.filter((result) => result.status === "rejected").length;
    byId("feed-status").textContent = failures
      ? `${state.external.length} public signals · ${failures} feed unavailable`
      : `${state.external.length} public attention signals loaded`;
  } catch {
    state.external = [];
    byId("feed-status").textContent = "Public attention feeds unavailable";
  }
}

function allObservations() {
  const primary = state.data.days.flatMap((day) =>
    day.items.map((item) => ({
      ...item,
      snapshot_date: day.date,
      observation_kind: "primary",
    })),
  );
  return [...primary, ...state.external].sort((a, b) => {
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
    byId("date-filter"),
    [...new Set(observations.map((item) => item.snapshot_date))].sort().reverse(),
    "dates",
    state.date,
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
      (!state.date || item.snapshot_date === state.date) &&
      (!state.category || (item.categories || []).includes(state.category)) &&
      (!state.source || item.source === state.source) &&
      (!state.event || item.event_kind === state.event) &&
      (!query || haystack.includes(query))
    );
  });
}

function openDetails(item) {
  const scoreEntries = [
    ["Priority", Number(item.total_score || 0).toFixed(2)],
    ["Evidence", Number(item.evidence_score || 0).toFixed(2)],
    ["Relevance", Number(item.relevance_score || 0).toFixed(2)],
    ["Recency", Number(item.recency_score || 0).toFixed(2)],
  ];
  const rationale = element(
    "ul",
    { className: "rationale-list" },
    (item.rationale || []).map((reason) => element("li", { text: reason })),
  );
  replaceChildren(byId("detail-content"), [
    element("p", {
      className: "detail-source",
      text: `${item.source} · ${item.event_kind} · ${item.snapshot_date}`,
    }),
    element("h2", { className: "detail-title", text: item.title, attrs: { id: "detail-title" } }),
    element("p", { className: "detail-summary", text: item.summary || "No summary provided." }),
    element(
      "dl",
      { className: "detail-grid" },
      scoreEntries.map(([label, value]) => definition(label, value)),
    ),
    element("h3", { text: "Why surfaced" }),
    rationale,
    element("a", {
      className: "primary-link",
      text: item.observation_kind === "attention" ? "Open public observation ↗" : "Open primary source ↗",
      attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
    }),
  ]);
  byId("detail-dialog").showModal();
}

function explorerCard(item) {
  const badge =
    item.observation_kind === "attention"
      ? element("span", { className: "attention-badge", text: "attention" })
      : null;
  const details = element("button", {
    className: "detail-button",
    text: "View evidence",
    attrs: { type: "button" },
  });
  details.addEventListener("click", () => openDetails(item));
  return element("article", { className: "explorer-card" }, [
    element("div", {}, [
      element("div", { className: "signal-meta" }, [
        badge,
        element("span", {
          text: `${item.snapshot_date} · ${item.source} · ${item.event_kind}`,
        }),
      ]),
      element("h3", {}, [
        element("a", {
          text: item.title,
          attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
        }),
      ]),
      element("p", {
        text: `${(item.categories || []).join(" · ") || "uncategorized"} · ${shorten(item.summary, 140)}`,
      }),
    ]),
    details,
  ]);
}

function renderExplorer() {
  syncFilters();
  const observations = filteredObservations();
  byId("explorer-count").textContent = `${observations.length} result${observations.length === 1 ? "" : "s"}`;
  replaceChildren(
    byId("explorer-list"),
    observations.length
      ? observations.map(explorerCard)
      : [
          element("p", {
            className: "empty-state",
            text: "No observations match these filters. Clear one or more filters to widen the view.",
          }),
        ],
  );
  writeUrl();
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
      if (button.dataset.view === "explorer") renderExplorer();
    });
  });
  byId("today-date").addEventListener("change", (event) => {
    state.date = event.target.value;
    renderToday();
  });
  byId("filters").addEventListener("input", () => {
    state.q = byId("search-filter").value;
    state.date = byId("date-filter").value;
    state.category = byId("category-filter").value;
    state.source = byId("source-filter").value;
    state.event = byId("event-filter").value;
    renderExplorer();
  });
  byId("clear-filters").addEventListener("click", () => {
    state.q = "";
    state.date = "";
    state.category = "";
    state.source = "";
    state.event = "";
    renderExplorer();
  });
  byId("dialog-close").addEventListener("click", () => byId("detail-dialog").close());
  byId("detail-dialog").addEventListener("click", (event) => {
    if (event.target === byId("detail-dialog")) byId("detail-dialog").close();
  });
}

async function initialize() {
  readUrl();
  bindEvents();
  try {
    const response = await fetch("data/radar.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (
      state.data.schema_version !== 1 ||
      !Array.isArray(state.data.days) ||
      !state.data.days.length
    ) {
      throw new Error("No compatible snapshots");
    }
    if (!state.data.facets.dates.includes(state.date)) state.date = state.data.latest_date;
    replaceChildren(
      byId("today-date"),
      [...state.data.facets.dates]
        .reverse()
        .map((date) => option(date, formatDate(date, { dateStyle: "medium" }), date === state.date)),
    );
    await loadExternalFeeds();
    renderToday();
    renderTrends();
    renderExplorer();
    setView(state.view, false);
    const latest = dailySnapshot(state.data.latest_date);
    const healthy = latest.health.filter((entry) => entry.ok).length;
    byId("status-copy").textContent =
      `Latest ${latest.date} · ${healthy}/${latest.health.length} sources`;
    byId("run-status").querySelector(".status-light").classList.add(
      healthy === latest.health.length ? "ok" : "warning",
    );
    byId("build-meta").textContent =
      `Schema ${state.data.schema_version} · Build ${formatDate(state.data.generated_at, {
        dateStyle: "medium",
        timeStyle: "short",
      })} UTC`;
  } catch (error) {
    document.querySelectorAll(".view").forEach((section) => {
      section.hidden = true;
    });
    byId("error-state").hidden = false;
    byId("run-status").textContent = "Validated data unavailable";
    console.error(error);
  }
}

initialize();
