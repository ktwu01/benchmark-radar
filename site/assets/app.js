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
  todayDate: "",
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
  if (state.view === "today") {
    state.todayDate = params.get("date") || "";
  } else {
    state.date = params.get("date") || "";
  }
  state.q = params.get("q") || "";
  state.category = params.get("category") || "";
  state.source = params.get("source") || "";
  state.event = params.get("event") || "";
}

function writeUrl() {
  const params = new URLSearchParams();
  if (state.view !== "today") params.set("view", state.view);
  const activeDate = state.view === "today" ? state.todayDate : state.date;
  if (activeDate && (state.view !== "today" || activeDate !== state.data?.latest_date)) {
    params.set("date", activeDate);
  }
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

function dailySnapshot(date = state.todayDate) {
  return (
    state.data.days.find((day) => day.date === date) ||
    state.data.days[state.data.days.length - 1]
  );
}

function scoreBlock(item) {
  const score = Number(item.total_score || 0);
  const width = Math.max(0, Math.min(100, (score / 4) * 100));
  const trackFill = element("span", {});
  const track = element("div", { className: "score-track" }, [trackFill]);
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

function pillBar(item) {
  const pills = [
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

function signalCard(item, index) {
  const title = element("a", {
    text: item.title,
    attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
  });
  const body = [
    pillBar(item),
    element("h3", {}, [title]),
    element("p", { text: shorten(item.summary) }),
  ];
  // The pill bar already states source and categories, so drop the rationale
  // entries that only restate them.
  const rationale = (item.rationale || [])
    .filter(Boolean)
    .filter((reason) => !/^(Matched|Primary record):/.test(reason));
  if (rationale.length) {
    body.push(
      element("p", {
        className: "signal-why",
        text: `Why surfaced: ${rationale.join("; ")}`,
      }),
    );
  }
  return element("article", { className: "signal-card" }, [
    element("div", { className: "signal-rank", text: String(index + 1).padStart(2, "0") }),
    element("div", {}, body),
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
  state.todayDate = day.date;
  byId("today-date").value = day.date;
  byId("scan-count").textContent = day.item_count;
  byId("briefing-date").textContent = formatDate(day.date);

  const reporting = day.health.filter((entry) => entry.ok);
  const failed = day.health.filter((entry) => !entry.ok);
  const represented = new Set(day.items.map((item) => item.source)).size;
  byId("briefing-copy").textContent = failed.length
    ? `${reporting.length} of ${day.health.length} configured sources reported; ${failed.length} failed and contributed nothing. Comparisons should be read with that limitation.`
    : "All configured sources reported successfully for this scan.";
  replaceChildren(byId("briefing-stats"), [
    definition("Window start", formatDate(day.since, { dateStyle: "medium" })),
    definition("Sources reporting", `${reporting.length}/${day.health.length}`),
    definition("Sources in results", represented),
    definition("Categories", Object.keys(day.category_counts).length),
  ]);

  const distribution = Object.entries(day.category_counts).sort((a, b) => b[1] - a[1]);
  const distributionMax = Math.max(1, ...distribution.map(([, count]) => count));
  replaceChildren(
    byId("scan-distribution"),
    distribution.map(([category, count], index) => {
      const fill = element("span", { className: "spark-fill" });
      fill.style.width = `${Math.max(4, (count / distributionMax) * 100)}%`;
      fill.style.setProperty("--bar-color", categoryColor(category, index));
      return element("div", { className: "spark-row" }, [
        element("span", { className: "spark-label", text: category.replaceAll("_", " ") }),
        element("span", { className: "spark-track" }, [fill]),
        element("span", { className: "spark-count", text: String(count) }),
      ]);
    }),
  );

  byId("today-count").textContent = `${day.item_count} records`;
  replaceChildren(
    byId("today-list"),
    day.items.map((item, index) => signalCard(item, index)),
  );

  byId("health-summary").textContent = `${reporting.length}/${day.health.length} reporting`;
  replaceChildren(
    byId("health-list"),
    day.health.map((entry) => {
      const children = [
        element("span", { className: `health-dot${entry.ok ? " ok" : ""}` }),
        element("span", { className: "health-name", text: entry.source }),
        element("span", {
          className: "health-count",
          text: entry.ok ? `${entry.item_count} found` : "failed",
        }),
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
      const healthy = day.health.filter((entry) => entry.ok).length;
      const link = element("a", { text: day.date, attrs: { href: `?date=${day.date}` } });
      link.addEventListener("click", (event) => {
        event.preventDefault();
        state.todayDate = day.date;
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
        element("td", { text: `${healthy}/${day.health.length} reporting` }),
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
    rationale: observation.rationale || ["Public attention signal; not quality evidence"],
    discovered_at: observation.discovered_at || feed.generated_at,
    snapshot_date: published.slice(0, 10),
    supporting_observations: (observation.supporting_observations || []).filter(
      (supporting) => supporting && safeHttpUrl(supporting.url),
    ),
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

function normalizedRecordTitle(title) {
  return title.toLowerCase().match(/[a-z0-9]+/g)?.join(" ") || title.toLowerCase().trim();
}

function attentionTotal(item) {
  return Number(item.metrics?.points || 0) + Number(item.metrics?.comments || 0);
}

function metricLabel(value, singular, plural = `${singular}s`) {
  const count = Number(value || 0);
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

function supportingRecord(item) {
  return {
    source_id: item.source_id,
    url: item.url,
    published_at: item.published_at,
    metrics: item.metrics || {},
    ...(item.artifact_urls?.[0] ? { primary_artifact_url: item.artifact_urls[0] } : {}),
  };
}

function clusterAttentionRecords(items) {
  const groups = new Map();
  items.forEach((item) => {
    const key = `${item.source}\u0000${normalizedRecordTitle(item.title)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  return [...groups.values()].map((group) => {
    if (group.length === 1) return group[0];
    const primary = [...group].sort(
      (left, right) =>
        attentionTotal(right) - attentionTotal(left) ||
        String(right.published_at).localeCompare(String(left.published_at)),
    )[0];
    const supporting = [
      ...(primary.supporting_observations || []),
      ...group
        .filter((item) => item.source_id !== primary.source_id)
        .flatMap((item) => [supportingRecord(item), ...(item.supporting_observations || [])]),
    ];
    const uniqueSupporting = [
      ...new Map(
        supporting
          .filter((item) => item.source_id !== primary.source_id && safeHttpUrl(item.url))
          .map((item) => [item.source_id, item]),
      ).values(),
    ];
    return {
      ...primary,
      categories: [...new Set(group.flatMap((item) => item.categories || []))].sort(),
      metrics: {
        points: group.reduce((sum, item) => sum + Number(item.metrics?.points || 0), 0),
        comments: group.reduce((sum, item) => sum + Number(item.metrics?.comments || 0), 0),
        submissions: group.reduce(
          (sum, item) => sum + Number(item.metrics?.submissions || 1),
          0,
        ),
      },
      rationale: [
        ...new Set([
          ...group.flatMap((item) => item.rationale || []),
          `Clustered ${group.length} public submissions with the same normalized title`,
        ]),
      ],
      supporting_observations: uniqueSupporting,
    };
  });
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
    state.external = clusterAttentionRecords(
      settled
        .filter((result) => result.status === "fulfilled")
        .flatMap((result) => result.value),
    );
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
  const isAttention = item.observation_kind === "attention";
  const scoreEntries = isAttention
    ? [
        ["HN points", Number(item.metrics?.points || 0).toLocaleString()],
        ["Comments", Number(item.metrics?.comments || 0).toLocaleString()],
        ["Submissions", Number(item.metrics?.submissions || 1).toLocaleString()],
        ["Published", formatDate(item.published_at, { dateStyle: "medium" })],
      ]
    : [
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
                  text: `Hacker News #${record.source_id}`,
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
    ...(isAttention && item.artifact_urls?.[0]
      ? [
          element("a", {
            className: "primary-link",
            text: "Open primary artifact ↗",
            attrs: {
              href: item.artifact_urls[0],
              target: "_blank",
              rel: "noopener noreferrer",
            },
          }),
        ]
      : []),
    element("a", {
      className: isAttention ? "secondary-link" : "primary-link",
      text: isAttention ? "Open public discussion ↗" : "Open primary source ↗",
      attrs: { href: item.url, target: "_blank", rel: "noopener noreferrer" },
    }),
  ]);
  replaceChildren(byId("detail-content"), [
    element("p", {
      className: "detail-source",
      text: `${item.source} · ${item.event_kind} · ${item.snapshot_date}`,
    }),
    element("h2", { className: "detail-title", text: item.title, attrs: { id: "detail-title" } }),
    element("p", { className: "detail-summary", text: item.summary || "No summary provided." }),
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
          text: `Discovered by the radar ${formatDate(item.discovered_at, { dateStyle: "medium", timeStyle: "short" })} UTC`,
        })
      : null,
    links,
  ]);
  byId("detail-dialog").showModal();
}

function explorerCard(item) {
  const isAttention = item.observation_kind === "attention";
  const badge =
    isAttention
      ? element("span", { className: "attention-badge", text: "attention" })
      : null;
  const details = element("button", {
    className: "detail-button",
    text: isAttention ? "View signal" : "View evidence",
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
          attrs: {
            href: isAttention && item.artifact_urls?.[0] ? item.artifact_urls[0] : item.url,
            target: "_blank",
            rel: "noopener noreferrer",
          },
        }),
      ]),
      element("p", {
        text: isAttention
          ? `${(item.categories || []).join(" · ") || "uncategorized"} · ${metricLabel(item.metrics?.points, "point")} · ${metricLabel(item.metrics?.comments, "comment")} · ${metricLabel(item.metrics?.submissions || 1, "submission")}`
          : `${(item.categories || []).join(" · ") || "uncategorized"} · ${shorten(item.summary, 140)}`,
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
    state.todayDate = event.target.value;
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
    await loadExternalFeeds();
    renderToday();
    renderTrends();
    renderExplorer();
    setView(state.view, false);
    const latest = dailySnapshot(state.data.latest_date);
    const healthy = latest.health.filter((entry) => entry.ok).length;
    byId("status-copy").textContent =
      `Latest ${latest.date} · ${healthy}/${latest.health.length} sources reporting`;
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
