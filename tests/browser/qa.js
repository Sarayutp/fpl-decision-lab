const frame = document.querySelector('#preview');
const result = document.querySelector('#result');
let started = 0;
function inspect() {
  const doc = frame.contentDocument;
  if (doc?.querySelector('#guide-content')) {
    result.textContent=JSON.stringify({page:'guide',width:frame.clientWidth,pageOverflow:doc.documentElement.scrollWidth-frame.clientWidth,tableOverflow:Math.max(0,...[...doc.querySelectorAll('.guide-content table')].map(table=>table.getBoundingClientRect().right-table.parentElement.getBoundingClientRect().right)),chapters:doc.querySelectorAll('#guide-content h2').length,toc:doc.querySelectorAll('.guide-toc a').length,download:doc.querySelector('a[download]')?.getAttribute('href')},null,2);
    return;
  }
  if (!doc?.querySelector('#runtime-state')) return;
  const appState = doc.querySelector('#runtime-state').dataset.kind;
  const visible = el => el.getClientRects().length > 0;
  const unlabeled = [...doc.querySelectorAll('input,select,textarea,button')].filter(visible).filter(el =>
    !el.labels?.length && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby') && !(el.tagName==='BUTTON' && el.textContent.trim())).map(el=>el.id || el.outerHTML.slice(0,90));
  const heading = doc.querySelector('#decision-title');
  const nav = doc.querySelector('.topbar nav');
  const css = frame.contentWindow.getComputedStyle(doc.documentElement);
  const rgb = hex => hex.trim().replace('#','').match(/../g).map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
  const luminance = hex => rgb(hex).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
  const contrast = (a,b) => {const v=[luminance(a),luminance(b)].sort((x,y)=>y-x);return (v[0]+.05)/(v[1]+.05);};
  const colors = Object.fromEntries(['--ink','--muted','--bg','--surface','--surface-2'].map(name=>[name,css.getPropertyValue(name)]));
  result.textContent = JSON.stringify({scenario:document.querySelector('#scenario').value,state:appState,width:frame.clientWidth,
    readyMs:Math.round(performance.now()-started),pageOverflow:doc.documentElement.scrollWidth-frame.clientWidth,
    rootWidth:doc.documentElement.clientWidth,bodyWidth:doc.body.clientWidth,
    overflowElements:[...doc.querySelectorAll('body *')].filter(el=>visible(el)&&!el.closest('.table-wrap')&&el.getBoundingClientRect().right>frame.clientWidth+1&&el.getBoundingClientRect().width>180).slice(0,16).map(el=>({id:el.id,tag:el.tagName,class:el.className,right:Math.round(el.getBoundingClientRect().right)})),
    menuVisible:Boolean(nav && visible(nav)),decisionVisible:Boolean(heading && visible(heading)),decisionCards:doc.querySelectorAll('#decision-grid .decision-card').length,
    unlabeledControls:unlabeled,mutedContrastOnPanel:contrast(colors['--muted'],colors['--surface-2']).toFixed(2),
    bodyContrast:contrast(colors['--ink'],colors['--bg']).toFixed(2),logEntries:doc.querySelectorAll('[data-log-entry]').length,
    saveDisabled:doc.querySelector('#save-planner')?.disabled,copyDisabled:doc.querySelector('#copy-briefing')?.disabled},null,2);
}
document.querySelector('#load').addEventListener('click',()=>{
  frame.width=document.querySelector('#width').value; started=performance.now(); result.textContent='กำลังโหลด…';
  frame.src=`${document.querySelector('#page').value}?qaState=${encodeURIComponent(document.querySelector('#scenario').value)}&preview=${Date.now()}`;
});
document.querySelector('#inspect').addEventListener('click',inspect);
document.querySelector('#show-section').addEventListener('click',()=>{const target=frame.contentDocument?.getElementById(document.querySelector('#section').value);if(target?.tagName==='DETAILS') target.open=true;target?.scrollIntoView();frame.scrollIntoView();});
frame.addEventListener('load',()=>{
  const timer=setInterval(()=>{const state=frame.contentDocument?.querySelector('#runtime-state')?.dataset.kind;
    if(frame.contentDocument?.querySelector('#guide-content') || state && state!=='loading' || performance.now()-started>12000){clearInterval(timer);inspect();}},100);
});
