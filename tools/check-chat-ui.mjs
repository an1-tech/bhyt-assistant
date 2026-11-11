import {Browser,sleep} from 'file:///C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {mkdirSync,writeFileSync} from 'node:fs';
const out='D:/Vinmec/bhyt-chatbot/.taste-skill/chat-v1.8';mkdirSync(out,{recursive:true});const checks=[];
for(let i=0;i<100;i++){try{const r=await fetch('http://127.0.0.1:8766/api/health');if(r.ok)break;}catch{}await sleep(100);}
const browser=await Browser.launch();
const assert=(value,message)=>{if(!value)throw new Error(message);checks.push(message);};
async function wait(p,fn){for(let i=0;i<100;i++){if(await p.eval(fn))return;await sleep(100);}throw new Error('UI timeout');}
async function ask(p,text){const before=await p.eval(()=>document.querySelectorAll('.assistant').length);await p.eval(t=>{const q=document.getElementById('question');q.value=t;q.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('composer').requestSubmit();},text);await wait(p,()=>document.getElementById('messages').getAttribute('aria-busy')==='false');assert(await p.eval(n=>document.querySelectorAll('.assistant').length===n+1,before),'Question produces one answer: '+text);}
try{
 for(const size of [{width:1440,height:900},{width:768,height:1024},{width:390,height:844,reducedMotion:true}]){
  const p=await browser.newPage(size);await p.goto('http://127.0.0.1:8766',{settleMs:500});await wait(p,()=>!document.getElementById('send').disabled);
  assert(await p.eval(()=>!document.getElementById('view-lookup').hidden),'Chat is default '+size.width);
  assert(await p.eval(()=>document.querySelectorAll('form').length===1&&document.querySelectorAll('textarea').length===1&&!document.querySelector('select,input,#case-form')),'Only one question input, no patient form '+size.width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No initial overflow '+size.width);
  await p.screenshot({path:out+'/initial-'+size.width+'.jpg',quality:88});
  await p.eval(()=>document.getElementById('question').focus());await p.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  assert(await p.eval(()=>document.activeElement.id==='send'),'Tab moves from question to send '+size.width);
  await p.eval(()=>{const q=document.getElementById('question');q.value='Trastuzumab điều trị ung thư vú có được BHYT chi trả không?';q.focus();});await p.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await wait(p,()=>document.querySelector('.assistant')&&document.getElementById('messages').getAttribute('aria-busy')==='false');
  assert(await p.eval(()=>document.querySelector('.assistant .conclusion').textContent.includes('Có quy định BHYT thanh toán')),'Direct breast answer without extra inputs '+size.width);
  assert(await p.eval(()=>document.querySelector('.assistant').textContent.includes('HER2 dương tính')&&document.querySelector('.assistant').textContent.includes('60%')),'Conditions and source rate stated '+size.width);
  assert(await p.eval(()=>!document.querySelector('.assistant').textContent.includes('Bạn đang dùng đường nào')&&!document.querySelector('.assistant').textContent.includes('Bạn có thể bổ sung')),'No patient questionnaire in reply '+size.width);
  assert(await p.eval(()=>document.querySelector('.assistant a[href*="sources/"]')),'Answer has source links '+size.width);
  await p.screenshot({path:out+'/answer-'+size.width+'.jpg',quality:88});
  await p.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  assert(await p.eval(()=>{const r=document.activeElement.getBoundingClientRect(),c=document.querySelector('.chat-composer').getBoundingClientRect(),h=document.querySelector('.topbar').getBoundingClientRect();return r.top>=h.bottom&&r.bottom<=c.top;}),'Focused evidence stays clear of sticky composer '+size.width);
  await ask(p,'Còn ung thư dạ dày thì sao?');
  assert(await p.eval(()=>[...document.querySelectorAll('.assistant')].at(-1).textContent.includes('50%')&&[...document.querySelectorAll('.assistant')].at(-1).textContent.includes('tiến xa hoặc di căn')),'Follow-up changes disease and conditions '+size.width);
  await ask(p,'Nếu HER2 âm tính thì sao?');
  assert(await p.eval(()=>[...document.querySelectorAll('.assistant .conclusion')].at(-1).textContent.includes('không khớp điều kiện')),'Negative HER2 does not get positive conclusion '+size.width);
  await p.eval(()=>{window.copiedChat='';Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>{window.copiedChat=text;}});[...document.querySelectorAll('.answer-foot button')].at(-1).click();});await wait(p,()=>!!window.copiedChat);
  assert(await p.eval(()=>copiedChat.includes('không khớp điều kiện')&&copiedChat.includes('NGUỒN')&&copiedChat.includes('không phải quyết định thanh toán')&&copiedChat.includes('đã thẩm định ngày 11/11/2026')&&!copiedChat.includes('chưa được bệnh viện thẩm định')),'Copy includes conclusion, evidence and scope '+size.width);
  await ask(p,'Metformin điều trị đái tháo đường típ 2 có được BHYT chi trả không?');
  assert(await p.eval(()=>[...document.querySelectorAll('.assistant .conclusion')].at(-1).textContent.includes('chưa đủ căn cứ')),'Incomplete indication evidence is explicit '+size.width);
  assert(await p.eval(()=>document.querySelectorAll('.turn').length===4),'Conversation history stays visible '+size.width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No answer overflow '+size.width);
  await p.eval(()=>{location.hash='sources';});await wait(p,()=>!document.getElementById('view-sources').hidden);
  assert(await p.eval(()=>document.querySelectorAll('#source-list .source-row').length===5&&document.querySelectorAll('#supplemental-source-list .source-row').length===6),'Four drug source groups, the lab source and six documents shown '+size.width);
  await p.screenshot({path:out+'/sources-'+size.width+'.jpg',quality:88});
  await p.eval(()=>{location.hash='lookup';});await wait(p,()=>!document.getElementById('view-lookup').hidden);await p.eval(()=>document.getElementById('new-chat').click());
  assert(await p.eval(()=>!document.querySelector('.turn')&&!document.getElementById('welcome').hidden&&document.activeElement.id==='question'),'New chat resets state and focuses input '+size.width);
  await p.eval(()=>document.getElementById('question').value='Dòng thứ nhất');await p.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',modifiers:8});await p.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:8});
  assert(await p.eval(()=>document.getElementById('question').value.includes('\n')&&!document.querySelector('.turn')),'Shift Enter adds a line without sending '+size.width);
  if(size.reducedMotion)assert(await p.eval(()=>getComputedStyle(document.documentElement).scrollBehavior==='auto'),'Reduced motion honored');
  assert(p.consoleErrors.length===0,'No JavaScript exceptions '+size.width);await p.close();
 }
 writeFileSync(out+'/browser-checks.json',JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length}));
}finally{await browser.close();}
