import {Browser,sleep} from 'file:///C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {writeFileSync} from 'node:fs';
const out='D:/Vinmec/bhyt-chatbot/.taste-skill/prototype-v1.7';
const browser=await Browser.launch();const checks=[];
const assert=(value,message)=>{if(!value)throw new Error(message);checks.push(message);};
async function wait(page,fn){for(let i=0;i<80;i++){if(await page.eval(fn))return;await sleep(100);}throw new Error('Timed out waiting for UI state');}
try{
 for(const size of [{width:1440,height:900},{width:768,height:1024},{width:390,height:844,reducedMotion:true}]){
  const page=await browser.newPage(size);
  await page.goto('http://127.0.0.1:8766',{settleMs:600});
  await wait(page,()=>document.getElementById('mode').textContent!=='Đang kết nối…');
  assert(await page.eval(()=>!document.getElementById('view-case').hidden),'Case view is default at '+size.width);
  assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No initial horizontal overflow '+size.width);
  await page.screenshot({path:out+'/initial-'+size.width+'.jpg',quality:88});
  // A real Tab from a focused search must move to the next usable form control.
  await page.eval(()=>document.getElementById('case-drug-search').focus());
  await page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  assert(await page.eval(()=>document.activeElement.id==='case-product'),'Keyboard Tab follows form order '+size.width);
  await page.eval(()=>document.querySelector('[data-case-demo="trastuzumab"]').click());
  await wait(page,()=>document.querySelector('.criterion-status')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await page.eval(()=>document.getElementById('case-result-body').textContent.includes('Chưa có thông tin')),'Missing HER2 is visible '+size.width);
  assert(await page.eval(()=>!document.querySelector('.source-rate')),'Unknown HER2 does not display a rate '+size.width);
  assert(await page.eval(()=>document.getElementById('case-result-body').textContent.includes('Ca minh họa')),'Example case clearly labelled '+size.width);
  await page.eval(()=>document.getElementById('case-result').scrollIntoView({block:'start',behavior:'instant'}));
  await page.screenshot({path:out+'/missing-her2-'+size.width+'.jpg',quality:88});
  await page.eval(()=>{const s=document.getElementById('case-answer-her2');s.value='positive';s.dispatchEvent(new Event('change',{bubbles:true}));});
  assert(await page.eval(()=>!document.querySelector('.criterion')),'Edited form invalidates prior result '+size.width);
  await page.eval(()=>document.getElementById('case-form').requestSubmit());
  await wait(page,()=>document.querySelector('.source-rate')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await page.eval(()=>document.querySelector('.source-rate strong').textContent.includes('60%')),'Breast/HER2 positive shows source branch 60% '+size.width);
  await page.eval(()=>document.getElementById('case-result').scrollIntoView({block:'start',behavior:'instant'}));
  await page.screenshot({path:out+'/positive-her2-'+size.width+'.jpg',quality:88,fullPage:true});
  // Switch branch; an unanswered gastric extent must remove the prior rate.
  await page.eval(()=>{const s=document.getElementById('case-answer-indication');s.value='gastric';s.dispatchEvent(new Event('change',{bubbles:true}));document.getElementById('case-form').requestSubmit();});
  await wait(page,()=>document.querySelector('.criterion')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await page.eval(()=>!document.querySelector('.source-rate')),'Gastric extent missing never inherits breast rate '+size.width);
  await page.eval(()=>{const s=document.getElementById('case-answer-extent');s.value='advanced';s.dispatchEvent(new Event('change',{bubbles:true}));document.getElementById('case-form').requestSubmit();});
  await wait(page,()=>document.querySelector('.source-rate')&&document.getElementById('case-result').getAttribute('aria-busy')==='false');
  assert(await page.eval(()=>document.querySelector('.source-rate strong').textContent.includes('50%')),'Gastric advanced/HER2 branch shows 50% '+size.width);
  await page.eval(()=>{window.copiedCase='';Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>{window.copiedCase=text;}});document.querySelector('.case-copy-row button').click();});
  await wait(page,()=>window.copiedCase.length>0);
  assert(await page.eval(()=>copiedCase.includes('chưa được Dược/BHYT thẩm định')&&copiedCase.includes('NGUYÊN VĂN GHI CHÚ')&&copiedCase.includes('CĂN CỨ')&&copiedCase.includes('QD3127_2020')&&copiedCase.includes('Nhãn sản phẩm đã đăng ký')&&copiedCase.includes('nguồn bổ sung kiểm tra 2026-11-07')),'Copy contains source, limitations and missing evidence '+size.width);
  assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),'No result horizontal overflow '+size.width);
  if(size.reducedMotion)assert(await page.eval(()=>getComputedStyle(document.documentElement).scrollBehavior==='auto'),'Reduced motion honored');
  assert(page.consoleErrors.length===0,'No JavaScript exceptions '+size.width);
  await page.close();
 }
 const page=await browser.newPage({width:1440,height:900});
 await page.goto('http://127.0.0.1:8766',{settleMs:600});
 // Autocomplete selection with real keyboard focus and Enter.
 await page.eval(()=>{const s=document.getElementById('case-drug-search');s.value='metfo';s.dispatchEvent(new Event('input',{bubbles:true}));});
 await wait(page,()=>document.querySelector('#case-drug-options button'));
 await page.eval(()=>document.getElementById('case-drug-search').focus());
 await page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
 assert(await page.eval(()=>document.activeElement.closest('#case-drug-options')!==null),'Autocomplete ArrowDown enters results');
 await page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
 await page.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
 await page.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await wait(page,()=>!document.getElementById('case-submit').disabled);
 assert(await page.eval(()=>document.getElementById('case-selected').textContent.includes('Metformin')),'Autocomplete Enter selects exact drug');
 await page.eval(()=>{document.getElementById('case-diagnosis').value='mã bệnh án: TEST';document.getElementById('case-form').requestSubmit();});
 await wait(page,()=>!document.getElementById('case-error').hidden);
 assert(await page.eval(()=>document.getElementById('case-error')===document.activeElement),'Validation error is focused');
 await page.close();
 writeFileSync(out+'/browser-checks.json',JSON.stringify({passed:checks.length,checks},null,2));
 console.log(JSON.stringify({passed:checks.length,checks}));
}finally{await browser.close();}
