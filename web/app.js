"use strict";
const $=s=>document.querySelector(s);
const fmt=n=>new Intl.NumberFormat('vi-VN').format(n);
let state={},token='',busy=false,ready=false,metadata=null,currentView=null;
const viewScroll={lookup:0,sources:0};
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
function link(url,label){try{if(!url)return null;const u=new URL(url,location.origin);if(u.origin!==location.origin&&u.protocol!=='https:')return null;if(u.origin===location.origin&&!u.pathname.startsWith('/sources/'))return null;const a=node('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return null;}}
function sourceName(id){return [...(metadata?.sources||[]),...(metadata?.source_update?.documents||[])].find(s=>s.id===id)?.title||id||'Nguồn';}
function addSourceLinks(parent,s){const row=node('div',undefined,'source-links');const local=s.local_url||(s.document_id==='TT20_2022'?'/sources/15-vbhn-byt-2024.pdf':s.document_id==='TT37_2024'?'/sources/37-2024-tt-byt.pdf':null);const seen=new Set();for(const [url,label] of [[s.official_url,'Bản công bố ↗'],[s.source_url||s.url,'Nguồn trích dẫn ↗'],[local,'PDF trên máy ↗']]){if(!url||seen.has(url))continue;seen.add(url);const a=link(url,label);if(a)row.append(a);}parent.append(row);}
function sourceBlock(s){const row=node('article',undefined,'evidence-row');row.append(node('strong',s.document_title||sourceName(s.document_id)),node('div',(s.locator||'').replace(/, dòng HTML \d+/g,'')+(s.page&&!s.locator?.includes('Trang PDF')?' · Trang '+s.page:''),'evidence-locator'));if(s.kind?.startsWith('clinical'))row.append(node('p',s.kind==='clinical_reference'?'Tham khảo điều trị; không tự xác nhận thanh toán.':'Chỉ dẫn PDF; chưa dùng nội dung để kết luận.','hint'));for(const f of s.source_review_flags||[])row.append(node('p',f.note,'notice'));addSourceLinks(row,s);const details=node('details',undefined,'citation');details.append(node('summary','Đọc nguyên văn'),node('pre',s.excerpt||''));row.append(details);return row;}
function evidenceGroup(parent,title,items){if(!items.length)return;const d=node('details',undefined,'citation');d.append(node('summary',title+' · '+items.length+' đoạn'));for(const c of items)d.append(sourceBlock(c));parent.append(d);}
function reportText(data,question){const out=['Câu hỏi: '+question,data.answer];for(const r of data.results||[]){const a=r.question_answer;if(!a)continue;out.push(r.ingredient,a.conclusion,...a.conditions,a.scope);}for(const c of [...(data.citations||[]),...(data.clinical_references||[])]){out.push('NGUỒN '+sourceName(c.document_id)+' · '+c.locator+' · '+(c.local_url||c.official_url||c.source_url),c.excerpt);for(const f of c.source_review_flags||[])out.push('Giới hạn: '+f.note);}if(data.notice)out.push(data.notice);for(const t of data.brand_notes||[])out.push(t);out.push('Bộ nguồn BHYT '+data.snapshot+'; tham khảo nguồn, chưa được bệnh viện thẩm định.');return out.join('\n');}
function renderReply(data,question){
 const box=node('article',undefined,'assistant');box.tabIndex=-1;box.append(node('h2','Cẩm nang BHYT'));
 const rows=data.results||[];
 if(!rows.length)box.append(node('p',data.answer,'conclusion'));
 for(const r of rows){const a=r.question_answer;const section=node('section',undefined,'drug-result');section.append(node('h3',r.ingredient,'drug-heading'),node('p',a?.conclusion||data.answer,'conclusion'));
  if(a?.conditions?.length){const conditions=node('div',undefined,'answer-block');conditions.append(node('strong','Điều kiện trong nguồn'));const list=node('ul');for(const text of a.conditions)list.append(node('li',text));conditions.append(list);section.append(conditions);}
  const sources=(data.citations||[]).filter(c=>r.record_ids?.includes(c.id));evidenceGroup(section,'Căn cứ của thuốc',sources);if(a?.scope)section.append(node('p',a.scope,'scope-note'));box.append(section);
 }
 if(data.suggestions?.length){const choices=node('div',undefined,'actions');for(const name of data.suggestions){const b=node('button',name);b.type='button';b.addEventListener('click',()=>send(name+' — '+question));choices.append(b);}box.append(choices);}
 if(data.suggested_followups?.length){const wrap=node('div',undefined,'followup-chips');wrap.append(node('strong','Hỏi tiếp'));const choices=node('div',undefined,'actions');for(const q of data.suggested_followups){const b=node('button',q);b.type='button';b.addEventListener('click',()=>send(q));choices.append(b);}wrap.append(choices);box.append(wrap);}
 if(data.brand_notes?.length)for(const t of data.brand_notes)box.append(node('p',t,'notice'));
 const legal=(data.citations||[]).filter(c=>!rows.some(r=>r.record_ids?.includes(c.id)));evidenceGroup(box,'Quy định BHYT liên quan',legal);evidenceGroup(box,'Tài liệu điều trị tham khảo',data.clinical_references||[]);
 if(data.notice)box.append(node('p',data.notice,'notice'));
 const foot=node('div',undefined,'answer-foot');const copy=node('button','Sao chép câu trả lời');copy.type='button';const text=reportText(data,question);copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(text);copy.textContent='Đã sao chép kèm nguồn';}catch{copy.textContent='Chưa sao chép được';}});foot.append(node('span','Theo bộ nguồn BHYT 06/11/2026'),copy);box.append(foot);return box;
}
async function send(text){
 text=(text??$('#question').value).trim();if(!text||!ready||busy)return;
 busy=true;$('#send').disabled=true;$('#new-chat').disabled=true;$('#loading').hidden=false;$('#error').hidden=true;$('#question').value='';$('#messages').setAttribute('aria-busy','true');let reply;
 const turn=node('section',undefined,'turn');const user=node('div',undefined,'query-heading');user.append(node('small','Bạn'),node('span',text));turn.append(user);$('#messages').append(turn);$('#welcome').hidden=true;
 try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify({message:text,state,department:'Tất cả các khoa'})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Chưa xử lý được câu hỏi.');state=JSON.parse(JSON.stringify(data.state||{}));reply=renderReply(data,text);turn.append(reply);}
 catch(e){turn.remove();$('#welcome').hidden=!!$('#messages').children.length;$('#error').textContent=e.message||'Không kết nối được ứng dụng.';$('#error').hidden=false;if(!$('#question').value)$('#question').value=text;}
 finally{busy=false;$('#send').disabled=!ready;$('#new-chat').disabled=false;$('#loading').hidden=true;$('#messages').setAttribute('aria-busy','false');if(reply){reply.focus({preventScroll:true});reply.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});}else $('#error').focus();}
}
function showView(name){name=name==='sources'?'sources':'lookup';const changed=currentView!==name;if(changed&&currentView)viewScroll[currentView]=scrollY;for(const n of document.querySelectorAll('.view'))n.hidden=n.id!=='view-'+name;for(const a of document.querySelectorAll('[data-view]')){if(a.dataset.view===name)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}currentView=name;if(changed)requestAnimationFrame(()=>scrollTo({top:viewScroll[name]||0,behavior:'instant'}));}
window.addEventListener('hashchange',()=>showView(location.hash.slice(1)));
$('#composer').addEventListener('submit',e=>{e.preventDefault();send();});
$('#question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}});
$('#new-chat').addEventListener('click',()=>{if(busy)return;state={};$('#messages').replaceChildren();$('#welcome').hidden=false;$('#question').value='';$('#error').hidden=true;$('#question').focus();});
for(const b of document.querySelectorAll('[data-query]'))b.addEventListener('click',()=>send(b.dataset.query));
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();location.hash='lookup';showView('lookup');$('#question').focus();}});
function renderSources(m){
 $('#review-status').textContent=m.review_status+'.';for(const text of m.missing)$('#missing-data').append(node('li',text));
 for(const s of m.sources){const row=node('article',undefined,'source-row');row.append(node('h3',s.title),node('p',fmt(s.chunks)+' đoạn trong bộ nguồn BHYT'));addSourceLinks(row,s);$('#source-list').append(row);}
 const update=m.source_update;if(!update)return;const date=s=>s.split('-').reverse().join('/');
 $('#source-update-summary').textContent=`Kiểm tra ${date(update.checked_as_of)} · ${update.documents.length} tài liệu / ${update.archived_pages} trang lưu · ${update.reference_pages} trang cho trích đoạn tham khảo. ${update.scope}`;
 for(const s of update.documents){const row=node('article',undefined,'source-row');row.append(node('h3',s.title),node('p',`${s.decision} · Ban hành ${date(s.published_at)} · ${s.pages} trang`),node('p',s.status_label),node('p','Bản đăng tại: '+s.host+' · Kiểm tra '+date(s.checked_as_of),'hint'));if(s.related_documents.length)row.append(node('p','Đọc cùng: '+s.related_documents.map(id=>update.documents.find(d=>d.id===id)?.decision||id).join(', '),'hint'));const d=node('details',undefined,'citation');d.append(node('summary','Phạm vi và giới hạn nguồn'),node('p',s.limitations));row.append(d);addSourceLinks(row,s);$('#supplemental-source-list').append(row);}
}
async function init(){try{const [hr,mr]=await Promise.all([fetch('/api/health'),fetch('/api/metadata')]);if(!hr.ok||!mr.ok)throw new Error();const h=await hr.json();metadata=await mr.json();if(h.version!=='1.9')throw new Error();token=h.token;ready=true;$('#send').disabled=false;$('#mode').textContent='Tra cứu theo nguồn';renderSources(metadata);}catch{$('#mode').textContent='Chưa kết nối';$('#connection-error').textContent='Chưa kết nối đúng bản chatbot v1.9. Khởi chạy start-windows.bat trong thư mục dự án rồi tải lại trang.';$('#connection-error').hidden=false;}}
showView(location.hash.slice(1));init();
