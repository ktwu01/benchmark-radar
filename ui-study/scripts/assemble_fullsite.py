"""Build the opt-in UI study from freshly generated repository inputs."""

# ruff: noqa: E501
import gzip
import json
import re
import shutil
import sys
from pathlib import Path

from catalog import build_explorer_catalog

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1] if len(sys.argv) > 1 else root.parent / "site").resolve()
out = root / "dist"
if source == out or out in source.parents:
    raise ValueError("The generated output cannot be used as source")
if not (source / "data/benchmark-index.json").is_file():
    raise ValueError("Run normalize-catalog and classify before building the UI study")
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
explorer = root / "explorer-source"
for p in source.rglob("*"):
    if not p.is_file():
        continue
    rel = p.relative_to(source)
    if str(rel) in ["data/radar.json", "explore-preview.html"] or "explore-preview" in p.name:
        continue
    if rel.parts[0] == "explore":
        rel = Path("relationships", *rel.parts[1:])
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)

build_explorer_catalog(source, out / "data/explorer-preview.json")

# Large archival payloads are losslessly compressed, without a smaller fallback.
radar = (source / "data/radar.json").read_bytes()
(out / "data/radar.json.gz").write_bytes(gzip.compress(radar, compresslevel=9, mtime=0))
(out / "data/radar.json").unlink(missing_ok=True)

# A single template owns navigation geometry on every route.
header_template = (root / "design/header.html").read_text().strip()


def site_header(relative):
    section = relative.parts[0] if len(relative.parts) > 1 else "today"
    active = {"benchmarks": "explore"}.get(section, section)
    if active not in ["today", "explore", "leaderboard", "saturation", "trends"]:
        active = "resources"
    return re.sub(
        r"\{\{active:(\w+)\}\}",
        lambda m: (
            'data-active="true" aria-current="page"' if m[1] == active else 'data-active="false"'
        ),
        header_template,
    )


for p in out.rglob("*.html"):
    if p.parent == out and p.name in ["index.html"] or "explore" not in p.relative_to(out).parts:
        relative = p.relative_to(out)
        upstream = source / (
            Path("explore", *relative.parts[1:])
            if relative.parts[0] == "relationships"
            else relative
        )
        if not upstream.exists():
            continue
        s = upstream.read_text()
        s = re.sub(
            r'(class=")primary-link("\s+href="https://github.com/ktwu01/benchmark-radar")',
            r"\1secondary-link\2",
            s,
        )
        s = re.sub(
            r'<header class="masthead">.*?</header>',
            lambda _, relative=relative: site_header(relative),
            s,
            count=1,
            flags=re.S,
        )
        if relative.parts[0] == "benchmarks":
            s = re.sub(
                r'<nav class="site">.*?</nav>',
                lambda _, relative=relative: site_header(relative),
                s,
                count=1,
                flags=re.S,
            )
            s = s.replace("<body>", '<body class="record-page">')
            s = s.replace('href="https://benchmark-radar.org/', 'href="/')
            s = re.sub(
                r"(<table\b.*?</table>)",
                r'<div class="record-table-scroll" tabindex="0" role="region" aria-label="Reported scores">\1</div>',
                s,
                flags=re.S,
            )
        if relative.name == "logos.html":
            s = s.replace(
                '<body class="logos-page">', '<body class="logos-page">' + site_header(relative)
            )
        # Inline record styles are imported layout, not a separate theme.
        s = re.sub(
            r"<style>(.*?)</style>",
            lambda m: (
                "<style>@layer legacy, tokens, base, components, pages, responsive; @layer legacy {"
                + m[1]
                + "}</style>"
            ),
            s,
            flags=re.S,
        )

        s = re.sub(r'<aside class="hf-upvote-banner">.*?</aside>', "", s, flags=re.S)
        s = re.sub(r'<details class="privacy-note">.*?</details>', "", s, flags=re.S)
        s = re.sub(r'<script[^>]*src="[^"]*clarity[^\"]*"[^>]*>\s*</script>', "", s)
        s = re.sub(r'(<meta name="robots" content=")[^"]*(")', r"\1noindex,nofollow\2", s)
        s = s.replace('href="/data/radar.json"', 'href="/data/radar.json.gz" download')
        s = s.replace(
            "</head>",
            '<link rel="stylesheet" href="/assets/study.css"><script src="/assets/study.js" defer></script></head>',
        )
        if 'id="today-view"' in s:
            s = s.replace(
                '<span id="today-sort"></span>',
                '<details class="today-sort-details"><summary data-study-en="Sort order" data-study-zh="排序规则">Sort order</summary><span id="today-sort"></span></details>',
            )
            s = s.replace(
                '<form class="filter-panel today-filters"',
                '<div class="study-page-title"><h1 data-study-en="Daily radar" data-study-zh="今日研究动态">Daily radar</h1><a href="/blog/archive/" data-study-en="Past briefs" data-study-zh="往期日报">Past briefs</a></div><nav class="study-field-launcher" aria-label="Explore research fields"></nav><form class="filter-panel today-filters"',
                1,
            )
            s = s.replace(
                '<section class="benchmark-skyline"',
                '<div class="study-domain-controls" data-scope-view="leaderboard"></div><section class="benchmark-skyline"',
                1,
            )
            s = s.replace(
                '<div class="benchmark-workbench">',
                '<div class="study-domain-controls" data-scope-view="saturation"></div><div class="benchmark-workbench">',
                1,
            )
        p.write_text(s)

# The previous explorer remains a first-class route and shares site navigation.
s = (explorer / "index.html").read_text()
s = s.replace('href="styles.css"', 'href="/explore/styles.css"').replace(
    'src="app.js"', 'src="/explore/app.js"'
)
s = re.sub(
    r'<header class="topbar">.*?</header>',
    lambda _: site_header(Path("explore/index.html")),
    s,
    count=1,
    flags=re.S,
)
s = re.sub(r'<link rel="icon"[^>]+>', '<link rel="icon" type="image/svg+xml" href="/icon.svg">', s)
s = s.replace(
    "</head>",
    '<link rel="stylesheet" href="/assets/study.css"><script src="/assets/study.js" defer></script></head>',
)
s = s.replace("https://benchmark-radar.org/cite/", "/cite/").replace(
    'target="_blank" rel="noopener" data-en="About the research ↗"', 'data-en="About the research"'
)
s = s.replace(
    '<div class="filter-row">',
    '<div class="study-explorer-directions" data-expanded="false"><button type="button" id="direction-toggle" class="study-scope-toggle" aria-expanded="false" aria-controls="direction-tabs">Research directions</button><nav id="direction-tabs" class="study-direction-tabs" aria-label="Research directions"></nav></div><div class="filter-row">',
)
(out / "explore").mkdir(exist_ok=True)
(out / "explore/index.html").write_text(s)
shutil.copy2(explorer / "styles.css", out / "explore/styles.css")
explorer_app = (explorer / "app.js").read_text()
explorer_app = explorer_app.replace(
    "https://benchmark-radar.org/benchmarks/", "/benchmarks/"
).replace("text('Original record','原站完整记录')", "text('Full record','完整记录')")
explorer_app = explorer_app.replace(
    "<h3 class=\"detail-section-title\">${text('Evidence'",
    "<a class=\"study-detail-link\" href=\"/saturation/?lfrontier=${encodeURIComponent(r.slug)}&field=${encodeURIComponent(state.field)}&sub=${encodeURIComponent(state.sub)}\">${text('Open full score history →','查看完整分数历史 →')}</a><h3 class=\"detail-section-title\">${text('Evidence'",
)
(out / "explore/app.js").write_text(explorer_app)
for obsolete in ["app.js", "styles.css"]:
    (out / obsolete).unlink(missing_ok=True)

# Share exact tag mappings with score views, without inference from titles.
js = (explorer / "app.js").read_text()
taxonomy = re.search(r"  const fields = (\[.*?\n  \]);", js, re.S).group(1)
(out / "assets/fields.js").write_text(
    "export const fields = "
    + taxonomy
    + ';\nexport function recordFields(record) {\n const tags = [...(record.tags || record.categories || [])].map(t => String(t).toLowerCase());\n const found=fields.filter(f=>f.id!=="other" && f.tags.some(t=>tags.includes(t.toLowerCase()))).map(f=>f.id);\n return found.length?found:["other"];\n}\nexport function matchesField(record, field="all", sub="") {\n if(field==="all") return true;\n if(!recordFields(record).includes(field)) return false;\n const direction=fields.find(f=>f.id===field)?.subs.find(s=>s[0]===sub);\n if(!direction)return true;\n const tags=[...(record.tags || record.categories || [])].map(t=>String(t).toLowerCase());\n return direction[2].some(t=>tags.includes(t.toLowerCase()));\n}\n'
)

app = (source / "assets/app.js").read_text()
app = 'import {fields as researchFields, matchesField} from "./fields.js";\n' + app
app = app.replace(
    "  const currentParams = new URLSearchParams(window.location.search);",
    '  const currentParams = new URLSearchParams(window.location.search);\n  state.researchField = researchFields.some(f=>f.id===currentParams.get("field"))?currentParams.get("field"):"all";\n  state.researchSub = currentParams.get("sub") || "";',
)
app = app.replace(
    "  const params = new URLSearchParams();\n  // Every filter",
    '  const params = new URLSearchParams();\n  if (["leaderboard","saturation"].includes(state.view)) {\n    if(state.researchField && state.researchField!=="all")params.set("field",state.researchField);\n    if(state.researchSub)params.set("sub",state.researchSub);\n  }\n  // Every filter',
)
app = app.replace(
    "  const model = skylineModel(state.benchmarkIndex, cutoff, null, state.lheight);",
    "  renderResearchControls();\n  const model = skylineModel(researchRecords(), cutoff, null, state.lheight);",
)
app = app.replace(
    "return scorePopulation(state.benchmarkIndex || [])\n    .filter",
    "return scorePopulation(researchRecords())\n    .filter",
)
app = app.replace(
    "function scoreBrowseRows(cutoff = state.lscore) {",
    "function scoreBrowseRows(cutoff = state.lscore, records = researchRecords()) {",
)
app = app.replace("return scorePopulation(researchRecords())", "return scorePopulation(records)")
app = app.replace(
    "const rows = scoreBrowseRows(matches ? 100 : state.lscore);",
    "const rows = scoreBrowseRows(matches ? 100 : state.lscore, matches ? state.benchmarkIndex : researchRecords());",
)
app = app.replace(
    "function renderBenchmarkSearch() {",
    "function renderBenchmarkSearch() {\n  renderResearchControls();",
)
app = app.replace(
    "const ranked = (board.entries || []).filter((entry) => entry.card_count > 0);",
    "const researchIds = new Set(researchRecords().map(r=>r.slug));\n  const ranked = (board.entries || []).filter((entry) => entry.card_count > 0 && researchIds.has(entry.benchmark_id || entry.id));",
)
app = app.replace(
    "const response = await fetch(path, { cache });",
    "const response = await fetchStudyPayload(path, { cache });",
)
app = app.replace(
    'const response = await fetch(path, { cache: "reload" });',
    'const response = await fetchStudyPayload(path, { cache: "reload" });',
)
app = app.replace(
    'attrs: { href: "/data/radar.json" }',
    'attrs: { href: "/data/radar.json.gz", download: "radar.json.gz" }',
)
app = app.replace('canonical: "/explore/"', 'canonical: "/relationships/"')
app = app.replace(
    'window.history.pushState(historyState, "", url);',
    'window.history.pushState(historyState, "", url);\n    window.dispatchEvent(new Event("radar:routechange"));',
)
app = app.replace(
    'window.history.replaceState(historyState, "", url);',
    'window.history.replaceState(historyState, "", url);\n  window.dispatchEvent(new Event("radar:routechange"));',
)
app = app.replace(
    "  syncNavState();",
    '  syncNavState();\n  window.dispatchEvent(new Event("radar:routechange"));',
)
app += """
// Shared domain controls are filters over the complete source-record index.
function researchRecords() {
  return (state.benchmarkIndex || []).filter(r=>matchesField(r,state.researchField || "all",state.researchSub || ""));
}
function renderResearchControls() {
  const field=state.researchField || "all", sub=state.researchSub || "";
  for(const host of document.querySelectorAll(".study-domain-controls")) {
    const zh=document.documentElement.lang.startsWith("zh");
    const choose=(f,s="")=>{if(s||f==="all")host.dataset.expanded="false";state.researchField=f;state.researchSub=s;state.benchmarkVisibleLimit=BENCHMARK_SEARCH_LIMIT;writeUrl("push");if(state.view==="leaderboard")renderLeaderboard();else renderSaturation();};
    const button=(title,f,s,active,count)=>{const b=element("button",{text:title,attrs:{type:"button","aria-pressed":String(active)}});if(count!==undefined)b.append(element("span",{text:String(count)}));b.addEventListener("click",()=>choose(f,s));return b;};
    const rows=state.benchmarkIndex||[];
    const primary=element("div",{className:"study-domain-tabs",attrs:{role:"group","aria-label":zh?"研究领域":"Research fields"}});
    primary.append(button(zh?"全部领域":"All research","all","",field==="all",rows.length));
    for(const f of researchFields)primary.append(button(zh?f.zh:f.en,f.id,"",field===f.id,rows.filter(r=>matchesField(r,f.id)).length));
    const children=[primary], f=researchFields.find(f=>f.id===field);
    if(f?.subs.length){const secondary=element("div",{className:"study-direction-tabs",attrs:{role:"group","aria-label":zh?"研究方向":"Research directions"}});secondary.append(button(zh?"全部方向":"All directions",field,"",!sub));for(const s of f.subs)secondary.append(button(zh?s[1]:s[0],field,s[0],sub===s[0],rows.filter(r=>matchesField(r,field,s[0])).length));children.push(secondary);}
    const selected=researchFields.find(f=>f.id===field);
    const current=sub || (selected?(zh?selected.zh:selected.en):(zh?"全部领域":"All research"));
    const toggle=element("button",{className:"study-scope-toggle",text:(zh?"研究领域 · ":"Research fields · ")+current,attrs:{type:"button","aria-expanded":String(host.dataset.expanded==="true"),"aria-controls":"scope-"+host.dataset.scopeView}});
    const panel=element("div",{className:"study-scope-panel",attrs:{id:"scope-"+host.dataset.scopeView}});
    panel.append(...children);
    toggle.addEventListener("click",()=>{host.dataset.expanded=String(host.dataset.expanded!=="true");toggle.setAttribute("aria-expanded",host.dataset.expanded);});
    replaceChildren(host,[toggle,panel]);
  }
}
async function fetchStudyPayload(path, options) {
  if(path!=="/data/radar.json") return fetch(path,options);
  const response=await fetch("/data/radar.json.gz",options);
  if(!response.ok)throw new Error(`HTTP ${response.status}`);
  if(typeof DecompressionStream!=="function")throw new Error("This browser cannot open the full archive. Use a current browser.");
  return new Response(response.body.pipeThrough(new DecompressionStream("gzip")),{headers:{"Content-Type":"application/json"}});
}
"""
(out / "assets/app.js").write_text(app)
for name in ["study.css", "study.js"]:
    shutil.copy2(root / "design" / name, out / "assets" / name)
# Layer imported styles instead of accumulating specificity patches.
layer_order = "@layer legacy, tokens, base, components, pages, responsive;\n"
for css in [
    *(p for p in (out / "assets").glob("*.css") if p.name != "study.css"),
    out / "explore/styles.css",
]:
    css.write_text(layer_order + "@layer legacy {\n" + css.read_text() + "\n}\n")
print(
    json.dumps(
        {
            "pages": len(list(out.rglob("*.html"))),
            "benchmarks": json.loads((out / "data/benchmark-index.json").read_text())["count"],
            "archive_bytes": (out / "data/radar.json.gz").stat().st_size,
        }
    )
)
