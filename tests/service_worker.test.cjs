const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
function setup(fetcher) {
  const entries=new Map();const events={};
  const context=vm.createContext({URL,Request,Response,Headers,AbortController,setTimeout,clearTimeout,
    self:{registration:{scope:'http://localhost:8011/'},addEventListener:(type,fn)=>events[type]=fn},
    caches:{open:async()=>({match:async key=>entries.get(typeof key==='string'?key:key.url)?.clone(),put:async(key,r)=>entries.set(typeof key==='string'?key:key.url,r.clone())})},fetch:fetcher});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/sw.js'),'utf8'),context);
  return {entries,request:(file,mode='cors')=>vm.runInContext(`networkFirst({url:'http://localhost:8011/${file}',mode:'${mode}'})`,context)};
}
test('offline data carries explicit cache provenance',async()=>{
  const s=setup(async()=>{throw Error('offline')});s.entries.set('http://localhost:8011/data/latest.json',new Response('{"schema_version":2}'));
  const r=await s.request('data/latest.json');assert.equal(r.headers.get('X-FPL-Cache'),'offline');assert.equal(r.status,200);
});
test('first offline visit returns an error, not an undefined response',async()=>{
  const s=setup(async()=>{throw Error('offline')});assert.equal((await s.request('data/latest.json')).status,503);
});
test('HTTP errors cannot overwrite a previously valid snapshot',async()=>{
  const s=setup(async()=>new Response('bad',{status:500}));s.entries.set('http://localhost:8011/data/latest.json',new Response('{"ok":true}'));
  assert.equal(await(await s.request('data/latest.json')).text(),'{"ok":true}');
});
test('navigation with a query falls back to the installed app shell',async()=>{
  const s=setup(async()=>{throw Error('offline')});s.entries.set('./index.html',new Response('<h1>FPL</h1>'));
  assert.equal(await(await s.request('?v=test','navigate')).text(),'<h1>FPL</h1>');
});
test('network-first assets replace older cached scripts',async()=>{
  const s=setup(async()=>new Response('new'));s.entries.set('http://localhost:8011/assets/app.js',new Response('old'));
  assert.equal(await(await s.request('assets/app.js')).text(),'new');
});
test('guide navigation with a query uses its own offline page, not the dashboard',async()=>{
  const s=setup(async()=>{throw Error('offline')});
  s.entries.set('./index.html',new Response('<h1>Dashboard</h1>'));
  s.entries.set('./guide.html',new Response('<h1>Guide</h1>'));
  assert.equal(await(await s.request('guide.html?print=1','navigate')).text(),'<h1>Guide</h1>');
});
test('online guide navigation does not poison the cached dashboard',async()=>{
  const s=setup(async()=>new Response('<h1>Guide</h1>'));
  s.entries.set('./index.html',new Response('<h1>Dashboard</h1>'));
  await s.request('guide.html','navigate');
  assert.equal(await s.entries.get('./index.html').text(),'<h1>Dashboard</h1>');
  assert.equal(await s.entries.get('./guide.html').text(),'<h1>Guide</h1>');
});
test('opening a Markdown document cannot overwrite the cached dashboard',async()=>{
  const s=setup(async()=>new Response('# User guide'));
  s.entries.set('./index.html',new Response('<h1>Dashboard</h1>'));
  await s.request('guide.md','navigate');
  assert.equal(await s.entries.get('./index.html').text(),'<h1>Dashboard</h1>');
});
