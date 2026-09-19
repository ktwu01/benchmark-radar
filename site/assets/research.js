import {fields, recordFields} from "./fields.js";
/* Research explorer. Source records stay separate; unknown scores stay unknown. */
(() => {
  'use strict';
  const root = document.getElementById('radar-explorer');
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const safeUrl = value => { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? escape(u.href) : ''; } catch { return ''; } };
  const text = (en, zh) => state.lang === 'zh' ? zh : en;
  const number = value => value == null ? '—' : Number(value).toLocaleString('en-US', {maximumFractionDigits: 2});
  const sourceNames = {model_reports:'Model reports',llm_stats:'LLM Stats',artificial_analysis:'Artificial Analysis',opencompass_hub:'OpenCompass Hub'};
  let catalog = [], filtered = [];
  const state = {field:'all', sub:'', query:'', source:'', score:'all', sort:'models', page:0, view:'list', lang:'en'};
  const pageSize = 12;
  const label = f => state.lang === 'zh' ? f.zh : f.en;
  const tagMatches = (r,tags) => tags.some(t=>r.tagsLower.includes(t.toLowerCase()));
  const inField = (r,id) => id==='all' || r.fields.includes(id);
  const validPercent = r => r.unit==='percent' && r.direction==='higher_is_better' && Number.isFinite(r.max) && r.max>=0 && r.max<=100;
  const band = r => r.raw==null ? 'unknown' : !validPercent(r) ? 'unverified' : r.max<70 ? 'under70' : r.max<90 ? '70to90' : 'over90';
  const scoreText = r => r.raw==null ? '—' : r.unit==='percent' ? `${number(r.max)}%` : `${number(r.raw)}${r.unit==='usd'?' USD':r.unit==='elo'?' Elo':''}`;
  const fieldOf = r => fields.find(f=>f.id===state.field&&r.fields.includes(f.id)) || fields.find(f=>r.fields.includes(f.id)) || fields[fields.length-1];
  const chromeI18n=JSON.parse(document.getElementById('chrome-i18n').textContent);
  function translateChrome(){
    document.querySelectorAll('[data-i18n]').forEach(el=>{const key=el.dataset.i18n;el.textContent=state.lang==='zh'?(chromeI18n[key]||key):key});
    const toggle=$('lang-toggle');toggle.setAttribute('aria-pressed',String(state.lang==='zh'));
    toggle.title=state.lang==='zh'?'Switch to English':'Switch to Chinese (中文)';
    $('lang-toggle-label').textContent=state.lang==='zh'?'EN':'中';
  }
  function readHash() {
    const p=new URLSearchParams(location.hash.slice(1));
    state.field=fields.some(f=>f.id===p.get('field'))?p.get('field'):'all';
    state.sub=p.get('sub')||'';state.query=p.get('q')||'';state.source=sourceNames[p.get('source')]?p.get('source'):'';
    state.score=['all','under70','70to90','over90','unknown','unverified'].includes(p.get('score'))?p.get('score'):'all';
    state.sort=['models','name','date','documents'].includes(p.get('sort'))?p.get('sort'):'models';state.view=p.get('view')==='coverage'?'coverage':'list';state.lang=p.get('lang')==='zh'?'zh':p.has('lang')?'en':savedLanguage();state.page=0;
  }
  function saveHash() {
    const p=new URLSearchParams();
    if(state.field!=='all')p.set('field',state.field);if(state.sub)p.set('sub',state.sub);if(state.query)p.set('q',state.query);if(state.source)p.set('source',state.source);if(state.score!=='all')p.set('score',state.score);if(state.sort!=='models')p.set('sort',state.sort);if(state.view!=='list')p.set('view',state.view);if(state.lang!=='en')p.set('lang',state.lang);
    const hash=p.toString();if(location.hash.slice(1)!==hash)try{history.pushState(null,'',`${location.pathname}${location.search}${hash?'#'+hash:''}`)}catch{/* Embedded previews may use an opaque origin; interactions remain local. */}
  }
  function change(changes) { Object.assign(state,changes,{page:0});saveHash();render(); }
  function scopedRecords() {
    const f=fields.find(f=>f.id===state.field);const sub=f?.subs.find(s=>s[0]===state.sub);
    return catalog.filter(r=>inField(r,state.field)&&(!sub||tagMatches(r,sub[2])));
  }
  function nav() {
    $('field-nav').innerHTML=`<button type="button" class="field-button ${state.field==='all'?'active':''}" data-field="all" aria-pressed="${state.field==='all'}">${text('All research','全部领域')}<span class="nav-count">${number(catalog.length)}</span></button><div class="nav-divider"></div>`+fields.map(f=>`<button type="button" class="field-button ${state.field===f.id?'active':''}" data-field="${f.id}" aria-pressed="${state.field===f.id}">${label(f)}<span class="nav-count">${number(catalog.filter(r=>inField(r,f.id)).length)}</span></button>`).join('');
    const f=fields.find(f=>f.id===state.field);
    $('subfield-nav').innerHTML=f?.subs.length?`<div class="subfield-heading">${text('RESEARCH DIRECTIONS','研究方向')}</div>`+f.subs.map(s=>`<button type="button" class="subfield-button ${state.sub===s[0]?'active':''}" data-sub="${s[0]}" aria-pressed="${state.sub===s[0]}"><span>${state.lang==='zh'?s[1]:s[0]}</span><span>${catalog.filter(r=>inField(r,f.id)&&tagMatches(r,s[2])).length}</span></button>`).join(''):'';
    $('direction-toggle').hidden=!f?.subs.length;
    $('direction-toggle').textContent=text('Research direction · ','研究方向 · ')+(state.sub || text('All directions','全部方向'));
    $('direction-tabs').innerHTML=f?.subs.length?`<button type="button" data-sub="" aria-pressed="${!state.sub}">${text('All directions','全部方向')}</button>`+f.subs.map(s=>`<button type="button" data-sub="${s[0]}" aria-pressed="${state.sub===s[0]}"><span>${state.lang==='zh'?s[1]:s[0]}</span><span>${catalog.filter(r=>inField(r,f.id)&&tagMatches(r,s[2])).length}</span></button>`).join(''):'';
  }
  function tiles(scope) {
    if(state.field==='all'){
      $('field-grid').innerHTML=fields.map((f,i)=>{const rows=catalog.filter(r=>inField(r,f.id)),scored=rows.filter(r=>r.raw!=null).length;return `<button class="field-tile" type="button" data-field="${f.id}"><div class="tile-header"><span>${label(f)}</span></div><span class="tile-count">${number(rows.length)}</span><div class="tile-foot"><span>${number(scored)} ${text('with scores','条有分数')}</span></div><div class="tile-track" aria-hidden="true"><span style="width:${rows.length?scored/rows.length*100:0}%"></span></div></button>`;}).join('');
    }else{
      const scored=scope.filter(r=>r.raw!=null).length;
      $('field-grid').innerHTML=`<div class="domain-summary"><div><span class="summary-count">${number(scope.length)}</span><span class="summary-label">${text('Benchmark records','Benchmark 记录')}</span></div><div><span class="summary-count">${number(scored)}</span><span class="summary-label">${text('With reported scores','已有分数记录')}</span></div><div><span class="summary-count">${number(scope.length-scored)}</span><span class="summary-label">${text('No reported score','尚无分数记录')}</span></div></div>`;
    }
  }
  function savedLanguage(){try{return localStorage.getItem("benchmark-radar:lang")==="zh"?"zh":"en"}catch{return "en"}}
  function render() {
    translateChrome();
    root.querySelectorAll('[data-en]').forEach(el=>el.textContent=el.getAttribute(state.lang==='zh'?'data-zh':'data-en'));
    const f=fields.find(f=>f.id===state.field);const sub=f?.subs.find(s=>s[0]===state.sub);
    const fieldName=sub?(state.lang==='zh'?sub[1]:sub[0]):f?label(f):text('All research','全部领域');
    $('page-title').textContent=f?fieldName:text('Research explorer','Benchmark 研究地图');
    document.documentElement.lang=state.lang==='zh'?'zh-CN':'en';
    $('lang-toggle-label').textContent=state.lang==='zh'?'EN':'中';$('lang-toggle').setAttribute('aria-pressed',String(state.lang==='zh'));$('lang-toggle').setAttribute('aria-label',state.lang==='zh'?'Switch to English':'切换为中文');
    $('name-filter').placeholder=text('Filter benchmark names…','筛选 benchmark 名称…');$('name-filter').value=state.query;$('name-filter').setAttribute('aria-label',text('Filter benchmark names','筛选 benchmark 名称'));
    $('source-filter').innerHTML=`<option value="">${text('All sources','全部来源')}</option>`+Object.entries(sourceNames).map(([k,v])=>`<option value="${k}">${v}</option>`).join('');$('source-filter').value=state.source;
    const scoreOptions=[['all','All score ranges','全部分数范围'],['under70','Below 70%','低于 70%'],['70to90','70–90%','70–90%'],['over90','90% and above','90% 及以上'],['unknown','No reported score','尚无分数'],['unverified','Other / unverified scale','其他 / 量纲未确认']];
    $('score-filter').innerHTML=scoreOptions.map(([v,en,zh])=>`<option value="${v}">${text(en,zh)}</option>`).join('');$('score-filter').value=state.score;
    $('sort').innerHTML=[['models','Scored models ↓','有分数的模型数 ↓'],['name','Name A–Z','名称 A–Z'],['date','Release date ↓','发布日期 ↓'],['documents','Source documents ↓','来源文档数 ↓']].map(([v,en,zh])=>`<option value="${v}">${text(en,zh)}</option>`).join('');$('sort').value=state.sort;
    const scope=scopedRecords();nav();tiles(scope);
    const needle=state.query.trim().toLowerCase();
    filtered=scope.filter(r=>(!needle||[r.name,...r.aliases].some(n=>n.toLowerCase().includes(needle)))&&(!state.source||r.source===state.source)&&(state.score==='all'||band(r)===state.score));
    filtered.sort((a,b)=>state.sort==='name'?a.name.localeCompare(b.name):state.sort==='date'?(b.date||'').localeCompare(a.date||'')||a.name.localeCompare(b.name):((state.sort==='documents'?b.docs:b.models)??-1)-((state.sort==='documents'?a.docs:a.models)??-1)||a.name.localeCompare(b.name));
    $('result-count').innerHTML=`<strong>${number(filtered.length)}</strong> ${text('records','条记录')} ${state.field==='all'?'':`· ${escape(fieldName)}`}${state.query||state.source||state.score!=='all'?` <span> / ${number(scope.length)}</span>`:''}`;
    $('clear').hidden=!(state.query||state.source||state.score!=='all'||state.sub);
    $('catalog-panel').hidden=state.view!=='list';$('coverage-panel').hidden=state.view!=='coverage';$('list-tab').setAttribute('aria-selected',String(state.view==='list'));$('coverage-tab').setAttribute('aria-selected',String(state.view==='coverage'));
    renderRows();renderCoverage();
    $('method-copy').textContent=text('Counts refer to source records, not unique benchmark names. A record can belong to several fields; field totals overlap. Field groups map existing source tags without merging records. Score ranges include only declared percentages where higher is better; other scales and missing scores remain visible. Highest reported scores can mix protocols and do not establish saturation. This view uses the locally generated catalog; collection dates differ by source. Name filtering is literal and includes aliases.','数量指来源记录，不代表去重后的 benchmark 数量。一个记录可以属于多个领域，各领域数量不可直接相加。领域分组根据来源标签映射，不合并记录。分数区间只纳入量纲明确且越高越好的百分比；其他量纲与缺失分数均保留。最高分可能来自不同测试协议，不能单凭高分断言已饱和。此视图使用本地生成的目录，各来源采集日期不同。名称筛选按字面匹配，包含别名。');
  }
  function renderRows() {
    const maxPage=Math.max(0,Math.ceil(filtered.length/pageSize)-1);state.page=Math.min(state.page,maxPage);
    const visible=filtered.slice(state.page*pageSize,(state.page+1)*pageSize);
    $('rows').innerHTML=visible.map(r=>`<tr data-record="${escape(r.id)}"><td><button type="button" class="benchmark-name" aria-haspopup="dialog" data-detail="${escape(r.id)}">${escape(r.name)}</button><span class="source-line">${sourceNames[r.source]}</span></td><td><span class="field-tag">${label(fieldOf(r))}</span></td><td>${r.raw==null?`<span class="na">${text('Not reported','暂无分数')}</span>`:`<span class="score-value">${scoreText(r)}</span>${r.unit?'':`<span class="score-sub">${text('source scale','原始量纲')}</span>`}`}</td><td>${r.models==null?`<span class="na">${text('Not recorded','暂无记录')}</span>`:`<span class="score-value">${number(r.models)}</span>`}</td><td>${r.date?escape(r.date):`<span class="na">${text('Unknown','未知')}</span>`}</td><td><span class="row-arrow" aria-hidden="true">↗</span></td></tr>`).join('');
    $('empty').hidden=visible.length>0;$('empty').innerHTML=text('No matching benchmarks. Try another name or clear the filters.','没有符合条件的 benchmark，可更换名称或清除筛选。');
    $('page-info').textContent=filtered.length?`${state.page*pageSize+1}–${Math.min((state.page+1)*pageSize,filtered.length)} ${text('of','/')} ${number(filtered.length)}`:'0';
    $('previous').disabled=state.page===0;$('next').disabled=state.page===maxPage;
  }
  function renderCoverage() {
    const bands=[['under70','Below 70%','低于 70%'],['70to90','70–90%','70–90%'],['over90','90% and above','90% 及以上'],['unverified','Other / unverified scale','其他 / 量纲未确认'],['unknown','No reported score','尚无分数']];
    $('coverage-panel').innerHTML=`<div class="coverage-view"><h2>${text('Reported score ranges','已报告分数分布')}</h2><p>${text('Select a range to inspect its benchmarks.','选择一个区间，查看对应 benchmark。')}</p>`+bands.map(([id,en,zh])=>{const n=filtered.filter(r=>band(r)===id).length;return `<button type="button" class="band-row" data-band="${id}" aria-label="${escape(text(en,zh))}: ${n}"><span>${text(en,zh)}</span><span class="band-track"><span style="width:${filtered.length?n/filtered.length*100:0}%"></span></span><span class="band-count">${number(n)}</span></button>`;}).join('')+`<div class="coverage-caption">${text('Share of records · percentage ranges use verified scales.','记录占比 · 百分比区间使用已确认量纲。')}</div></div>`;
  }
  function chart(r) {
    const points=r.history.filter(h=>h[0]&&/^\d{4}-\d{2}-\d{2}/.test(h[0])&&Number.isFinite(h[1])).map(h=>({date:h[0].slice(0,10),value:h[1],model:h[2]})).sort((a,b)=>a.date.localeCompare(b.date));
    if(!points.length)return `<p class="chart-note">${text('No dated numeric observations in this source record.','这个来源记录中没有带日期的数值观测。')}</p>`;
    const w=Math.min(660,Math.max(260,root.getBoundingClientRect().width-80)),h=220,l=54,right=20,top=26,bottom=40;const dates=points.map(p=>Date.parse(p.date)),values=points.map(p=>p.value);let xmin=Math.min(...dates),xmax=Math.max(...dates),ymin=Math.min(...values),ymax=Math.max(...values);if(xmin===xmax){xmin-=86400000;xmax+=86400000}const pad=(ymax-ymin)*.12||Math.max(1,Math.abs(ymax)*.1);ymin-=pad;ymax+=pad;const x=d=>l+(Date.parse(d)-xmin)/(xmax-xmin)*(w-l-right),y=v=>top+(ymax-v)/(ymax-ymin)*(h-top-bottom);
    let lines='';for(let i=0;i<4;i++){const v=ymin+(ymax-ymin)*i/3;lines+=`<line x1="${l}" x2="${w-right}" y1="${y(v)}" y2="${y(v)}" stroke="#e1e6ee"/><text x="${l-7}" y="${y(v)+4}" text-anchor="end" fill="#677386" font-size="13">${number(v)}</text>`;}
    return `<svg class="history-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${escape(text('Reported score observations over time','各日期的已报告分数'))}"><title>${escape(r.name)} · ${text('Score observations','分数观测')}</title>${lines}<text x="${l}" y="12" fill="#677386" font-size="13">${r.unit==='percent'?'%':text('Source units','原始单位')}</text>${points.map(p=>`<circle cx="${x(p.date)}" cy="${y(p.value)}" r="3.2" fill="#657fa1" opacity=".75"><title>${escape(p.date+' · '+p.model+' · '+number(p.value))}</title></circle>`).join('')}<text x="${l}" y="${h-10}" fill="#677386" font-size="13">${points[0].date}</text><text x="${w-right}" y="${h-10}" text-anchor="end" fill="#677386" font-size="13">${points[points.length-1].date}</text></svg>`;
  }
  function renderDetail(id) {
    const r=catalog.find(x=>x.id===id);if(!r)return;
    const history=[...r.history].sort((a,b)=>(b[0]||'').localeCompare(a[0]||''));const basis=[...new Set(history.map(h=>h[5]).filter(Boolean))];
    const modelProxy=basis.some(b=>b==='model_announcement'||b==='model_release');
    const evidence=history.map(h=>`<div class="evidence-item"><span>${escape(h[0]?.slice(0,10)||text('Undated','日期未知'))}</span><div><a href="${safeUrl(h[4])}" target="_blank" rel="noopener">${escape(h[2]||text('Unknown model','未知模型'))} ↗</a>${h[3]?`<details class="run-details"><summary>${text('Run details','运行条件')}</summary><p>${escape(h[3])}</p></details>`:''}</div><span class="evidence-score">${number(h[1])}${r.unit==='percent'?'%':''}</span></div>`).join('');
    const artifacts=r.artifacts.filter(a=>safeUrl(a.url));
    $('detail-content').innerHTML=`<div class="detail-top"><span>${sourceNames[r.source]} · ${label(fieldOf(r))}</span><button type="button" class="close-detail" id="close-detail" aria-label="${text('Close details','关闭详情')}">×</button></div><h2 id="detail-title" class="detail-title">${escape(r.name)}</h2><p class="detail-description">${escape(r.description||text('No description recorded by this source.','这个来源尚未记录介绍。'))}</p><div class="detail-metrics"><div><strong>${scoreText(r)}</strong><span>${text('Highest reported','最高已报告分数')}</span></div><div><strong>${number(r.models)}</strong><span>${text('Scored models','有分数的模型数')}</span></div><div><strong>${number(r.docs)}</strong><span>${text('Source documents','来源文档数')}</span></div></div><h3 class="detail-section-title">${text('Reported scores over time','已报告分数随时间变化')}</h3>${chart(r)}<p class="chart-note">${text('Each dot is a reported observation. Protocols can differ; dots are not connected into a comparable trend.','每个点是一条已报告观测。测试协议可能不同，因此不连成可比趋势线。')} ${modelProxy?text('Some dates are model-release proxies, not evaluation dates.','部分日期为模型发布日期代理，不是评测日期。'):text('Dates follow source publication records.','日期按来源报告记录展示。')}</p><a class="research-detail-link" href="/saturation/?lfrontier=${encodeURIComponent(r.slug)}&field=${encodeURIComponent(state.field)}&sub=${encodeURIComponent(state.sub)}">${text('Open full score history →','查看完整分数历史 →')}</a><h3 class="detail-section-title">${text('Evidence','原始证据')} <span class="na">${number(history.length)} ${text('numeric observations','条数值观测')}</span></h3><div class="evidence-list">${evidence||r.documents.map(d=>`<div class="evidence-item"><span>${text('Document','来源文档')}</span><a href="${safeUrl(d.source_url)}" target="_blank" rel="noopener">${escape(d.title||d.document_type)} ↗</a></div>`).join('')||text('No source documents recorded.','暂无来源文档记录。')}</div><div class="detail-links">${safeUrl(r.url)?`<a href="${safeUrl(r.url)}" target="_blank" rel="noopener">${text('Open source','打开来源')} ↗</a>`:''}${artifacts.map(a=>`<a href="${safeUrl(a.url)}" target="_blank" rel="noopener">${escape(a.kind)} ↗</a>`).join('')}<a href="/benchmarks/${encodeURIComponent(r.slug)}/" target="_blank" rel="noopener">${text('Full record','完整记录')} ↗</a></div><details class="detail-provenance"><summary>${text('Record metadata','记录信息')}</summary><p>${escape(r.id)} · ${escape(r.metric||text('Metric not recorded','未记录指标'))} · ${escape(r.direction||text('Direction unknown','方向未知'))}</p></details>`;
    $('close-detail').addEventListener('click',()=>$('detail-dialog').close());if(!$('detail-dialog').open)$('detail-dialog').showModal();
  }
  let detailRequest = 0;
  async function openDetail(id) {
    const record=catalog.find(r=>r.id===id);if(!record)return;
    const request=++detailRequest;
    $('detail-content').textContent=text('Loading source evidence…','正在加载来源证据…');
    if(!$('detail-dialog').open)$('detail-dialog').showModal();
    try {
      if(!record.detailLoaded){
        const response=await fetch('/data/benchmarks/'+encodeURIComponent(record.slug)+'.json');
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        const detail=await response.json();
        if(detail.record?.key!==record.id)throw new Error('Record identity mismatch');
        record.documents=detail.record.documents||[];record.artifacts=detail.record.artifacts||[];
        record.history=Object.values(detail.scores_by_source||{}).flatMap(group=>(group.rows||[])
          .filter(row=>Number.isFinite(row.value)).map(row=>[
            row.reported_date,record.unit==='percent'?row.value*record.multiplier:row.value,
            row.model_name||row.model_id,typeof row.protocol==='string'?row.protocol:row.protocol?JSON.stringify(row.protocol):null,
            row.source_url,row.date_precision]));
        record.detailLoaded=true;
      }
      if(request===detailRequest&&$('detail-dialog').open)renderDetail(id);
    } catch(error) {
      if(request===detailRequest){
        $('detail-content').textContent=text('Could not load evidence. Close and retry. ','无法加载证据，请关闭后重试。 ')+error.message;
        const close=document.createElement('button');close.textContent=text('Close','关闭');close.onclick=()=>$('detail-dialog').close();$('detail-content').append(close);
      }
    }
  }
  root.addEventListener('click',e=>{
    const el=e.target.closest('button');if(!el)return;
    if(el.hasAttribute('data-field'))change({field:el.dataset.field,sub:'',query:'',score:'all'});
    else if(el.hasAttribute('data-sub')){const toggle=$('direction-toggle');toggle.setAttribute('aria-expanded','false');toggle.parentElement.dataset.expanded='false';change({sub:state.sub===el.dataset.sub?'':el.dataset.sub});}
    else if(el.hasAttribute('data-detail'))openDetail(el.dataset.detail);
    else if(el.hasAttribute('data-band'))change({score:el.dataset.band,view:'list'});
  });
  $('rows').addEventListener('click', event => {
    if (event.target.closest('button, a') || window.getSelection()?.toString()) return;
    const button = event.target.closest('tr[data-record]')?.querySelector('.benchmark-name');
    if (button) { button.focus(); button.click(); }
  });
  $('direction-toggle').addEventListener('click',()=>{const toggle=$('direction-toggle');const expanded=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(expanded));toggle.parentElement.dataset.expanded=String(expanded);});
  $('name-filter').addEventListener('input',e=>change({query:e.target.value}));
  $('source-filter').addEventListener('change',e=>change({source:e.target.value}));$('score-filter').addEventListener('change',e=>change({score:e.target.value}));$('sort').addEventListener('change',e=>change({sort:e.target.value}));
  $('clear').addEventListener('click',()=>change({query:'',source:'',score:'all',sub:''}));$('lang-toggle').addEventListener('click',()=>{const lang=state.lang==='en'?'zh':'en';try{localStorage.setItem('benchmark-radar:lang',lang)}catch{}change({lang});});
  $('list-tab').addEventListener('click',()=>change({view:'list'}));$('coverage-tab').addEventListener('click',()=>change({view:'coverage'}));
  root.querySelectorAll('[role=tab]').forEach(tab=>tab.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const target=tab.id==='list-tab'?$('coverage-tab'):$('list-tab');target.focus();target.click();}}));
  $('previous').addEventListener('click',()=>{state.page--;renderRows()});$('next').addEventListener('click',()=>{state.page++;renderRows()});
  $('detail-dialog').addEventListener('click',e=>{if(e.target===$('detail-dialog'))$('detail-dialog').close()});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)&&!$('detail-dialog').open){e.preventDefault();$('name-filter').focus()}});
  window.addEventListener('popstate',()=>{readHash();render()});
  $('export').addEventListener('click',()=>{
    const data=filtered.map(r=>({source_record_id:r.id,name:r.name,source:sourceNames[r.source],fields:r.fields,highest_reported_raw:r.raw,unit:r.unit,models_with_scores:r.models,source_documents:r.docs,released:r.date,source_url:r.url}));
    const blob=new Blob([JSON.stringify({catalog:'/data/benchmark-index.json',filters:{...state},count:data.length,records:data},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='benchmark-radar-view.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function registerExplorerTool() {
    const context=document.modelContext;
    if(!context?.registerTool)return;
    const lifecycle=new AbortController();
    const allowedFields=['all',...fields.map(f=>f.id)];
    const allowedScores=['all','under70','70to90','over90','unknown','unverified'];
    try {
      Promise.resolve(context.registerTool({
        name:'filter_benchmarks',
        title:'Filter benchmarks',
        description:'Update the visible catalog by research field, literal benchmark name, source, or score range. This changes only the current view and never modifies source records.',
        inputSchema:{type:'object',properties:{field:{type:'string',enum:allowedFields},query:{type:'string',maxLength:200},source:{type:'string',enum:['',...Object.keys(sourceNames)]},score:{type:'string',enum:allowedScores}},additionalProperties:false},
        annotations:{readOnlyHint:false,untrustedContentHint:true},
        execute(input){
          if(!input||typeof input!=='object'||Array.isArray(input))throw new Error('Expected filter object');
          for(const key of Object.keys(input))if(!['field','query','source','score'].includes(key))throw new Error('Unknown filter');
          if(input.field!==undefined&&!allowedFields.includes(input.field))throw new Error('Unknown field');
          if(input.source!==undefined&&!['',...Object.keys(sourceNames)].includes(input.source))throw new Error('Unknown source');
          if(input.score!==undefined&&!allowedScores.includes(input.score))throw new Error('Unknown score range');
          if(input.query!==undefined&&(typeof input.query!=='string'||input.query.length>200))throw new Error('Invalid name query');
          change({...input,sub:'',view:'list'});
          return {count:filtered.length,field:state.field,query:state.query,source:state.source,score:state.score,first_records:filtered.slice(0,5).map(r=>({id:r.id,name:r.name,source:sourceNames[r.source]}))};
        }
      },{signal:lifecycle.signal})).catch(()=>{});
      window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
    }catch{/* Browsers without this optional interface retain normal UI actions. */}
  }
  async function init() {
    try {
      const response=await fetch('/data/benchmark-index.json');
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const payload=await response.json();
      if(!Array.isArray(payload.benchmarks)||!payload.benchmarks.length)throw new Error('Invalid catalog');
      catalog=payload.benchmarks.map(entry=>{
        const score=entry.score_summary||{}, evidence=entry.evidence_summary||{};
        const tags=entry.categories||[];
        return {id:entry.key,slug:entry.slug,name:entry.name,aliases:entry.aliases||[],source:entry.source,
          tags,tagsLower:tags.map(t=>t.toLowerCase()),fields:recordFields(entry),description:entry.description,
          publisher:entry.publisher,date:entry.released,url:entry.source_url,max:score.display_max,
          raw:score.raw_max,unit:entry.unit,direction:entry.score_direction,multiplier:score.display_multiplier||1,
          models:evidence.model_count,docs:evidence.document_count,observations:entry.score_count,
          history:[],documents:[],artifacts:[]};
      });
      $('load-state').hidden=true;$('loaded-content').hidden=false;readHash();render();registerExplorerTool();
    }catch(error){$('load-state').textContent=`Could not load the benchmark catalog. ${error.message}. Please reload to retry.`;$('load-state').setAttribute('role','alert');}
  }
  init();
})();
