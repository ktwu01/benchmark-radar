const CATEGORY_COLORS = {
  benchmark: "#255ea8",
  evaluation: "#dc633f",
  dataset: "#4c948b",
  data_quality: "#c99327",
  agentic: "#756aa8",
};
const FALLBACK_COLORS = ["#756aa8", "#397f9a", "#a4576d", "#70833d"];
const ALL_DATES_PAGE_SIZE = 100;

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
  const recommendationExplanation = Number.isFinite(recommendationScore)
    ? `Priority score meets this scan's ${recommendationScore.toFixed(0)}-point triage threshold; not an endorsement.`
    : "Priority score meets this scan's triage threshold; not an endorsement.";
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
    ...(item.recommended
      ? [
          element("span", {
            className: "recommendation-badge",
            text: "Recommended",
            attrs: {
              title: recommendationExplanation,
              "aria-label": `Recommended to review. ${recommendationExplanation}`,
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

function briefingProvenance(briefing) {
  if (briefing.generator !== "openai-responses") return null;
  const usage = briefing.usage || {};
  const input = briefing.input || {};
  return element("p", {
    className: "daily-briefing-meta",
    text: `GPT synthesis: ${briefing.model || "OpenAI model"} via OpenAI Responses API · ${Number(usage.input_tokens || 0).toLocaleString()} input / ${Number(usage.output_tokens || 0).toLocaleString()} output tokens · ${Number(input.evidence_items || 0).toLocaleString()} evidence records and ${Number(input.history_days || 0).toLocaleString()} history days injected.`,
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
      text: "Evidence cited by GPT",
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
  const caveat = briefing.caveat
    ? element("p", { className: "daily-briefing-caveat" }, [
        element("strong", { text: "Caveat: " }),
        document.createTextNode(String(briefing.caveat)),
      ])
    : null;
  const evidence = briefingEvidenceList(citations);
  if (!provenance && !caveat && !evidence) return null;

  const label = citations.length
    ? `Evidence & briefing details · ${citations.length.toLocaleString()} sources`
    : "Briefing details";
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
  const bullets = Array.isArray(briefing.bullets) ? briefing.bullets : [];
  const citations = validBriefingCitations(briefing.citations);
  // A briefing carrying another day's date describes the wrong day, so it is
  // withheld rather than shown beside this date's listings.
  const usable = briefing.date === day.date ? bullets.filter((line) => line.trim()) : [];
  replaceChildren(
    byId("daily-briefing-body"),
    usable.length
      ? [
          element("ul", { className: "daily-briefing-list" },
          // Model prose remains text nodes. Only exact evidence IDs present in
          // the snapshot's validated citation map become links.
          usable.map((line) => element("li", {}, briefingContent(line, citations)))),
          briefingDetails(briefing, citations),
        ]
      : [
          element("p", {
            className: "empty-state",
            text: "No briefing was recorded for this day.",
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
  return element("article", { className: "answer" }, [
    // The confidence sits on the question's own line: it qualifies the answer
    // that follows, so a reader should meet it before reading the claim.
    element("h4", { className: "answer-question" }, [
      document.createTextNode(String(answer?.question || "")),
      ...(confidence
        ? [
            element("span", {
              className: `pill pill-confidence pill-confidence-${confidence}`,
              text: `${confidence} confidence`,
            }),
          ]
        : []),
    ]),
    element("p", { className: "answer-signal", text: String(answer?.signal || "") }),
    element("p", { className: "answer-plain" }, [
      element("em", { text: "In plain English: " }),
      document.createTextNode(String(answer?.plain_english || "")),
    ]),
    answerCitations(answer),
    // Stated on the answer rather than hidden in a tooltip: "the evidence does
    // not support an answer today" is a result, not a rendering failure.
    ...(insufficient
      ? [
          element("p", {
            className: "answer-insufficient",
            text: "Evidence is insufficient to answer this today.",
          }),
        ]
      : []),
    element("p", { className: "answer-takeaway" }, [
      element("strong", { text: "Takeaway: " }),
      document.createTextNode(String(answer?.takeaway || "")),
    ]),
    // The counter-view is the point of the format: an answer that only ever
    // confirms itself teaches a reader nothing about how much to trust it.
    element("p", { className: "answer-counter-view" }, [
      element("strong", { text: "Counter-view: " }),
      document.createTextNode(String(answer?.counter_view || "")),
    ]),
  ]);
}

function questionsProvenance(questions) {
  if (questions.generator !== "openai-responses") return null;
  const usage = questions.usage || {};
  return element("p", {
    className: "daily-questions-meta",
    text: `Answered by ${questions.model || "OpenAI model"} in ${Number(questions.calls || 0).toLocaleString()} calls · ${Number(usage.input_tokens || 0).toLocaleString()} input / ${Number(usage.output_tokens || 0).toLocaleString()} output tokens · every figure computed before the call and cited by ID.`,
  });
}

// The Q&A is opt-in and generated once per UTC day, so a day can legitimately
// have none: it predates the feature, was disabled, or the calls failed. The
// snapshot's `questions.status` says which, so the empty state names the
// actual reason instead of one generic message for all three.
function absentQuestionsMessage(questions) {
  const status = questions.status;
  if (status === "disabled") {
    return questions.reason || "Daily questions were not enabled for this run.";
  }
  if (status === "error") {
    return `Daily questions failed to generate: ${questions.reason || "unknown error"}.`;
  }
  return "No questions were answered for this day.";
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
          text: String(group?.title || "Questions"),
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

function renderToday() {
  const showingAllDates = state.todayDate === "all";
  const day = dailySnapshot(showingAllDates ? state.data.latest_date : state.todayDate);
  if (!day) return;
  byId("today-date").value = state.todayDate;

  // The briefing and connector health describe one scan, not an archive-wide
  // result set. Hiding them in All dates mode keeps latest-day context from
  // appearing to explain observations collected across the full history.
  byId("daily-briefing").hidden = showingAllDates;
  byId("daily-questions").hidden = showingAllDates;
  byId("source-health-panel").hidden = showingAllDates;

  renderDailyBriefing(day);
  renderDailyQuestions(day);

  syncFilters();
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
  const visibleObservations = showingAllDates
    ? observations.slice(0, state.todayResultsLimit)
    : observations;
  const remainingResults = observations.length - visibleObservations.length;
  const showMore = byId("today-show-more");
  showMore.hidden = remainingResults <= 0;
  showMore.textContent = remainingResults > 0
    ? `Show ${Math.min(ALL_DATES_PAGE_SIZE, remainingResults)} more · ${remainingResults} remaining`
    : "Show more results";
  const evidenceCount = observations.filter(
    (item) => item.observation_kind === "evidence",
  ).length;
  const attentionCount = observations.length - evidenceCount;
  byId("today-count").textContent =
    `${observations.length} result${observations.length === 1 ? "" : "s"} · ` +
    `${evidenceCount} evidence · ${attentionCount} attention`;
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

  const healthEntries = [
    ...day.ingest_health.map((entry) => ({ ...entry, layer: "Radar ingest" })),
    ...day.producer_health.map((entry) => ({ ...entry, layer: "Producer report" })),
  ];
  // Fetch plumbing is not what the reader came for, so the roster stays
  // collapsed to one line and the reader expands it on demand. The summary
  // still carries the failure count, so a gap is legible without opening the
  // panel: connector failures are usually long-lived and known, and
  // force-opening on every one of them buried the list beside it.
  const failedCount = healthEntries.filter((entry) => !entry.ok).length;
  byId("health-status").textContent = failedCount
    ? `${failedCount} of ${healthEntries.length} failed`
    : `${healthEntries.length} ok`;
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
          text: `+${ranked.length - shown.length} more categories`,
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
            ? ` · flat vs ${previous.date.slice(5)}`
            : ` · ${deltaText(total - previousTotal)} vs ${previous.date.slice(5)}`),
    }),
    rows.length ? element("span", { className: "day-tooltip-rows" }, rows) : null,
    element("span", {
      className: "day-tooltip-attention",
      text: `Active attention: ${day.attention.active_count}`,
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
            `Every record matching at least one taxonomy category is retained. A score of ` +
            `${Number(recommendationScore).toFixed(2)} or above adds the Recommended ` +
            "badge; it does not control inclusion. Watchlisted artifacts are also retained.",
        })
      : historicalMinimum !== undefined && historicalMinimum !== null
        ? element("p", {
            className: "discovery-note",
            text:
              `This historical scan used ${Number(historicalMinimum).toFixed(2)} as an ` +
              "inclusion cutoff. Records below it were not retained.",
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
        url
          ? element("a", {
              className: "adopter-link",
              text: name,
              attrs: { href: url, target: "_blank", rel: "noopener noreferrer" },
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
      label: "Early signal",
      description:
        "Only one dated organization is visible so far. It is too early to infer a plateau.",
    };
  }
  if (total > 0 && advances / total >= 0.8) {
    return {
      id: "saturated",
      label: "Saturated reporting",
      description:
        "At least 80% of organizations in this curated registry report it; that is convention, not quality.",
    };
  }
  if (isNewBenchmark(entry, board) && advances <= 4) {
    return {
      id: "emerging",
      label: "New & spreading",
      description:
        "Released in the newest 18-month window and already reported by several independent organizations.",
    };
  }
  return {
    id: "established",
    label: "Established",
    description:
      "Reported across multiple organizations, but not yet a corpus-wide convention in this registry.",
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
    ["emerging", "New & spreading"],
    ["early", "Early signals"],
    ["established", "Established"],
    ["saturated", "Saturated reporting"],
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
                : ` · ${metricLabel(elapsed, "day")} after ${
                    index ? "the previous frontier step" : "release"
                  }`
            }`,
          }),
          element("a", {
            className: "milestone-source",
            text: event.organization,
            attrs: {
              href: event.url,
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
          text: `Released ${formatDate(entry.released, { dateStyle: "medium" })}`,
        })
      : null,
    list,
    repeats
      ? element("p", {
          className: "milestone-repeat-note",
          text: `${metricLabel(repeats, "repeat report")} did not add a new organization to the frontier.`,
        })
      : null,
  ]);
}

function renderFrontierTaskPreview(entry) {
  const shape = taskShape(entry);
  replaceChildren(byId("frontier-task-preview"), [
    element("p", {
      className: "eyebrow",
      text: shape.provenance || "Representative task shape",
    }),
    element("h3", { text: shape.title, attrs: { id: "frontier-task-heading" } }),
    element("div", { className: "task-shape" }, [
      shape.example ? element("span", { text: "Paraphrased example" }) : null,
      shape.example ? element("p", { text: shape.example }) : null,
      element("span", { text: "Scenario" }),
      element("p", { text: shape.scenario }),
      element("span", { text: "Evaluated artifact" }),
      element("p", { text: shape.artifact }),
    ]),
    element("p", {
      className: "task-shape-note",
      text: shape.provenance
        ? "Not a verbatim benchmark item. This description paraphrases the official source; open it for exact tasks and protocol."
        : "Not a verbatim benchmark item. This is an illustrative format based on the recorded domain; use the official source for exact tasks and protocol.",
    }),
    entry.caveat
      ? element("div", { className: "frontier-caveat" }, [
          element("strong", { text: "Comparison caveat" }),
          element("p", { text: entry.caveat }),
        ])
      : null,
    entry.url
      ? element("a", {
          className: "frontier-source-link",
          text: "Open official benchmark source ↗",
          attrs: {
            href: entry.url,
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
        "aria-label": `${entry.name} has only one dated reporting organization; it is too early to infer a plateau.`,
      },
    },
    [
      element("div", { className: "frontier-sparse-step is-complete" }, [
        element("span", { text: "01" }),
        element("strong", { text: "Benchmark released" }),
        element("small", {
          text: entry.released
            ? formatDate(entry.released, { dateStyle: "medium" })
            : "Release date unrecorded",
        }),
      ]),
      element("div", { className: "frontier-sparse-step is-complete" }, [
        element("span", { text: "02" }),
        element("strong", { text: "First reporting organization" }),
        element("small", {
          text: first
            ? `${first.organization} · ${formatDate(first.published, { dateStyle: "medium" })}`
            : "No dated report",
        }),
      ]),
      element("div", { className: "frontier-sparse-step is-awaiting" }, [
        element("span", { text: "03" }),
        element("strong", { text: "Awaiting an independent second organization" }),
        element("small", {
          text: repeatCount
            ? `${metricLabel(repeatCount, "later repeat")} still leaves one frontier step`
            : "Too early to infer a reporting plateau",
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
      element("span", { text: "Best on record" }),
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
        element("span", { text: "Headroom left" }),
        element("strong", { text: `${saturation.headroom}` }),
        // On a lower-is-better metric the backend measures headroom to zero, not
        // to `bound`. Naming the bound in both cases would print "10 points to
        // the 100-point bound" for a score of 10, which is arithmetically false.
        element("small", {
          text:
            record.direction === "lower_is_better"
              ? "points to zero, the floor of this metric"
              : `points to the ${saturation.bound}-point bound of this metric`,
        }),
      ]),
    );
  }
  rows.push(
    element("div", { className: "score-readout-figure" }, [
      element("span", { text: "Readable values" }),
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
        element("span", { className: "score-evidence-yes", text: "Supports: " }),
        document.createTextNode(evidence.supports),
      ]),
      element("p", {}, [
        element("span", { className: "score-evidence-no", text: "Does not support: " }),
        document.createTextNode(evidence.does_not_support),
      ]),
    ]),
    record.third_party_count
      ? element("p", {
          className: "score-readout-note",
          // The verb has to agree with the count, not stay singular beside a
          // pluralized noun ("4 values here is a third party...").
          text: `${metricLabel(record.third_party_count, "value")} here ${
            record.third_party_count === 1 ? "is a third party" : "are third parties"
          } quoting another vendor's figure, marked with a ring on the chart.`,
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
          "No score for this benchmark could be read verbatim from the cited documents, so the " +
          "chart shows adoption only. An absent value is not a zero and not a plateau.",
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
    pinned && details.url
      ? element("a", {
          className: "frontier-tooltip-source",
          text: "Open source record ↗",
          attrs: {
            href: details.url,
            target: "_blank",
            rel: "noopener noreferrer",
            tabindex: selectedFrontierSourceVisited ? "-1" : "0",
          },
        })
      : null,
    element("span", {
      className: "frontier-tooltip-hint",
      text: pinned
        ? "Pinned · click the marker again or press Escape to close"
        : "Click the marker to pin these details",
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
        ["legend-swatch-diamond", "New organization", "cumulative count increases"],
        [
          "legend-swatch-tick-first",
          "First card from that organization",
          "the tick under the jump",
        ],
        [
          "legend-swatch-tick-repeat",
          "Later card, organization already counted",
          "count unchanged",
        ],
      ];
  if (record) {
    items.push([
      "legend-swatch-score",
      "Readable score",
      "connected only at one instrument and protocol",
    ]);
    if (record.series.some((series) => series.connectable && !series.single_organization)) {
      items.push([
        "legend-swatch-score-line",
        "Solid score connection",
        "same instrument and protocol across organizations",
      ]);
    }
    if (record.series.some((series) => series.connectable && series.single_organization)) {
      items.push([
        "legend-swatch-score-line-single-org",
        "Dashed score connection",
        "same instrument and protocol, one organization only",
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
      const r = 7;
      group.append(
        svgElement("polygon", {
          points: `${pointX},${pointY - r} ${pointX + r},${pointY} ${pointX},${pointY + r} ${pointX - r},${pointY}`,
        }),
      );
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
        `best on record ${record.saturation.best_value}`,
      ),
    );

    for (const observation of record.observations) {
      const source = (board.model_cards || []).find(
        (card) => card.model_card_id === observation.source_id,
      );
      const sourceLabel = source
        ? `${source.organization} · ${source.model} (${String(
            source.document_type || "model card",
          ).replaceAll("_", " ")})`
        : observation.source_id.replaceAll("_", " ");
      const group = svgElement("g", {
        class: `score-point${observation.reported_by ? " score-point-third-party" : ""}`,
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "data-frontier-point": "",
        "aria-label":
          `${observation.value} ${record.metric} by ${observation.model} ` +
          `(${observation.organization}), ${formatDate(observation.reported_at, {
            dateStyle: "medium",
          })}, protocol ${observation.protocol}` +
          (observation.reported_by ? `, cited by ${observation.reported_by}` : "") +
          ". Click to pin record details.",
      });
      group.append(
        svgElement("circle", {
          cx: x(observation.reported_at),
          cy: scoreY(observation.value),
          r: 5,
        }),
      );
      makeFrontierPointInteractive(group, {
        kind: "Readable score",
        title: `${observation.organization} · ${observation.model}`,
        rows: [
          { label: "Organization", value: observation.organization },
          { label: "Model", value: observation.model },
          {
            label: "Date",
            value: formatDate(observation.reported_at, { dateStyle: "medium" }),
          },
          {
            label: "Score",
            value: `${observation.value}${record.unit === "percent" ? "%" : ` ${record.unit}`} ${record.metric}`,
          },
          { label: "Instrument", value: observation.instrument },
          { label: "Protocol", value: observation.protocol },
          { label: "Source", value: sourceLabel },
          { label: "Read from", value: observation.read_from.replaceAll("_", " ") },
          ...(observation.reported_by
            ? [{ label: "Cited by", value: observation.reported_by }]
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
          "no readable score in this window",
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
        narrow ? `${record.metric} (zoom)` : `${record.metric} (zoomed)`,
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
        ? "release"
        : events.length
          ? "first dated mention"
          : "first readable score",
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
        narrow ? "distinct orgs" : "cumulative distinct organizations",
      ),
    );
  }
  svg.append(
    svgElement(
      "text",
      { x: margin.left + plotWidth / 2, y: height - 7, "text-anchor": "middle", class: "frontier-axis-label" },
      "publication time",
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
  replaceChildren(byId("frontier-chart"), [
    element("p", { className: "empty-state", text: message }),
  ]);
}

function renderAdoptionFrontier(board) {
  const adopted = (board.entries || []).filter((entry) => entry.card_count > 0);
  const defaultEntry = frontierDefaultEntry(board);
  if (!adopted.length || !defaultEntry) {
    clearAdoptionFrontier("No dated model-card mentions yet.");
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
  byId("frontier-heading").textContent = `${entry.name} adoption trajectory`;
  const events = frontierEvents(entry);
  if (!events.length) {
    // No dated mention means no adoption timeline can be drawn. The score
    // reading is independent of that, though: the registry permits a card
    // without a `published` date, and clearing the panel outright would hide
    // every readable score because the *other* layer had no usable date. So the
    // score track still draws, on its own, with the points and comparable series
    // intact rather than reduced to the aggregate readout.
    clearAdoptionFrontier("This benchmark has no dated mentions.");
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
  stageElement.textContent = `Reporting stage · ${stage.label}`;
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
        ((entry.adopters || []).some((adopter) => !adopter.published) ? " with a dated card" : ""),
    }),
    element("span", {
      text: `last new organization ${formatDate(lastAdvance.published, { dateStyle: "medium" })}`,
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
      element("p", { className: "score-label", text: "Model cards" }),
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
            href: adopter.url,
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
      element("span", { className: "benchmark-new-badge", text: "new instrument" }),
    );
  }

  const frontierButton = element("button", {
    className: "secondary-link frontier-jump",
    text: "View adoption frontier ↑",
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
      element("h3", { text: "Reported by" }),
      adopters,
      frontierButton,
      entry.url
        ? element("a", {
            className: "primary-link",
            text: "Benchmark home ↗",
            attrs: { href: entry.url, target: "_blank", rel: "noopener noreferrer" },
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
    option("", "All domains", !state.ldomain),
    ...domains.map((domain) =>
      option(domain, domain.replaceAll("_", " "), domain === state.ldomain),
    ),
  ]);
  const organizations = Object.keys(board.organizations || {}).sort();
  replaceChildren(byId("leaderboard-organization"), [
    option("", "All organizations", !state.lorg),
    ...organizations.map((organization) =>
      option(organization, organization, organization === state.lorg),
    ),
  ]);
  replaceChildren(byId("leaderboard-era"), [
    option("", "Any release date", !state.lera),
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
  const evidenceStat = (value, label, detail) =>
    element("article", { className: "evidence-stat" }, [
      element("strong", { text: Number(value || 0).toLocaleString() }),
      element("span", { text: label }),
      element("small", { text: detail }),
    ]);
  replaceChildren(byId("leaderboard-insights"), [
    evidenceStat(
      board.model_card_count,
      "source documents",
      "Each document counts once per benchmark.",
    ),
    evidenceStat(
      board.organization_count,
      "organizations",
      "The denominator for reporting breadth.",
    ),
    evidenceStat(
      Object.keys(board.domains || {}).length,
      "Domains reported at least once",
      `${metricLabel(board.benchmark_count, "benchmark")} tracked · ${metricLabel(
        topEntries.length,
        "benchmark",
      )} reported.`,
    ),
    evidenceStat(
      newSharedSignals.length,
      "new shared signals",
      "New instruments crossing three dated organizations.",
    ),
    element("p", { className: "evidence-thesis" }, [
      element("strong", { text: "New instruments" }),
      element("span", {
        text: ` · ${metricLabel(
          newSharedSignals.length,
          "benchmark",
        )} released in the newest 18-month window already appear across three or more dated organizations. Follow their trajectories before reading the raw rank.`,
      }),
    ]),
  ]);

  const entries = leaderboardEntries();
  const filtersActive = Boolean(state.lq || state.ldomain || state.lorg || state.lera);
  const visibleEntries =
    filtersActive || state.leaderboardShowAll ? entries : entries.slice(0, 18);
  byId("leaderboard-count").textContent = filtersActive
    ? `${metricLabel(entries.length, "benchmark")} of ${board.entries.length}`
    : `${visibleEntries.length} shown · ${board.entries.length} tracked`;
  replaceChildren(
    byId("leaderboard-list"),
    visibleEntries.length
      ? visibleEntries.map(leaderboardRow)
      : [
          element("p", {
            className: "empty-state",
            text: "No benchmarks match these filters. Clear one or more filters to widen the view.",
          }),
        ],
  );
  const showAllButton = byId("leaderboard-show-all");
  showAllButton.hidden = filtersActive || entries.length <= 18;
  showAllButton.textContent = state.leaderboardShowAll
    ? "Show the first 18 benchmarks"
    : `Show all ${entries.length} benchmarks`;

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
            : "date unknown",
        }),
      ]),
      element("h3", { text: card.model }),
    ]),
    element("div", { className: "score" }, [
      element("div", { className: "score-value" }, [
        element("strong", { text: String(card.benchmark_count) }),
      ]),
      element("p", { className: "score-label", text: "Benchmarks" }),
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
            benchmark.url
              ? element("a", {
                  className: "adopter-link",
                  text: benchmark.name,
                  attrs: {
                    href: benchmark.url,
                    target: "_blank",
                    rel: "noopener noreferrer",
                  },
                })
              : element("span", { className: "adopter-link", text: benchmark.name }),
            element("span", {
              className: "adopter-meta",
              text: benchmark.released
                ? `released ${formatDate(benchmark.released, { dateStyle: "medium" })}`
                : "release date unrecorded",
            }),
          ]),
        ),
      ),
    ]),
  );

  return element("details", { className: "record-card" }, [
    summary,
    element("div", { className: "record-detail" }, [
      element("h3", { text: "Benchmarks this document reports" }),
      element("p", {
        className: "section-note",
        // Says what the reader is and is not looking at, at the point of
        // looking. A mention is not a score, and the expanded list would
        // otherwise read as if it were an extract of the card's results table.
        text:
          "Every benchmark this document puts in front of readers, counted once each. " +
          "These are mentions, not scores: the source records the configuration, and " +
          "this registry deliberately does not.",
      }),
      ...groups,
      element("a", {
        className: "primary-link",
        text: "Open source document ↗",
        attrs: { href: card.url, target: "_blank", rel: "noopener noreferrer" },
      }),
      card.retrieved_at
        ? element("p", {
            className: "adopter-meta",
            text: `Last read by a human on ${formatDate(card.retrieved_at, {
              dateStyle: "medium",
            })}`,
          })
        : null,
    ]),
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
    renderLeaderboard();
    writeUrl();
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
    renderToday();
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
    if (event.key === "Escape" && selectedFrontierPoint) {
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
    renderToday();
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
    if (state.todayDate !== "all" && !state.data.facets.dates.includes(state.todayDate)) {
      state.todayDate = state.data.latest_date;
    }
    replaceChildren(
      byId("today-date"),
      [
        option("all", "All dates", state.todayDate === "all"),
        ...[...state.data.facets.dates].reverse().map((date) =>
          option(date, formatDate(date, { dateStyle: "medium" }), date === state.todayDate),
        ),
      ],
    );
    renderToday();
    renderLeaderboard();
    renderTrends();
    renderTrendMap();
    // A permalink to ?view=leaderboard on a build without the curated registry
    // has nothing to show, so fall back to Today rather than opening a blank
    // section behind a nav entry that renderLeaderboard just hid.
    if (state.view === "leaderboard" && !state.data.model_card_leaderboard) {
      state.view = "today";
    }
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
