import {Browser,sleep} from 'file:///C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {mkdirSync,writeFileSync} from 'node:fs';
const out='D:/Vinmec/bhyt-chatbot/.taste-skill/prototype-v1.7';mkdirSync(out,{recursive:true});
const browser=await Browser.launch();const checks=[];
const assert=(value,message)=>{if(!value)throw new Error(message);checks.push(message);};
async function wait(p,fn){for(let i=0;i<80;i++){if(await p.eval(fn))return;await sleep(100);}throw new Error('UI timeout');}
try{
 for(const width of [1440,768,390]){
  const p=await browser.newPage({width,height:900,reducedMotion:width===390});
  await p.goto('http://127.0.0.1:8766/#sources',{settleMs:600});
  await wait(p,()=>document.querySelectorAll('#supplemental-source-list .source-row').length===6);
  assert(await p.eval(()=>document.querySelectorAll('#source-list .source-row').length===4),'Four legal source groups preserved '+width);
  assert(await p.eval(()=>document.getElementById('source-update-summary').textContent.includes('204')&&document.getElementById('source-update-summary').textContent.includes('99')),'Source totals derived from registry '+width);
  assert(await p.eval(()=>document.querySelectorAll('#supplemental-source-list a[href*="/sources/clinical/"]').length===6),'Six archived PDFs accessible '+width);
  assert(await p.eval(()=>document.getElementById('supplemental-source-list').textContent.includes('Chờ xác minh bản ký')),'Unsigned source status visible '+width);
  await p.eval(()=>document.querySelector('#supplemental-source-list details').open=true);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'Sources have no horizontal overflow '+width);
  await p.screenshot({path:out+'/sources-'+width+'.jpg',quality:88});
  await p.eval(()=>{location.hash='case';document.querySelector('[data-case-demo="trastuzumab"]').click();});
  await wait(p,()=>document.querySelector('.criterion')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await p.eval(()=>document.querySelector('#case-source-coverage .coverage-row:nth-child(2)').textContent.includes('Có tham khảo')),'Breast source coverage updates '+width);
  assert(await p.eval(()=>!!document.querySelector('#case-result-body a[href*="qd3128-2020-breast.pdf#page="]')&&!document.querySelector('#case-result-body a[href*="qd3127-2020-gastric.pdf"]')),'Breast case links correct guideline pages '+width);
  await p.eval(()=>{const c=[...document.querySelectorAll('.criterion')].find(x=>x.querySelector('strong').textContent.includes('Hướng dẫn Bộ Y tế'));c.querySelector('details').open=true;c.scrollIntoView({block:'start',behavior:'instant'});});
  assert(await p.eval(()=>!!document.querySelector('.criterion details[open] a[href*="#page="]')),'Criterion opens page-linked clinical evidence '+width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'Expanded evidence has no horizontal overflow '+width);
  await p.screenshot({path:out+'/clinical-evidence-'+width+'.jpg',quality:88});
  await p.eval(()=>document.querySelector('[data-case-demo="metformin"]').click());
  await wait(p,()=>document.querySelector('.case-summary')?.textContent.includes('Metformin')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await p.eval(()=>document.querySelector('#case-source-coverage .coverage-row:nth-child(2)').textContent.includes('Chờ xác minh')),'Metformin does not claim verified signed guideline '+width);
  assert(await p.eval(()=>!!document.querySelector('#case-result-body a[href*="qd1353-2021-diabetes-amendment.pdf"]')),'Diabetes amendment always accompanies pointer '+width);
  assert(p.consoleErrors.length===0,'No JavaScript exceptions '+width);
  await p.close();
 }
 writeFileSync(out+'/source-browser-checks.json',JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length}));
}finally{await browser.close();}
