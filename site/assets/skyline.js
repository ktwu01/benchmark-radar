// Benchmark measurements from one catalog. Source names describe provenance;
// the same measurement rules apply to every record. Time never enters dominance.
export const SKYLINE_DOMAINS = {
  Code: ["coding", "code", "coding_agent"],
  Science: ["science", "biology", "math", "ai_research"],
  Agent: ["agent", "agents", "agentic", "tool_use", "computer_use"],
  Multimodal: ["multimodal", "vision", "image", "video", "audio", "spatial_reasoning", "vlm"],
  Other: [],
};
export const SKYLINE_START_DATE = "2024-01-01";
export const SKYLINE_HEIGHT_LABELS = {
  models: "Models with reported scores",
  documents: "Source documents",
};

export function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

export function benchmarkDate(record, entry = {}) {
  const released = [entry?.released, record.released].find(validDate);
  if (released) return { date: released, dateBasis: "released" };
  // Actual numeric score-publication dates take precedence over proxies.
  // A model-card mention or batch crawl does not date a benchmark.
  const dates = [record.first_reported_at, record.first_score_reported_at,
    ...(record.observations || []).filter((row) => Number.isFinite(row.value)
      && !["model_announcement", "crawl"].includes(row.date_precision))
      .map((row) => row.reported_at || row.reported_date)]
    .filter(validDate).sort();
  if (dates.length) return { date: dates[0], dateBasis: "first_score" };
  // Aggregators date their score entries by the scored model's release. Keep
  // that earliest score-record date as an explicitly labelled proxy; never
  // relabel it as the benchmark's release or a score publication date.
  const firstRecord = record.first_score_record;
  if (["day", "document_publication", "score_publication", "model_announcement"].includes(firstRecord?.date_precision)
    && validDate(firstRecord?.reported_at)) return {
    date: firstRecord.reported_at,
    dateBasis: firstRecord.date_precision === "model_announcement" ? "score_record_proxy" : "first_score",
  };
  return { date: null, dateBasis: null };
}

export function benchmarkDateLabel(row) {
  return row.dateBasis === "released" ? "Released"
    : row.dateBasis === "score_record_proxy" ? "First dated LLM score (model-release proxy)"
      : "First LLM score reported";
}

// This is the population used by the chart, rankings and browser. Keeping a
// row does not require a score, date, adoption count, or join to another source.
export function scoreBrowserSummary(record) {
  const summary = record.score_summary;
  if (!summary) return null;
  const direction = record.score_direction || record.direction;
  if (record.unit === "percent" && direction === "lower_is_better"
    && Number.isFinite(summary.raw_min) && summary.raw_min >= 0 && summary.raw_max <= 100) {
    return { ...summary, display_max: 100 - summary.raw_min, normalized_from_lower: true };
  }
  return summary;
}

export function scorePopulation(catalog = []) {
  return catalog.map((record) => ({
    id: record.slug, name: record.name, source: record.source,
    record, summary: scoreBrowserSummary(record), ...benchmarkDate(record),
  }));
}

function hasReportedScore(summary) {
  return Number.isFinite(summary?.display_max) && summary.numeric_count > 0;
}

export function matchesScoreCutoff(summary, cutoff) {
  // Frontier and its ranking show reported scores only, including genuine zeroes.
  // "All" lifts the numeric cutoff; it does not restore unscored benchmarks.
  return hasReportedScore(summary) && (cutoff >= 100 || summary.display_max < cutoff);
}

export function skylineModel(catalog = [], cutoff = 70, matchingIds = null, heightMetric = "models", dateRange = null) {
  // A date range (#570) narrows what the figure shows, like the score cutoff
  // does: a benchmark whose release or first-score date falls outside it is
  // not drawn and cannot be a frontier candidate, but the dominance
  // comparison set stays the full cohort, so the slice cannot promote a
  // dominated benchmark onto the frontier. An undated record has no date, so
  // no bound can place it outside the span: it stays visible in the undated
  // panel instead of being counted as outside the range (principle.md).
  const from = validDate(dateRange?.from) ? dateRange.from : null;
  const to = validDate(dateRange?.to) ? dateRange.to : null;
  const inRange = (row) => {
    if (!from && !to) return true;
    if (!row.date) return true;
    return (!from || row.date >= from) && (!to || row.date <= to);
  };
  const population = scorePopulation(catalog);
  const all = population.map((item) => {
    const { id, name, source, record, summary } = item;
    const direction = record.score_direction;
    const unit = record.unit || summary?.unit;
    const percent = unit === "percent" && ["higher_is_better", "lower_is_better"].includes(direction);
    const inverted = percent && direction === "lower_is_better";
    const rawScore = (inverted ? summary?.raw_min : summary?.raw_max) ?? summary?.display_max ?? null;
    const displayScore = summary?.display_max ?? null;
    const score = percent && Number.isFinite(displayScore) && displayScore >= 0 && displayScore <= 100
      && Number.isFinite(summary?.raw_min) && summary.raw_min >= 0 && summary.raw_max <= 100
      ? displayScore : null;
    // A reported value remains visible even when its scale is not verified.
    const plotScore = score ?? (unit == null && direction === "higher_is_better"
      && Number.isFinite(displayScore) && displayScore >= 0 && displayScore <= 100 ? displayScore : null);
    const measuredDocuments = record.evidence_summary?.document_count;
    const documentCount = Number.isInteger(measuredDocuments) && measuredDocuments >= 0 ? measuredDocuments : null;
    const modelCount = Number.isInteger(summary?.model_count) && summary.model_count >= 0 ? summary.model_count : null;
    const heightCount = heightMetric === "documents" ? documentCount : modelCount;
    const { date, dateBasis } = item;
    const domainValues = [...(record.categories || []), record.modality]
      .filter(Boolean).map((value) => value.toLowerCase());
    const missing = [];
    if (!Number.isFinite(displayScore)) missing.push("score");
    else if (score === null) missing.push("scale");
    if (heightCount === null) missing.push("count");
    if (!date) missing.push("date");
    return {
      id, name, source, summary, date, dateBasis,
      dateReference: dateBasis === "released" && record.released === date ? record.released_reference
        : dateBasis === "first_score" && record.first_score_reported_at === date ? record.first_score_source_reference : null,
      time: date ? Date.parse(`${date}T00:00:00Z`) : null,
      score, plotScore, displayScore, rawScore, inverted, documentCount, modelCount, heightCount, missing,
      domain: Object.keys(SKYLINE_DOMAINS).find((domain) => SKYLINE_DOMAINS[domain].some((value) => domainValues.includes(value))) || "Other",
      sourceUrl: summary?.source_reference?.source_url || record.source_url,
      sourceId: summary?.source_reference?.source_id, reportedAt: summary?.source_reference?.reported_at,
      metric: record.metric, protocol: summary?.source_reference?.protocol, instrument: summary?.source_reference?.instrument,
    };
  });
  // The requested cohort starts on 2024-01-01. Within that cohort, only score
  // and the selected raw count determine dominance, before score or search.
  const comparable = (row) => hasReportedScore(row.summary) && row.date >= SKYLINE_START_DATE
    && row.score !== null && row.heightCount !== null;
  const withinDates = all.filter((row) => row.date === null || row.date >= SKYLINE_START_DATE);
  const cohort = withinDates.filter((row) => row.date !== null && hasReportedScore(row.summary));
  const eligible = cohort.filter(comparable);
  for (const row of all) {
    row.pareto = !comparable(row) ? null : !eligible.some((other) => other.score <= row.score && other.heightCount >= row.heightCount
      && (other.score < row.score || other.heightCount > row.heightCount));
  }
  // The figure's cutoff is independent of Saturation search. Normalized reversed
  // metrics remain explicit in the tooltip; they never change source scores.
  const visible = withinDates.filter((row) => (!matchingIds || matchingIds.has(row.id))
    && matchesScoreCutoff(row.summary, cutoff) && inRange(row));
  const dated = visible.filter((row) => row.date !== null);
  return {
    all, visible, dated, cohort, eligible, heightMetric, heightLabel: SKYLINE_HEIGHT_LABELS[heightMetric], comparable: dated.filter(comparable),
    rows: visible.filter((row) => row.plotScore !== null),
    pending: visible.filter((row) => row.plotScore === null),
    undated: visible.filter((row) => row.date === null),
    beforeStart: all.length - withinDates.length,
    population: all.length, sources: new Set(all.map((row) => row.source)).size,
    hidden: all.length - visible.length,
    dateRange: { from, to },
    dateHidden: withinDates.filter((row) => (!matchingIds || matchingIds.has(row.id))
      && matchesScoreCutoff(row.summary, cutoff) && !inRange(row)).length,
    // Exclusive counts: old records first, then unscored, then score/search,
    // then the date range.
    unscored: withinDates.filter((row) => !hasReportedScore(row.summary)).length,
  };
}

export function skylineGeometry(all) {
  const startYear = 2024;
  const start = Date.UTC(startYear, 0, 1);
  const times = all.map((row) => row.time).filter((time) => Number.isFinite(time) && time >= start);
  const last = times.length ? Math.max(...times) : start;
  const endYear = new Date(last).getUTCFullYear();
  const end = Date.UTC(endYear, Math.floor(new Date(last).getUTCMonth() / 3) * 3 + 3, 1);
  const maximum = Math.max(1, ...all.map((row) => row.heightCount).filter(Number.isFinite));
  // Oblique projection: time to the right, low scores at the front, counts up.
  // Fixed domains across cutoffs prevent filtering from moving the surviving points.
  const project = (timeFraction, score, count = 0) => [
    250 + timeFraction * 920 - score * 1.4,
    515 - score * 2.5 - 220 * Math.log1p(count) / Math.log1p(maximum),
  ];
  const timeFraction = (time) => !Number.isFinite(time) || time < start ? null : (time - start) / (end - start);
  const years = Array.from({ length: endYear - startYear + 1 }, (_, index) => startYear + index);
  const quarters = [];
  for (let year = startYear; year <= endYear; year++) {
    for (let month = 0; month < 12; month += 3) {
      const time = Date.UTC(year, month, 1);
      if (time < end) quarters.push({ time, year, quarter: month / 3 + 1 });
    }
  }
  return { width: 1300, height: 646, startYear, endYear, years, quarters, start, end, maximum, project, timeFraction };
}

// Separate nearby marks vertically while preserving each exact date on X.
// This is an individual-record timeline, not a year bin or histogram.
export function skylineDateLanes(rows, dateX, gap = 12) {
  const ends = [];
  const points = [...rows].sort((a, b) => a.time - b.time || a.id.localeCompare(b.id)).map((row) => {
    const x = dateX(row.time);
    let lane = ends.findIndex((end) => x - end >= gap);
    if (lane < 0) lane = ends.length;
    ends[lane] = x;
    return { row, x, lane };
  });
  return { points, lanes: ends.length };
}

// Unknown dates still have scores. Preserve the exact score vertically and
// spread neighboring records horizontally in an explicitly undated panel.
export function skylineScoreLanes(rows, scoreY, gap = 9) {
  const ends = [];
  const points = [...rows].sort((a, b) => b.plotScore - a.plotScore || a.id.localeCompare(b.id)).map((row) => {
    const y = scoreY(row.plotScore);
    let lane = ends.findIndex((end) => y - end >= gap);
    if (lane < 0) lane = ends.length;
    ends[lane] = y;
    return { row, y, lane };
  });
  return { points, lanes: ends.length };
}

// Coincident stem tips keep their measured coordinates. Only their interactive
// caps fan out, with a connector back to the true tip, so none hides another.
export function skylineCapPositions(rows, position, contains, gap = 10) {
  const placed = new Map();
  const coordinates = [];
  for (const row of [...rows].sort((a, b) => Number(b.pareto) - Number(a.pareto)
    || a.time - b.time || a.plotScore - b.plotScore || a.id.localeCompare(b.id))) {
    const actual = position(row);
    let cap = actual;
    const clear = (point) => contains(row, point)
      && coordinates.every((other) => Math.hypot(point[0] - other[0], point[1] - other[1]) >= gap);
    if (!clear(cap)) {
      search: for (let radius = gap; radius <= 1300; radius += gap) {
        for (let step = 0; step < 16; step++) {
          const angle = -Math.PI / 2 + step * Math.PI / 8;
          const candidate = [actual[0] + radius * Math.cos(angle), actual[1] + radius * Math.sin(angle)];
          if (clear(candidate)) { cap = candidate; break search; }
        }
      }
    }
    placed.set(row.id, cap);
    coordinates.push(cap);
  }
  return placed;
}

export function skylineFrontierSteps(rows) {
  // Equal score/count pairs all remain Pareto. Draw their shared corner once.
  const frontier = rows.filter((row) => row.pareto)
    .sort((a, b) => a.score - b.score || a.id.localeCompare(b.id));
  const steps = [];
  for (const row of frontier) {
    const previous = steps.at(-1);
    if (previous?.score === row.score && previous.count === row.heightCount) continue;
    if (previous) steps.push({ score: row.score, count: previous.count });
    steps.push({ score: row.score, count: row.heightCount });
  }
  return steps;
}
