import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = readFileSync('site/assets/app.js', 'utf8');
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf('\n}\n', start) + 2);
}
function constant(name) {
  const start = source.indexOf(`const ${name} = {`);
  return source.slice(start, source.indexOf('\n};', start) + 3);
}
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.ownText = ''; }
  set textContent(value) { this.ownText = value; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(' '); }
  append(child) { this.children.push(child); }
  setAttribute(key, value) { this.attrs[key] = value; }
}
let language = 'en';
const document = { createElement: tag => new Node(tag) };
const functions = ['t', 'element', 'formatDate', 'safeHttpUrl', 'catalogSourceMeta', 'catalogDisplayFactor', 'catalogSourceTable', 'catalogScoreResults', 'catalogScoresBlock'];
const render = new Function('document', 'getLang', `
${constant('I18N')}
${constant('CATALOG_SOURCE_META')}
const dateValue = value => Date.parse(value);
const catalogScoreChart = () => null;
const infoDisclosure = text => element('details', {text});
${functions.map(fn).join('\n')}
return {catalogScoreResults, catalogScoresBlock};
`)(document, () => language);
const all = (node, predicate) => [node, ...node.children.flatMap(child => all(child, predicate))].filter(predicate);
const rows = Array.from({length: 1100}, (_, i) => ({
  obs_id: `observation-${i}`, model_name: `Model ${i}`, value: i,
  reported_date: i % 2 ? '2026-09-01' : null, date_precision: 'model_announcement',
}));
rows[0] = {obs_id: 'zero', model_name: '<Model zero>', raw_value: 0, value: 0, reported_date: null, source_url: 'javascript:alert(1)'};
rows[1] = {obs_id: 'document', model_name: 'Same model', value: 42, reported_date: '2026-09-02', date_precision: 'document_publication', instrument: 'Variant A', protocol: 'no tools', source_url: 'https://example.org/report'};
rows[2] = {obs_id: 'variant', model_name: 'Same model', value: 43, reported_date: '2026-09-02', date_precision: 'document_publication', instrument: 'Variant B', protocol: 'with tools'};
const originalOrder = rows.map(row => row.obs_id);
const section = render.catalogScoreResults('model_reports', rows);
const items = all(section, node => node.tag === 'li');
assert.equal(items.length, rows.length, 'large histories never truncate observations');
for (const row of rows) assert(items.some(item => item.textContent.includes(row.model_name)));
const zero = items.find(item => item.textContent.includes('<Model zero>'));
assert.equal(all(zero, node => node.className === 'catalog-result-value')[0].textContent, '0');
assert(zero.textContent.includes('Date unknown'));
assert.equal(all(zero, node => node.tag === 'a').length, 0, 'unsafe URLs are not linked');
assert(items.some(item => item.textContent.includes('Variant A') && item.textContent.includes('no tools')));
assert(items.some(item => item.textContent.includes('Variant B') && item.textContent.includes('with tools')));
assert.deepEqual(rows.map(row => row.obs_id), originalOrder, 'rendering does not reorder source observations');
assert.equal(render.catalogScoreResults('llm_stats', []), null);
const separate = render.catalogScoresBlock({scores_by_source: {
  model_reports: {rows}, llm_stats: {rows: [{model_name: 'Registry-only model', value: 99}]},
}});
const sources = all(separate, node => node.className === 'catalog-source');
assert.equal(sources.length, 2);
assert.deepEqual(sources.map(node => all(node, item => item.tag === 'li').length).sort((a,b) => a-b), [1, 1100]);
assert.equal(sources.filter(node => node.textContent.includes('Registry-only model')).length, 1);
language = 'zh';
const chinese = render.catalogScoreResults('model_reports', rows);
assert(all(chinese, node => node.tag === 'h3')[0].textContent.includes('Benchmark 已报告成绩 · 模型报告'));
for (const label of ['模型发布日期', '文档发布日期', '日期未知', '打开来源记录 ↗']) assert(chinese.textContent.includes(label), label);
for (const label of ['Reported benchmark scores', 'Model reports', 'model release date', 'Document publication date', 'Date unknown', 'Open source record']) assert(!chinese.textContent.includes(label), label);
language = 'en';
assert(render.catalogScoreResults('model_reports', rows).textContent.includes('Reported benchmark scores · Model reports'));
console.log('Complete histories, undated zero scores, source partitions, run variants, safe links, and Chinese/English rendering passed.');
