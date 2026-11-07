import {Browser} from 'file:///C:/Users/admin/.agents/skills/design-taste-frontend/scripts/lib/cdp.mjs';
import {mkdirSync,writeFileSync} from 'node:fs';
const out='D:/Vinmec/bhyt-chatbot/.taste-skill/extra';mkdirSync(out,{recursive:true});
const browser=await Browser.launch();const checks=[];
try{
 for(const scenario of [{name:'reduced-motion',width:375,height:812,reducedMotion:true,route:'lookup'},{name:'landscape',width:844,height:390,route:'lookup'},{name:'catalog-mobile',width:390,height:844,route:'catalog'},{name:'sources-mobile',width:390,height:844,route:'sources'}]){
  const page=await browser.newPage(scenario);await page.goto('http://127.0.0.1:8766/#'+scenario.route,{settleMs:800});
  const result=await page.eval(()=>({width:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,scrollBehavior:getComputedStyle(document.documentElement).scrollBehavior,transition:getComputedStyle(document.querySelector('#send')).transitionDuration,title:[...document.querySelectorAll('h1')].filter(x=>x.getBoundingClientRect().height>0).map(x=>x.innerText),font:document.fonts.check('16px Geist'),catalogCount:document.querySelectorAll('.catalog-row').length,sourceCount:document.querySelectorAll('.source-row').length}));
  if(result.scrollWidth>result.width)throw new Error(scenario.name+': overflow');
  if(result.title.length!==1||!result.font)throw new Error(scenario.name+': missing title/font');
  if(scenario.reducedMotion&&(!result.reduced||result.scrollBehavior!=='auto'||result.transition!=='0s'))throw new Error('Reduced motion not honored');
  if(scenario.route==='catalog'&&result.catalogCount!==20)throw new Error('Catalog not loaded');
  await page.screenshot({path:out+'/'+scenario.name+'.jpg',quality:85});checks.push({name:scenario.name,passed:true,...result});await page.close();
 }
 writeFileSync(out+'/checks.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks,null,2));
}finally{await browser.close();}
