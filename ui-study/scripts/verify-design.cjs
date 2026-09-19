/* Source/cascade checks complement DOM tests; they do not measure browser layout. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const css = require('css-tree');
const root = path.resolve(__dirname, '../dist');
const files = fs.readdirSync(root, {recursive:true}).filter(name=>name.endsWith('.html'));
const headers = new Set();
let pages = 0;
for (const file of files) {
  const html = fs.readFileSync(path.join(root,file),'utf8');
  if (html.includes('http-equiv="refresh"')) continue;
  const matches = [...html.matchAll(/<header class="site-header">[\s\S]*?<\/header>/g)];
  assert.equal(matches.length,1,file+' needs one header');
  const header = matches[0][0];
  assert.equal((header.match(/data-active="true"/g)||[]).length,1,file+' needs one active item');
  assert.match(header, /<img src="\/icon.svg" width="32" height="32" alt="">/);
  headers.add(header.replace(/data-active="(?:true|false)"(?: aria-current="page")?/g,''));
  assert.match(html,/href="\/assets\/study.css"/);
  for (const inline of html.matchAll(/<style>([\s\S]*?)<\/style>/g)) {
    assert.match(inline[1],/@layer legacy/);
  }
  pages++;
}
assert.equal(headers.size,1,'Every route must share the same header structure');
const source = fs.readFileSync(path.resolve(__dirname,'../design/study.css'),'utf8');
const errors = [];
css.parse(source,{onParseError:error=>errors.push(error.message)});
assert.deepEqual(errors,[]);
for (const filename of ['assets/styles.css','assets/blog.css','assets/logos.css','explore/styles.css']) {
  const content=fs.readFileSync(path.join(root,filename),'utf8');
  assert.match(content,/^@layer legacy, tokens, base, components, pages, responsive;\n@layer legacy/);
  css.parse(content,{onParseError:error=>errors.push(error.message)});
}
assert.deepEqual(errors,[]);
function luminance(hex){const rgb=hex.match(/\w\w/g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
function contrast(foreground,background){const values=[luminance(foreground),luminance(background)].sort((a,b)=>b-a);return (values[0]+.05)/(values[1]+.05);}
const pairs=[['202733','ffffff'],['55606f','ffffff'],['55606f','f6f7f9'],['2b5fa8','edf3fc']];
const ratios=pairs.map(([text,bg])=>({text:'#'+text,background:'#'+bg,ratio:+contrast(text,bg).toFixed(2)}));
for(const {ratio} of ratios)assert.ok(ratio>=4.5);
console.log(JSON.stringify({pages,headerVariants:headers.size,cssParseErrors:errors.length,textContrast:ratios,visualLayout:'Not measured: static managed preview is unavailable.'},null,2));
