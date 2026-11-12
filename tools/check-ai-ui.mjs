// Run against serve-ai-fixture.py, never a production AI server.
// Người thực hiện: Đỗ Quốc An
import {mkdirSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const {Browser,sleep}=await import(pathToFileURL(process.env.TASTE_CDP_MODULE||'C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs').href);
const base='http://127.0.0.1:8881',out='.taste-skill/ux-ui/ai-browser';mkdirSync(out,{recursive:true});
const checks=[];const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
async function wait(p,fn){for(let i=0;i<100;i++){if(await p.eval(fn))return;await sleep(100);}throw Error('UI timeout');}
async function ask(p,q){await p.eval(q=>{document.querySelector('#question').value=q;document.querySelector('#composer').requestSubmit();},q);await wait(p,()=>!document.querySelector('#send').disabled);}
const browser=await Browser.launch();
try{
 for(const width of [1440,768,390]){
  const p=await browser.newPage({width,height:900,reducedMotion:true});await p.goto(base,{settleMs:600});await wait(p,()=>!document.querySelector('#send').disabled);
  assert(await p.eval(()=>document.querySelector('.chat-privacy').textContent.includes('OpenAI')),'AI data flow disclosed '+width);
  await ask(p,'Trastuzumab trong ung thư vú có được BHYT chi trả không?');
  assert(await p.eval(()=>document.querySelector('.conclusion').textContent.includes('60%')&&document.querySelector('.conclusion').textContent.includes('HER2')),'Concise lead keeps rate and marker '+width);
  assert(await p.eval(()=>document.querySelector('.full-conditions')&&!document.querySelector('.full-conditions').open),'Additional conditions are expandable '+width);
  await p.eval(()=>document.querySelector('.full-conditions').open=true);
  assert(await p.eval(()=>document.querySelector('.full-conditions').innerText.includes('phạm vi')||document.querySelector('.full-conditions').innerText.includes('Phạm vi')),'Expanded full conditions remain readable '+width);
  await p.eval(()=>{window.copied='';Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>{window.copied=text;}});document.querySelector('.answer-foot button').click();});await wait(p,()=>!!window.copied);
  assert(await p.eval(()=>[...document.querySelectorAll('.drug-result .answer-block li')].every(li=>window.copied.includes(li.textContent))),'Copy retains every condition '+width);
  await p.eval(()=>document.querySelector('.source-preview-button').click());
  assert(await p.eval(()=>document.querySelector('#source-dialog').open&&document.querySelector('#source-dialog mark')),'Original highlighted source remains accessible '+width);
  await p.eval(()=>document.querySelector('#close-source').click());
  await p.eval(()=>document.querySelector('#new-chat').click());
  await ask(p,'Trastu K vú BH trả ko?');
  assert(await p.eval(()=>document.querySelector('.confirm-block')&&!document.querySelector('.drug-result')),'Interpretation waits for confirmation '+width);
  assert(await p.eval(()=>document.querySelector('.confirm-block').textContent.includes('Trastuzumab trong ung thư vú')),'Interpretation displays actual normalized question '+width);
  await p.screenshot({path:out+'/interpretation-'+width+'.jpg',quality:90});
  await p.eval(()=>[...document.querySelectorAll('.confirm-block button')].find(b=>b.textContent==='Đúng, tra cứu câu này').click());await wait(p,()=>!document.querySelector('#send').disabled);
  assert(await p.eval(()=>[...document.querySelectorAll('.assistant')].at(-1).textContent.includes('Đang tra cứu: Trastuzumab')),'Confirmed interpretation is used '+width);
  assert(await p.eval(()=>document.querySelector('.conclusion').textContent.includes('60%')),'Confirmed question receives source-bound result '+width);
  await p.screenshot({path:out+'/answer-'+width+'.jpg',quality:90});
  await ask(p,'Nếu HER2 âm tính thì sao?');
  assert(await p.eval(()=>[...document.querySelectorAll('.conclusion')].at(-1).textContent.includes('không khớp')),'Negative follow-up preserved '+width);
  await ask(p,'Lỗi API thử nghiệm');
  assert(await p.eval(()=>[...document.querySelectorAll('.assistant')].at(-1).textContent.includes('AI tạm thời chưa sẵn sàng')),'API outage shows local fallback '+width);
  assert(await p.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow '+width);
  assert(p.consoleErrors.length===0,'No browser exceptions '+width);
  await p.close();
 }
 writeFileSync(out+'/checks.json',JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length}));
}finally{await browser.close();}
