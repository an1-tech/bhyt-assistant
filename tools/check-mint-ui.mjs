// UI regression checks. Run against an already-started local server.
// Người thực hiện: Đỗ Quốc An
import {mkdirSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const toolkit=process.env.TASTE_CDP_MODULE || 'C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
const {Browser,sleep}=await import(pathToFileURL(toolkit).href);
const base=process.argv[2] || 'http://127.0.0.1:8879';
const out='.taste-skill/ux-ui/mint';mkdirSync(out,{recursive:true});
const checks=[];
function assert(ok,name){if(!ok)throw Error(name);checks.push(name);}
async function wait(p,fn){for(let i=0;i<100;i++){if(await p.eval(fn))return;await sleep(100);}throw Error('UI timeout');}
async function key(p,key,code){await p.send('Input.dispatchKeyEvent',{type:'keyDown',key,windowsVirtualKeyCode:code});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key,windowsVirtualKeyCode:code});}
async function ask(p,text){await p.eval(t=>{document.querySelector('#question').value=t;document.querySelector('#composer').requestSubmit();},text);await wait(p,()=>!document.querySelector('#send').disabled);}
const browser=await Browser.launch();
try{
 for(const width of [1440,768,390,320]){
  const p=await browser.newPage({width,height:width<600?844:900,reducedMotion:true});
  await p.goto(base,{settleMs:500});await wait(p,()=>!document.querySelector('#send').disabled);
  assert(await p.eval(()=>{const i=document.querySelector('.welcome-mascot');return i.complete&&i.naturalWidth>0;}),'Mascot loads '+width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'Welcome fits viewport '+width);
  assert(await p.eval(()=>document.querySelector('footer').textContent.includes('Đỗ Quốc An')),'Author attribution '+width);
  await p.screenshot({path:out+'/welcome-'+width+'.jpg',quality:90});
  await ask(p,'Trastuzumab điều trị ung thư vú có được BHYT chi trả không?');
  assert(await p.eval(()=>{const a=document.querySelector('.assistant');return !a.textContent.includes('Quy định BHYT liên quan')&&!a.textContent.includes('Tài liệu điều trị tham khảo')&&!a.textContent.includes('Căn cứ của thuốc')&&a.querySelectorAll('.source-quote').length===1;}),'Only direct source, no duplicate or background groups '+width);
  await p.eval(()=>{window.copied='';Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>{window.copied=text;}});document.querySelector('.answer-foot button').click();});
  await wait(p,()=>!!window.copied);
  assert(await p.eval(()=>(window.copied.match(/^NGUỒN /gm)||[]).length===1&&window.copied.includes('HER2')&&window.copied.includes('60%')),'Copy keeps direct evidence and conditions only '+width);
  assert(await p.eval(()=>{
   const citations=[{id:'drug'},{id:'lab'},{id:'transition'},{id:'effective'},{id:'background'}];
   const mixed={results:[{record_ids:['drug']}],lab_results:[{citation:{id:'lab'}}],citations};
   const t={...mixed,transition_review:{article8_ids:['transition'],effective_date_id:'effective'}};
   return answerCitations(mixed).map(c=>c.id).join(',')==='drug,lab'&&answerCitations(t).map(c=>c.id).join(',')==='drug,lab,transition,effective'&&answerCitations({status:'policy_lookup',citations}).length===5&&answerCitations({status:'unknown',citations}).length===0;
  }),'Mixed, transition and policy answers retain their own sources '+width);
  assert(await p.eval(()=>document.querySelector('#examples').hidden&&document.querySelector('#welcome').hidden),'Welcome yields to conversation '+width);
  await p.eval(()=>document.querySelector('.assistant').scrollIntoView({block:'start',behavior:'instant'}));
  assert(await p.eval(()=>{const r=document.querySelector('.assistant-brand').getBoundingClientRect();return r.top>=document.querySelector('.topbar').getBoundingClientRect().bottom&&r.bottom<document.querySelector('.chat-composer').getBoundingClientRect().top;}),'Answer starts in readable viewport '+width);
  await p.screenshot({path:out+'/answer-'+width+'.jpg',quality:90});
  await p.eval(()=>{const b=document.querySelector('.source-preview-button');b.focus();b.click();});
  assert(await p.eval(()=>document.querySelector('#source-dialog').open&&document.activeElement.id==='close-source'),'Source dialog receives focus '+width);
  assert(await p.eval(()=>document.querySelector('#source-dialog .source-quote').textContent===document.querySelector('.assistant .source-quote').textContent),'Drug preview exactly matches original '+width);
  assert(await p.eval(()=>document.querySelectorAll('#source-dialog mark').length>0&&document.querySelector('#source-dialog a[href*="#page="]')),'Highlighted source and exact PDF page '+width);
  assert(await p.eval(()=>{const d=document.querySelector('#source-dialog'),r=d.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&d.scrollWidth<=d.clientWidth;}),'Source dialog fits viewport '+width);
  await p.screenshot({path:out+'/source-'+width+'.jpg',quality:90});
  for(let i=0;i<8;i++)await key(p,'Tab',9);
  assert(await p.eval(()=>document.activeElement===document.body||!!document.activeElement.closest('#source-dialog')),'Modal prevents focus entering background '+width);
  await key(p,'Escape',27);
  assert(await p.eval(()=>!document.querySelector('#source-dialog').open&&document.activeElement.classList.contains('source-preview-button')),'Escape restores source-button focus '+width);
  await p.eval(()=>document.querySelector('#new-chat').click());
  await ask(p,'HbA1c theo dõi đái tháo đường có điều kiện BHYT gì?');
  await p.eval(()=>document.querySelector('.source-preview-button').click());
  assert(await p.eval(()=>document.querySelector('#source-dialog .lab-quote').textContent===document.querySelector('.lab-result .lab-quote').textContent),'Lab preview preserves every condition '+width);
  assert(await p.eval(()=>document.querySelector('#source-dialog .lab-source a').href.endsWith('/sources/labs/hba1c.html#source-row')),'Lab preview retains exact source row '+width);
  await p.eval(()=>document.querySelector('#close-source').click());
  await p.eval(()=>{location.hash='sources';});await wait(p,()=>!document.querySelector('#view-sources').hidden);
  await p.eval(()=>document.querySelector('#new-chat').click());await wait(p,()=>!document.querySelector('#view-lookup').hidden);
  assert(await p.eval(()=>!document.querySelector('.turn')&&document.activeElement.id==='question'&&!document.querySelector('#examples').hidden),'New chat works from sources page '+width);
  await p.eval(()=>{window.savedFetch=window.fetch;window.fetch=async()=>{throw Error('Lỗi mạng thử nghiệm');};});
  await ask(p,'Câu hỏi thử lỗi mạng');
  assert(await p.eval(()=>!document.querySelector('#welcome').hidden&&!document.querySelector('#examples').hidden&&!document.querySelector('#error').hidden&&document.querySelector('#question').value==='Câu hỏi thử lỗi mạng'),'Failed request restores editable welcome '+width);
  await p.eval(()=>{window.fetch=window.savedFetch;});
  assert(await p.eval(()=>getComputedStyle(document.documentElement).scrollBehavior==='auto'),'Reduced motion '+width);
  assert(p.consoleErrors.length===0,'No browser exceptions '+width);
  await p.close();
 }
 writeFileSync(out+'/checks.json',JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length}));
}finally{await browser.close();}
