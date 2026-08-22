import {
  CATEGORY_COLORS,
  FALLBACK_COLORS,
  ORGANIZATION_COLORS,
  ORGANIZATION_FALLBACK_COLORS,
  ORGANIZATION_ICONS,
  ORGANIZATION_FALLBACK_ICON,
  MODEL_FAMILY_ICONS,
  organizationColor,
  organizationIcon,
  modelIcon,
  iconGlyph,
  brandGlyph,
  modelGlyph,
} from "./glyphs.js";

// One page of results, in the list and at a time (issue #311). The first
// paint carries 20 cards; each further page is loaded by scrolling to the
// sentinel below the list. 100 at once was the archive bound, and a busy day
// paid for all of it before the reader could scroll.
const TODAY_PAGE_SIZE = 20;
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

// Fetch health records a run under its internal key ("first_party_feeds"),
// while the source mix counts finished evidence under the label a reader sees
// ("First-party feed"). Without this bridge a source that returned nothing is
// simply missing from the mix, and a reader cannot tell "this source looked
// and found nothing" apart from "this source does not exist" (issue #260).
const SOURCE_DISPLAY_NAMES = {
  arxiv: "arXiv",
  huggingface: "Hugging Face",
  github: "GitHub",
  openreview: "OpenReview",
  semantic_scholar: "Semantic Scholar",
  github_releases: "GitHub Release",
  first_party_feeds: "First-party feed",
  openalex: "OpenAlex",
  brave: "Brave Web",
};

const sourceDisplayName = (key) =>
  SOURCE_DISPLAY_NAMES[key] || String(key).replaceAll("_", " ");

// One sentence per kind of zero, so hovering a zero answers the question it
// raises instead of only restating that the number is zero.
const SOURCE_GAP_REASONS = {
  unreachable: "This source could not be reached on this day.",
  empty: "This source was checked and found nothing at all on this day.",
  unranked: "This source returned something, but none of it scored high enough to be listed.",
};

// Sources that ran for this day but put nothing into the ranked evidence, kept
// in the order fetch health reports them so the ledger reads the same way every
// day. Why a source is at zero decides what the reader should do about it, and
// the source mix counts ranked evidence while fetch health counts raw records,
// so there are three different zeros and only one of them is "nothing arrived":
//   unreachable  the fetch failed, so nothing could arrive
//   empty        the fetch worked and returned no records at all
//   unranked     records arrived but none scored high enough to be listed
// Calling the third one "found nothing" would be wrong: GitHub returning 300
// records that all scored too low is a scoring outcome, not a broken source.
function zeroItemSources(day) {
  const counts = day.source_counts || {};
  const merged = new Map();
  (day.ingest_health || [])
    .filter((entry) => entry.kind !== "attention")
    .forEach((entry) => {
      const name = sourceDisplayName(entry.source);
      if (Number(counts[name] || 0) > 0) return;
      // One source can be reported by more than one row (a connector retried
      // under a second method). A failure anywhere is the answer worth showing,
      // and the raw counts add up across the rows that did return something.
      const previous = merged.get(name);
      merged.set(name, {
        name,
        ok: previous ? previous.ok && entry.ok : entry.ok,
        fetched: (previous?.fetched || 0) + Number(entry.item_count || 0),
      });
    });
  return [...merged.values()].map((entry) => ({
    ...entry,
    state: !entry.ok ? "unreachable" : entry.fetched > 0 ? "unranked" : "empty",
  }));
}

// Why the Today list is empty, when a source filter is what emptied it.
//
// "No observations match these filters. Clear one or more filters" is right
// when the filters are too narrow and wrong when the source simply had a
// quiet day: clearing filters cannot conjure evidence that was never
// collected, so the advice sends the reader looking for a mistake they did
// not make. Filtering to First-party feed on Aug 18 2026 is exactly that
// case, and it read as a broken filter (issue #254).
//
// Only speaks when the source filter alone is active. With a second filter
// on, the source's own zero is no longer the whole story, and guessing which
// of the two emptied the list would be a worse answer than the general one.
function emptyTodayMessage(day, benchmarkMatches = 0) {
  // A search that found the benchmark but no daily coverage of it is not a
  // filter that is set too narrow, and telling the reader to widen it sends
  // them adjusting controls that cannot produce the rows they want. Name what
  // was found instead, and point at it (issue #245).
  //
  // Only when the query is the sole filter. With a second one active, a
  // matching observation may exist and have been removed by that filter, so
  // "nothing was collected" would be a claim this function cannot check. And
  // the two date modes need different sentences: "on this date" is false in
  // All dates mode, where the search already covered the whole archive.
  const queryOnly =
    state.q.trim() &&
    !state.kind &&
    !state.category &&
    !state.source &&
    !state.organization &&
    !state.event;
  if (queryOnly && benchmarkMatches === "pending") {
    return t("Still checking the benchmark registry\u2026");
  }
  if (queryOnly && benchmarkMatches) {
    return t(
      state.todayDate === "all"
        ? "No collected observation mentions \u201c{q}\u201d, but it is in the benchmark registry. The matches are listed above."
        : "Nothing was collected about \u201c{q}\u201d on this date, but it is in the benchmark registry. The matches are listed above.",
    ).replace("{q}", state.q.trim());
  }
  const others = [state.q.trim(), state.kind, state.category, state.event].filter(Boolean);
  if (!state.source || others.length) {
    return t("No observations match these filters. Clear one or more filters to widen the view.");
  }
  const wanted = state.source.trim().toLowerCase();
  const gap = zeroItemSources(day).find((entry) => entry.name.toLowerCase() === wanted);
  if (!gap) {
    return t("No observations match these filters. Clear one or more filters to widen the view.");
  }
  // The three states from issue #260, said in the second person because the
  // reader is standing in front of the empty list asking about this source.
  const reason = {
    unreachable: t("{source} could not be reached on this day, so nothing was collected from it."),
    empty: t("{source} was checked on this day and had nothing new. The filter is working."),
    unranked: t(
      "{source} returned something on this day, but none of it scored high enough to be listed.",
    ),
  }[gap.state];
  return `${reason.replace("{source}", state.source)} ${t("Try another date, or clear the filter.")}`;
}

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
    Explore: "探索",
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
    "Which of that movement is corroborated by more than one data source?":
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
    Filters: "筛选",
    "More filters": "更多筛选",
    "Date:": "日期:",
    "Search benchmarks…": "搜索基准…",
    "Refresh data": "刷新数据",
    "Today's radar": "今日雷达",
    "Matching observations": "匹配结果",
    Sources: "来源",
    "All-time totals": "全部统计",
    All: "全部",
    // --- Today view row and metrics -----------------------------------------
    "Updated": "更新于",
    "Released": "发布于",
    "Just now": "刚刚",
    "{n}m ago": "{n} 分钟前",
    "{n}h ago": "{n} 小时前",
    "{n}d ago": "{n} 天前",
    "yesterday": "昨天",
    "{loaded} of {total} results loaded · scroll for more":
      "已加载 {loaded}/{total} 条结果 · 下滑加载更多",
    "All {total} results loaded": "已加载全部 {total} 条结果",
    "normal": "正常",
    "Sort: Priority ↓": "排序:优先度 ↓",
    "Sort: Date, then Priority ↓": "排序:日期,再按优先度 ↓",
    "Sort: Date ↓": "排序:日期 ↓",
    // --- Leaderboard ---------------------------------------------------------
    "Which benchmarks do model cards report?": "模型卡报告了哪些基准?",
    "What does this source record?": "这个来源记录了什么？",
    "Registry overview": "总览",
    "What the two layers say": "两层信息说了什么",
    "Stated findings": "明确结论",
    "Scores over time": "分数随时间变化",
    "Benchmark reported scores over time": "基准报告分数随时间的变化",
    "All tracked benchmarks": "所有追踪的基准",
    "Search every benchmark": "搜索全部基准",
    "Most reported benchmarks in model cards": "模型卡中报告最多的benchmark",
    Rank: "排名",
    Benchmark: "基准",
    "leaderboard.column.model_cards": "模型卡数量",
    "Jump to a benchmark": "跳转到某个基准",
    "One score, copied from the report that published it": "一个分数，照抄自发布它的报告",
    "Show all {n} benchmarks": "显示全部 {n} 个基准",
    "Show top {n}": "只显示前 {n} 个",
    "A report counts once per test, even if it lists that test several times. Some reports publish their results as a picture rather than text, and we read those with software that can misread a digit, so the list at the bottom of this page links every count back to the report it came from.":
      "一份报告对同一项测试只计一次，即使它列出了多次。有些报告以图片而非文字发布结果，我们用软件读取，可能会看错数字，因此本页底部的清单把每个计数链接回它的来源报告。",
    model: "个模型",
    models: "个模型",
    "No model card in this registry reports a benchmark yet.": "此登记册中还没有任何模型卡报告基准。",
    "Search benchmarks, tasks, domains…": "搜索基准、任务、领域…",
    "{n} benchmarks": "{n} 个基准",
    "Curated registry": "精选登记册",
    "No benchmark in this registry has a score read from a document yet.": "此登记册中还没有任何基准有从文档中读到的分数。",
    "What would it take to chart best score against lowest cost?":
      "要把最高分数和最低成本画在一张图上,还差什么?",
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
    "How to read this chart": "如何解读这张图",
    "frontier.explainer.sub":
      "每个能从引文文档中逐字读到的数值,按该文档的发布日期放置(而非任何评测日期),只在测试变体与运行条件完全一致时才相连。末端趋于平直通常意味着没有更新的数字可读,因此缺口被标出而不是用线穿过。一条曲线是否已经饱和,由你来判读,本面板不会给出饱和分数。",
    "leaderboard.filters.note":
      "每张模型卡对同一基准只计一次。一张在四个配置中报告 AIME 的卡,与只报告一次的卡计数相同,因此冗长的附录不能压过不同的供应商。机构可以打破平局:六个供应商报告同一计数是共同标准,只有一个供应商报告则是自家风格。",
    "leaderboard.ledger.note":
      "这是计算排名的精选来源列表。展开任意一张卡可看到其报告的全部基准,并按源文档的分组方式分组,以便我们的数据能逐行对照原文核查。",
    "Benchmarks with this name": "同名的基准",
    "Showing {shown} of {total} registry records matching \u201c{q}\u201d. Narrow the search to see the rest.":
      "显示与\u201c{q}\u201d匹配的 {total} 条登记册记录中的 {shown} 条。缩小搜索范围可查看其余记录。",
    "Still checking the benchmark registry\u2026": "正在查询基准登记册\u2026",
    "The crawled benchmark catalog could not be loaded, so these results may be incomplete.":
      "无法加载抓取的基准目录,因此这些结果可能不完整。",
    "The benchmark registry could not be loaded, so this search covered collected observations only.":
      "无法加载基准登记册,因此本次搜索只覆盖了已收集的内容。",
    "No collected observation mentions \u201c{q}\u201d, but it is in the benchmark registry. The matches are listed above.":
      "收集到的内容中没有提到\u201c{q}\u201d,但它在基准登记册中。匹配结果列在上方。",
    "Registry records matching \u201c{q}\u201d. These are benchmarks the radar tracks, not things collected on a date.":
      "登记册中与\u201c{q}\u201d匹配的记录。这些是雷达追踪的基准,而不是某一天收集到的内容。",
    "Nothing was collected about \u201c{q}\u201d on this date, but it is in the benchmark registry. The matches are listed above.":
      "这一天没有收集到关于\u201c{q}\u201d的内容,但它在基准登记册中。匹配结果列在上方。",
    "pareto.readiness.summary": "要把最高分数和最低成本画在一张图上,还差什么?",
    "pareto.readiness.note1":
      "两个分数只有在各自都记录了以下信息时才能比较:测的是哪个版本、取的是哪一部分、数值高好还是低好、用的哪个模型、由什么软件运行、给了多少思考时间、花了多少钱、用了多长时间、何时发布,以及这个数字出自哪里。其中测试本身和运行方式必须一致,而模型、成本、耗时和日期可以不同,因为它们正是图表要对比的内容。本站记录的是某张模型卡提到了某个基准,还没有记录这些测量值。",
    "pareto.readiness.note2":
      "一旦有了这些数据,这张图就可以把成本或速度与分数对照,并只把那些在两方面都无人能同时超越的结果连成一条线。再加一个日期滑块,就能看出这条线随时间如何移动。",
    "map.heading.note":
      "看看哪些内容最常出现,以及它们来自哪里。想查看某个具体条目时,再打开连接视图。",
    "map.explorer.note": "这里有很多点。选择一个点即可查看它与什么相连,或打开匹配结果。",
    "map.detail.note":
      "选择主题、来源或机构,即可在今日页面只看相关结果。选择条目即可查看它每次出现的记录。",
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
    "score read from a document": "个从文档读到的分数",
    "scores read from a document": "个从文档读到的分数",
    organization: "个机构",
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
    evidence: "条证据",
    attention: "关注",
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
    "Two snapshots are available, but they covered different data sources or a different report limit, so the change between them is not comparable.":
      "已有两个快照,但两者覆盖的数据源或报告上限不同,因此它们之间的变化不可比较。",
    "Compared with": "与",
    "surfaced evidence is": "相比,已出现的证据",
    "active attention is": ",活跃关注度",
    "Biggest domain moves": "最大的领域变化",
    "covered different data sources or used a different report limit than": "覆盖的数据源或报告上限不同于",
    "so the two scans": "因此这两次扫描",
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
    "Recent activity": "最近动态",
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
    // Sources at zero on a day (issue #260). The sentence templates carry
    // {sources} and {date} so zh can order them its own way.
    "On {date} these sources found nothing at all: {sources}.":
      "{date},这些来源什么都没有找到:{sources}。",
    "On {date} these sources could not be reached: {sources}.":
      "{date},这些来源无法访问:{sources}。",
    "On {date} these sources returned something, but none of it scored high enough to be listed: {sources}.":
      "{date},这些来源有返回内容,但都没有达到上榜所需的分数:{sources}。",
    "A source that stays at zero for several days is usually broken, not quiet.":
      "一个来源连续几天都是零,通常说明它出了问题,而不是没有新内容。",
    "This source was checked and found nothing at all on this day.":
      "这个来源当天检查过了,但什么都没有找到。",
    "This source could not be reached on this day.": "这个来源当天无法访问。",
    "This source returned something, but none of it scored high enough to be listed.":
      "这个来源有返回内容,但都没有达到上榜所需的分数。",
    // --- Map ----------------------------------------------------------------
    "Big picture": "整体概览",
    "What we found": "我们发现了什么",
    "Want more detail?": "想看更多细节?",
    "See how everything connects": "看看所有内容如何相连",
    "view.map.note":
      "总览概括了整个语料库。关系画布包含每一个工件以及与其相连的机构、来源和主题;选择节点即可将其带入今日筛选。",
    "Pick a dot": "选择一个点",
    "See what it connects to": "看看它连接了什么",
    "view.map.detail.note": "主题、来源和机构节点会设置对应的今日筛选。工件节点会设置日期和标题搜索。",
    // --- Frontier / workbench -------------------------------------------------
    "Priority & evidence": "优先度与证据",
    "View score track ↑": "查看分数轨道 ↑",
    "Show on the chart ↑": "在图表中显示 ↑",
    "Model cards": "模型卡",
    "Best on record": "历史最佳",
    "Only charted score": "唯一入图分数",
    "Headroom left": "剩余空间",
    "Readable values": "可读数值",
    "Supports: ": "支持: ",
    "Does not support: ": "不支持: ",
    "Score read from a document": "从文档读到的分数",
    Model: "模型",
    Adoption: "采用",
    "Open source record ↗": "打开来源记录 ↗",
    "Open source document ↗": "打开来源文档 ↗",
    "Read from": "读取自",
    "Cited by": "被引用",
    "Test variant": "测试变体",
    "Run conditions": "运行条件",
    "new benchmark": "新基准",
    "Not yet reported": "尚未报告",
    "not yet reported in these cards": "这些模型卡中尚未报告",
    "Reported by": "报告机构",
    "Reported score": "报告的分数",
    "Score as reported": "报告的分数",
    "self reported": "自行报告",
    "model release date": "模型发布日期",
    "Best reported score:": "报告的最高分:",
    "{n} row(s) have no release date, so they carry no position on this axis and are not drawn.":
      "有 {n} 行没有发布日期,因此在此坐标轴上没有位置,未被绘制。",
    "{count} scores reported to {source}, placed at each model's release date, which is the only date recorded and is not when the score was measured. Highest {best} by {model}, lowest {low}.":
      "向 {source} 报告的 {count} 个分数,按各模型的发布日期排布;这是唯一记录在案的日期,并非分数的测量时间。最高 {best},来自 {model};最低 {low}。",
    "Date (model release)": "日期（模型发布）",
    "Benchmark home ↗": "基准主页 ↗",
    "Top cards": "头部模型卡",
    "Disclosure": "披露",
    "No benchmarks match these filters. Clear one or more filters to widen the view.":
      "没有符合条件的基准。清除一个或多个筛选条件以扩大范围。",
    "source documents": "来源文档",
    "Each document counts once per benchmark.": "每份文档对每个基准只计一次。",
    "Each document counts once per benchmark. Plus {count} crawled benchmark records from {sources}.":
      "每份文档对每个基准只计一次。另有来自 {sources} 的 {count} 条爬取的基准记录。",
    "{count} more in the crawled catalog, {withScores} with a reported score.":
      "爬取目录中还有 {count} 个，其中 {withScores} 个有报告的分数。",
    organizations: "机构",
    "The denominator for reporting breadth.": "衡量报告广度时的分母。",
    "Benchmarks tracked": "追踪的基准数",
    "Benchmarks reported at least once": "被报告至少一次的基准数",
    "The subset a ranked row can speak to.": "排名行所能覆盖的子集。",
    "New benchmarks": "新基准",
    "Benchmarks this document reports": "此文档报告的基准",
    "Last curated on": "最后整理于",
    "date unknown": "日期未知",
    "shown": "显示",
    "tracked": "追踪",
    "of": "共",
    // --- External catalog detail (issue #316) --------------------------------
    // The crawled benchmark detail panel (identity / openness / size) shipped
    // its section headings, field labels and "not established" placeholders in
    // English under zh, so only the shared "Released" line came through. These
    // cover the rest of that panel; the benchmark's own description text stays
    // as authored because it is source data, not chrome.
    Identity: "基本信息",
    "description not established": "简介尚未确定",
    Publisher: "发布方",
    "publisher not established": "发布方尚未确定",
    "release date not established": "发布日期尚未确定",
    Modality: "模态",
    "modality not established": "模态尚未确定",
    "No paper, repository, dataset or site link established.":
      "尚未确定论文、代码仓库、数据集或站点链接。",
    "Identity below is inherited from the {donor} card for a reviewed equivalent benchmark; scores are unchanged.":
      "以下基本信息继承自 {donor} 中经人工核对为同一基准的记录；分数不受影响。",
    Openness: "开放性",
    "openness not established": "开放性尚未确定",
    open: "开放",
    restricted: "受限",
    "Code licence": "代码许可证",
    "Data licence": "数据许可证",
    "not established": "尚未确定",
    "No openness evidence recorded.": "未记录开放性证据。",
    Size: "规模",
    "size not established": "规模尚未确定",
    "counts the": "统计的是",
    "what it counts is unclear": "统计对象不明",
    "evidence ↗": "证据 ↗",
    // Publisher roles and artifact kinds are label maps keyed by a raw enum, so
    // an unmapped role/kind still falls back to its raw value rather than blank.
    "published the hub card": "发布了 Hub 卡片",
    "organization behind the paper": "论文背后的机构",
    maintainer: "维护者",
    Paper: "论文",
    "Code repository": "代码仓库",
    Dataset: "数据集",
    "Project site": "项目站点",
    // --- Contact --------------------------------------------------------------
    "Benchmark Radar": "Benchmark 雷达日报",
    "Get in touch": "联系我",
    Email: "邮件",
    WeChat: "微信",
    Discord: "Discord",
    "Want the full dataset? No crawler needed: star the repository, then get in touch and I will share a one-click export.":
      "想要完整数据集？不需要爬虫：先给仓库点个 Star，然后联系我，我会告诉你怎么一键导出。",
    "Star the repository": "给仓库点 Star",
    "Want the dataset? No crawler needed: star the repository, then":
      "想要数据集？不需要爬虫：先给仓库点 Star，然后",
    "contact the author": "联系作者",
    "for a one-click export.": "即可一键导出。",
    // --- Remaining dynamic strings ------------------------------------------
    " on a": " 以",
    " scored records on": " 项已评分记录,以",
    " · current": " · 现行",
    " · superseded": " · 已取代",
    "(zoom)": "(缩放)",
    "(zoomed)": "(已缩放)",
    "A wrong row in the adoption ranking is a real bug. So is a data source that stopped returning anything, or a benchmark you expected the radar to see.":
      "采用排行中的一行错误就是真实的 bug;某个数据源停止采集,或者一个你期待雷达发现的基准没有出现,同样是 bug。",
    "All domains": "所有领域",
    "All organizations": "所有机构",
    "Any release date": "任意发布日期",
    "Artifact nodes connected to topics, organizations, and discovery sources":
      "连接到主题、机构与发现来源的工件节点",
    Artifacts: "工件",
    Authors: "作者",
    "Click the marker to pin these details": "点击标记以固定这些详情",
    "Click to pin record details": "点击固定记录详情",
    Comments: "评论",
    "Discovery sources": "发现来源",
    "Every benchmark this document puts in front of readers, counted once each. These are mentions, not scores: the source records the configuration, and this registry deliberately does not.":
      "此文档呈现给读者的每个基准,各计一次。这是提及次数,不是分数:来源记录了配置,而这个登记册刻意不记录。",
    "Every record matching at least one taxonomy category is retained. A score of":
      "只要匹配至少一个分类类别的记录都会被保留。达到分数",
    "How priority is scored": "优先度如何评分",
    "Most represented organizations": "出现最多的机构",
    "No benchmark is reported by a curated card yet.": "目前还没有精选模型卡报告任何基准。",
    "No description published at the source.": "来源没有发布描述。",
    "No discovery sources yet.": "还没有发现来源。",
    "No further description beyond the preview above.": "除了上面的预览,没有更多描述。",
    "No organizations identified yet.": "还没有识别出机构。",
    "No source documents in the registry yet.": "登记册中还没有来源文档。",
    "No topics assigned yet.": "还没有分配主题。",
    "Not a verbatim benchmark item. This description paraphrases the official source; open it for the exact tasks and scoring rules.":
      "不是逐字的基准条目。此描述转述自官方来源;请打开它以查看确切的题目与评分规则。",
    "Not a verbatim benchmark item. This is an illustrative format based on the recorded domain; use the official source for the exact tasks and scoring rules.":
      "不是逐字的基准条目。这是根据记录领域生成的示例格式;请使用官方来源查看确切的题目与评分规则。",
    "No score for this benchmark could be read verbatim from the cited documents, so there is no track to draw. An absent value is not a zero and not a plateau.":
      "无法从引文文档中逐字读到该基准的分数,因此没有可绘制的轨道。缺失的数值既不是零,也不是平台期。",
    "No model card in this registry reports this benchmark yet, so there is no score to draw. That zero is a reading, not a gap in the collection.":
      "本登记册中还没有任何模型卡报告该基准,因此没有可绘制的分数。这个零是一个读数,而不是收集上的缺口。",
    "No score for this benchmark could be read verbatim from the cited documents. An absent value is not a zero and not a plateau.":
      "无法从引文文档中逐字读到该基准的分数。缺失的数值既不是零,也不是平台期。",
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
    Released: "发布于",
    Relevance: "相关性",
    "Representative task shape": "代表性任务形态",
    "Rubric v": "评分标准 v",
    Score: "分数",
    Scored: "已评分",
    "Scores from the": "分数来自",
    "Scoring rubric v": "评分标准 v",
    "Show the first 18 benchmarks": "显示前 18 个基准",
    "Showing all": "显示全部",
    Submissions: "提交数",
    "The current rubric is v": "当前评分标准为 v",
    "This historical scan used": "本次历史扫描采用了",
    "This record scores": "该记录得分",
    "This record was scored by rubric v": "该记录由评分标准 v",
    "Topic coverage": "主题覆盖",
    Topics: "主题",
    "What this score does not claim": "这个分数的含义之外",
    "reported scores over time": "报告分数随时间的变化",
    "charted score": "个入图分数",
    "charted scores": "个入图分数",
    after: "之后",
    "an inclusion cutoff. Records below it were not retained.": "为纳入门槛。低于它的记录未被保留。",
    as: "作为",
    "author nodes summarized above and omitted from the canvas": "个作者节点已在上面汇总,并从画布中省略",
    "best on record": "历史最佳",
    by: "由",
    "cited by": "被引用",
    contributes: "贡献",
    "here are third parties": "有第三方",
    "here is a third party": "有第三方",
    listed: "已列出",
    "no score read from a document in this window": "此窗口中没有从文档中读到的分数",
    // Issue #254: why the Today list is empty, when a source filter emptied it.
    "No observations match these filters. Clear one or more filters to widen the view.":
      "没有符合这些筛选条件的结果。请清除一个或多个筛选条件以扩大范围。",
    "{source} could not be reached on this day, so nothing was collected from it.":
      "{source} 在这一天无法访问，因此未从中收集到任何内容。",
    "{source} was checked on this day and had nothing new. The filter is working.":
      "{source} 在这一天已检查过，没有新内容。筛选功能正常。",
    "{source} returned something on this day, but none of it scored high enough to be listed.":
      "{source} 在这一天有返回内容，但都未达到列入所需的分数。",
    "Try another date, or clear the filter.": "请尝试其他日期，或清除筛选条件。",
    // Stale-run banner: plain words a first-time reader can act on.
    "Last updated {date}, {hours} hours ago. The automatic update has not succeeded since.":
      "数据上次更新于 {date}，距今 {hours} 小时。那之后的自动更新一直没有成功。",
    "Some sources failed to answer on {date}: {gaps}.": "{date} 有几个来源没有响应：{gaps}。",
    "What broke?": "哪里出了问题？",
    "one value read verbatim from a cited document": "一个从引文文档中逐字读到的数值",
    "not yet reported": "尚未报告",
    "points to zero, the floor of this metric": "指向零,该指标的底线",
    "run conditions": "运行条件",
    "document publication date": "文档发布日期",
    "quoting another vendor's figure, marked with a ring on the chart":
      "引用另一家供应商的数据,图表中以圆环标出",
    release: "发布",
    "release date unrecorded": "未记录发布日期",
    released: "发布于",
    "scale. Every number below is read from the same definition the pipeline applies.":
      "的标尺。下面每个数字都按流程应用的同一套定义读取。",
    to: "到",
    "to the total": "到总分",
    "two versions are not directly comparable, and past records are not rescored.":
      "两个版本不可直接比较,过去的记录不会重新评分。",
    weight: "权重",
    "Also connected to": "还连接到",
    "At a glance": "一眼看懂",
    "Change over": "过去",
    "Days it appeared": "出现天数",
    "First found": "首次发现",
    Items: "条目",
    "Items connected to topics, organizations, and sources": "与主题、机构和来源相连的条目",
    "Last found": "最近发现",
    "Latest priority score": "最新优先级分数",
    "No organizations yet.": "还没有机构。",
    "No sources yet.": "还没有来源。",
    "No topics yet.": "还没有主题。",
    "Nothing found yet.": "还没有发现任何内容。",
    Selected: "已选择",
    "Times found": "发现次数",
    "What it is about": "内容主题",
    "Where we found it": "发现来源",
    "Who appears most": "谁出现得最多",
    item: "条目",
    items: "条目",
    "not enough earlier data": "没有足够的早期数据",
    "AI agents": "AI 智能体",
    benchmarks: "基准",
    datasets: "数据集",
    evaluations: "评测",
    "times found": "次发现",
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
  benchmarkIndex: null,
  // Null until the first fetch attempt resolves either way. A slug permalink
  // can only be checked against the index once the index has actually
  // arrived, so "not yet loaded" and "failed to load" must not look alike.
  benchmarkIndexLoaded: false,
  benchmarkQuery: "",
  leaderboardShowAll: false,
  leaderboardTopExpanded: false,
  todayResultsKey: "",
  todayResultsLimit: TODAY_PAGE_SIZE,
  todayRenderedCount: 0,
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

// A round (i) toggle for one sentence of provenance/method text that a reader
// needs once, not on every visit to an already-familiar block. Collapsed by
// default; the marker itself carries the affordance (no plain "How to read
// this" text link), so it stays visible and consistent wherever it appears --
// the score-evidence and frontier-explainer disclosures share its "expand"
// visual treatment even though they use a text summary instead of this icon.
function infoDisclosure(text) {
  return element("details", { className: "info-disclosure" }, [
    element("summary", {
      className: "info-disclosure-toggle",
      attrs: { "aria-label": t("What does this source record?") },
      text: "i",
    }),
    element("p", { className: "info-disclosure-body", text }),
  ]);
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

// `push` adds a history entry; `replace` overwrites the current one.
//
// Every call used to replace, so no navigation was ever backable: a reader who
// searched, opened a benchmark and pressed Back left the site entirely, because
// the search URL had been overwritten rather than kept (issue #286).
//
// Pushing everything is the wrong fix. The filter boxes call this on a debounce
// as the reader types, so `q=m`, `q=mm`, `q=mml`, `q=mmlu` would each become an
// entry and Back would walk backwards through their own typing one keystroke at
// a time. The split is by what the reader did:
//
//   push    a discrete navigation they chose -- changing view, selecting a
//           benchmark, opening an entity
//   replace continuous refinement of the view they are already on -- typing in
//           a filter, moving the date, toggling a facet, closing a dialog
function writeUrl(mode = "replace") {
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
  const url = `${window.location.pathname}${query ? `?${query}` : ""}${hash ? `#${hash}` : ""}`;
  // Pushing a URL identical to the current one would make Back a no-op that
  // looks broken: the reader presses it, the address bar does not change, and
  // they press it again. Re-selecting the benchmark already shown is the
  // common way to hit this.
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (mode === "push" && url !== current) {
    window.history.pushState(null, "", url);
    return;
  }
  window.history.replaceState(null, "", url);
}

// A pushed entry changes the URL on Back without re-rendering anything, so the
// page would silently disagree with its own address bar. This is what makes the
// pushes above safe: the restored URL is read back into state and the view it
// describes is drawn (issue #286).
function onPopState() {
  // Before the payload lands, state is not yet drawable. Read the URL anyway:
  // initialize() renders from state once the fetch settles, and skipping the
  // read here would leave it rendering whatever the reader navigated away
  // from while the address bar showed the restored entry.
  readUrl();
  if (!state.data) return;
  // A leaderboard permalink on a build with no curated registry has nothing to
  // show, same fallback initialize() applies. Without it, Back into such an
  // entry opens an empty section behind a hidden nav button.
  if (state.view === "leaderboard" && !state.data.model_card_leaderboard) {
    state.view = "today";
  }
  setView(state.view, false);
  // The renderers read their own controls back from state (the date picker at
  // renderToday, the leaderboard search at renderLeaderboardFilters), so this
  // restores the form values as well as the content.
  rerenderCurrentView();
  // The rubric lives in the hash rather than the query, so it is restored
  // separately: Back out of an open dialog should close it.
  const dialog = byId("rubric-dialog");
  if (state.rubric && state.data.rubrics?.[state.rubric]) {
    if (!dialog?.open) openRubric(null, state.rubric);
  } else if (dialog?.open) {
    dialog.close();
  }
}

// Issue #236. Crawlers see one document; these four states are still four
// different pages a reader can land on and link to, so each one restates its
// own title, description, and canonical URL when it becomes active. The
// canonicals carry only the view parameter: filter permutations (q, date,
// lq, lfrontier, ...) consolidate into the clean view URL instead of
// fragmenting ranking signals across every state of the same page. These
// strings are English on purpose: they describe the site to a search engine,
// while the visible interface translates through data-i18n.
const VIEW_SEO = {
  today: {
    title: "Benchmark Radar — today's new AI benchmarks",
    description:
      "A daily evidence-first map of new AI benchmarks, evaluations, and datasets, collected every day from arXiv, GitHub, Hugging Face, OpenReview, Semantic Scholar, Hacker News, and first-party lab feeds.",
    query: "",
  },
  leaderboard: {
    title: "Most reported AI benchmarks in frontier model cards | Benchmark Radar",
    description:
      "Which benchmarks frontier labs actually report: a live Model Card Adoption Rank computed from curated model cards and system cards, plus reported score progression over time.",
    query: "view=leaderboard",
  },
  trends: {
    title: "AI benchmark discovery trends over time | Benchmark Radar",
    description:
      "Daily volume of new AI benchmark evidence by category, source, and event, with a ledger of every collection day in the corpus.",
    query: "view=trends",
  },
  map: {
    title: "Explore connections across AI benchmarks | Benchmark Radar",
    description:
      "See how benchmarks, datasets, evaluations, sources, and organizations connect across the Benchmark Radar corpus, and jump from any topic into the filtered daily list.",
    query: "view=map",
  },
};

function applyViewSeo(view) {
  const seo = VIEW_SEO[view] || VIEW_SEO.today;
  document.title = seo.title;
  const description = document.querySelector('meta[name="description"]');
  if (description) description.setAttribute("content", seo.description);
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    const url = new URL(window.location.pathname, window.location.origin);
    if (seo.query) url.search = seo.query;
    else url.search = "";
    canonical.setAttribute("href", url.href);
  }
}

// `update` false is for restoring a view that is already in the URL (boot and
// popstate), where writing history again would either duplicate the entry or
// fight the entry being restored.
function setView(view, update = true, mode = "push") {
  applyViewSeo(view);
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
  if (update) writeUrl(mode);
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
  const raw = Number(item.total_score || 0);
  const max = Number(scoreMax(item));
  // Issue #248: a 100-point score rounds to an integer (68, not 68.46), but
  // legacy 0-4 records carry meaningful hundredths (3.01, 2.94), so they keep
  // two decimals. The track always uses the raw value, so it never
  // misrepresents the ratio.
  const precision = max > 10 ? 0 : 2;
  const score = raw.toFixed(precision);
  const maxDisplay = precision === 0 ? String(Math.round(max)) : String(max);
  const width = Math.max(0, Math.min(100, (raw / max) * 100));
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
      "aria-label": `${t("Priority score")} ${score} ${t("of")} ${maxDisplay}. ${t("How is this scored?")}`,
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
    element("div", { className: "score-value" }, [
      element("strong", { text: score }),
      element("span", { text: `/ ${maxDisplay}` }),
    ]),
    track,
    explain,
  ]);
}

function titleCase(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

// The timestamp that best describes when the observed event happened. The
// updated_at field only exists for update events, so fall back through the
// publish and discovery times rather than dropping the time entirely.
function eventTimestamp(item) {
  if (item.updated_at) return item.updated_at;
  if (item.published_at) return item.published_at;
  return item.discovered_at || "";
}

// Time is one of the highest-signal attributes on a Today page, so rows show
// how long ago an event happened instead of a bare "UPDATED" (issue #248).
// A YYYY-MM-DD as a UTC timestamp, or NaN when it is absent or unparseable.
// Pinned to T00:00:00Z for the same reason scoreTrackChart's axis is: a bare
// date string is parsed in local time by some engines, which slides a point
// across a day boundary depending on where the reader is sitting.
function dateValue(date) {
  if (!date) return Number.NaN;
  return new Date(`${String(date).slice(0, 10)}T00:00:00Z`).getTime();
}

function relativeTime(iso) {
  if (!iso) return "";
  const time = new Date(iso).getTime();
  if (!Number.isFinite(time)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - time) / 60000));
  if (minutes < 1) return t("Just now");
  if (minutes < 60) return t("{n}m ago", { n: minutes });
  const hours = Math.round(minutes / 60);
  if (hours < 24) return t("{n}h ago", { n: hours });
  const days = Math.round(hours / 24);
  if (days <= 1) return t("yesterday");
  if (days < 7) return t("{n}d ago", { n: days });
  return formatDate(iso, { dateStyle: "medium" });
}

function eventVerb(item) {
  const kind = String(item.event_kind || "");
  const verb = kind === "updated" ? t("Updated") : kind === "released" ? t("Released") : titleCase(kind);
  const time = relativeTime(eventTimestamp(item));
  return time ? `${verb} ${time}` : verb;
}

// The collapsed row carries a plain-text provenance line instead of the six
// uppercase chips: source and event in normal typography, at most two
// categories, everything else under expansion (issue #248).
function recordMeta(item) {
  const categories = item.categories || [];
  const visible = categories.slice(0, 2).map(titleCase);
  const extra = categories.length - visible.length;
  return element("div", { className: "record-meta" }, [
    element("span", { className: "meta-source", text: item.source }),
    element("span", {
      className: "meta-event",
      text: eventVerb(item),
      attrs: {
        title: eventTimestamp(item)
          ? `${formatDate(eventTimestamp(item), { dateStyle: "medium", timeStyle: "short" })} UTC`
          : "",
      },
    }),
    ...(visible.length
      ? visible.map((category) => element("span", { className: "meta-category", text: category }))
      : [element("span", { className: "meta-category", text: t("uncategorized") })]),
    ...(extra > 0
      ? [element("span", { className: "meta-more", text: `+${extra}` })]
      : []),
    ...(item.watchlist
      ? [element("span", { className: "meta-watchlist", text: `★ ${item.watchlist}` })]
      : []),
  ]);
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

// The search box reads the daily feed: titles, summaries and source names of
// what the crawl collected on a date. The benchmark registry is a different
// dataset, and until issue #245 nothing joined them, so a reader searching for
// a benchmark by name got one of two wrong answers. "researchclawbench"
// returned "No observations match these filters", advice that cannot work
// because clearing a filter does not add a dataset. "terminal-bench" was worse:
// it returned an arXiv paper on uncertainty propagation, which ranked because
// the string "Terminal-Bench-2" appears in its abstract. Both benchmarks are in
// the registry with scores, and both were unreachable from the box that looks
// like the way to find them.
//
// So the query runs against the registry too, and its matches are named as
// benchmarks rather than mixed into a list sorted by daily priority. A prose
// mention inside an abstract and a registry record are different kinds of
// answer, and collapsing them is what produced the arXiv result.
let benchmarkIndexRerenderQueued = false;

function renderTodayBenchmarks() {
  const section = byId("today-benchmarks");
  if (!section) return 0;
  const query = state.q.trim();
  if (!query) {
    section.hidden = true;
    replaceChildren(byId("today-benchmarks-results"), []);
    return 0;
  }
  // Only fetched when someone actually searches, so the dashboard's first
  // paint never waits on a catalog most visits do not open.
  //
  // Attached once, not once per keystroke. loadBenchmarkIndex() caches its
  // promise, so on a slow connection every debounced keystroke would hang
  // another handler on the same fetch and they would all fire together when it
  // landed, each one re-filtering the observations and rebuilding the list.
  if (!state.benchmarkIndexLoaded && !benchmarkIndexRerenderQueued) {
    benchmarkIndexRerenderQueued = true;
    loadBenchmarkIndex().then((records) => {
      state.benchmarkIndex = records;
      state.benchmarkIndexLoaded = true;
      if (state.q.trim()) renderToday({ resultsOnly: true });
    });
  }
  const board = state.data?.model_card_leaderboard;
  const curated = searchCuratedEntries(board, query, { includeUnscored: true });
  const external = searchBenchmarkIndex(state.benchmarkIndex || [], query);
  // A row is only worth clicking if the panel it leads to can draw. That needs
  // more than a non-empty board: renderAdoptionFrontier() gives up unless some
  // adopted entry has a readable score record and a default entry resolves, so
  // a registry of card mentions with no scores yet renders the same empty panel
  // as no registry at all. A button that goes nowhere is worse than no button,
  // so those rows render as plain records instead.
  const navigate = Boolean(
    (board?.entries || []).some(
      (item) => item.card_count > 0 && scoreRecord(item.benchmark_id),
    ) && frontierDefaultEntry(board),
  );
  // loadBenchmarkIndex() resolves null only on failure. That is a different
  // answer from a search that matched nothing, and it stays true whether or
  // not the curated layer had a hit: reporting it only on an empty result
  // would present half a registry search as a whole one.
  const indexFailed = state.benchmarkIndexLoaded && state.benchmarkIndex === null;
  // Sliced before the rows are built, not after. "bench" matches 355 of the
  // 1,148 crawled records, and building every one of them into a DOM subtree
  // with a listener to then discard all but 50 is work done on each keystroke.
  const curatedShown = curated.slice(0, BENCHMARK_SEARCH_LIMIT);
  const externalShown = external.slice(
    0,
    Math.max(0, BENCHMARK_SEARCH_LIMIT - curatedShown.length),
  );
  const rows = [
    ...curatedShown.map((entry) => curatedResultRow(entry, { navigate, inert: !navigate })),
    ...externalShown.map((record) => benchmarkResultRow(record, { navigate, inert: !navigate })),
  ];
  // Still on the wire. Zero matches is not yet a fact, so the empty list must
  // not print the sentence this whole change exists to stop printing: on a
  // cold search for a crawled-only benchmark the catalog has not arrived, and
  // a slow request would leave "clear one or more filters" on screen for as
  // long as it takes. Reported as pending until it settles.
  const indexPending = !state.benchmarkIndexLoaded;
  if (!rows.length && !indexFailed && !indexPending) {
    section.hidden = true;
    replaceChildren(byId("today-benchmarks-results"), []);
    return 0;
  }
  section.hidden = false;
  const total = curated.length + external.length;
  // Saying "matching X" over a truncated list invites the reader to conclude a
  // benchmark that is present but past row 50 does not exist, which is the
  // reading this whole change is trying to prevent. Show the arithmetic.
  const truncated = total > rows.length;
  const note = rows.length
    ? truncated
      ? t(
          "Showing {shown} of {total} registry records matching \u201c{q}\u201d. Narrow the search to see the rest.",
        )
          .replace("{shown}", rows.length)
          .replace("{total}", total)
          .replace("{q}", query)
      : t(
          "Registry records matching \u201c{q}\u201d. These are benchmarks the radar tracks, not things collected on a date.",
        ).replace("{q}", query)
    : "";
  const warning = indexFailed
    ? t("The crawled benchmark catalog could not be loaded, so these results may be incomplete.")
    : indexPending
      ? t("Still checking the benchmark registry\u2026")
      : "";
  byId("today-benchmarks-note").textContent = [note, warning].filter(Boolean).join(" ");
  replaceChildren(byId("today-benchmarks-results"), rows);
  return !total && indexPending ? "pending" : total;
}

// Loads the next page when the sentinel below the list scrolls into view
// (issue #311). One observer for the session: the sentinel never leaves the
// DOM, so a render only re-teaches it how many results remain. A load bumps
// the bound and re-renders, which re-fires this callback while the sentinel
// is still on screen -- that is what keeps filling a short first page until
// something scrollable exists, without ever carding the whole day up front.
let todaySentinelObserver = null;

function todayPageLimit() {
  // Without IntersectionObserver there is no scroll trigger, and the manual
  // button is gone; capping the list there would strand every row past the
  // first page behind a control that does not exist. The bound is the scroll
  // loading mechanism, so an engine without one gets the uncapped list.
  if (typeof IntersectionObserver === "undefined") return Infinity;
  return state.todayResultsLimit;
}

function watchTodaySentinel(remainingResults) {
  const sentinel = byId("today-sentinel");
  if (!sentinel) return;
  if (typeof IntersectionObserver === "undefined") return;
  if (!todaySentinelObserver) {
    todaySentinelObserver = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      const total = filteredObservations().length;
      if (state.todayResultsLimit >= total) return;
      state.todayResultsLimit += TODAY_PAGE_SIZE;
      renderToday({ resultsOnly: true });
    });
  }
  todaySentinelObserver.disconnect();
  todaySentinelObserver.observe(sentinel);
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
  // The badge tracks the secondary filters live, including during the
  // resultsOnly re-renders that follow each drawer interaction.
  updateFiltersCount();
  const observations = filteredObservations();
  const benchmarkMatches = renderTodayBenchmarks();
  const resultsKey = [
    state.todayDate,
    state.q,
    state.kind,
    state.category,
    state.source,
    state.organization,
    state.event,
  ].join("\u0000");
  let resultsKeyChanged = false;
  if (resultsKey !== state.todayResultsKey) {
    resultsKeyChanged = true;
    state.todayResultsKey = resultsKey;
    state.todayResultsLimit = TODAY_PAGE_SIZE;
  }
  // A single busy scan can carry hundreds of observations. Bound every render,
  // not just the all-dates archive, so initial load and filter feedback never
  // have to build the entire card list before the reader can interact.
  const visibleObservations = observations.slice(0, todayPageLimit());
  const remainingResults = observations.length - visibleObservations.length;
  // The legend is two readings, not three (issue #311): the class breakdown
  // and the order. The raw total repeated what the breakdown already adds up
  // to, and the attention noun lost its verb now that it stands beside
  // "normal" instead of a sentence.
  const evidenceCount = observations.filter(
    (item) => item.observation_kind === "evidence",
  ).length;
  const attentionCount = observations.length - evidenceCount;
  byId("today-breakdown").textContent =
    `${evidenceCount} ${t("normal")} · ${attentionCount} ${t("attention")}`;
  // The list is sorted by priority within a day; say so at the point of use
  // rather than making the reader infer it. Attention rows carry no priority,
  // so a kind-filtered attention set falls back to date order, and in All
  // dates mode the archive is ordered by date first and priority second
  // (issue #248).
  const priorityScored = visibleObservations.some((item) => Number(item.total_score) > 0);
  byId("today-sort").textContent = !priorityScored
    ? t("Sort: Date ↓")
    : showingAllDates
      ? t("Sort: Date, then Priority ↓")
      : t("Sort: Priority ↓");
  // A load-more pass appends the new page rather than rebuilding the list:
  // replaceChildren would recreate every <details> closed, collapsing a card
  // the reader had expanded and jumping them up the page mid-read.
  const listHost = byId("today-list");
  const renderedCount = state.todayRenderedCount || 0;
  const growsInPlace =
    !resultsKeyChanged && renderedCount > 0 && visibleObservations.length > renderedCount;
  if (growsInPlace) {
    // The appended slice maps from zero, so the rank offset travels with it:
    // page two continues at 21, not back at 01.
    listHost.append(
      ...visibleObservations
        .slice(renderedCount)
        .map((item, offset) => observationCard(item, renderedCount + offset)),
    );
  } else {
    replaceChildren(
      listHost,
      visibleObservations.length
        ? visibleObservations.map(observationCard)
        : [
            element("p", {
              className: "empty-state",
              text: emptyTodayMessage(day, benchmarkMatches),
            }),
          ],
    );
  }
  state.todayRenderedCount = visibleObservations.length;
  // What is loaded, said where more loads from (issue #311). Scrolling this
  // paragraph into view pulls the next page, so the count doubles as the
  // control's own status line.
  byId("today-loaded").textContent =
    remainingResults > 0
      ? t("{loaded} of {total} results loaded · scroll for more", {
          loaded: visibleObservations.length,
          total: observations.length,
        })
      : t("All {total} results loaded", { total: observations.length });
  watchTodaySentinel(remainingResults);

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
      : t("Two snapshots are available, but they covered different data sources or a different report limit, so the change between them is not comparable.");
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
        `${latest.date} ${t("covered different data sources or used a different report limit than")} ${previous.date}, ${t("so the two scans")} ` +
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
  renderSourceGapNote(state.data.days[dayCount - 1]);
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
        element("td", {}, sourceMixCell(day)),
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

// The ledger is long and the newest day sits at the top of it, so the gaps for
// that day are stated once in plain words above the table. Naming the sources
// is the point: "3 sources are at zero" tells a reader there is a problem but
// not where to look, and each of the three reasons calls for different
// follow-up (fix the fetch, wait, or look at the scoring).
function renderSourceGapNote(day) {
  const note = byId("source-gap-note");
  if (!note) return;
  const gaps = day ? zeroItemSources(day) : [];
  if (!gaps.length) {
    note.hidden = true;
    note.textContent = "";
    return;
  }
  const named = (state) =>
    gaps.filter((entry) => entry.state === state).map((entry) => entry.name);
  const sentence = (template, names) =>
    names.length ? t(template, { date: formatDate(day.date), sources: names.join(", ") }) : "";
  const sentences = [
    sentence("On {date} these sources found nothing at all: {sources}.", named("empty")),
    sentence("On {date} these sources could not be reached: {sources}.", named("unreachable")),
    sentence(
      "On {date} these sources returned something, but none of it scored high enough to be listed: {sources}.",
      named("unranked"),
    ),
  ].filter(Boolean);
  // Only the first two sentences are a reason to go and check something. A
  // source whose records all scored too low is the ranking doing its job, so
  // adding the warning there would cry wolf on a normal day.
  const worrying = named("empty").length + named("unreachable").length;
  note.textContent = worrying
    ? `${sentences.join(" ")} ${t("A source that stays at zero for several days is usually broken, not quiet.")}`
    : sentences.join(" ");
  note.classList.toggle("is-warning", worrying > 0);
  note.hidden = false;
}

// The source mix used to list only sources that found something, so a day on
// which a source found nothing looked identical to a day on which that source
// did not exist. The zeros are the interesting half: a source that quietly
// returns nothing several days running is usually broken, not idle, so they are
// spelled out here rather than left to be inferred from an absence (issue #260).
function sourceMixCell(day) {
  const found = Object.entries(day.source_counts || {});
  const gaps = zeroItemSources(day);
  const parts = [];
  // "none" contradicts a row that goes on to name three sources at zero, so it
  // is only printed when the day has nothing at all to say about its sources.
  if (found.length || !gaps.length) {
    parts.push(
      element("span", {
        text: found.length
          ? found.map(([name, count]) => `${name.replaceAll("_", " ")} ${count}`).join(" · ")
          : t("none"),
      }),
    );
  }
  gaps.forEach((entry) => {
    parts.push(
      element("span", {
        // Why it is zero is the reader's next question, and an unranked source
        // is the ranking working as intended rather than a fault to chase, so
        // it is not dressed up in the same alarm colour as the other two.
        className: entry.state === "unranked" ? "source-gap is-unranked" : "source-gap",
        text: `${entry.name} 0`,
        attrs: { title: t(SOURCE_GAP_REASONS[entry.state]) },
      }),
    );
  });
  return parts;
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
    if (dateOrder) return dateOrder;
    const scoreOrder = Number(b.total_score || 0) - Number(a.total_score || 0);
    if (scoreOrder) return scoreOrder;
    // Attention rows carry no priority, so within a day they order by the
    // event timestamp the row displays, keeping the visible order consistent
    // with the "Sort: Date ↓" caption.
    return String(eventTimestamp(b)).localeCompare(String(eventTimestamp(a)));
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

// The trigger badge counts the secondary filters currently narrowing the
// list, so the drawer is discoverable without opening it.
function updateFiltersCount() {
  const active = [
    state.kind,
    state.category,
    state.source,
    state.organization,
    state.event,
  ].filter(Boolean).length;
  byId("filters-count").textContent = `(${active})`;
}

function closeFiltersDrawer() {
  const drawer = byId("filters-drawer");
  if (!drawer.hidden) {
    drawer.hidden = true;
    byId("filters-toggle").setAttribute("aria-expanded", "false");
  }
}

function filteredObservations() {
  const query = state.q.trim().toLowerCase();
  const sourceLower = state.source.trim().toLowerCase();
  return allObservations().filter((item) => {
    const haystack = `${item.title} ${item.summary} ${item.source}`.toLowerCase();
    return (
      (state.todayDate === "all" || item.snapshot_date === state.todayDate) &&
      (!state.kind || item.observation_kind === state.kind) &&
      (!state.category || (item.categories || []).includes(state.category)) &&
      (!state.source || item.source.toLowerCase() === sourceLower) &&
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
  // v2 records retain everything eligible and use 40 only as the
  // recommendation marker.
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
              "or above marks the item as recommended; it does not control inclusion. Watchlisted artifacts are also retained.",
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
  const categoryLine = (item.categories || []).length
    ? (item.categories || []).map(titleCase).join(" · ")
    : t("uncategorized");
  return element("div", { className: "record-detail" }, [
    element("p", {
      className: "detail-source",
      text:
        `${item.source} · ${eventVerb(item)} · ${categoryLine}` +
        `${item.watchlist ? ` · ★ ${item.watchlist}` : ""} · ${item.snapshot_date}`,
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
  const typeLabel = {
    artifact: t("item"),
    topic: t("topic"),
    source: t("source"),
    organization: t("organization"),
  }[entity.type] || entity.type;
  const topicAggregate = (state.data.corpus.aggregates.topics || []).find(
    (entry) => `topic:${entry.topic}` === entity.id,
  );
  const stats = [
    definition(t("Kind"), typeLabel),
    definition(t("First found"), formatDate(entity.first_seen_at, { dateStyle: "medium" })),
    definition(t("Last found"), formatDate(entity.last_seen_at, { dateStyle: "medium" })),
    definition(t("Days it appeared"), Number(entity.seen_days?.length || 0).toLocaleString()),
    ...(entity.type === "artifact"
      ? [
          definition(t("Times found"), Number(entity.observation_count || 0).toLocaleString()),
          definition(
            t("Latest priority score"),
            entity.latest_score === null || entity.latest_score === undefined
              ? t("not scored")
              : Number(entity.latest_score).toFixed(2),
          ),
        ]
      : []),
    ...(topicAggregate
      ? [
          definition(t("Items"), topicAggregate.entity_count),
          definition(t("Sources"), topicAggregate.source_breadth),
          definition(
            `${t("Change over")} ${
              state.data.corpus.aggregates.observed_window_days ??
              state.data.corpus.aggregates.window_days
            } ${t("days")}`,
            topicAggregate.velocity === null
              ? t("not enough earlier data")
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
    element("p", { className: "eyebrow", text: t("Selected") }),
    element("h2", { text: entity.label }),
    element("p", {
      text:
        entity.type === "artifact"
          ? "Today is now ready to show this item."
          : `Today is now filtered by this ${typeLabel}.`,
    }),
    element("dl", {}, stats),
    relatedEntities.length
      ? element("p", {
          className: "discovery-note",
          text: `${t("Also connected to")} ${relatedEntities
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
  writeUrl("push");
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
      ({
        agentic: t("AI agents"),
        benchmark: t("benchmarks"),
        dataset: t("datasets"),
        evaluation: t("evaluations"),
        data_quality: t("data quality"),
      }[topic.topic] || topic.topic.replaceAll("_", " ")),
      `${Number(topic.entity_count || 0).toLocaleString()} ${t("items")} · ${metricLabel(
        topic.source_breadth,
        "source",
      )}`,
    ]);
  const sourceEntries = rankedCounts(aggregates.sources).map(([source, count]) => [
    source,
    `${Number(count || 0).toLocaleString()} ${t("times found")}`,
  ]);
  const organizationEntries = rankedCounts(aggregates.organizations).map(
    ([organization, count]) => [
      organization,
      `${Number(count || 0).toLocaleString()} ${t("times found")}`,
    ],
  );
  const coverageEntries = [
    [t("Items"), Number(entityTypes.artifact || 0).toLocaleString()],
    [t("Organizations"), Number(entityTypes.organization || 0).toLocaleString()],
    [t("Authors"), Number(entityTypes.person || 0).toLocaleString()],
    [t("Sources"), Number(entityTypes.source || 0).toLocaleString()],
    [t("Topics"), Number(entityTypes.topic || 0).toLocaleString()],
  ];
  replaceChildren(byId("map-insights"), [
    mapInsightCard(t("At a glance"), coverageEntries, t("Nothing found yet.")),
    mapInsightCard(t("What it is about"), topicEntries, t("No topics yet.")),
    mapInsightCard(t("Where we found it"), sourceEntries, t("No sources yet.")),
    mapInsightCard(
      t("Who appears most"),
      organizationEntries,
      t("No organizations yet."),
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
  // A benchmark with no release date is excluded by every dated era above, so
  // without this option it would be unreachable from the era control entirely
  // (issue #292). An era filter is a claim about dates, and "we do not know
  // this one's date" is an answer a reader has to be able to ask for.
  { value: "undated", label: "No release date recorded", undated: true },
];

function leaderboardEntries() {
  const board = state.data?.model_card_leaderboard;
  if (!board) return [];
  const query = state.lq.trim().toLowerCase();
  const era = LEADERBOARD_ERAS.find((candidate) => candidate.value === state.lera);
  return (board.entries || []).filter((entry) => {
    if (state.ldomain && entry.domain !== state.ldomain) return false;
    if (state.lorg && !(entry.organizations || []).includes(state.lorg)) return false;
    if (era?.undated) {
      if (entry.released) return false;
    } else if (era) {
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
      // `advances` still feeds the leaderboard's new-instruments disclosure.
      // The running total that went with it was the staircase's y value and has
      // no reader now, so it is not carried.
      const advances = !seenOrganizations.has(adopter.organization);
      seenOrganizations.add(adopter.organization);
      return { ...adopter, advances };
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
  const scored = (board.entries || []).filter(
    (entry) => entry.card_count > 0 && scoreRecord(entry.benchmark_id),
  );
  const datedCount = (entry) => scoreRecord(entry.benchmark_id)?.dated_observation_count || 0;
  // The page opens on the benchmark it ranks first, so the figure answers the
  // question the ranking above it just raised. It used to open on the NEWEST
  // scored instrument, which put AutomationBench under a page headed "most
  // reported in model cards" -- a benchmark the reader had not seen named
  // anywhere above the figure.
  //
  // `scored` is already in adoption_rank order (rank 1 first), so the ranking
  // and the default agree by construction rather than by a second sort that
  // could drift from it.
  //
  // A one-point plot says nothing visually, so a benchmark with fewer than two
  // dated readings is passed over even if it ranks higher; the picker still
  // reaches every scored benchmark.
  const drawable = scored.filter((entry) => datedCount(entry) >= 2);
  return (drawable.length ? drawable : scored)[0];
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

// The searchable catalog over every benchmark we know of: the curated registry
// plus every crawled external record. The stage-grouped shortlist above it is a
// curated browse surface and stays; this is the "choose anyone" path, because
// the shortlist can only ever show about 13 of 1,148.
//
// One row per source record, never per merged group. Two sources describing the
// same benchmark stay two labelled rows until identity.yml says otherwise under
// human review, since a wrong merge is invisible to a reader and two labelled
// duplicates are not.
const BENCHMARK_SEARCH_LIMIT = 50;

let benchmarkIndexPromise = null;

function loadBenchmarkIndex() {
  if (!benchmarkIndexPromise) {
    benchmarkIndexPromise = fetch("data/benchmark-index.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => payload.benchmarks || [])
      .catch(() => null);
  }
  return benchmarkIndexPromise;
}

function foldName(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function searchBenchmarkIndex(records, query) {
  const needle = foldName(query);
  if (!needle) return [];
  const scored = [];
  for (const record of records) {
    const name = foldName(record.name);
    // The crawled catalog carries no domain, so publisher and modality are the
    // fields a "tasks, domains" query can land on here.
    const named = name.includes(needle);
    if (!named && !foldName(record.publisher).includes(needle) && !foldName(record.modality).includes(needle)) {
      continue;
    }
    // Prefix beats substring, then a record that can answer more of the
    // reader's questions beats one that cannot, then shorter names first so
    // "MMLU" outranks "MMLU-Pro-Extended" for the query "mmlu".
    const answers =
      (record.publisher ? 1 : 0) +
      (record.openness !== "unknown" ? 1 : 0) +
      (record.has_size ? 1 : 0) +
      (record.score_count > 0 ? 1 : 0);
    scored.push({
      record,
      rank: [named ? (name.startsWith(needle) ? 0 : 1) : 2, -answers, name.length],
    });
  }
  scored.sort(
    (a, b) =>
      a.rank[0] - b.rank[0] ||
      a.rank[1] - b.rank[1] ||
      a.rank[2] - b.rank[2] ||
      a.record.name.localeCompare(b.record.name),
  );
  return scored.map((item) => item.record);
}

// Openness is a three-state answer and `unknown` is the common one. It renders
// as a neutral chip, never a warning: the reader is being told what we know,
// not that something is wrong with the benchmark.
function opennessChip(status) {
  const label = {
    open: t("open"),
    restricted: t("restricted"),
    unknown: t("openness not established"),
  }[status] || t("openness not established");
  return element("span", {
    className: `benchmark-openness benchmark-openness-${status || "unknown"}`,
    text: label,
  });
}

function benchmarkResultRow(record, { navigate = false, inert = false } = {}) {
  // The name is the scanning target, and the count is the measure. Publisher,
  // size, openness and the source chip printed on every row -- three of them
  // as "not established" on most crawled records -- so a reader scanned past
  // four grey fields to reach the next name (issue #298).
  //
  // Those fields still exist on the record and are still searchable; the
  // detail panel is where a reader who wants them asks for them.
  const button = element("button", {
    className: "benchmark-result",
    attrs: {
      type: "button",
      "aria-pressed": record.slug === state.lfrontier ? "true" : "false",
    },
  }, [
    element("span", { className: "benchmark-result-name", text: record.name }),
    // A count of collected numbers, never a quality signal: 239 rows means
    // llm-stats collected 239 numbers, not that the benchmark is better.
    element("span", {
      className: "benchmark-result-facts",
      text: record.score_count
        ? metricLabel(record.score_count, "reported score", "reported scores")
        : t("no scores collected"),
    }),
  ]);
  if (inert) {
    button.disabled = true;
    return button;
  }
  button.addEventListener("click", () => {
    selectFrontier(record.slug);
    if (navigate) {
      // setView toggles visibility and the URL; it does not draw. On a first
      // visit the leaderboard has never rendered, so switching to it without
      // this leaves the reader on an empty panel.
      setView("leaderboard");
      renderLeaderboard();
      return;
    }
    renderBenchmarkSearch();
    const board = state.data?.model_card_leaderboard;
    if (board) renderAdoptionFrontier(board);
    writeUrl("push");
  });
  return button;
}

// Search covers both layers. It used to read the crawled index only, so a
// reader typing "GPQA" was shown crawled rows and not the curated GPQA Diamond
// record that the panel actually charts, while the picker had the opposite
// blind spot. Curated matches rank above crawled ones for the same reason the
// picker lists them first: they are the layer with a protocol and a time axis.
//
// Matched on aliases as well as the name, because the registry records them
// ("HLE" for Humanity's Last Exam) precisely so a reader does not have to know
// the canonical spelling.
// `includeUnscored` exists for callers that are answering "does the radar
// track this?" rather than "can this be charted?". The leaderboard picker
// needs a score record because it drives a chart, but 20 of the 79 curated
// entries have no score progression, and 5 of those are in no crawled index
// either: CVE-Bench, Chatbot Arena, CursorBench, MTOB and ViBench were tracked
// benchmarks that name search could not find, which is issue #245 again with a
// different benchmark in it.
function searchCuratedEntries(board, query, { includeUnscored = false } = {}) {
  const needle = foldName(query);
  if (!needle) return [];
  const scored = [];
  for (const entry of board?.entries || []) {
    if (!includeUnscored && !scoreRecord(entry.benchmark_id)) continue;
    // Name and aliases identify the record; `domain` is what the placeholder
    // means by tasks and domains, since the task shape shown in the panel is
    // selected by domain. Matching it lets "agent" or "science" return a set
    // rather than nothing.
    const names = [entry.name, ...(entry.aliases || [])].map(foldName);
    const hits = names.filter((name) => name.includes(needle));
    if (!hits.length && !foldName(entry.domain).includes(needle)) continue;
    // Exact beats prefix beats substring, then the shortest matched string.
    // Ranking on the entry name alone put AutomationBench above Humanity's Last
    // Exam for the query "HLE": the registry really does record the alias
    // `HLEAutomationBench`, so both were prefix hits and the shorter entry name
    // won. What a reader means by "HLE" is the record that answers to it
    // exactly, so the matched alias is what gets ranked, not the entry name.
    const tier = (name) => (name === needle ? 0 : name.startsWith(needle) ? 1 : 2);
    // A domain-only hit is a weaker answer than a name hit: the reader typed a
    // field value, not an identity, so those rank below every named match.
    const best = hits.length ? Math.min(...hits.map(tier)) : 3;
    const shortest = hits.length
      ? Math.min(...hits.filter((name) => tier(name) === best).map((name) => name.length))
      : 0;
    scored.push({ entry, rank: [best, shortest, foldName(entry.name).length] });
  }
  scored.sort(
    (a, b) =>
      a.rank[0] - b.rank[0] ||
      a.rank[1] - b.rank[1] ||
      a.rank[2] - b.rank[2] ||
      a.entry.name.localeCompare(b.entry.name),
  );
  return scored.map((item) => item.entry);
}

// `navigate` is for rows rendered outside the leaderboard. There, selecting a
// benchmark updates a panel the reader is not looking at, so the click would
// register as nothing happening. Carrying them to the panel is the only
// behaviour that matches what the row looks like it promises.
function curatedResultRow(entry, { navigate = false, inert = false } = {}) {
  // The name is the scanning target. Domain, release year, source chip and
  // score count rendered on every row and turned the list into a wall of grey
  // text that had to be read before a name could be found (issue #298). The
  // count stays because it is the measure this registry is built on; the rest
  // is still searchable, just not printed.
  const button = element("button", {
    className: "benchmark-result benchmark-result-curated",
    attrs: {
      type: "button",
      "aria-pressed": entry.benchmark_id === state.lfrontier ? "true" : "false",
    },
  }, [
    element("span", { className: "benchmark-result-name", text: entry.name }),
    element("span", {
      className: "benchmark-result-facts",
      text: metricLabel(entry.card_count, "model", "models"),
    }),
  ]);
  // Nothing to navigate to and no panel on screen to update: an enabled
  // control whose click does nothing visible is a worse answer than a row that
  // does not look clickable.
  if (inert) {
    button.disabled = true;
    return button;
  }
  button.addEventListener("click", () => {
    selectFrontier(entry.benchmark_id);
    if (navigate) {
      // setView toggles visibility and the URL; it does not draw. On a first
      // visit the leaderboard has never rendered, so switching to it without
      // this leaves the reader on an empty panel.
      setView("leaderboard");
      renderLeaderboard();
      return;
    }
    renderBenchmarkSearch();
    const board = state.data?.model_card_leaderboard;
    if (board) renderAdoptionFrontier(board);
    writeUrl("push");
  });
  return button;
}

function renderBenchmarkSearch() {
  const container = byId("benchmark-search-results");
  const status = byId("benchmark-search-status");
  if (!container || !status) return;
  const records = state.benchmarkIndex;
  const board = state.data?.model_card_leaderboard;
  // The curated layer is in the dashboard payload, which is already loaded, so
  // search still works over it while the crawled index is on the wire or after
  // that fetch has failed. Only the crawled half degrades.
  const curatedCount = (board?.entries || []).filter((entry) =>
    scoreRecord(entry.benchmark_id),
  ).length;
  if (!records && !curatedCount) {
    replaceChildren(container, []);
    status.textContent = "";
    return;
  }
  if (!state.benchmarkQuery) {
    replaceChildren(container, []);
    // Stated as reach, not as a boast: the number is what this box searches
    // right now, so it drops when the crawled index fails to load rather than
    // advertising records that cannot be returned. "Sources" counts the layers
    // behind those records (the curated registry plus each crawl), not the
    // radar's discovery connectors, which supply no benchmark to this index.
    const sources = new Set((records || []).map((record) => record.source));
    if (curatedCount) sources.add("curated");
    status.textContent = `${t("{n} benchmarks").replace(
      "{n}",
      (curatedCount + (records?.length || 0)).toLocaleString(),
    )} \u00b7 ${metricLabel(sources.size, "source")}`;
    return;
  }
  const curatedMatches = searchCuratedEntries(board, state.benchmarkQuery);
  const externalMatches = records
    ? searchBenchmarkIndex(records, state.benchmarkQuery)
    : [];
  // Curated first, then crawled, and the cap applies across both so a common
  // name cannot push every curated hit off the end of the list.
  const shownCurated = curatedMatches.slice(0, BENCHMARK_SEARCH_LIMIT);
  const shownExternal = externalMatches.slice(
    0,
    Math.max(0, BENCHMARK_SEARCH_LIMIT - shownCurated.length),
  );
  const total = curatedMatches.length + externalMatches.length;
  replaceChildren(container, [
    ...shownCurated.map(curatedResultRow),
    ...shownExternal.map(benchmarkResultRow),
  ]);
  status.textContent = total
    ? t("{shown} of {total} matches")
        .replace("{shown}", String(shownCurated.length + shownExternal.length))
        .replace("{total}", String(total))
    : t("No benchmark matches that name");
}

function initBenchmarkSearch() {
  const input = byId("benchmark-search-input");
  if (!input || input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  const onInput = debounce(() => {
    state.benchmarkQuery = input.value.trim();
    renderBenchmarkSearch();
  });
  input.addEventListener("input", onInput);
  loadBenchmarkIndex().then((records) => {
    // A missing or broken index leaves the curated shortlist fully working.
    // Search is additive, so its failure must not take the navigator with it.
    state.benchmarkIndex = records;
    state.benchmarkIndexLoaded = true;
    const status = byId("benchmark-search-status");
    if (!records && status) {
      status.textContent = t("Benchmark search is unavailable right now");
      input.disabled = true;
    } else {
      // Skipped on failure: renderBenchmarkSearch() would blank the
      // unavailability notice just written into the status line.
      renderBenchmarkSearch();
    }
    // A ?lfrontier=<slug> permalink can only resolve once the index fetch has
    // settled either way: a resolved index confirms the slug, a failed one
    // turns the panel's loading state into an explicit unavailability note
    // (see renderAdoptionFrontier).
    const board = state.data?.model_card_leaderboard;
    // renderLeaderboard() calls renderAdoptionFrontier(board) itself, and the
    // registry-overview tiles cite the crawled totals once the index is in --
    // they render before this fetch resolves on first load, so they need this
    // second pass rather than staying curated-only forever.
    if (board && state.view === "leaderboard") renderLeaderboard();
  });
}

// --- External catalog detail (display plan steps 4, 6, 7) --------------------
//
// `state.lfrontier` holds either a canonical registry benchmark_id or an
// external slug. A slug selection renders into the same workbench panel: the
// identity, openness, size and per-source score blocks below, with the curated
// chart chrome hidden. Nothing here merges the two layers: the adoption chart
// belongs to the curated registry and is never interleaved with crawled
// tables, and the crawled tables are never joined into the chart.

// A shard is fetched on selection and cached for the rest of the session,
// keyed by slug. Payloads are tens of kilobytes and a session opens a handful,
// so the cache is never evicted (display plan step 7).
const benchmarkShardCache = new Map();

function loadBenchmarkShard(slug) {
  if (!benchmarkShardCache.has(slug)) {
    benchmarkShardCache.set(
      slug,
      fetch(`data/benchmarks/${slug}.json`)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .catch(() => null),
    );
  }
  return benchmarkShardCache.get(slug);
}

// What each source actually recorded, stated next to its name on the table
// rather than in a footnote. llm-stats rows are vendor-announced numbers with
// no protocol and no evaluation date (AUDIT.md section 1); the label says so
// where the numbers are read.
const EXTERNAL_SOURCE_META = {
  llm_stats: {
    name: "LLM Stats",
    noteKey:
      // "No date is recorded" was false and was the complaint in issue #269:
      // every one of the 5,544 rows carries one. What is missing is a date for
      // the measurement -- the date recorded is the model's own release -- and
      // that is the distinction worth stating, since it is why these rows are
      // ordered by score rather than drawn on a time axis. The axis label was
      // corrected then; this note was not.
      "Self-reported scores collected by LLM Stats. No evaluation protocol is recorded, and the only date is each model's own release, not when the score was measured, so rows are listed in the source's own order.",
    emptyKey: "LLM Stats recorded no scores for this benchmark.",
  },
  opencompass_hub: {
    name: "OpenCompass Hub",
    noteKey:
      "Scores embedded in the OpenCompass hub card. Column meaning varies from card to card, and rows are listed in the source's own order.",
    emptyKey: "The OpenCompass hub card records no scores for this benchmark.",
  },
};

function externalSourceMeta(source) {
  return (
    EXTERNAL_SOURCE_META[source] || {
      name: source,
      noteKey: "Scores as recorded by this source, in the source's own order.",
      emptyKey: "This source recorded no scores for this benchmark.",
    }
  );
}

// The publisher field carries an explicit role because the crawled value is
// not automatically "who made it": OpenCompass publishOrg names whoever
// published the hub card, which is frequently not the benchmark's creator
// (AUDIT.md section 2). The role is printed next to the name so the
// attribution is never stronger than the evidence.
function publisherRoleLabel(role) {
  return (
    {
      hub_publisher: t("published the hub card"),
      paper_org: t("organization behind the paper"),
      maintainer: t("maintainer"),
    }[role] || role
  );
}

function artifactKindLabel(kind) {
  return (
    {
      paper: t("Paper"),
      repo: t("Code repository"),
      dataset: t("Dataset"),
      site: t("Project site"),
    }[kind] || kind
  );
}

function externalFactList(facts) {
  return element(
    "dl",
    { className: "external-facts" },
    facts.flatMap(([name, value]) => [
      element("dt", { text: name }),
      element("dd", { text: value }),
    ]),
  );
}

// One block per question the reader came with. Every field renders, and an
// empty one says "not established" instead of disappearing: hiding an empty
// field reads as "not applicable", and whether these facts are known is
// precisely the reader's question (display plan step 4).
// A record with no identity of its own may show a reviewed equivalent's
// (issue #262): llm-stats carries the scores and the OpenCompass card carries
// the publisher, artifacts and dates. When it does, the borrowed values are
// never presented as this source's own -- this note names the donor card and
// the review, so "Anthropic" reads as "from the OpenCompass card", not "from
// LLM Stats".
function externalInheritanceNote(detail) {
  const inheritance = detail.identity_inheritance;
  if (!inheritance) return null;
  const donorName = externalSourceMeta(inheritance.donor_source).name;
  return element("p", {
    className: "external-inherited",
    text: t(
      "Identity below is inherited from the {donor} card for a reviewed equivalent benchmark; scores are unchanged.",
      { donor: donorName },
    ),
  });
}

function externalIdentityBlock(detail) {
  const publisher = detail.publisher;
  const description = l10nProse(detail.description?.en, detail.description?.zh);
  const artifacts = (detail.artifacts || []).filter((artifact) =>
    safeHttpUrl(artifact.url),
  );
  return element("section", { className: "external-block" }, [
    element("h3", { text: t("Identity") }),
    // Crawled descriptions are third-party text. They only ever go through
    // text(), which sets textContent, so markup in the crawl can never execute.
    element("p", {
      className: "external-description",
      text: description || t("description not established"),
    }),
    externalInheritanceNote(detail),
    externalFactList([
      [
        t("Publisher"),
        publisher?.name
          ? `${publisher.name} (${publisherRoleLabel(publisher.role)})`
          : t("publisher not established"),
      ],
      [
        t("Released"),
        detail.released
          ? formatDate(detail.released, { dateStyle: "medium" })
          : t("release date not established"),
      ],
      [t("Modality"), detail.modality || t("modality not established")],
    ]),
    artifacts.length
      ? element(
          "ul",
          { className: "external-artifacts" },
          artifacts.map((artifact) =>
            element("li", {}, [
              element("a", {
                text: `${artifactKindLabel(artifact.kind)} · ${artifact.id || artifact.url}`,
                attrs: {
                  href: safeHttpUrl(artifact.url),
                  target: "_blank",
                  rel: "noopener noreferrer",
                },
              }),
            ]),
          ),
        )
      : element("p", {
          className: "external-empty",
          text: t("No paper, repository, dataset or site link established."),
        }),
  ]);
}

function externalOpennessBlock(detail) {
  const openness = detail.openness || {};
  const evidence = (openness.evidence || []).filter((item) =>
    safeHttpUrl(item.evidence_url),
  );
  return element("section", { className: "external-block" }, [
    element("h3", { text: t("Openness") }),
    element("p", { className: "external-openness-chip" }, [
      opennessChip(openness.status),
    ]),
    // The basis is the reviewer's own note on how the status was decided, so
    // it prints as evidence rather than being paraphrased away.
    openness.basis
      ? element("p", { className: "external-basis", text: openness.basis })
      : null,
    externalFactList([
      [t("Code licence"), openness.code_license || t("not established")],
      [t("Data licence"), openness.data_license || t("not established")],
    ]),
    evidence.length
      ? element(
          "ul",
          { className: "external-artifacts" },
          evidence.map((item) =>
            element("li", {}, [
              element("a", {
                text: item.locator || item.value || item.evidence_url,
                attrs: {
                  href: safeHttpUrl(item.evidence_url),
                  target: "_blank",
                  rel: "noopener noreferrer",
                },
              }),
            ]),
          ),
        )
      : element("p", {
          className: "external-empty",
          text: t("No openness evidence recorded."),
        }),
  ]);
}

function externalSizesBlock(detail) {
  const sizes = detail.sizes || [];
  return element("section", { className: "external-block" }, [
    element("h3", { text: t("Size") }),
    sizes.length
      ? element(
          "ul",
          { className: "external-sizes" },
          sizes.map((size) =>
            element("li", {}, [
              element("span", {
                text:
                  `${Number(size.value).toLocaleString()} ${size.unit}` +
                  (size.split ? ` · ${size.split} split` : "") +
                  // A count with no idea what it counts is worse than no
                  // number, so `unclear` is printed rather than smoothed over.
                  (size.measures && size.measures !== "unclear"
                    ? ` · ${t("counts the")} ${String(size.measures).replaceAll("_", " ")}`
                    : ` · ${t("what it counts is unclear")}`),
              }),
              safeHttpUrl(size.evidence_url)
                ? element("a", {
                    className: "external-evidence-link",
                    text: t("evidence ↗"),
                    attrs: {
                      href: safeHttpUrl(size.evidence_url),
                      target: "_blank",
                      rel: "noopener noreferrer",
                    },
                  })
                : null,
            ]),
          ),
        )
      : element("p", { className: "external-empty", text: t("size not established") }),
  ]);
}

// Scores render one table per source, and the partition is read from the
// shard's keyed `scores_by_source` object rather than reconstructed here:
// there is deliberately no flat array in this code path for a later sort to
// rank across sources. Within a table the rows stay in the source's own order
// (rank_in_source_response), which is the only ordering the source asserted.
// No percentages and no bars: every crawled series carries display_scale:
// null, so there is no honest scale to draw one from. vending-bench-2 declares
// max 1.0 and carries 8017.59, so the declared bound is never a denominator
// either. comparable_group is null on every crawled row, so no row here ever
// joins a line, a trend, or a shared ranking.
function externalScoresBlock(shard) {
  const bySource = shard.scores_by_source || {};
  const sources = Object.keys(bySource).sort();
  // No "Scores" heading: the panel title names the benchmark and the subline
  // names the source and the count, so this said nothing the reader had not
  // just read, and it was the top half of ~150px of dead space above the
  // chart (issue #298).
  return element("section", { className: "external-block" }, [
    // Spread, not nesting: element() appends children verbatim, so a mapped
    // array passed as one child would stringify into "[object HTMLDivElement]".
    ...(sources.length
      ? sources.map((source) => externalSourceTable(source, bySource[source]))
      : [element("p", { className: "external-empty", text: t("no scores collected") })]),
  ]);
}

// --- The reported field (crawled scores) -------------------------------------
//
// A crawled row carries no protocol, so it is not joined to the curated layer's
// `benchmark_scores.yml` records: none of the join-rule machinery in
// `scoreTrackChart` (instrument/protocol grouping, evidence grading) applies to
// a row without one. What it does share with that chart is everything visual --
// same margins, same point size, same pale-face-plus-brand-glyph marker, same
// grid and tick classes -- because the reader should not have to learn a second
// chart language to read a second kind of evidence.
//
// It does carry a date. Every one of the 5,544 crawled rows has a
// `reported_date`, and `date_precision` is `model_announcement` for all of
// them: it is when the model was announced, never when this score was measured
// (issue #279). Those are different facts, and the axis is only honest if it
// says which one it is drawing.
//
// So the x-axis is the model's release date, labelled as such. That answers a
// real question -- are newer models better at this benchmark? -- without
// claiming to answer one it cannot: nothing here says when anyone ran the
// evaluation. A model released in March can be scored in August, so reading
// these points as a measurement timeline would be wrong, and the axis label
// and every tooltip say "model release" rather than "date" to stop that.
//
// Ordering by score, which is what this chart did before, threw the dates away
// entirely and produced a monotonic ramp that looks like progress and is really
// just a sorted list.
function externalScoreChart(source, payload) {
  const meta = externalSourceMeta(source);
  // A row whose value did not parse is in the table verbatim and out of the
  // chart: a point can only be drawn at a position, and there is no honest
  // position for a value that is not a number. A row with no parseable release
  // date is out for the same reason once the axis is time: there is no honest
  // x for it. Both exclusions are declared in the source's (i) note rather than
  // left to be inferred from a count that does not add up.
  const numeric = (payload.rows || []).filter(
    (row) => typeof row.value === "number" && Number.isFinite(row.value),
  );
  const dated = numeric.filter((row) => Number.isFinite(dateValue(row.reported_date)));
  // Sorted by date so the axis reads left to right in time. Ties broken by
  // score so same-day releases land in a stable order rather than whatever
  // order the crawl happened to return.
  const plotted = dated
    .slice()
    .sort(
      (a, b) => dateValue(a.reported_date) - dateValue(b.reported_date) || a.value - b.value,
    );
  if (!plotted.length) return null;

  // Sorted for the band and the tick labels. `plotted` is in date order now, so
  // its last element is the most recently released model, not the best score:
  // reading the best off the end of the array is exactly the bug the date axis
  // would introduce if these two orderings were conflated.
  const values = plotted.map((row) => row.value).sort((a, b) => a - b);
  const low = values[0];
  const high = values[values.length - 1];
  const bestRow = plotted.reduce((best, row) => (row.value > best.value ? row : best), plotted[0]);
  const bestValue = high;
  const pad = Math.max((high - low) * 0.18, Math.abs(high) * 0.05, Number.EPSILON);
  const band = { low: low - pad, high: high + pad };

  // Same viewBox and margins as scoreTrackChart, so the two charts sit at the
  // same visual scale wherever a reader compares them.
  const narrow = typeof window !== "undefined" && window.innerWidth <= 760;
  const width = narrow ? 520 : 920;
  const scoreHeight = 480;
  const margin = { top: 32, right: 20, bottom: 62, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const height = margin.top + scoreHeight + margin.bottom;
  const scoreTop = margin.top;
  // Positioned by date, so a cluster of releases in one month reads as a
  // cluster rather than being spread evenly by rank. A field whose releases all
  // land on one day has no interval to spread across, so its points are drawn
  // at the left edge rather than at the midpoint of a range that does not exist.
  const times = plotted.map((row) => dateValue(row.reported_date));
  const firstTime = Math.min(...times);
  const lastTime = Math.max(...times);
  const span = lastTime - firstTime;
  const x = (time) => (span > 0 ? margin.left + ((time - firstTime) / span) * plotWidth : margin.left);
  const scoreY = (value) => {
    if (band.high <= band.low) return scoreTop + scoreHeight / 2;
    return scoreTop + scoreHeight - ((value - band.low) / (band.high - band.low)) * scoreHeight;
  };

  const svg = svgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "group",
    "aria-label": t(
      "{count} scores reported to {source}, placed at each model's release date, which is the only date recorded and is not when the score was measured. Highest {best} by {model}, lowest {low}.",
      {
        count: plotted.length.toLocaleString(),
        source: meta.name,
        best: bestValue,
        model: bestRow.model_name || t("not recorded"),
        low: values[0],
      },
    ),
  });

  // The band pads so points are not drawn on the frame, but the ticks label
  // the real extremes. They used to print the padded bounds, so AIME 2025 --
  // values 0.067 to 1.0 -- announced an axis from "-0.1" to "1.17": a negative
  // score and a ceiling above anything observed, neither of which exists in
  // the data (issue #269).
  // Intermediate ticks so a point's height can be read rather than inferred
  // (issue #298). Generated strictly inside [low, high]: the extremes are the
  // real observed values, and a tick outside them would reintroduce exactly
  // the padded-bound axis issue #269 removed ("-0.1" to "1.17" on AIME 2025).
  const yTicks = [high, low];
  if (high > low) {
    for (const fraction of [0.25, 0.5, 0.75]) {
      const value = low + (high - low) * fraction;
      // Rounded for the label, then kept only if rounding left it inside the
      // observed range and distinct from the extremes it sits between.
      const rounded = Number(value.toFixed(2));
      if (rounded > low && rounded < high && !yTicks.includes(rounded)) {
        yTicks.push(rounded);
      }
    }
  }
  for (const value of yTicks) {
    const gridY = scoreY(value);
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: gridY,
        x2: width - margin.right,
        y2: gridY,
        class: "frontier-grid",
      }),
    );
    svg.append(
      svgElement(
        "text",
        { x: margin.left - 12, y: gridY + 4, "text-anchor": "end", class: "frontier-tick" },
        Number(value.toFixed(2)),
      ),
    );
  }

  const bestY = scoreY(bestValue);
  // No running-best line on this layer, deliberately (issue #288 review).
  //
  // A maximum is a comparability claim: it says these numbers can be ranked
  // against each other. This layer cannot support that. The normalizer records
  // `direction: None` because the source states no metric direction, and
  // `comparability_class: none` because it records no protocol -- see
  // external_catalog.py, "the only honest comparability class is none". Taking
  // a max over those rows would assume larger-is-better and assume the rows are
  // measuring the same thing, and neither is in evidence.
  //
  // The flat best-on-record rule stays: it labels one row's own value, which is
  // a fact about that row rather than a ranking across rows.
  svg.append(
    svgElement("line", {
      x1: margin.left,
      y1: bestY,
      x2: width - margin.right,
      y2: bestY,
      class: "score-best-line",
    }),
  );
  // Attached to the left end of the reference line it annotates. Anchored at
  // the far right it floated away from the rule and read as a stray number
  // (issue #298).
  svg.append(
    svgElement(
      "text",
      { x: margin.left + 6, y: bestY - 6, "text-anchor": "start", class: "score-best-label" },
      `${t("Best reported score:")} ${bestValue.toFixed(2)}`,
    ),
  );

  for (const row of plotted) {
    const pointX = x(dateValue(row.reported_date));
    const pointY = scoreY(row.value);
    const thirdParty = row.reported_by === "third_party";
    // Same left-to-right reveal as the curated chart (issue #312): one kind
    // of mark, one entrance, on both layers.
    const group = svgElement("g", {
      class: `score-point${thirdParty ? " score-point-third-party" : ""}`,
      tabindex: "0",
      role: "button",
      "aria-pressed": "false",
      "data-frontier-point": "",
      style: `--reveal-delay:${frontierPointRevealDelay(pointX, margin, plotWidth)}ms`,
      "aria-label":
        `${row.model_name || t("not recorded")} ${t("by")} ${row.organization || t("not recorded")}` +
        (thirdParty ? `, ${t("cited by")} ${meta.name}` : "") +
        `. ${t("Click to pin record details")}.`,
    });
    group.append(svgElement("circle", { cx: pointX, cy: pointY, r: 9, class: "score-point-face" }));
    if (thirdParty) {
      group.append(
        svgElement("circle", { cx: pointX, cy: pointY, r: 12, class: "score-point-citation-ring" }),
      );
    }
    group.append(
      modelGlyph(row.model_name, row.organization, pointX, pointY, 14, "score-point-glyph"),
    );
    // The same pinned-card system the curated chart uses (makeFrontierPointInteractive
    // + #frontier-tooltip), not a native <title>. Only the rows this source
    // actually carries are listed -- Instrument, Protocol and Read-from do not
    // exist in a crawled row (see the module comment above), and showing them
    // as "not recorded" here would manufacture filler where the curated card
    // shows real values. Date is real (see external_catalog.py's
    // date_precision), but it is the model's own announcement date, not a
    // measurement date, so the row label says so rather than reading as
    // equivalent to the curated chart's "Date".
    makeFrontierPointInteractive(group, {
      kind: t("Reported score"),
      title: `${row.organization || t("not recorded")} · ${row.model_name || t("not recorded")}`,
      rows: [
        { label: t("Organization"), value: row.organization || t("not recorded") },
        { label: t("Model"), value: row.model_name || t("not recorded") },
        { label: t("Score as reported"), value: String(row.raw_value ?? row.value) },
        ...(row.reported_date
          ? [
              {
                label: t("Date (model release)"),
                value: formatDate(row.reported_date, { dateStyle: "medium" }),
              },
            ]
          : []),
        { label: t("Reported by"), value: t("self reported") },
        ...(thirdParty ? [{ label: t("Cited by"), value: meta.name }] : []),
      ],
      url: row.source_url,
    });
    svg.append(group);
  }
  enableFrontierTouchTargets(svg);

  // Endpoint ticks, matching the curated chart's axis. They label the real
  // first and last release date rather than a padded range, for the same
  // reason the score ticks do (issue #269).
  if (span > 0) {
    const endpoints = [
      [margin.left, firstTime, "start"],
      [margin.left + plotWidth, lastTime, "end"],
    ];
    for (const [tickX, time, anchor] of endpoints) {
      svg.append(
        svgElement(
          "text",
          { x: tickX, y: height - 26, "text-anchor": anchor, class: "frontier-tick" },
          formatDate(new Date(time).toISOString().slice(0, 10), {
            year: "numeric",
            month: "short",
          }),
        ),
      );
    }
    // Quarter boundaries between the endpoints, so a point's date can be read
    // off the axis rather than interpolated (issue #298). Only quarters that
    // fall strictly inside the observed span are drawn, and only where they
    // clear the endpoint labels: the extremes stay the real first and last
    // release date, never a rounded range.
    const quarterGap = 46;
    const first = new Date(firstTime);
    const cursor = new Date(
      Date.UTC(first.getUTCFullYear(), Math.ceil((first.getUTCMonth() + 1) / 3) * 3, 1),
    );
    while (cursor.getTime() < lastTime) {
      const tickX = x(cursor.getTime());
      if (
        tickX - margin.left > quarterGap &&
        margin.left + plotWidth - tickX > quarterGap
      ) {
        svg.append(
          svgElement("line", {
            x1: tickX,
            y1: scoreTop + scoreHeight,
            x2: tickX,
            y2: scoreTop + scoreHeight + 5,
            class: "frontier-grid",
          }),
        );
        svg.append(
          svgElement(
            "text",
            { x: tickX, y: height - 26, "text-anchor": "middle", class: "frontier-tick" },
            formatDate(cursor.toISOString().slice(0, 10), {
              year: "numeric",
              month: "short",
            }),
          ),
        );
      }
      cursor.setUTCMonth(cursor.getUTCMonth() + 3);
    }
  }
  svg.append(
    svgElement(
      "text",
      {
        x: margin.left + plotWidth / 2,
        y: height - 7,
        "text-anchor": "middle",
        class: "frontier-axis-label",
      },
      // Says which date this is on the axis itself, not only in a tooltip a
      // reader has to open. Nothing here records when any of these scores was
      // actually measured; that qualification lives in the (i) note and the
      // chart's aria-label, so the axis names the date and stops.
      t("model release date"),
    ),
  );
  return svg;
}

function externalSourceTable(source, payload) {
  const meta = externalSourceMeta(source);
  const rows = payload.rows || [];
  const series = payload.series || {};
  const notes = [t(meta.noteKey)];
  // A declared maximum that observed values exceed is a fact about the source,
  // not a scale. Printed as a claim, used as nothing.
  if (series.max_score_contradicted) {
    notes.push(
      t("The source declares a maximum of {max} but carries values above it, so that bound is not a scale.").replace(
        "{max}",
        String(series.declared_max),
      ),
    );
  }
  // The chart replaces the table entirely: it draws the same shape the
  // curated saturation chart draws, from the same rows, and the table added
  // nothing the chart plus its pinned point cards did not already say.
  // Rows the chart cannot place are declared in the (i) note rather than on the
  // axis label, which names the date and nothing else (issue #298). Dropping
  // the count entirely would hide scores that exist.
  const undated = (payload.rows || []).filter(
    (row) =>
      typeof row.value === "number" &&
      Number.isFinite(row.value) &&
      !Number.isFinite(dateValue(row.reported_date)),
  ).length;
  if (undated) {
    notes.push(
      t("{n} row(s) have no release date, so they carry no position on this axis and are not drawn.").replace(
        "{n}",
        undated.toLocaleString(),
      ),
    );
  }
  const chart = externalScoreChart(source, payload);
  // The source name and the score count are on the panel subline now, so this
  // block carries no heading of its own: it repeated both and pushed the chart
  // ~150px down the page (issue #298). The provenance note is the one thing
  // that was only here, so it moves to the (i) beside the panel title.
  const infoHost = byId("frontier-heading-info");
  if (infoHost) replaceChildren(infoHost, [infoDisclosure(notes.join(" "))]);
  return element("div", { className: "external-source" }, [
    // frontier-chart's own layout class (position: relative, full-width svg)
    // rather than a bespoke one: the pinned tooltip's positioning math reads
    // its own parentElement as the clamp box, and reusing this class is what
    // makes that box behave identically to the curated chart's.
    chart
      ? element("div", { className: "frontier-chart" }, [chart, frontierTooltip()])
      : element("p", { className: "external-empty", text: t(meta.emptyKey) }),
  ]);
}

// Identity siblings are cross-links, never merges: a variant points at a
// related record the reader may have been looking for, and each link selects
// that record's own shard rather than folding it into this one.
function externalSiblingsBlock(shard) {
  const siblings = shard.siblings || [];
  if (!siblings.length) return null;
  const relationLabel = (relation) =>
    ({
      equivalent: t("same benchmark, other source"),
      "variant:split_sibling": t("related split"),
      "variant:framework_sibling": t("same framework"),
      "variant:introduced_in": t("introduced in the same paper"),
      "variant:of": t("has a related variant"),
    })[relation] || String(relation).replaceAll("_", " ");
  const items = siblings.map((sibling) => {
    const link = element("button", {
      className: "external-sibling-link",
      text: sibling.name,
      attrs: { type: "button" },
    });
    link.addEventListener("click", () => {
      selectFrontier(sibling.slug);
      const board = state.data?.model_card_leaderboard;
      if (board) renderAdoptionFrontier(board);
      writeUrl("push");
    });
    return element("li", {}, [
      link,
      element("span", {
        className: "external-sibling-meta",
        text: `${externalSourceMeta(sibling.source).name} · ${relationLabel(sibling.relation)}`,
      }),
    ]);
  });
  return element("section", { className: "external-block" }, [
    element("h3", { text: t("Related records") }),
    element("ul", { className: "external-siblings" }, items),
  ]);
}

function externalBenchmarkDetail(shard) {
  const detail = shard.record || {};
  // Scores first: it is the one block a reader came for on this panel (the
  // adjacent curated chart is a saturation-over-time view, and this is its
  // external-record counterpart), and it is the block most likely to have
  // content -- identity, openness and size are frequently "not established".
  return [
    externalScoresBlock(shard),
    externalIdentityBlock(detail),
    externalOpennessBlock(detail),
    externalSizesBlock(detail),
    externalSiblingsBlock(shard),
  ];
}

// The chart chrome only describes the curated score layer, so it is hidden
// while an external record occupies the panel. Hiding is the honest direction
// here: none of those elements could show anything but an empty state for a
// record the curated registry does not track, and an empty chart reads as "no
// score" where the truth is "not measured by this layer".
const CANONICAL_FRONTIER_CHROME = [
  "frontier-explainer-sub",
  "frontier-legend",
  "frontier-chart",
  "frontier-org-key",
  "frontier-score-readout",
  "frontier-evidence",
];

function setCanonicalFrontierChrome(visible) {
  for (const id of CANONICAL_FRONTIER_CHROME) {
    const node = byId(id);
    if (node) node.hidden = !visible;
  }
  const external = byId("frontier-external");
  if (external) {
    external.hidden = visible;
    // Emptied, not just hidden. A crawled record's DOM carries its own
    // tooltip and its own focusable points; left in place they stay in the
    // tab order and in every document-wide query behind a `hidden` attribute
    // that only affects painting (issue #261).
    if (visible) replaceChildren(external, []);
  }
}

// Shared shell for the three external states (record, loading, unavailable):
// heading, source badge where the curated path hides it, the curated picker
// still offering every scored canonical benchmark, and the message or detail
// in the external container.
// --- The benchmark picker ----------------------------------------------------
//
// One <select> over both layers, grouped rather than interleaved. The curated
// registry and the crawled catalog are separate namespaces (a `benchmark_id`
// against a source-prefixed `slug`), and they answer to different standards: a
// curated row carries an instrument, a protocol and a document publication
// date, so it can be drawn on a time axis; a crawled row carries none of those
// and renders as a table. A reader has to be able to tell which they are
// looking at before they click, so the group label says it.
//
// A crawled record with no readable score is omitted for the same reason its
// curated counterpart is: the panel would have nothing to show it.
function frontierPickerGroups(scored) {
  const groups = [
    [
      t("Curated registry"),
      [...scored]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((entry) => [entry.benchmark_id, entry.name]),
    ],
  ];
  const external = (state.benchmarkIndex || []).filter((record) => record.score_count > 0);
  for (const source of [...new Set(external.map((record) => record.source))].sort()) {
    groups.push([
      externalSourceMeta(source).name,
      external
        .filter((record) => record.source === source)
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((record) => [record.slug, record.name]),
    ]);
  }
  return groups.filter(([, rows]) => rows.length);
}

function renderFrontierPicker(scored, selectedValue) {
  replaceChildren(
    byId("frontier-benchmark"),
    frontierPickerGroups(scored).map(([label, rows]) =>
      element(
        "optgroup",
        // The count is on the label because the groups are wildly uneven (59
        // curated against several hundred crawled) and a reader scrolling a
        // long list deserves to know how far the group runs.
        { attrs: { label: `${label} (${rows.length.toLocaleString()})` } },
        rows.map(([value, name]) => option(value, name, value === selectedValue)),
      ),
    ),
  );
}

// "External benchmark · 115 reported scores · LLM Stats": what the eyebrow, the
// badge and the scores-block heading used to say between them, on one line
// (issue #298). The score count comes from the record rather than the shard so
// it is present before the shard lands.
function externalSubline(record, meta) {
  const parts = [t("External benchmark")];
  if (record.score_count) {
    parts.push(metricLabel(record.score_count, "reported score", "reported scores"));
  }
  parts.push(meta.name);
  return parts.join(" \u00b7 ");
}

function renderExternalShell(
  board,
  scored,
  { eyebrow, heading, badge, message, prependOption, subline },
) {
  clearFrontierPointSelection();
  setCanonicalFrontierChrome(false);
  // A shell replaces whatever chart was on screen, so no completion timer may
  // spend a reveal the reader is no longer looking at.
  drawnFrontierEntranceKey = null;
  // An empty eyebrow or badge is hidden rather than rendered blank: a crawled
  // record states its source once, on the subline, and repeating it in a
  // non-interactive chip beside the title read as broken state (issue #298).
  const eyebrowNode = byId("frontier-eyebrow");
  eyebrowNode.textContent = eyebrow || "";
  eyebrowNode.hidden = !eyebrow;
  byId("frontier-heading").textContent = heading;
  const stage = byId("frontier-stage");
  stage.className = "frontier-stage";
  stage.hidden = !badge;
  stage.textContent = badge || "";
  const sublineNode = byId("frontier-subline");
  if (sublineNode) {
    sublineNode.textContent = subline || "";
    sublineNode.hidden = !subline;
  }
  const infoHost = byId("frontier-heading-info");
  if (infoHost) replaceChildren(infoHost, []);
  renderFrontierPicker(scored, state.lfrontier);
  if (prependOption) {
    const picker = byId("frontier-benchmark");
    const [value, label] = prependOption;
    const existing = [...picker.options].find((candidate) => candidate.value === value);
    if (existing) existing.selected = true;
    else picker.prepend(option(value, label, true));
  }
  replaceChildren(byId("frontier-external"), [
    element("p", { className: "empty-state", text: message }),
  ]);
}

// Superseded shard paints are dropped: if the same record is rendered twice
// before its (cached) shard promise settles, only the latest call may paint,
// or the second paint would clear the entrance class before the browser ever
// drew the first frame.
let externalRenderSeq = 0;

function renderExternalBenchmark(board, scored, record) {
  const meta = externalSourceMeta(record.source);
  // One title, one metadata line. The eyebrow ("External catalog record") and
  // the source badge both said what this line says, and the reader had to read
  // three elements to learn one fact (issue #298).
  renderExternalShell(board, scored, {
    eyebrow: "",
    heading: record.name,
    badge: "",
    subline: externalSubline(record, meta),
    message: t("Loading benchmark details…"),
  });
  // Scored crawled records are in the picker already. An unscored one is not,
  // and it is still reachable by search, so it is prepended as its own option:
  // a <select> displaying a different benchmark than the one rendered would be
  // lying about the state.
  const picker = byId("frontier-benchmark");
  const existing = [...picker.options].find((candidate) => candidate.value === record.slug);
  if (existing) existing.selected = true;
  else picker.prepend(option(record.slug, `${record.name} · ${meta.name}`, true));
  const container = byId("frontier-external");
  const renderToken = ++externalRenderSeq;
  loadBenchmarkShard(record.slug).then((shard) => {
    // The reader may have moved on while the shard was on the wire; only paint
    // if this record is still the selection -- and only if no newer render of
    // this panel has superseded this callback.
    if (state.lfrontier !== record.slug) return;
    if (renderToken !== externalRenderSeq) return;
    if (!shard) {
      // A failed shard fetch leaves the index row and the selection in place;
      // only the panel reports the failure (display plan step 7).
      replaceChildren(container, [
        element("p", {
          className: "empty-state",
          text: t("Could not load details for this benchmark."),
        }),
      ]);
      return;
    }
    // The entrance is keyed to arriving at this record; a re-render after an
    // unrelated panel redraw does not replay it.
    container.classList.toggle(
      "score-chart-enter",
      frontierShouldAnimate(`external:${record.slug}`),
    );
    replaceChildren(container, externalBenchmarkDetail(shard));
  });
}

// Entry points for a reader who has nothing in mind to type, ranked by how
// many curated model cards report the benchmark. That ordering is the one
// reading this registry is built to make, so the list needs no editorial
// curation and no computed subheadings: "most reported" is both the rank and
// the reason a name is worth trying.
//
// Every row is a curated benchmark, because `card_count` is a curated fact:
// the crawled catalog records scores, not who chose to report them. The
// crawled layer is not hidden by this, it is reached from the search box and
// the picker, both of which cover all 679 scored crawled records alongside
// these.
const BENCHMARK_EXAMPLE_LIMIT = 20;

function renderBenchmarkNavigator(board) {
  // What this list ranks by, behind the same (i) toggle the crawled source
  // blocks use. "Most reported" alone invited the reading that AIME 2025 with
  // 115 crawled scores should outrank GPQA Diamond with 26 model cards (issue
  // #269); they answer different questions, and a reader cannot know that from
  // the heading alone.
  const infoHost = byId("benchmark-example-info");
  if (infoHost && !infoHost.firstChild) {
    const disclosure = infoDisclosure(
        t(
          "Ranked by how many curated model cards report each benchmark, which measures vendor reporting convention rather than benchmark quality. A crawled score count answers a different question: AIME 2025 carries 115 crawled scores and GPQA Diamond 26 model cards, and those are different measures rather than competing ones.",
      ),
    );
    // The panel is fixed (see styles.css: the navigator scrolls and would clip
    // it), so it carries no automatic anchor. Placed under the toggle each
    // time it opens, and clamped to the viewport so it never runs off-screen.
    const place = () => {
      const body = disclosure.querySelector(".info-disclosure-body");
      const box = disclosure.getBoundingClientRect();
      body.style.top = `${box.bottom + 6}px`;
      body.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - body.offsetWidth - 8))}px`;
    };
    disclosure.addEventListener("toggle", place);
    disclosure.addEventListener("pointerenter", place);
    disclosure.addEventListener("focusin", place);
    infoHost.append(disclosure);
  }
  const host = byId("benchmark-shortlist");
  if (host) {
    const examples = (board.entries || [])
      // Scored only, same rule as every other route into the panel: an example
      // that opens the no-score refusal is not an example.
      .filter((entry) => entry.card_count > 0 && scoreRecord(entry.benchmark_id))
      .sort((a, b) => b.card_count - a.card_count || a.name.localeCompare(b.name))
      .slice(0, BENCHMARK_EXAMPLE_LIMIT);
    replaceChildren(
      host,
      examples.map((entry) => {
        const card = element("button", {
          className: "benchmark-example",
          attrs: {
            type: "button",
            "aria-pressed": entry.benchmark_id === state.lfrontier ? "true" : "false",
          },
        }, [
          element("span", { className: "benchmark-example-name", text: entry.name }),
          // One count, and it is a fact about the world rather than about this
          // pipeline: how many vendors chose to report the benchmark. How many
          // of those mentions we could read a number out of is a statement
          // about our own collection, which is noise beside a figure.
          element("small", {
            className: "benchmark-example-meta",
            text: metricLabel(entry.card_count, "model card"),
          }),
        ]);
        card.addEventListener("click", () => {
          selectFrontier(entry.benchmark_id);
          renderAdoptionFrontier(board);
          writeUrl("push");
        });
        return card;
      }),
    );
  }
  // Binds the input and kicks off the crawled-index fetch on first call; a
  // no-op afterwards. Without it the box searches the curated layer only and
  // the reach line undercounts, which is how it read "59 benchmarks, 1 source".
  initBenchmarkSearch();
  renderBenchmarkSearch();
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
        ? t("Not a verbatim benchmark item. This description paraphrases the official source; open it for the exact tasks and scoring rules.")
        : t("Not a verbatim benchmark item. This is an illustrative format based on the recorded domain; use the official source for the exact tasks and scoring rules."),
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

// Whether a record's points span any time at all. A chart headed "over time"
// has to be drawn across at least two distinct dates; one date, or one point,
// is a reading rather than a trajectory however it is plotted.
function spansTime(record) {
  if (!record || record.observation_count < 2) return false;
  return Boolean(
    record.first_reported_at &&
      record.last_reported_at &&
      record.first_reported_at !== record.last_reported_at,
  );
}

// The plotted band for a score axis. Percent metrics are NOT drawn 0-100: every
// value in this corpus sits in the upper half, so a full-height axis compresses
// the interesting movement into a sliver. The band is padded around the observed
// range instead, and the axis is labelled with its real bounds so a reader
// cannot mistake a zoomed axis for a full one.
// The running best: for each date, the highest score anyone had reached by
// then (issue #288). Requested as a Pareto frontier "just like
// harbor-index.org", whose frontier plots cost against pass rate. This corpus
// records neither cost nor latency for any score -- a curated observation
// carries value/model/organization/reported_at/instrument/protocol, a crawled
// row carries value/model_name/reported_date -- so that chart cannot be drawn
// here without inventing the axis. Tracked separately.
//
// What IS drawable is the same idea on the axes this chart already has: the
// set of points nothing else beats, which on one score axis over time is the
// running maximum. It says "nothing had beaten this yet", never "these points
// are a series", so it does not reintroduce the segment the join rule forbids.
//
// But a maximum is still a comparability claim -- it says these numbers can be
// ranked against each other -- so callers must pass points that share an
// instrument and a protocol. The crawled layer cannot: it records neither, and
// its normalizer sets comparability to none, so it draws no line at all.
//
// Returns [] when the line would assert nothing: fewer than two distinct dates,
// or a single point.
function runningBestSteps(points, { descends = false } = {}) {
  const dated = points
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value))
    .sort((a, b) => a.time - b.time);
  if (dated.length < 2) return [];
  if (new Set(dated.map((point) => point.time)).size < 2) return [];
  const steps = [];
  let best = null;
  for (const point of dated) {
    // "Better" is not always larger: a lower-is-better metric improves
    // downward, and the frontier has to follow the metric rather than the
    // number, or it would trace the worst result on those benchmarks.
    const improves = best === null || (descends ? point.value < best : point.value > best);
    if (!improves) continue;
    best = point.value;
    steps.push({ time: point.time, value: best });
  }
  return steps.length >= 2 ? steps : [];
}

// Steps as an SVG path: horizontal to the next improvement's date, then
// vertical to its value. A diagonal would imply the score moved continuously
// between two reports, which is the interpolation this corpus cannot support.
function runningBestPath(steps, x, y, endX) {
  const parts = [`M ${x(steps[0].time)} ${y(steps[0].value)}`];
  for (const step of steps.slice(1)) {
    parts.push(`H ${x(step.time)}`);
    parts.push(`V ${y(step.value)}`);
  }
  parts.push(`H ${endX}`);
  return parts.join(" ");
}

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
      // "Best" ranks a field, and where the record holds one score there is no
      // field to top. "Only charted score" says the same number without the
      // implied competition it won, and is scoped to this chart on purpose:
      // one score here is not a claim that nobody else ever published one.
      element("span", {
        text: record.observation_count === 1 ? t("Only charted score") : t("Best on record"),
      }),
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
      // "comparable run" was jargon for a group of scores sharing an instrument
      // AND a protocol, which is the only condition under which two numbers on
      // this chart may be read against each other (issue #261). The count is
      // worth showing and the term was not: a reader should not have to learn
      // this project's vocabulary to know whether the values can be compared.
      // metricLabel's default pluralizer appends "s" to the last word, which
      // turned this into "0 set measured the same ways". The plural is passed
      // explicitly so the noun, not the trailing adverb, takes the inflection.
      element("small", {
        text: `${metricLabel(record.dated_observation_count, "date")} · ${metricLabel(
          record.comparable_series_count,
          "set measured the same way",
          "sets measured the same way",
        )}`,
      }),
    ]),
  );

  return element("div", { className: "score-readout-inner" }, [
    element("div", { className: "score-readout-figures" }, rows),
    // Scores first, method second: the figures above are the numbers a reader
    // came for, and the supports/does-not-support prose is the reasoning behind
    // them. Collapsed by default so it stays one tap away rather than pushing
    // the next benchmark's figures further down the page.
    element("details", { className: `score-evidence score-evidence-${evidence.id}` }, [
      element("summary", {}, [element("strong", { text: evidence.label })]),
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
  // Unreachable on the canonical path (the picker only lists scored benchmarks),
  // but the message stays honest rather than naming a chart that does not draw.
  if (!record) {
    replaceChildren(host, [
      element("p", {
        className: "score-readout-empty",
        text:
          t("No score for this benchmark could be read verbatim from the cited documents. An absent value is not a zero and not a plateau."),
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

// Each chart owns its tooltip. The curated panel mounts one inside
// #frontier-chart and every crawled source block mounts another inside
// #frontier-external, so a document-wide id is not an address: getElementById
// returns the first match, #frontier-external sits above #frontier-chart in
// index.html, and the curated chart's card ends up written into the crawled
// chart's hidden node (issue #261 -- hover and click both looked dead because
// they shared one lookup). The id is still unique per instance because
// aria-describedby has to point at something, and `frontierTooltipFor` reads
// the point's own chart rather than the document.
let frontierTooltipSeq = 0;

function frontierTooltip() {
  const tooltip = element("div", {
    className: "frontier-tooltip",
    attrs: {
      id: `frontier-tooltip-${++frontierTooltipSeq}`,
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
    // Same reasoning as positionFrontierTooltip: walk from the tooltip's own
    // parent rather than the curated chart's id, so Tab-to-next-point also
    // works inside the crawled chart's copy of this tooltip.
    const points = [...tooltip.parentElement.querySelectorAll("[data-frontier-point]")];
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

// The tooltip belonging to the chart this point is drawn in. Falls back to a
// document-wide lookup only for a detached node, which no live point is.
function frontierTooltipFor(node) {
  return node?.closest(".frontier-chart")?.querySelector(".frontier-tooltip") || null;
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
  // The host is wherever the tooltip actually lives, not a hardcoded id: the
  // curated chart mounts it inside #frontier-chart, and the crawled chart
  // mounts an identical instance inside #frontier-external so an external
  // record's points get the same pinned card. Positioning math only needs a
  // bounding box to clamp against, and the tooltip's own parent is that box.
  const host = tooltip.parentElement;
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
  const tooltip = frontierTooltipFor(describedFrontierPoint);
  if (!tooltip || tooltip.hidden || !describedFrontierPoint) return;
  positionFrontierTooltip(tooltip, describedFrontierPoint);
}

function showFrontierTooltip(group, details, { pinned = false } = {}) {
  const tooltip = frontierTooltipFor(group);
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
  const tooltip = frontierTooltipFor(describedFrontierPoint);
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
    const tooltip = frontierTooltipFor(selectedFrontierPoint);
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
    const tooltip = frontierTooltipFor(group);
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
    frontierTooltipFor(group)?.querySelector("a")?.focus();
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
      const points = [
        ...(frontierTooltipFor(group)?.parentElement?.querySelectorAll("[data-frontier-point]") ||
          []),
      ];
      const next = points[points.indexOf(selectedFrontierPoint) + 1];
      if (group === next) {
        event.preventDefault();
        selectedFrontierSourceVisited = false;
        showFrontierTooltip(selectedFrontierPoint, selectedFrontierDetails, { pinned: true });
        frontierTooltipFor(selectedFrontierPoint)?.querySelector("a")?.focus();
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

// A legend keyed to the marks actually on the chart. Only score marks remain:
// the staircase and rug keys went with their bands, since a key describing
// marks that are not on screen is worse than no key.
function renderFrontierLegend(entry, record) {
  const host = byId("frontier-legend");
  if (!host) return;
  const swatch = (className) => element("span", { className: `legend-swatch ${className}` });
  const items = [];
  if (record) {
    // One phrase, not a label plus a restatement of the label. "Score read
    // from a document / one value read verbatim from a cited document" said
    // the same thing twice beside a single dot.
    items.push(["legend-swatch-score", t("One score, copied from the report that published it"), ""]);
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

// The per-organization color key under the chart. Each organization with a
// plotted score gets a small circular chip in its frontier color carrying its
// brand glyph, so the reader can map a colored glyph on the chart back to a
// name without hovering (issue #178, HLE/harbor style). Built from the score
// record itself, whose observations are in date order: an organization whose
// card carried no readable number is not keyed to a chart it does not appear
// on.
function renderFrontierOrgKey(record) {
  const host = byId("frontier-org-key");
  if (!host) return;
  const ordered = [];
  const seen = new Set();
  for (const observation of record?.observations || []) {
    if (seen.has(observation.organization)) continue;
    seen.add(observation.organization);
    ordered.push(observation.organization);
  }
  if (!ordered.length) {
    replaceChildren(host, []);
    return;
  }
  replaceChildren(
    host,
    ordered.map((org) => {
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

// The saturation curve: every score read verbatim from a cited document, on a
// publication-time axis. The adoption staircase that used to lead this chart
// was retired: a staircase of who reported when answers a different question,
// and the score track carries strictly more of what a reader came for. So the
// score band now gets the full height the staircase, the card rug, and the
// inter-band gaps vacated, and the only marks on the chart are the scores, the
// connections the join rule permits, and the reading gap.
// Entrance timing for the score charts (issue #312). A point brightens while
// the drawing front crosses its date, so the reveal reads left to right the
// way the data does. 120ms lets the line start first; 780ms spreads the
// points across the 900ms drawing window. Shared by both layers so a reader
// never learns two reveal behaviors for one kind of mark.
function frontierPointRevealDelay(pointX, margin, plotWidth) {
  return Math.round(120 + ((pointX - margin.left) / plotWidth) * 780);
}

// The entrance plays when the reader arrives at a benchmark and runs to
// completion before it is spent. The crawled catalog settling mid-reveal
// re-renders this panel, and a key spent on first paint would cancel the very
// reveal it was drawn for: same-selection repaints inside the window replay
// the entrance from its start rather than cutting it off, and once the window
// closes the selection counts as seen, so later repaints render finished.
// The key commits only while the Leaderboard is the visible view: a redraw
// into a hidden panel must not spend an entrance the reader has yet to see.
const FRONTIER_ENTRANCE_MS = 1400;
let completedFrontierEntranceKey = null;
let frontierEntranceTimer = null;
let drawnFrontierEntranceKey = null;

function frontierShouldAnimate(key) {
  if (state.view !== "leaderboard") return false;
  // Remember what is actually on screen: the completion callback below may
  // fire after the reader has moved to another benchmark.
  drawnFrontierEntranceKey = key;
  const done = completedFrontierEntranceKey === key;
  if (!done) {
    clearTimeout(frontierEntranceTimer);
    const spendOrDefer = () => {
      // Spending the entrance requires that it was seen to the end: a hidden
      // tab defers its own completion, and a reader who navigated away -- to
      // another view or another benchmark -- gets the reveal again on return.
      if (
        typeof document !== "undefined" &&
        document.visibilityState !== "visible"
      ) {
        frontierEntranceTimer = setTimeout(spendOrDefer, FRONTIER_ENTRANCE_MS);
        return;
      }
      if (state.view === "leaderboard" && drawnFrontierEntranceKey === key) {
        completedFrontierEntranceKey = key;
      }
    };
    frontierEntranceTimer = setTimeout(spendOrDefer, FRONTIER_ENTRANCE_MS);
  }
  return !done;
}

function scoreTrackChart(entry, board) {
  const record = scoreRecord(entry.benchmark_id);
  // Callers only ever select a benchmark that has a score record; this guard is
  // for the defensive case, since a chart with no points reads as "scores went
  // to zero here", which is worse than no chart.
  if (!record) return null;
  // This benchmark's own dated mentions are not drawn, but the newest one still
  // bounds the reading-gap marker below: "still mentioned, nothing newer could
  // be read" is a claim that needs the mention date. The registry-wide newest
  // card is never consulted: an unrelated vendor's recent document is not
  // evidence that this benchmark went unread (shipped Arena-Hard and Aider
  // Polyglot have no adopter newer than their last score).
  const lastMention = frontierEvents(entry).at(-1)?.published;
  const startText = record.first_reported_at;
  const endText = [lastMention, record.last_reported_at].filter(Boolean).sort().at(-1);
  const start = new Date(`${startText}T00:00:00Z`).getTime();
  const rawEnd = new Date(`${endText}T00:00:00Z`).getTime();
  const end = Math.max(rawEnd, start + 86_400_000);
  // A narrower viewBox on a narrow viewport. `width: 100%` scales height with
  // width, so a 920-unit box at 390px CSS pixels rendered the whole chart about
  // 90px tall and the marks became unreadable. Halving the coordinate width
  // lets the same content scale up rather than being squashed; distorting the
  // aspect ratio instead would stretch the axis text illegibly.
  const narrow = typeof window !== "undefined" && window.innerWidth <= 760;
  const width = narrow ? 520 : 920;
  const band = scoreBand(record);
  // 480 = the old staircase plot (276) plus the band gap (34), the card rug
  // (26) and its gap (12), over the old 132-unit strip. The y-axis is zoomed to
  // the observed range, so the vacated height is vertical resolution for the
  // one thing about this band a reader must not misjudge.
  const scoreHeight = 480;
  // The left margin is wider than the site's other charts because the axis
  // label is a metric name ("resolved", "pass@1") rather than a fixed word,
  // and a 52px gutter clipped the longer ones at the viewBox edge.
  const margin = { top: 32, right: 20, bottom: 62, left: 68 };
  const plotWidth = width - margin.left - margin.right;
  const height = margin.top + scoreHeight + margin.bottom;
  const x = (date) =>
    margin.left +
    ((new Date(`${date}T00:00:00Z`).getTime() - start) / (end - start)) * plotWidth;
  const scoreTop = margin.top;
  // Better is always up. `direction` exists in the schema precisely so a metric
  // where lower wins (an edit distance, an error rate) does not render its
  // improvements as a downward slope; consulting it here is what makes the axis
  // mean "better" rather than "larger".
  const scoreDescends = record.direction === "lower_is_better";
  const scoreY = (value) => {
    if (band.high <= band.low) return scoreTop + scoreHeight / 2;
    const fraction = (value - band.low) / (band.high - band.low);
    const fromFloor = scoreDescends ? 1 - fraction : fraction;
    return scoreTop + scoreHeight - fromFloor * scoreHeight;
  };

  const svg = svgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    // A group rather than an image: image descendants are presentational in the
    // accessibility tree, which would hide the interactive marker buttons.
    role: "group",
    "aria-label":
      `${entry.name} scores over time. ${metricLabel(
        record.observation_count,
        "score read from a document",
        "scores read from a document",
      )} from ${formatDate(record.first_reported_at, { dateStyle: "medium" })} to ` +
      `${formatDate(record.last_reported_at, { dateStyle: "medium" })}, best ` +
      `${record.saturation.best_value}.`,
  });

  {
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

    // No segment joins any two score points, in either layer.
    //
    // A shared instrument and protocol makes two numbers *comparable*. It does
    // not make them a *series*, and a drawn segment asserts the second. On
    // shipped GPQA Diamond the join rule connected DeepSeek-V4-Pro (90.1) to
    // DeepSeek-V4-Flash (88.1) and drew a decline, when the later point is a
    // smaller model rather than a regression over time; the cross-vendor pair
    // (Gemma 4 31B to GLM-5.1) implied a trajectory between two systems that
    // share nothing but a protocol string. Both are the same error the reading
    // gap exists to prevent, and neither is fixable by restricting which pairs
    // may join, because the defect is in the segment, not in the pairing.
    //
    // Comparability is still computed and still stated: it drives the paired
    // comparison readout below the chart, which says in words what a pair of
    // dates does and does not support. Words can carry that caveat; a line
    // cannot.

    // The frontier: where the best-so-far actually rose (issue #288). The
    // requested cost-versus-score chart cannot be drawn from this corpus, which
    // records no cost for any score; this is the same idea on the axes the
    // chart already has. It asserts only that nothing had beaten a value yet,
    // never that the points between are a series -- which is why it coexists
    // with the join rule that forbids connecting adjacent points.
    // Partitioned by instrument AND protocol, the same rule the join uses. A
    // max across protocols is still a comparability claim: on GPQA Diamond the
    // observations run "Pass@1, 8K output limit" beside "averaged over 10
    // samples", and ranking those against each other asserts they measure the
    // same thing (issue #288 review).
    //
    // The largest comparable group wins the line, so the chart draws the one
    // run it can actually speak to rather than a mixture it cannot.
    const runs = new Map();
    for (const observation of record.observations) {
      const key = `${observation.instrument || ""}\u0000${observation.protocol || ""}`;
      if (!runs.has(key)) runs.set(key, []);
      runs.get(key).push({
        time: new Date(`${observation.reported_at}T00:00:00Z`).getTime(),
        value: observation.value,
      });
    }
    // Same-date readings collapse to their directional best before anything
    // reads them: drawn in source order, the line could step twice on one
    // date and pass through an inferior number that shares a better reading's
    // date. Collapsing here means the steps, and the membership marks derived
    // from them, can never disagree.
    const collapsedRuns = [...runs.entries()].map(([key, points]) => {
      const bestByDate = new Map();
      for (const point of points) {
        const current = bestByDate.get(point.time);
        if (
          current === undefined ||
          (scoreDescends ? point.value < current : point.value > current)
        ) {
          bestByDate.set(point.time, point.value);
        }
      }
      const collapsed = [...bestByDate.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([time, value]) => ({ time, value }));
      return { key, points: collapsed };
    });
    // The line belongs to exactly one comparable run -- the one with the most
    // advances (issue #288). Its steps draw it; its best-so-far holders light
    // up with it.
    const runSteps = collapsedRuns.map(({ key, points }) => ({
      key,
      points,
      steps: runningBestSteps(points, { descends: scoreDescends }),
    }));
    const frontier = runSteps.sort((a, b) => b.steps.length - a.steps.length)[0];
    const frontierSteps = frontier?.steps;
    // Which points the saturation line is made of (issue #312's definition):
    // within that run, every reading that holds the best value as of its
    // date. These stay at full emphasis; all other points fade back so the
    // eye lands on the line first. Membership is keyed by run, then time and
    // value, so an unrelated run reporting the same number on the same date
    // is not mistaken for the line. Gated on the line actually existing -- a
    // benchmark whose history holds no comparable pair draws no line, so
    // nothing may dim behind an absent reference.
    const frontierMarks = new Set();
    if (frontier && frontier.steps.length) {
      let best = null;
      for (const point of frontier.points) {
        if (best === null || (scoreDescends ? point.value < best : point.value > best)) {
          best = point.value;
        }
        if (point.value === best) {
          frontierMarks.add(`${frontier.key}\u0000${point.time}\u0000${point.value}`);
        }
      }
    }
    if (frontierSteps?.length) {
      svg.append(
        svgElement("path", {
          d: runningBestPath(
            frontierSteps,
            (time) => x(new Date(time).toISOString().slice(0, 10)),
            scoreY,
            margin.left + plotWidth,
          ),
          class: "score-frontier-line",
          fill: "none",
          // Normalized length: the entrance animation (issue #312) draws the
          // line with a dash offset from 1 to 0, which needs a total length
          // known in advance. Measuring geometry on this detached tree is not
          // portable, so the length is declared instead.
          pathLength: "1",
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
      const pointX = x(observation.reported_at);
      const pointY = scoreY(observation.value);
      // "其他的点可以淡化" (issue #312): readings that are not part of the
      // saturation line recede behind it -- but only while there IS a line.
      // A benchmark with no comparable pair draws no reference, so every
      // point keeps full emphasis rather than all of it receding together.
      // Hover and focus restore a receded point, so de-emphasis never costs
      // legibility. Membership is looked up under the observation's own
      // comparable run, so a same-date same-value reading from another run
      // stays off the line.
      const onFrontier = frontierMarks.has(
        `${observation.instrument || ""}\u0000${observation.protocol || ""}\u0000${new Date(
          `${observation.reported_at}T00:00:00Z`,
        ).getTime()}\u0000${observation.value}`,
      );
      const offTheLine = Boolean(frontierSteps?.length) && !onFrontier;
      // Entrance order follows the axis (issue #312): each point brightens
      // while the drawing front crosses its date, so the reveal reads left to
      // right the way the data does. The timing is shared with the crawled
      // layer's chart so both figures reveal the same way.
      const revealDelay = frontierPointRevealDelay(pointX, margin, plotWidth);
      const group = svgElement("g", {
        class: `score-point${
          offTheLine ? " score-point-dim" : ""
        }${observation.reported_by ? " score-point-third-party" : ""}`,
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "data-frontier-point": "",
        style: `--reveal-delay:${revealDelay}ms`,
        "aria-label":
          `${observation.value} ${record.metric} ${t("by")} ${observation.model} ` +
          `(${observation.organization}), ${formatDate(observation.reported_at, {
            dateStyle: "medium",
          })}, ${t("run conditions")} ${observation.protocol}` +
          (observation.reported_by ? `, ${t("cited by")} ${observation.reported_by}` : "") +
          `. ${t("Click to pin record details")}.`,
      });
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
        kind: t("Score read from a document"),
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
          { label: t("Test variant"), value: observation.instrument },
          { label: t("Run conditions"), value: observation.protocol },
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
      // Centred on the span, except when the span runs to the end of the axis:
      // a centred label there puts half its width past the right gutter and the
      // viewBox clips it, which on shipped GPQA Diamond left the reader with
      // "NO READABLE SCORE IN THI". Anchoring to the span's right end instead
      // keeps the whole string inside without measuring text, which is not
      // available on a detached SVG and would differ per locale anyway.
      const gapReachesAxisEnd = endX >= margin.left + plotWidth - 1;
      svg.append(
        svgElement(
          "text",
          {
            x: gapReachesAxisEnd ? endX : (lastScoreX + endX) / 2,
            y: scoreTop + scoreHeight + 18,
            "text-anchor": gapReachesAxisEnd ? "end" : "middle",
            class: "score-gap-label",
          },
          t("no score read from a document in this window"),
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
  svg.append(
    svgElement(
      "text",
      { x: margin.left + plotWidth / 2, y: height - 7, "text-anchor": "middle", class: "frontier-axis-label" },
      t("document publication date"),
    ),
  );
  enableFrontierTouchTargets(svg);
  return svg;
}

function clearAdoptionFrontier(message) {
  clearFrontierPointSelection();
  // Every caller of this is on the curated path, so the canonical chrome is
  // restored here rather than at each call site: an external selection that
  // hid it must not leave the next canonical render missing its chart blocks.
  setCanonicalFrontierChrome(true);
  // The empty state replaces any chart on screen, so a running completion
  // timer must not spend its reveal.
  drawnFrontierEntranceKey = null;
  byId("frontier-eyebrow").textContent = t("Scores over time");
  const stage = byId("frontier-stage");
  stage.textContent = "";
  // The badge only carries the source name on the external path; an empty one
  // would render as a bare outline beside the picker.
  stage.hidden = true;
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
  // The panel is the saturation curve now, so a benchmark enters the picker
  // only when a score could be read verbatim from a cited document. 20 of the
  // 79 adopted benchmarks carry card mentions without a single readable score;
  // with the adoption staircase retired they would render an empty panel, so
  // they are absent here and a permalink to one falls back to the default.
  const scored = adopted.filter((entry) => scoreRecord(entry.benchmark_id));
  const defaultEntry = frontierDefaultEntry(board);
  if (!scored.length || !defaultEntry) {
    clearAdoptionFrontier(t("No benchmark in this registry has a score read from a document yet."));
    return;
  }
  // Resolution order is the permalink contract (display plan step 6): an exact
  // external slug first, then a canonical registry id so links shared before
  // the widening keep working, then nothing. The slug check is what makes the
  // 594 llm-stats-only benchmarks addressable rather than merely counted.
  const slugRecord = state.lfrontier
    ? (state.benchmarkIndex || []).find((record) => record.slug === state.lfrontier)
    : null;
  if (slugRecord) {
    renderBenchmarkNavigator(board);
    renderExternalBenchmark(board, scored, slugRecord);
    return;
  }
  // A canonical id that the registry knows but the score layer does not. Before
  // the panel became the score track this resolved and drew an adoption
  // staircase, so links to these 20 benchmarks are already out there. Falling
  // through to the default would show a different benchmark under the reader's
  // own URL with nothing to say so, which is worse than an explicit refusal.
  // The index is not consulted: a canonical id and an external slug are separate
  // namespaces (every slug is source-prefixed), so no pending fetch can change
  // this answer.
  //
  // Resolved against every registry entry, not just the adopted ones. `adopted`
  // is gated on card_count > 0, so a benchmark recorded before any model card
  // reports it was invisible here and fell through to the default: issue #287,
  // where ?lfrontier=rsi_bench drew AutomationBench's track, its 31.8% best on
  // record and its model points, under a URL still reading rsi_bench and with
  // nothing on the page saying so. A benchmark nobody has scored is exactly the
  // one a reader is most likely to ask about, so it has to answer for itself.
  const unscoredEntry = state.lfrontier
    ? (board.entries || []).find(
        (candidate) =>
          candidate.benchmark_id === state.lfrontier && !scoreRecord(candidate.benchmark_id),
      )
    : null;
  if (unscoredEntry) {
    renderBenchmarkNavigator(board);
    renderExternalShell(board, scored, {
      eyebrow: t("Scores over time"),
      heading: unscoredEntry.name,
      // Same contract renderExternalBenchmark keeps for crawled records: the
      // picker only lists scored benchmarks, so an unscored selection matches
      // no option and the browser falls back to showing the first one. A
      // <select> reading AA-LCR beside a panel headed RSI-Bench is lying about
      // the state, so the selection is prepended as its own option.
      prependOption: [unscoredEntry.benchmark_id, unscoredEntry.name],
      badge: "",
      // Two different absences, and a reader chasing a brand-new benchmark
      // wants to know which one they hit. No card has reported it yet is a
      // statement about the field's attention; cards report it but no score
      // could be read verbatim is a statement about our sources.
      message: unscoredEntry.card_count
        ? t(
            "No score for this benchmark could be read verbatim from the cited documents, so there is no track to draw. An absent value is not a zero and not a plateau.",
          )
        : t(
            "No model card in this registry reports this benchmark yet, so there is no score to draw. That zero is a reading, not a gap in the collection.",
          ),
    });
    return;
  }
  let entry = scored.find((candidate) => candidate.benchmark_id === state.lfrontier);
  if (!entry && state.lfrontier && !state.benchmarkIndexLoaded) {
    // A permalink whose index is still on the wire. Hold the selection and say
    // so: snapping to the default now would rewrite the reader's URL before
    // the slug could even be checked, and initBenchmarkSearch re-renders this
    // panel when the fetch settles.
    renderBenchmarkNavigator(board);
    renderExternalShell(board, scored, {
      eyebrow: t("Scores over time"),
      heading: state.lfrontier,
      badge: "",
      message: t("Loading benchmark details…"),
    });
    return;
  }
  if (!entry && state.lfrontier && !state.benchmarkIndex) {
    // The index fetch failed, so a slug can never resolve. The panel says so
    // outright; the selection and the URL stay as the reader wrote them.
    renderBenchmarkNavigator(board);
    renderExternalShell(board, scored, {
      eyebrow: t("Scores over time"),
      heading: state.lfrontier,
      badge: "",
      message: t("Could not load details for this benchmark."),
    });
    return;
  }
  if (!entry) {
    // The requested benchmark does not exist. Falling back to the default is
    // right -- an empty panel is worse -- but the URL must stop naming a
    // benchmark the panel is not showing, or a shared link reads as evidence
    // about the wrong thing (the defect issue #287 fixed for canonical ids,
    // which crawled slugs could still reach).
    //
    // Repaired here rather than at the call sites because this is the one
    // place the substitution happens, and it happens on three different paths:
    // first load, the re-render after the crawled index settles, and Back.
    const substituted = Boolean(state.lfrontier);
    state.lfrontier = defaultEntry.benchmark_id;
    state.lfrontierExplicit = false;
    entry = defaultEntry;
    // replaceState, never push: the reader did not navigate, an address that
    // was already wrong got corrected.
    if (substituted && state.view === "leaderboard") writeUrl();
  }
  setCanonicalFrontierChrome(true);
  // The stage badge is an adoption reading ("Saturated reporting" is a judgement
  // about who reports, not about scores), so the canonical path leaves it empty
  // and hidden. The external path reuses the element for the source name.
  const stageBadge = byId("frontier-stage");
  stageBadge.textContent = "";
  stageBadge.hidden = true;
  renderFrontierPicker(scored, state.lfrontier);
  renderBenchmarkNavigator(board);

  const record = scoreRecord(entry.benchmark_id);
  // "over time" promises a series, and 15 of the 59 charted benchmarks hold a
  // single score: GSM8K read "GSM8K reported scores over time" above one point
  // from March 2024. One reading is not a trajectory, and the heading is the
  // first thing that sets the expectation, so it says which of the two it is.
  //
  // The test is two distinct dates rather than two observations. Scores that
  // all share one date span no time however many there are, so counting rows
  // would be the wrong question to ask even though no benchmark is in that
  // state today.
  // The heading is the benchmark's name. What kind of picture this is -- a
  // track over time, or a single reading that is not one -- moves to the
  // eyebrow above it, which used to say "Scores over time" regardless and so
  // repeated the heading rather than qualifying it.
  byId("frontier-heading").textContent = entry.name;
  byId("frontier-eyebrow").textContent = spansTime(record)
    ? t("Scores over time")
    : metricLabel(record?.observation_count || 0, "charted score");
  renderFrontierLegend(entry, record);
  renderFrontierOrgKey(record);
  clearFrontierPointSelection();
  byId("frontier-chart").classList.toggle(
    "score-chart-enter",
    frontierShouldAnimate(`curated:${entry.benchmark_id}`),
  );
  replaceChildren(byId("frontier-chart"), [scoreTrackChart(entry, board), frontierTooltip()]);
  renderScoreReadout(entry);
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
  // A benchmark with no readable score is no longer focusable either: the panel
  // is the score track now, so the jump would land on the default entry instead
  // of the benchmark the finding is about.
  const target = finding.benchmark_id
    ? (board.entries || []).find(
        (entry) => entry.benchmark_id === finding.benchmark_id && scoreRecord(entry.benchmark_id),
      )
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
      writeUrl("push");
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
      element("span", { className: "benchmark-new-badge", text: t("new benchmark") }),
    );
  }

  // The jump targets the saturation curve, so it is only offered when a score
  // could be read: for the 20 adopted benchmarks without one it would snap to
  // the default entry and lie about what it opened.
  const frontierButton = scoreRecord(entry.benchmark_id)
    ? element("button", {
        className: "secondary-link frontier-jump",
        text: t("View score track ↑"),
        attrs: { type: "button" },
      })
    : null;
  frontierButton?.addEventListener("click", () => {
    selectFrontier(entry.benchmark_id);
    renderAdoptionFrontier(board);
    writeUrl("push");
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

// The page is named after this ranking, so it leads (issue #256). Five lines,
// one measure, and nothing about how the number was computed: a reader who
// wants only the ranking never has to read the methodology, and the full table
// underneath still carries the filters and every remaining benchmark.
//
// `board.entries` arrives ranked by adoption_rank (model_cards.py), which
// breaks card-count ties on organization count and then name. Re-sorting here
// on card_count alone would disagree with entry.rank and print a row numbered
// 05 in position 04, so the order is read, never recomputed.
const LEADERBOARD_TOP_LIMIT = 5;

function renderLeaderboardTop(board) {
  const host = byId("leaderboard-top-list");
  if (!host) return;
  // The eyebrow, the h1, the deck and the "How to read this evidence" note all
  // sat between the page title and the figure, saying four things about one
  // ranking. They are one (i) beside the heading now: a reader who wants the
  // caveat opens it, and a reader who wants the ranking sees the ranking.
  const infoHost = byId("leaderboard-top-info");
  if (infoHost && !infoHost.firstChild) {
    // `board.measures` is published data, not a string restated here. A reader
    // who takes this order as a quality ranking draws the opposite of the
    // intended conclusion, and the correction has to travel with the payload
    // that produced the order rather than drift from it in the browser.
    infoHost.append(
      infoDisclosure(
        [
          board.measures,
          t(
            "A report counts once per test, even if it lists that test several times. Some reports publish their results as a picture rather than text, and we read those with software that can misread a digit, so the list at the bottom of this page links every count back to the report it came from.",
          ),
        ]
          .filter(Boolean)
          .join(" "),
      ),
    );
  }
  const ranked = (board.entries || []).filter((entry) => entry.card_count > 0);
  const entries = state.leaderboardTopExpanded ? ranked : ranked.slice(0, LEADERBOARD_TOP_LIMIT);
  const more = byId("leaderboard-top-more");
  // A registry where nothing is reported yet is a real state, not a bug, and
  // five blank lines is a worse answer than saying so.
  if (!entries.length) {
    replaceChildren(host, [
      element("li", {
        className: "empty-state",
        text: t("No model card in this registry reports a benchmark yet."),
      }),
    ]);
    if (more) more.hidden = true;
    return;
  }
  // Each row's bar is scaled against the top entry currently on screen, so the
  // gap the reader is meant to see (e.g. GPQA Diamond vs. everything below it)
  // stays visible whether five rows are shown or all of them are (issue #314).
  const maxCount = Math.max(...entries.map((entry) => entry.card_count));
  replaceChildren(
    host,
    entries.map((entry) =>
      element("li", { className: "leaderboard-top-row" }, [
        element("span", {
          className: "leaderboard-top-rank",
          text: String(entry.rank).padStart(2, "0"),
        }),
        element("span", { className: "leaderboard-top-name", text: entry.name }),
        element("span", { className: "leaderboard-top-bar" }, [
          element("span", {
            className: "leaderboard-top-bar-fill",
            attrs: { style: `width:${((entry.card_count / maxCount) * 100).toFixed(1)}%` },
          }),
        ]),
        element("span", {
          className: "leaderboard-top-count",
          text: metricLabel(entry.card_count, "model card"),
        }),
      ]),
    ),
  );
  if (more) {
    more.hidden = ranked.length <= LEADERBOARD_TOP_LIMIT;
    more.textContent = state.leaderboardTopExpanded
      ? `${t("Show top {n}").replace("{n}", String(LEADERBOARD_TOP_LIMIT))} ↑`
      : `${t("Show all {n} benchmarks").replace("{n}", String(ranked.length))} ↓`;
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
  renderLeaderboardTop(board);
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
  // Crawled totals, shown beside the curated ones rather than folded into them:
  // a model card and a crawled leaderboard row are different kinds of evidence
  // (one cites a document with a protocol, the other does not), so the two
  // counts stay two counts. Absent until the index has loaded (it fetches
  // async on first search-panel init); the tile falls back to the curated
  // figure alone rather than showing a stale or invented crawled total.
  const crawledIndex = state.benchmarkIndex || [];
  const crawledWithScores = crawledIndex.filter((record) => record.score_count > 0).length;
  replaceChildren(byId("leaderboard-insights"), [
    evidenceDisclosure(
      {
        value: board.model_card_count,
        label: t("source documents"),
        detail: state.benchmarkIndexLoaded
          ? t("Each document counts once per benchmark. Plus {count} crawled benchmark records from {sources}.", {
              count: crawledIndex.length.toLocaleString(),
              sources: [...new Set(crawledIndex.map((record) => externalSourceMeta(record.source).name))]
                .sort()
                .join(", "),
            })
          : t("Each document counts once per benchmark."),
      },
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
        detail:
          t("across {domains}{listed}.", {
            domains: metricLabel(domainCount, "domain"),
            listed: board.entries.length ? ` · ${metricLabel(board.entries.length, "benchmark")} ${t("listed")}` : "",
          }) +
          (state.benchmarkIndexLoaded
            ? ` ${t("{count} more in the crawled catalog, {withScores} with a reported score.", {
                count: crawledIndex.length.toLocaleString(),
                withScores: crawledWithScores.toLocaleString(),
              })}`
            : ""),
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
        element("strong", { text: t("New benchmarks") }),
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
            text: `${t("Last curated on")} ${formatDate(card.retrieved_at, {
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
  const explorer = byId("relationship-explorer");
  const entityTypes = corpus.aggregates?.entity_types || {};

  renderMapInsights(corpus);
  byId("map-summary").textContent =
    `${Number(entityTypes.artifact || 0).toLocaleString()} ${t("items")} · ` +
    `${Number(entityTypes.organization || 0).toLocaleString()} ${t("organizations")} · ` +
    `${Number(entityTypes.source || 0).toLocaleString()} ${t("sources")} · ` +
    `${Number(entityTypes.topic || 0).toLocaleString()} ${t("topics")}`;

  // A permalink to a node is an explicit request for the deep view. Otherwise
  // keep the expensive, thousands-of-node canvas out of the DOM until the
  // reader asks for it.
  if (selectedFromUrl) explorer.open = true;
  if (!explorer.dataset.renderBound) {
    explorer.dataset.renderBound = "true";
    explorer.addEventListener("toggle", () => {
      if (explorer.open) renderTrendMap();
      else replaceChildren(byId("map-canvas"), []);
    });
  }
  if (!explorer.open) {
    replaceChildren(byId("map-canvas"), []);
    return;
  }

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
    "aria-label": t("Items connected to topics, organizations, and sources"),
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
        {
          source: t("Sources"),
          organization: t("Organizations"),
          artifact: t("Items"),
          topic: t("Topics"),
        }[type],
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
  replaceChildren(byId("map-canvas"), [svg]);
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
        element("span", {
          text: `${item.source} · ${eventVerb(item)}`,
          // The relative time on the row carries the exact timestamp on
          // hover, matching the evidence rows (issue #248).
          attrs: {
            title: eventTimestamp(item)
              ? `${formatDate(eventTimestamp(item), { dateStyle: "medium", timeStyle: "short" })} UTC`
              : "",
          },
        }),
      ])
    : recordMeta(item);
  const summary = (item.summary || "").trim()
    ? shorten(item.summary)
    : t("No description published at the source.");
  const header = element("summary", { className: "record-summary" }, [
    element("span", {
      className: "signal-rank",
      text: String(index + 1).padStart(2, "0"),
    }),
    element("div", { className: "record-heading" }, [
      // The benchmark title leads the row; the provenance line follows it
      // instead of classifying the item before it is named (issue #248).
      element("h3", { text: item.title }),
      metadata,
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

// The contact dialog (issue #191) keeps every reach-out channel in one place:
// email, WeChat, and Discord. The header badge (issue #213) merged the two
// separate WeChat and Discord buttons into a single Contact control that
// opens this dialog, so a reader lands on a choice rather than being launched
// out of the page on a guess.
//
// Since issue #311 it also answers "where is the data": the header export
// button is gone, and dataset requests are meant to arrive as a conversation.
// Star first, then ask -- the note says so, so neither side wastes a round
// trip.
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
      text: t("A wrong row in the adoption ranking is a real bug. So is a data source that stopped returning anything, or a benchmark you expected the radar to see."),
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
    // The dataset answer travels with the contact channels (issue #311): a
    // reader opening this sheet to ask for data reads the terms of the ask
    // before writing it.
    element("div", { className: "contact-dataset" }, [
      element("p", {
        className: "detail-summary",
        text: t("Want the full dataset? No crawler needed: star the repository, then get in touch and I will share a one-click export."),
      }),
      element("a", {
        className: "secondary-link",
        text: t("Star the repository"),
        attrs: {
          href: `https://github.com/${REPO_SLUG}`,
          target: "_blank",
          rel: "noopener noreferrer",
        },
      }),
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
  // Without this a pushed entry would change the URL on Back and leave the
  // page showing the previous view, silently disagreeing with its own address
  // bar (issue #286).
  window.addEventListener("popstate", onPopState);
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
  byId("leaderboard-top-more").addEventListener("click", () => {
    state.leaderboardTopExpanded = !state.leaderboardTopExpanded;
    renderLeaderboardTop(state.data.model_card_leaderboard);
  });
  byId("leaderboard-show-all").addEventListener("click", () => {
    state.leaderboardShowAll = !state.leaderboardShowAll;
    renderLeaderboard();
    byId("leaderboard-table-heading").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  byId("frontier-benchmark").addEventListener("change", (event) => {
    selectFrontier(event.target.value);
    renderAdoptionFrontier(state.data.model_card_leaderboard);
    writeUrl("push");
  });
  byId("today-date").addEventListener("change", (event) => {
    state.todayDate = event.target.value;
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
  // The drawer trigger, its outside-click and Escape dismissal, and the
  // refresh control. The drawer sits inside the #filters form, so its
  // selects already reach the shared input handler above.
  byId("filters-toggle").addEventListener("click", () => {
    const drawer = byId("filters-drawer");
    drawer.hidden = !drawer.hidden;
    byId("filters-toggle").setAttribute("aria-expanded", String(!drawer.hidden));
  });
  document.addEventListener("click", (event) => {
    if (byId("filters-drawer").hidden) return;
    if (byId("filters").contains(event.target)) return;
    closeFiltersDrawer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeFiltersDrawer();
  });
  byId("refresh-button").addEventListener("click", refreshData);
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
  byId("badge-contact").addEventListener("click", openContact);
  // The footer's "contact the author" opens the same sheet as the header
  // badge (issue #311): one contact surface, two doors.
  byId("footer-contact").addEventListener("click", openContact);
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

// The banner's one job is to send a worried reader somewhere useful within a
// click: the public Actions log answers "what broke", and the contact dialog
// that already exists on the page answers "who do I tell". The error messages
// in those logs are credential-safe by construction, so linking out publishes
// nothing the repository does not already show.
const DAILY_RADAR_RUNS_URL = `https://github.com/${REPO_SLUG}/actions/workflows/daily-radar.yml`;

function contactGlyph() {
  // Same speech-bubble path as the header's Contact badge (issue #213), so a
  // reader meets one icon for one meaning.
  const icon = svgElement("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
  icon.append(
    svgElement("path", {
      d: "M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z",
    }),
  );
  return icon;
}

async function pointAtLatestFailedRun(link) {
  // The workflows page lists every workflow and buries yesterday's failure.
  // One unauthenticated lookup pins the link to the exact failed run, which is
  // where "was it the API key or something else" is actually answered. Any
  // failure keeps the fallback href, which always resolves.
  try {
    const response = await fetch(
      `https://api.github.com/repos/${REPO_SLUG}/actions/workflows/daily-radar.yml/runs?status=failure&per_page=1`,
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!response.ok) return;
    const data = await response.json();
    const url = data.workflow_runs?.[0]?.html_url;
    if (url) link.setAttribute("href", url);
  } catch (_) {
    // Offline or rate-limited: the fallback href already points somewhere real.
  }
}

function renderStaleBanner() {
  const banner = byId("stale-banner");
  const latestDay = state.data.days[state.data.days.length - 1];
  const generatedAt = new Date(state.data.generated_at);
  const ageHours = (Date.now() - generatedAt.getTime()) / 3_600_000;
  const degraded = !latestDay.required_coverage_complete;
  banner.classList.toggle("stale-banner-degraded", degraded);
  if (ageHours <= STALE_AFTER_HOURS && !degraded) {
    banner.hidden = true;
    banner.replaceChildren();
    return;
  }
  const parts = [];
  if (ageHours > STALE_AFTER_HOURS) {
    parts.push(
      t("Last updated {date}, {hours} hours ago. The automatic update has not succeeded since.", {
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
      t("Some sources failed to answer on {date}: {gaps}.", {
        date: latestDay.date,
        gaps: latestDay.required_coverage_gaps.join(", "),
      }),
    );
  }

  const whatBroke = element("a", {
    className: "stale-banner-action",
    text: t("What broke?"),
    attrs: { href: DAILY_RADAR_RUNS_URL, target: "_blank", rel: "noopener noreferrer" },
  });
  pointAtLatestFailedRun(whatBroke);

  // A <button>, not an <a>: it opens the existing contact dialog instead of
  // navigating away, exactly like the header badge does.
  const contactButton = element("button", {
    type: "button",
    className: "stale-banner-action",
    attrs: { "aria-haspopup": "dialog" },
  });
  contactButton.append(contactGlyph(), document.createTextNode(t("Contact")));
  contactButton.addEventListener("click", openContact);

  banner.replaceChildren(
    document.createTextNode(parts.join(" ")),
    element("span", { className: "stale-banner-actions" }, [whatBroke, contactButton]),
  );
  banner.hidden = false;
}

// The refresh control revalidates radar.json against the server (cache:
// "reload" bypasses the reader's local copy) so a day rebuilt since the
// page loaded can appear without a full reload. A failed or incompatible
// refresh keeps the current data rather than blanking the dashboard.
async function refreshData() {
  try {
    const response = await fetch("data/radar.json", { cache: "reload" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (
      data.schema_version !== 2 ||
      !Array.isArray(data.days) ||
      !data.days.length
    ) {
      throw new Error("No compatible snapshots");
    }
    state.data = data;
    if (state.todayDate !== "all" && !state.data.facets.dates.includes(state.todayDate)) {
      state.todayDate = state.data.latest_date;
    }
    closeFiltersDrawer();
    rerenderCurrentView();
  } catch (error) {
    console.error(error);
  }
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
