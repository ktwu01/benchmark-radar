// Execute production functions with small deterministic inputs, without a browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { SKYLINE_START_DATE, benchmarkDate, benchmarkDateLabel, skylineModel as buildSkylineModel, skylineGeometry, skylineDateLanes, skylineScoreLanes, skylineCapPositions, skylineFrontierSteps, scorePopulation, matchesScoreCutoff } from '../site/assets/skyline.js';
import { matchesField } from '../site/assets/fields.js';
const source = readFileSync('site/assets/app.js', 'utf8');
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf('\n}\n', start) + 2);
}
const state = {
  todayDate: '30d', q: '', source: '', kind: '', category: '', organization: '', event: '',
  data: { latest_date: '2026-09-06', facets: { dates: ['2026-09-06'] } },
};
const observation = (date, id = date) => ({
  snapshot_date: date, observation_kind: 'evidence', source: 'GitHub', source_id: id,
  title: 'agent benchmark', summary: '', categories: [],
});
let observations = [observation('2026-09-07'), observation('2026-09-06'), observation('2026-08-08', 'repeated'), observation('2026-08-09', 'repeated'), observation('2026-08-07'), observation('2026-07-09'), observation('2026-07-08')];
const dateNames = ['todayDateRange', 'todayIsMultiDate', 'validTodayDate', 'filteredObservations', 'observationRecordKey', 'latestObservationsByRecord'];
const dates = new Function('state', 'allObservations', `${source.match(/const TODAY_WINDOWS = .*;/)[0]}\n${dateNames.map(fn).join('\n')}\nreturn {${dateNames.join(',')}};`)(state, () => observations);
assert.deepEqual(dates.todayDateRange(), {start:'2026-08-08',end:'2026-09-06'});
assert.equal(dates.validTodayDate(), true);
assert.deepEqual(dates.filteredObservations().map(r=>r.snapshot_date), ['2026-09-06','2026-08-09']);
state.todayDate = '60d';
assert.deepEqual(dates.todayDateRange(), {start:'2026-07-09',end:'2026-09-06'});
assert.equal(dates.filteredObservations().length, 4);
state.todayDate = 'all';
assert.equal(dates.filteredObservations().length, 6);
state.todayDate = '2026-08-08';
assert.equal(dates.filteredObservations()[0].snapshot_date, '2026-08-08');
state.todayDate = '30d';
state.q = 'absent';
assert.equal(dates.filteredObservations().length, 0);
state.q = 'agent';
state.source = 'github';
assert.equal(dates.filteredObservations().length, 2);
state.data.latest_date = '2024-03-01';
assert.deepEqual(dates.todayDateRange(), {start:'2024-02-01',end:'2024-03-01'});

const summary = (display_max, numeric_count=1) => ({display_max,numeric_count,display_multiplier:1,raw_min:display_max,raw_max:display_max});
state.data.model_card_leaderboard = {entries:[{benchmark_id:'curated',name:'Curated'}]};
state.data.benchmark_score_progression = {benchmarks:{curated:{score_summary:summary(60,2)}}};
state.benchmarkIndex = [
  {slug:'curated',name:'Curated',source:'model_reports',score_summary:summary(60,2)},
  {slug:'external',name:'Catalog',source:'llm_stats',score_summary:summary(60,9)},
  {slug:'over70',name:'Over70',source:'artificial_analysis',score_summary:summary(70,20)},
  {slug:'at100',name:'At100',source:'llm_stats',score_summary:summary(100,30)},
  {slug:'missing',name:'Missing',source:'llm_stats',score_summary:summary(null,0)},
];
state.lscore = 70;
const scoreNames = ['researchRecords','scoreRecord','matchesScoreFilter','scoreBrowseRows','saturationRows','scoreRankingRows','benchmarkQueryIds','searchBenchmarkIndex','foldName','frontierDefaultEntry','catalogDisplayFactor'];
state.benchmarkQuery = '';
const scores = new Function('matchesField', 'state', 'scorePopulation', 'matchesScoreCutoff', 'SKYLINE_START_DATE', `${scoreNames.map(fn).join('\n')}\nreturn {${scoreNames.join(',')}};`)(matchesField, state, scorePopulation, matchesScoreCutoff, SKYLINE_START_DATE);
assert.deepEqual(scores.scoreBrowseRows().map(r=>r.id), ['external','curated','missing']);
assert.equal(scores.frontierDefaultEntry(state.data.model_card_leaderboard).id,'external');
assert.equal(scores.matchesScoreFilter(summary(69.999)),true);
assert.equal(scores.matchesScoreFilter(summary(70)),false);
assert.equal(scores.matchesScoreFilter(summary(60,0)),false);
assert.equal(scores.matchesScoreFilter(summary(0)),true,'zero is a reported score');
assert.equal(scores.matchesScoreFilter(null),false);
state.lscore=100;
assert.deepEqual(scores.scoreBrowseRows().map(r=>r.id), ['at100','over70','external','curated','missing']);
state.lscore=90;
assert.deepEqual(scores.scoreBrowseRows().map(r=>r.id), ['over70','external','curated','missing']);
// An intermediate step the old three-option filter could not express.
state.lscore=40;
assert.deepEqual(scores.scoreBrowseRows().map(r=>r.id), ['missing']);
// Searching bypasses the slider without losing old or unscored source records.
state.lscore=70;
state.benchmarkIndex.push(
  {slug:'old95',name:'Old high score',aliases:['NeedleBench'],source:'artificial_analysis',released:'2020-01-01',score_summary:summary(95,3)},
  {slug:'unscored',name:'Unscored lookup',aliases:['NeedleBench'],source:'opencompass_hub'},
);
for (const row of state.benchmarkIndex) row.categories = ['lookup'];
const fixtureRecords = state.benchmarkIndex;
const ranking = scores.scoreRankingRows().map(row=>row.id);
assert.deepEqual(ranking,['at100','over70','external','curated']);
const browsing = scores.saturationRows().map(row=>row.id);
assert(!browsing.includes('old95'));
assert(browsing.includes('unscored'));
state.benchmarkQuery='NeedleBench';
assert.deepEqual(scores.saturationRows().map(row=>row.id),['old95','unscored']);
assert.equal(state.lscore,70,'search must not reset the shared slider');
state.benchmarkQuery='lookup';
assert.equal(scores.saturationRows().length,fixtureRecords.length);
assert.equal(new Set(scores.saturationRows().map(row=>row.source)).size,4);
state.benchmarkQuery='not in catalog';
assert.deepEqual(scores.saturationRows(),[]);
state.benchmarkQuery='';
assert.deepEqual(scores.saturationRows().map(row=>row.id),browsing,'clearing search restores the cutoff');
state.lscore=10;
assert.deepEqual(scores.scoreRankingRows().map(row=>row.id),ranking,'the ranking never follows the slider');
state.lscore=100;
assert.deepEqual(new Set(scores.saturationRows().map(row=>row.id)),new Set(fixtureRecords.map(row=>row.slug)));
state.lscore=70;
state.benchmarkIndex=null;
assert.deepEqual(scores.scoreBrowseRows().map(r=>r.id), [],'a missing index cannot fall back to a preferred source');
assert.equal(scores.catalogDisplayFactor({score_summary:{display_multiplier:100}}),100);
assert.equal(scores.catalogDisplayFactor({score_summary:{display_multiplier:1}}),1);
const cutoff = new Function(`${fn('scoreCutoff')}\nreturn scoreCutoff;`)();
assert.equal(cutoff('40'), 40);
assert.equal(cutoff('100'), 100);
assert.equal(cutoff(null), 70, 'a missing cutoff falls back to the default');
assert.equal(cutoff('under70'), 70, 'a stale token from an old link falls back');
assert.equal(cutoff('5'), 70, 'below the slider minimum falls back');
assert.equal(cutoff('999'), 70, 'above the slider maximum falls back');
assert.equal(cutoff('44'), 40, 'an off-step value snaps to the nearest step');

// A page reload must revalidate recovered dates, while views within one page
// share their request. Failed loads still return the explicit unavailable state.
const makeLoaders = new Function('fetch', `const state = {}; let benchmarkIndexPromise = null;
  const benchmarkShardCache = new Map();
  ${fn('loadBenchmarkIndex')}
  ${fn('loadBenchmarkShard')}
  return {loadBenchmarkIndex,loadBenchmarkShard};`);
const requests = [];
const loaders = makeLoaders(async (url,options) => {
  requests.push({url,options});
  return {ok:true,json:async()=>({benchmarks:[{slug:'dated',released:'2025-02-14'}]})};
});
const firstIndex = loaders.loadBenchmarkIndex();
assert.equal(loaders.loadBenchmarkIndex(),firstIndex);
assert.equal((await firstIndex)[0].released,'2025-02-14');
const firstShard = loaders.loadBenchmarkShard('dated');
assert.equal(loaders.loadBenchmarkShard('dated'),firstShard);
await firstShard;
assert.deepEqual(requests,[
  {url:'/data/benchmark-index.json',options:{cache:'no-cache'}},
  {url:'/data/benchmarks/dated.json',options:{cache:'no-cache'}},
]);
const unavailable = makeLoaders(async () => ({ok:false,status:503}));
assert.equal(await unavailable.loadBenchmarkIndex(),null);
assert.equal(await unavailable.loadBenchmarkShard('missing'),null);

function fixtureCatalog(benchmarks={},entries=[],catalog=[]) {
  if (catalog.some(row => row.source === 'model_reports')) return catalog;
  return [...Object.entries(benchmarks).map(([id, record]) => {
    const named = entries.find(entry => entry.benchmark_id === id);
    const numeric = (record.observations || []).filter(row => Number.isFinite(row.value));
    const values = numeric.map(row => row.value);
    const best = numeric.find(row => row.value === Math.max(...values));
    const document = named?.adopters?.find(card => card.model_card_id === best?.source_id);
    const scoreSummary = record.score_summary || (values.length ? summary(Math.max(...values),values.length) : null);
    return {
      ...record, slug:id, name:named?.name || id, source:'model_reports',
      categories:[named?.domain].filter(Boolean), released:named?.released,
      score_direction:record.direction,
      score_summary:scoreSummary ? {...scoreSummary,raw_min:Math.min(...values),raw_max:Math.max(...values)} : null,
      source_url:document?.url,
      evidence_summary:{document_count:named?.adopters ? new Set(named.adopters.map(card=>card.model_card_id)).size : null},
    };
  }),...catalog];
}
const skylineModel = (benchmarks={},entries=[],catalog=[],cutoff=70,matchingIds=null,metric='models') =>
  buildSkylineModel(fixtureCatalog(benchmarks,entries,catalog),cutoff,matchingIds,metric);
const cardSkyline = (benchmarks={},entries=[],catalog=[],cutoff=70,matchingIds=null) =>
  skylineModel(benchmarks,entries,catalog,cutoff,matchingIds,'documents');
// --- Benchmark Frontier: identity, normalization and dominance ----------------
const entry = (id, count, extra = {}) => ({
  benchmark_id: id, name: id, released: '2025-01-01', domain: 'science',
  // A deliberately wrong summary guards against ever using it or score counts.
  card_count: 999,
  adopters: Array.from({length: count}, (_, n) => ({
    model_card_id: `card-${n}`, published: '2026-01-01', url: `https://example.org/${n}`,
  })), ...extra,
});
const record = (value, extra = {}) => ({
  unit: 'percent', direction: 'higher_is_better', metric: 'accuracy',
  observations: [{value, source_id: 'card-0', reported_at: '2026-01-01'}], ...extra,
});
const tracks = {
  hardest: record(10), twin: record(10), adopted: record(20),
  dominated: record(30), sameScore: record(20), sameAdoption: record(21),
  all: record(100), zero: record(0),
};
const cards = [entry('hardest',2), entry('twin',2,{released:'2024-01-01'}),
  entry('adopted',5), entry('dominated',4), entry('sameScore',3),
  entry('sameAdoption',5), entry('all',6), entry('zero',0)];
const model = cardSkyline(tracks,cards,[],100);
const paretoIds = (m) => m.rows.filter((row)=>row.pareto).map((row)=>row.id).sort();
assert.deepEqual(paretoIds(model), ['adopted','all','hardest','twin','zero']);
assert.equal(model.rows.length,8,'coincident benchmarks retain their identities');
assert.equal(model.rows.find(r=>r.id==='zero').documentCount,0,'known zero adoption stays valid');
assert.equal(model.rows.find(r=>r.id==='twin').date,'2024-01-01','the inclusive cohort boundary is eligible; age never affects dominance');
for (let cut = 10; cut <= 100; cut += 10) {
  const sliced = cardSkyline(tracks,cards,[],cut);
  assert.deepEqual(sliced.rows, model.rows.filter((row)=>cut===100 || row.score<cut));
  assert.equal(sliced.rows.some(row=>row.score===cut),cut===100,'cutoff is strict except All');
  assert.deepEqual(skylineGeometry(sliced.eligible).project(.5,20,2),
    skylineGeometry(model.eligible).project(.5,20,2),'a slice never rescales its survivors');
}
const duplicate = entry('repeats',2);
duplicate.adopters.push({...duplicate.adopters[0]});
const duplicated = cardSkyline({repeats:record(45,{observations:Array(100).fill({value:45})})},[duplicate],[],100);
assert.equal(duplicated.rows[0].documentCount,2,'repeated cards and repeated score rows cannot inflate adoption');
assert.equal(duplicated.rows[0].score,45);
const reversed = cardSkyline({error:record(90,{
  direction:'lower_is_better',observations:[{value:90},{value:25}],
})},[entry('error',1)],[],100);
assert.equal(reversed.rows[0].score,75,'best normalized score is 100 minus the LOWEST error');
assert.equal(reversed.rows[0].rawScore,25);
assert.equal(cardSkyline({error:record(25,{direction:'lower_is_better'})},[entry('error',1)],[],70).rows.length,0);
const invalids = {
  elo:record(50,{unit:'elo'}), dollars:record(5,{unit:'usd'}),
  fraction:record(.7,{unit:undefined}), unknown:record(30,{direction:undefined}),
  bogus:record(30,{direction:'inferred'}), negative:record(-1), high:record(101),
  unscored:record(null), unmeasured:record(10), undated:record(10,{observations:[{value:10}]}),
};
const invalidModel = cardSkyline(invalids,
  Object.keys(invalids).filter(id=>id!=='unmeasured').map(id=>entry(id,0,{released:null})),[],100);
assert.deepEqual(invalidModel.rows.map(row=>row.id),['fraction','unmeasured','undated'],
  'unknown dates or adoption cannot remove a reported number from the main visualization');
assert.equal(invalidModel.pending.length,6,'numeric scores on other scales retain individual marks');
assert.deepEqual(invalidModel.undated.map(row=>row.id),['undated'],
  'an adoption mention does not date a benchmark; undated scores remain inspectable');
assert.equal(invalidModel.unscored,1,'excluded unscored records are counted separately');
assert(!invalidModel.visible.some(row=>row.id==='unscored'));
assert.equal(invalidModel.all.filter(row=>row.missing.includes('scale')).length,7);
assert.equal(invalidModel.all.find(row=>row.id==='unmeasured').documentCount,null,'unknown adoption is not zero');
assert.equal(invalidModel.all.find(row=>row.id==='unscored').score,null,'unknown score is not zero');
assert.equal(invalidModel.population,10);
assert(invalidModel.pending.filter(row=>row.missing.includes('score') || row.missing.includes('scale') || row.missing.includes('count'))
  .every(row=>row.pareto===null),'unknown score or adoption cannot qualify for Pareto');
const dateIndependent=cardSkyline({dated:record(50),undated:record(10,{observations:[{value:10}]})},
  [entry('dated',1),entry('undated',2,{released:null,adopters:[{model_card_id:'a'},{model_card_id:'b'}]})],[],100);
assert.equal(dateIndependent.rows[0].pareto,true,'dominance is calculated within the established 2024+ cohort');
assert.equal(dateIndependent.undated[0].pareto,null,'an undated benchmark is not claimed to belong to 2024+');
assert.equal(dateIndependent.comparable.length,1);
const datesModel = cardSkyline({date:record(40,{first_reported_at:'2024-04-03'})},
  [entry('date',1,{released:'2026-02-30',adopters:[{model_card_id:'x',published:'2023-12-11'}]})],[],100);
assert.equal(datesModel.rows[0].date,'2024-04-03','earliest score report takes priority over an adoption-only mention');
assert.equal(datesModel.rows[0].dateBasis,'first_score');
assert.deepEqual(benchmarkDate({released:'2025-06-15',first_reported_at:'2024-02-01'}),
  {date:'2025-06-15',dateBasis:'released'},'release takes precedence over score dates');
assert.deepEqual(benchmarkDate({observations:[
  {value:20,reported_at:'2025-03-01'}, {value:30,reported_at:'2024-01-01'},
  {value:null,reported_at:'2020-01-01'}, {value:40,reported_date:'2018-01-01',date_precision:'model_announcement'},
  {value:10,reported_at:'2023-01-01',date_precision:'crawl'},
]}),{date:'2024-01-01',dateBasis:'first_score'},'take the earliest numeric score, ignoring non-score and surrogate dates');
assert.deepEqual(benchmarkDate({first_observed:'2026-08-17',collected_at:'2026-08-17',
  observations:[{value:20,reported_date:'2024-01-01',date_precision:'model_announcement'}]}),
  {date:null,dateBasis:null},'neither a crawl nor a model release can become a benchmark date');
assert.equal(benchmarkDate({first_score_reported_at:'2024-02-29'}).date,'2024-02-29');
assert.equal(benchmarkDate({released:'2026-02-30',first_score_reported_at:'2024-02-30'}).date,null);
const proxyRecord={first_score_record:{reported_at:'2024-02-29',date_precision:'model_announcement',obs_id:'first-score'}};
assert.deepEqual(benchmarkDate(proxyRecord),{date:'2024-02-29',dateBasis:'score_record_proxy'},
  'source-dated numeric score records must reach the main timeline with their proxy basis intact');
assert.equal(benchmarkDateLabel(benchmarkDate(proxyRecord)),'First dated LLM score (model-release proxy)');
assert.deepEqual(benchmarkDate({...proxyRecord,released:'2025-01-01'}),{date:'2025-01-01',dateBasis:'released'});
assert.deepEqual(benchmarkDate({...proxyRecord,first_score_reported_at:'2025-02-01'}),{date:'2025-02-01',dateBasis:'first_score'},
  'actual publication evidence takes priority over a model-date proxy');
assert.equal(benchmarkDate({first_score_record:{reported_at:'2024-01-01',date_precision:'crawl'}}).date,null);
const boundary=cardSkyline({old:record(30),fallbackOld:record(20,{observations:[
  {value:10,reported_at:'2023-12-31'}, {value:20,reported_at:'2025-01-01'}]}), boundary:record(40)},
  [entry('old',8,{released:'2023-12-31'}),entry('fallbackOld',9,{released:null}),entry('boundary',1,{released:'2024-01-01'})],[],100);
assert.deepEqual(boundary.visible.map(row=>row.id),['boundary'],'the first score is chosen before the date cutoff, even at score 100');
assert.equal(boundary.beforeStart,2);
assert.equal(model.rows.find(r=>r.id==='hardest').sourceUrl,'https://example.org/0');
assert.equal(model.rows.find(r=>r.id==='hardest').domain,'Science');
assert.equal(cardSkyline({other:record(20)},[entry('other',1,{domain:'unmapped'})],[],100).rows[0].domain,'Other');
assert.deepEqual(skylineFrontierSteps(model.rows),[
  {score:0,count:0},{score:10,count:0},{score:10,count:2},
  {score:20,count:2},{score:20,count:5},{score:100,count:5},{score:100,count:6},
],'staircase corners use raw score and adoption, with shared corners drawn once');
const g = skylineGeometry(model.eligible);
assert.equal(g.startYear,2024,'the user-requested starting date is a hard cutoff');
assert.equal(g.timeFraction(Date.UTC(2023,11,31)),null,'pre-2024 dates cannot be clamped onto the axis');
assert.equal(g.timeFraction(Date.UTC(2024,0,1)),0);
assert.equal(g.timeFraction(null),null,'unknown time has no invented position');
assert.deepEqual(g.years,[2024,2025]);
assert(g.project(1,0)[0]>g.project(0,0)[0],'time increases to the right');
assert(g.project(.5,0)[1]>g.project(.5,100)[1],'low scores are in front');
assert(g.project(.5,20,5)[1]<g.project(.5,20,2)[1],'adoption grows upward');
assert(g.project(.5,20,1)[1]-g.project(.5,20,2)[1]
  >g.project(.5,20,5)[1]-g.project(.5,20,6)[1],'heights use a logarithmic scale');

// Exercise production SVG construction without a browser or a DOM.
function svgElement(tag,attrs={},text=null) {
  return {tag,attrs,text,children:[],append(...children){this.children.push(...children);}};
}
const translate = (key,params={})=>Object.entries(params).reduce((s,[k,v])=>s.replaceAll(`{${k}}`,v),key);
const chart = new Function('skylineGeometry','skylineDateLanes','skylineScoreLanes','skylineCapPositions','skylineFrontierSteps','svgElement','t','metricLabel','shorten','formatDate','makeFrontierPointInteractive','scoreSourceLabel','benchmarkDateLabel',
  `${fn('skylineChart')}\nreturn skylineChart;`)(skylineGeometry,skylineDateLanes,skylineScoreLanes,skylineCapPositions,skylineFrontierSteps,svgElement,translate,
  (n,label)=>`${n} ${label}`, (s,n)=>s.slice(0,n), x=>x, (node,details)=>{node.details=details;}, x=>x, benchmarkDateLabel);
const flatten = (node)=>[node,...node.children.flatMap(flatten)];
for (const cutoff of [10,70,100]) {
  const m=cardSkyline(tracks,cards,[],cutoff);
  const nodes=flatten(chart(m,cutoff));
  assert.equal(nodes.filter(n=>'data-frontier-point' in n.attrs).length,m.rows.length);
  assert.equal(nodes.filter(n=>'data-frontier-anchor' in n.attrs).length,m.rows.length);
  assert.equal(nodes.filter(n=>n.attrs.class?.startsWith('skyline-projection ')).length,m.rows.length);
  assert.equal(nodes.filter(n=>n.attrs.class==='skyline-guide').length,m.rows.length);
  assert.equal(nodes.filter(n=>n.attrs.class==='skyline-slice').length,cutoff<100?1:0);
  assert.equal(new Set(nodes.filter(n=>'data-benchmark-id' in n.attrs).map(n=>n.attrs['data-benchmark-id'])).size,m.rows.length);
  assert(!JSON.stringify(nodes).includes('NaN'));
  assert(!JSON.stringify(nodes).includes('Infinity'));
  const labelLayer=nodes.find(n=>n.attrs.class==='skyline-labels');
  assert.equal(labelLayer.children.filter(n=>n.tag==='text').length,m.rows.filter(r=>r.pareto).length);
}
assert(!JSON.stringify(chart(cardSkyline({},[],[],70),70)).includes('NaN'),'empty chart retains usable axes');
// Catalog model coverage and curated document adoption are separate measures.
const countedTracks = {
  hard: record(10,{score_summary:{...summary(10,400),model_count:2}}),
  popular: record(50,{score_summary:{...summary(50,700),model_count:577}}),
  dominated: record(60,{score_summary:{...summary(60,650),model_count:200}}),
  unknown: record(15,{score_summary:{...summary(15,900),model_count:null}}),
  old: record(10,{score_summary:{...summary(10,1000),model_count:1000}}),
};
const countedCards = [entry('hard',3),entry('popular',1),entry('dominated',20),entry('unknown',1),
  entry('old',30,{released:'2023-12-31'})];
const byModels = skylineModel(countedTracks,countedCards,[],100);
const byCards = cardSkyline(countedTracks,countedCards,[],100);
assert.equal(byModels.heightMetric,'models','full-source model coverage is the default height');
assert.deepEqual(byModels.visible.map(row=>row.id),byCards.visible.map(row=>row.id));
assert.deepEqual(paretoIds(byModels),['hard','popular']);
assert.deepEqual(paretoIds(byCards),['dominated','hard']);
assert.equal(byModels.rows.find(row=>row.id==='unknown').heightCount,null,
  'neither score-row counts nor card counts may fill in an unknown model count');
assert.equal(byModels.rows.find(row=>row.id==='popular').documentCount,1);
assert.equal(byCards.rows.find(row=>row.id==='popular').modelCount,577);
assert.equal(skylineGeometry(byModels.cohort).maximum,577,'model heights exceed 200 and exclude pre-2024 records');
assert.equal(skylineGeometry(byCards.cohort).maximum,20,'document mode retains real document counts');
for(const cut of [10,30,70,100]) {
  const sliced=skylineModel(countedTracks,countedCards,[],cut);
  assert.equal(skylineGeometry(sliced.cohort).maximum,577,'score slicing never rescales the count axis');
  assert.deepEqual(paretoIds(sliced),paretoIds(byModels).filter(id=>cut===100 || countedTracks[id].score_summary.display_max<cut));
}
const searchHeight=skylineModel(countedTracks,countedCards,[],70,new Set(['hard']));
assert.equal(skylineGeometry(searchHeight.cohort).maximum,577,'search never rescales the count axis');
for(const m of [byModels,byCards]) {
  const drawn=flatten(chart(m,100));
  const max=skylineGeometry(m.cohort).maximum;
  const ticks=drawn.filter(node=>node.attrs.class==='skyline-tick skyline-count-tick');
  assert.equal(ticks.at(-1).text,String(max));
  assert.deepEqual(drawn.filter(node=>node.attrs.class==='skyline-tick skyline-score-tick-left').map(node=>node.text),
    ['0','20','40','60','80','100']);
  assert.deepEqual(drawn.filter(node=>'data-axis' in node.attrs).map(node=>node.attrs['data-axis']),[m.heightMetric,'score']);
  const popular=drawn.find(node=>node.attrs['data-benchmark-id']==='popular');
  assert.equal(popular.attrs['data-height-count'],m.heightMetric==='models'?577:1);
  assert(popular.details.rows.some(row=>row.label==='Models with reported scores' && row.value==='577'));
  assert(popular.details.rows.some(row=>row.label==='Source documents' && row.value==='1'));
}
// A complete rebuilt corpus exercises crowded labels and the production input contract.
const corpus = JSON.parse(readFileSync('site/data/radar.json','utf8'));
const catalog = JSON.parse(readFileSync('site/data/benchmark-index.json','utf8')).benchmarks;
const benchmarkRecords=corpus.benchmark_score_progression.benchmarks;
const corpusEntries=corpus.model_card_leaderboard.entries;
const full=buildSkylineModel(catalog,100);
const expected=catalog.length;
assert.equal(full.population,expected);
assert.equal(full.visible.length+full.beforeStart+full.unscored,expected);
assert(full.population>=1259,'principle.md: investigate a corpus smaller than 1,259 records');
assert(full.sources>=4,'principle.md: every source belongs to the same population');
assert.equal(new Set(full.all.map(row=>row.id)).size,expected,'source rows are never silently merged');
assert.equal(full.all.filter(row=>row.source==='opencompass_hub').length,
  catalog.filter(row=>row.source==='opencompass_hub').length,'unscored records remain in the corpus');
state.data=corpus;
state.benchmarkIndex=catalog;
const fullModes = new Map([['models',full],['documents',cardSkyline(benchmarkRecords,corpusEntries,catalog,100)]]);
for(const [heightMetric,fullMode] of fullModes) for(const cutoff of [10,30,70,100]) {
  state.lscore=cutoff;
  const current=buildSkylineModel(catalog,cutoff,null,heightMetric);
  assert.deepEqual(current.visible,fullMode.all.filter(row=>(row.date===null || row.date>=SKYLINE_START_DATE) && matchesScoreCutoff(row.summary,cutoff)));
  assert.equal(current.visible.length+current.hidden,expected);
  assert.equal(current.rows.length+current.pending.length,current.visible.length);
  assert.equal(current.unscored,full.unscored,'the missing-score exclusion is independent of the cutoff');
  assert(current.visible.every(row=>Number.isFinite(row.displayScore) && row.summary.numeric_count>0),
    'every displayed benchmark has a numeric reported score, even with All selected');
  assert(current.hidden-current.beforeStart-current.unscored>=0,'exclusion counts must not overlap');
  assert.deepEqual(current.visible.map(row=>row.id).sort(), scores.scoreRankingRows().filter(row=>matchesScoreCutoff(row.summary,cutoff)).map(row=>row.id).sort(),
    'the figure is the cutoff slice of the independently ranked scored cohort');
  const rendered=chart(current,cutoff);
  const drawn=flatten(rendered);
  const marks=drawn.filter(node=>'data-benchmark-id' in node.attrs);
  assert(!drawn.some(node=>node.tag==='text' && node.text?.startsWith('No score reported')),
    'remove the unscored bands themselves, not only their dots');
  assert.equal(marks.length,current.visible.length,
    'principle.md: every surviving record must be drawn in the main SVG, never only counted or put in a collapsed list');
  assert.deepEqual(marks.map(node=>node.attrs['data-benchmark-id']).sort(),current.visible.map(row=>row.id).sort(),
    'the main visualization represents exactly the filtered full corpus, with no missing or duplicate marks');
  const plotted=drawn.filter(node=>node.attrs.class?.startsWith('skyline-point '));
  assert.equal(plotted.length,current.rows.length,'every usable score is on the main plane');
  const measured=plotted.filter(node=>node.attrs['data-height-count']!=='unknown' && node.attrs['data-benchmark-date']);
  assert.equal(drawn.filter(node=>node.attrs.class==='skyline-stem skyline-mark').length,measured.length,
    'unknown counts never become fake zero-height stems');
  assert.equal(drawn.filter(node=>node.attrs.class==='skyline-guide').length,measured.length,
    'every measured height has a side-wall projection; scale qualifications stay visible');
  if(cutoff===70) {
    const main=plotted.filter(node=>node.attrs['data-benchmark-date']);
    assert(main.length>=300,'a few dozen main skyline points plus hundreds in a side panel still fails principle.md');
    const scoredSources=new Set(current.rows.filter(row=>row.date!==null).map(row=>row.source));
    assert(scoredSources.has('llm_stats') && scoredSources.has('artificial_analysis'));
    for(const row of current.rows.filter(row=>row.date!==null)) {
      const mark=main.find(node=>node.attrs['data-benchmark-id']===row.id);
      assert(mark,`${row.id}: every dated numeric score belongs in the main skyline`);
      if(row.dateBasis==='score_record_proxy') {
        assert.equal(mark.attrs['data-date-basis'],'score_record_proxy');
        assert(mark.details.rows.some(detail=>detail.label==='First dated LLM score (model-release proxy)'));
      }
    }
    assert(current.dated.length>300,'investigate a timeline limited to a few dozen curated benchmarks');
    assert(current.visible.length>300,'excluding unscored records must preserve the scored catalog');
    if(heightMetric==='models') {
      assert(measured.length>300,'the measured model counts must produce hundreds of real stems, not a curated-only skyline');
      assert(skylineGeometry(current.cohort).maximum>200,'investigate a height axis missing the large source model counts');
    }
    for(const source of new Set(current.visible.map(row=>row.source))) {
      const sourceIds=new Set(current.visible.filter(row=>row.source===source).map(row=>row.id));
      assert(sourceIds.size>0);
      assert(marks.some(mark=>sourceIds.has(mark.attrs['data-benchmark-id'])),'every source with matching scores is drawn');
    }
  }
  for(const row of current.rows.filter(row=>row.score===null)) {
    assert.equal(row.pareto,null,'a source display scale cannot certify Pareto eligibility');
    const mark=plotted.find(node=>node.attrs['data-benchmark-id']===row.id);
    assert.equal(mark.attrs['data-score-basis'],'source-reported');
    assert(mark.attrs.class.includes('is-unverified'));
    assert(mark.details.rows.some(detail=>detail.label==='Score scale' && detail.value==='Not verified for comparison'));
  }
  const geometry=skylineGeometry(current.cohort);
  const projections=drawn.filter(node=>'data-projection-for' in node.attrs);
  const projectedRows=current.rows.filter(row=>row.date!==null && row.heightCount!==null);
  assert.equal(projections.length,projectedRows.length);
  for(const row of projectedRows) {
    const point=projections.find(node=>node.attrs['data-projection-for']===row.id);
    assert.deepEqual([point.attrs.cx,point.attrs.cy],geometry.project(0,row.plotScore,row.heightCount),
      'the side view drops only time; it preserves score and the selected raw count');
    if(row.score===null) assert(point.attrs.class.includes('is-unverified') && !point.attrs.class.includes('is-pareto'));
  }
  const datedScored=plotted.filter(node=>node.attrs['data-benchmark-date']);
  for(const mark of datedScored) {
    const row=current.rows.find(row=>row.id===mark.attrs['data-benchmark-id']);
    const cap=mark.children.find(node=>'data-frontier-anchor' in node.attrs);
    const stem=mark.children.find(node=>node.attrs.class==='skyline-stem skyline-mark');
    if(stem) {
      const expectedTip=geometry.project(geometry.timeFraction(row.time),row.plotScore,row.heightCount);
      assert.deepEqual([stem.attrs.x2,stem.attrs.y2],expectedTip,
        'spreading a cap cannot change the measured time, score or count at its stem');
    }
    for(const other of datedScored) {
      if(other===mark) continue;
      const otherCap=other.children.find(node=>'data-frontier-anchor' in node.attrs);
      assert(Math.hypot(cap.attrs.cx-otherCap.attrs.cx,cap.attrs.cy-otherCap.attrs.cy)>=9.99,
        'nearby and coincident scored benchmarks must all remain targetable');
    }
  }
  const pending=drawn.filter(node=>node.attrs.class?.startsWith('skyline-pending-point ') && node.attrs['data-benchmark-date']);
  for(const mark of drawn.filter(node=>'data-benchmark-date' in node.attrs)) {
    const row=current.dated.find(row=>row.id===mark.attrs['data-benchmark-id']);
    assert.equal(mark.attrs['data-benchmark-date'],row.date);
    assert(row.date>=SKYLINE_START_DATE);
    if(row.dateReference) {
      assert.equal(mark.details.url,row.dateReference.source_url,
        'recovered dates must expose their primary source on the visible mark');
      assert.equal(mark.details.urlLabel,'Open date source ↗');
    }
  }
  for(const mark of pending) {
    const row=current.pending.find(row=>row.id===mark.attrs['data-benchmark-id']);
    const cap=mark.children.find(node=>node.attrs.class==='skyline-pending-cap');
    assert.equal(cap.attrs.cx,geometry.project(geometry.timeFraction(row.time),0)[0],
      'a missing-score dot preserves the exact date, not its alphabetic position in a year bin');
    for(const other of pending) {
      if(other===mark) continue;
      const otherCap=other.children.find(node=>node.attrs.class==='skyline-pending-cap');
      assert(Math.hypot(cap.attrs.cx-otherCap.attrs.cx,cap.attrs.cy-otherCap.attrs.cy)>=11.99,
        'numeric scores on other scales remain individually visible and targetable');
    }
  }
  const undatedScored=plotted.filter(node=>node.attrs['data-date-basis']==='unknown');
  for(const mark of undatedScored) {
    const row=current.rows.find(row=>row.id===mark.attrs['data-benchmark-id']);
    const cap=mark.children.find(node=>'data-frontier-anchor' in node.attrs);
    assert.equal(cap.attrs.cy,580-row.plotScore*5,'unknown dates retain the exact reported score in the visible main chart');
    for(const other of undatedScored) {
      if(other===mark) continue;
      const otherCap=other.children.find(node=>'data-frontier-anchor' in node.attrs);
      assert(Math.hypot(cap.attrs.cx-otherCap.attrs.cx,cap.attrs.cy-otherCap.attrs.cy)>=8.99,
        'undated scores do not cover each other');
    }
  }
  const axisLabels=drawn.filter(node=>node.tag==='text').map(node=>node.text);
  assert(axisLabels.includes('2024'));
  for(const year of ['2010','2013','2016','2019','2022','2023','Before 2022']) assert(!axisLabels.includes(year));
  const maxY=Number(rendered.attrs.viewBox.split(' ').at(-1));
  for(const text of drawn.filter(n=>n.tag==='text')) {
    assert(text.attrs.x>=0 && text.attrs.x<=Number(rendered.attrs.viewBox.split(' ')[2]) && text.attrs.y>=0 && text.attrs.y<=maxY,
      `${text.text}: label anchor outside viewBox`);
  }
}
const selected=new Set([full.visible.find(row=>row.displayScore<70).id]);
const querySlice=buildSkylineModel(catalog,70,selected);
assert.deepEqual(querySlice.visible.map(row=>row.id),[...selected]);
assert.equal(querySlice.population,expected,'a search never redefines the universe');
const unscoredSelection=new Set([full.all.find(row=>!Number.isFinite(row.displayScore)).id]);
assert.equal(buildSkylineModel(catalog,100,unscoredSelection).visible.length,0,
  'searching for an unscored record does not restore it to the score figure');
console.log('Full-corpus coverage, source parity, unknown measurements, score slicing, Pareto, and SVG construction passed.');

// Alias, domain and no-score searches apply to every source with the same ranking.
const nameSearch = new Function('foldName', `${fn('searchBenchmarkIndex')}\nreturn searchBenchmarkIndex;`)(
  value=>String(value || '').toLowerCase().replace(/[^a-z0-9]+/g,''));
const searchable = [
  {slug:'prefix',name:'AutomationBench',source:'model_reports',aliases:['HLEAutomationBench']},
  {slug:'exact',name:'Humanity Last Exam',source:'artificial_analysis',aliases:['HLE']},
  {slug:'domain',name:'Unscored test',source:'opencompass_hub',categories:['science']},
];
assert.deepEqual(nameSearch(searchable,'HLE').map(row=>row.slug),['exact','prefix']);
assert.deepEqual(nameSearch(searchable,'science').map(row=>row.slug),['domain']);
assert.deepEqual(nameSearch(searchable.map(row=>({...row,source:'another_source'})),'HLE').map(row=>row.slug),['exact','prefix']);

// Execute the shared slider handler against both sets of controls.
state.benchmarkIndex = fixtureRecords;
const controls = new Map(['leaderboard-score-filter','leaderboard-score-value','saturation-score-filter','saturation-score-value'].map(id=>[id,{}]));
let skylineRenders=0, saturationRenders=0, urlWrites=0;
const filters = new Function('state','byId','t','renderBenchmarkSkyline','renderSaturation','writeUrl',`
  const BENCHMARK_SEARCH_LIMIT = 50;
  ${fn('scoreCutoff')}
  ${fn('syncScoreFilters')}
  ${fn('setScoreFilter')}
  return {setScoreFilter,syncScoreFilters};
`)(state,id=>controls.get(id),text=>text,()=>skylineRenders++,()=>saturationRenders++,()=>urlWrites++);
state.view='leaderboard';
state.benchmarkQuery='';
state.lfrontier='old95';
state.lfrontierExplicit=true;
state.benchmarkVisibleLimit=100;
filters.setScoreFilter(40);
assert.equal(skylineRenders,1);
assert.equal(saturationRenders,0);
assert.equal(state.benchmarkVisibleLimit,100);
assert.equal(state.lfrontier,'old95');
for (const view of ['leaderboard','saturation']) assert.equal(controls.get(`${view}-score-filter`).value,40);
state.view='saturation';
filters.setScoreFilter(60);
assert.equal(saturationRenders,1);
assert.equal(skylineRenders,1);
assert.equal(state.benchmarkVisibleLimit,50);
assert.equal(state.lfrontier,'old95','selected histories remain complete outside the browsing cutoff');
state.benchmarkQuery='NeedleBench';
state.benchmarkVisibleLimit=100;
filters.setScoreFilter(10);
assert.equal(saturationRenders,1,'the slider must not rebuild an unfiltered search');
assert.equal(state.benchmarkVisibleLimit,100,'changing the paused filter must not reset search pagination');
assert.deepEqual(scores.saturationRows().map(row=>row.id),['old95','unscored']);
assert.equal(state.lscore,10);
state.benchmarkQuery='';
assert(!scores.saturationRows().some(row=>row.id==='old95'));
filters.setScoreFilter(100);
assert.equal(controls.get('leaderboard-score-value').textContent,'All');
assert.equal(controls.get('saturation-score-value').textContent,'All');
assert.equal(urlWrites,4);
console.log('Shared slider, independent rankings, and full-catalog Saturation searches passed.');

// Exercise the active score renderer with the rebuilt publisher leaderboard.
// Checking the retired scoreTrackChart source would miss both of these bugs.
const scoreChartDeps = {
  svgElement, t: translate, window: {innerWidth: 1280},
  catalogSourceMeta: source => ({name: source}),
  dateValue: date => Date.parse(date), formatDate: date => date,
  frontierPointRevealDelay: () => 0,
  frontierPointSizes: () => ({face: 9, glyph: 12}),
  modelGlyph: () => svgElement('path'),
  makeFrontierPointInteractive: (node, details) => {node.details = details;},
  enableFrontierTouchTargets: () => {},
};
const renderScores = new Function(...Object.keys(scoreChartDeps),
  ['catalogPlottedRows','catalogDisplayFactor','catalogScorePositions','catalogRecordSetters','recordSetterPath','catalogScoreChart'].map(fn).join('\n') + '\nreturn catalogScoreChart;'
)(...Object.values(scoreChartDeps));
const publisherPayload = JSON.parse(readFileSync('site/data/benchmarks/frontier_challenge.json','utf8')).scores_by_source.model_reports;
for (const viewport of [1280, 390]) {
  scoreChartDeps.window.innerWidth = viewport;
  const rendered = renderScores('model_reports', publisherPayload);
  const marks = rendered.children.filter(node => node.attrs['data-frontier-point'] === '');
  assert.equal(marks.length,13);
  const faces = marks.map(node => node.children.find(child => child.tag === 'circle'));
  assert.equal(new Set(faces.map(node => `${node.attrs.cx}|${node.attrs.cy}`)).size,13,
    'each tied system needs its own selectable position');
  const yByScore = new Map();
  for (const mark of marks) {
    const face = mark.children.find(child => child.tag === 'circle');
    const details = Object.fromEntries(mark.details.rows.map(row => [row.label,row.value]));
    const score = details['Score as reported'];
    if (yByScore.has(score)) assert.equal(face.attrs.cy,yByScore.get(score),'ties keep exact score heights');
    yByScore.set(score,face.attrs.cy);
    assert.equal(details['Measured by'],'ApodexAI');
    assert.equal(details['Reported by'],'benchmark publisher');
    assert.equal(mark.details.url,'https://apodexai.github.io/FrontierAgent/benchmarks/FrontierChallenge/');
    assert.equal(details['Document publication date'],'2026-08-25');
    assert(face.attrs.cx >= 68 && face.attrs.cx <= (viewport <= 760 ? 500 : 900));
  }
  const guides = rendered.children.filter(node => node.attrs.class === 'score-tie-guide');
  assert.equal(guides.length,5);
  assert(guides.every(node => node.attrs.x1 === 68 && node.attrs.y1 === node.attrs.y2));
  assert(rendered.children.some(node => node.tag === 'text' && node.text === '2026-08-25'));
}
// Chronological spacing stays unchanged when there is no collision; zero stays.
const ordinary = renderScores('llm_stats', {series:{direction:'higher_is_better'}, rows:[
  {value:0,reported_date:'2025-01-01',obs_id:'zero',model_name:'Zero'},
  {value:50,reported_date:'2026-01-01',obs_id:'later',model_name:'Later'},
]});
const ordinaryMarks = ordinary.children.filter(node => node.attrs['data-frontier-point'] === '');
assert.equal(ordinaryMarks.length,2);
assert.deepEqual(ordinaryMarks.map(node=>node.children.find(child=>child.tag==='circle').attrs.cx),[68,500]);
assert(!ordinary.children.some(node=>node.attrs.class==='score-tie-guide'));

// Field scope narrows browsing, but a name query still searches every source.
state.benchmarkIndex = [
  {slug:'agent',name:'Agent',source:'model_reports',categories:['tool_use'],score_summary:summary(40)},
  {slug:'unknown',name:'Unknown',source:'llm_stats',categories:[],score_summary:summary(null,0)},
  {slug:'safety',name:'Safety',source:'artificial_analysis',categories:['safety'],score_summary:summary(95)},
];
state.researchField = 'agents';
state.researchSub = 'Tool use';
state.lscore = 70;
state.benchmarkQuery = '';
assert.deepEqual(scores.saturationRows().map(r=>r.id), ['agent']);
state.benchmarkQuery = 'Safety';
assert.deepEqual(scores.saturationRows().map(r=>r.id), ['safety']);
assert.equal(state.researchField, 'agents');
state.benchmarkQuery = 'Unknown';
assert.deepEqual(scores.saturationRows().map(r=>r.id), ['unknown']);
state.benchmarkQuery = '';
assert.deepEqual(scores.saturationRows().map(r=>r.id), ['agent']);
