import {Browser,sleep} from 'file:///C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {writeFileSync,mkdirSync} from 'node:fs';
const base=(process.argv[2]||'http://127.0.0.1:8766').replace(/\/$/,'');
mkdirSync('audit/lab-browser',{recursive:true});
const checks=[], browser=await Browser.launch();
const assert=(ok,name)=>{checks.push({name,passed:!!ok});if(!ok)throw Error(name);};
async function wait(p,fn){for(let i=0;i<100;i++){if(await p.eval(fn))return;await sleep(100);}throw Error('Timeout '+fn);}
async function key(p,name,code){await p.send('Input.dispatchKeyEvent',{type:'keyDown',key:name,code:name,windowsVirtualKeyCode:code,...(name==='Enter'?{text:'\r'}:{})});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key:name,code:name,windowsVirtualKeyCode:code});}
async function ask(p,q){const count=await p.eval(()=>document.querySelectorAll('.assistant').length);await p.eval(q=>{const el=document.querySelector('#question');el.value=q;el.focus();},q);await key(p,'Enter',13);await wait(p,()=>!document.querySelector('#send').disabled&&document.querySelector('#loading').hidden);assert(await p.eval(()=>document.querySelectorAll('.assistant').length)===count+1,'Submitted question: '+q);}
try{
 for(const width of [1440,768,390]){
  const p=await browser.newPage({width,height:width===390?844:900,reducedMotion:true});await p.goto(base,{settleMs:600});await wait(p,()=>!document.querySelector('#send').disabled);
  assert(await p.eval(()=>document.querySelectorAll('textarea').length===1),'One chat input '+width);
  await ask(p,'HbA1c theo dõi đái tháo đường có điều kiện BHYT gì?');
  assert(await p.eval(()=>document.querySelector('.lab-result').innerText.includes('thai kỳ')&&document.querySelectorAll('.lab-result .answer-block li').length===3),'All branches visible '+width);
  assert(await p.eval(()=>document.activeElement.classList.contains('assistant')),'Focus moves to answer '+width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow in chat '+width);
  await p.eval(()=>document.querySelector('.lab-result').scrollIntoView({block:'start',behavior:'instant'}));await p.screenshot({path:`audit/lab-browser/chat-${width}.jpg`,quality:90});
  const source=await p.eval(()=>document.querySelector('.lab-source a').href);assert(source.endsWith('/sources/labs/hba1c.html#source-row'),'Exact service link '+width);
  await p.eval(()=>document.querySelector('.lab-source a').focus());
  assert(await p.eval(()=>getComputedStyle(document.activeElement).outlineStyle!=='none'),'Keyboard focus visible on source link '+width);
  const prior=await browser.send('Target.getTargets');await key(p,'Enter',13);
  let target;for(let i=0;i<30;i++){const ts=await browser.send('Target.getTargets');target=ts.targetInfos.find(t=>!prior.targetInfos.some(a=>a.targetId===t.targetId)&&t.url.includes('/sources/labs/hba1c.html'));if(target)break;await sleep(100);}
  assert(!!target,'Enter opens source in separate tab '+width);if(target)await browser.send('Target.closeTarget',{targetId:target.targetId});
  const s=await browser.newPage({width,height:900,reducedMotion:true});await s.goto(source,{settleMs:200});await wait(s,()=>document.querySelector('img')?.complete);
  assert(await s.eval(()=>document.querySelector('img').naturalWidth>0),'Source crop loaded '+width);
  assert(await s.eval(()=>document.querySelector('#source-row').getBoundingClientRect().top<innerHeight),'Anchor opens correct row '+width);
  assert(await s.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No overflow in source reader '+width);
  await s.eval(()=>document.querySelector('summary').focus());await key(s,'Enter',13);
  assert(await s.eval(()=>document.querySelector('details').open&&document.querySelector('.lab-verbatim').innerText.includes('90 ± 3')),'Keyboard opens readable full quotation '+width);
  await s.screenshot({path:`audit/lab-browser/source-${width}.jpg`,quality:90,fullPage:true});await s.close();
  await ask(p,'HbA1c hôm nay theo dõi đái tháo đường');
  assert(await p.eval(()=>[...document.querySelectorAll('.lab-result')].at(-1).innerText.includes('gần nhất được thực hiện ngày nào')),'Only missing date requested '+width);
  await ask(p,'Lần trước cách 60 ngày');assert(await p.eval(()=>[...document.querySelectorAll('.lab-result')].at(-1).innerText.includes('ngắn hơn')),'Follow-up uses date '+width);
  await ask(p,'Cả xét nghiệm EGFR và thuốc Erlotinib trong ung thư phổi không tế bào nhỏ có BHYT không?');
  assert(await p.eval(()=>{const a=[...document.querySelectorAll('.assistant')].at(-1);return a.querySelectorAll('.lab-result').length===1&&a.querySelectorAll('.drug-result').length===2&&a.innerText.includes('50%');}),'Mixed reply has independent test and drug sections '+width);
  await p.eval(()=>[...document.querySelectorAll('.assistant')].at(-1).scrollIntoView({behavior:'instant',block:'start'}));await p.screenshot({path:`audit/lab-browser/mixed-${width}.jpg`,quality:90});
  assert(await p.eval(()=>reportText({answer:'a',snapshot:'s',lab_results:[{name:'test',conclusion:'c',reasons:['r'],conditions:['t'],scope:'scope',citation:{viewer_url:'/sources/labs/egfr.html#source-row'}}]},'q').includes('/sources/labs/egfr.html#source-row')),'Copy report includes source location '+width);
  await p.eval(()=>document.querySelector('#new-chat').click());assert(await p.eval(()=>document.querySelectorAll('.assistant').length===0&&!document.querySelector('#welcome').hidden),'New chat clears state '+width);
  await ask(p,'Lần trước cách 60 ngày');assert(await p.eval(()=>!document.querySelector('.lab-result')),'New chat has no stale lab context '+width);
  await p.eval(()=>{location.hash='sources';});await wait(p,()=>!document.querySelector('#view-sources').hidden);assert(await p.eval(()=>document.querySelector('#source-list').innerText.includes('HbA1c')&&document.querySelector('#source-list').innerText.includes('10/11/2026')||document.querySelector('#source-list').innerText.includes('2026-11-10')),'Lab source in source catalogue '+width);
  assert(await p.eval(()=>matchMedia('(prefers-reduced-motion: reduce)').matches&&getComputedStyle(document.documentElement).scrollBehavior==='auto'),'Reduced motion honored '+width);
  assert(p.consoleErrors.length===0,'No JS exceptions '+width);await p.close();
 }
 writeFileSync('audit/lab-browser/browser-results.json',JSON.stringify({checks},null,2));console.log(JSON.stringify({passed:checks.length}));
}catch(e){writeFileSync('audit/lab-browser/browser-results.json',JSON.stringify({checks,error:String(e)},null,2));throw e;}
finally{await browser.close();}
