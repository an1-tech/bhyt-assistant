"use strict";
const $=s=>document.querySelector(s);
const fmt=n=>new Intl.NumberFormat('vi-VN').format(n);
let state={},token='',busy=false,ready=false,metadata=null,currentView=null;
const viewScroll={lookup:0,sources:0};
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
function link(url,label){try{if(!url)return null;const u=new URL(url,location.origin);if(u.origin!==location.origin&&u.protocol!=='https:')return null;if(u.origin===location.origin&&!u.pathname.startsWith('/sources/'))return null;const a=node('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return null;}}
function sourceName(id){return [...(metadata?.sources||[]),...(metadata?.source_update?.documents||[])].find(s=>s.id===id)?.title||id||'Nguồn';}
function addSourceLinks(parent,s){const row=node('div',undefined,'source-links');let local=s.local_url||(s.document_id==='TT20_2022'?'/sources/15-vbhn-byt-2024.pdf':s.document_id==='TT37_2024'?'/sources/37-2024-tt-byt.pdf':null);if(local&&s.page&&!local.includes('#')&&(s.document_id!=='TT20_2022'||s.page_checked))local+='#page='+s.page;const seen=new Set();for(const [url,label] of [[s.official_url,'Bản công bố ↗'],[s.source_url||s.url,'Nguồn trích dẫn ↗'],[local,'PDF trên máy ↗']]){if(!url||seen.has(url))continue;seen.add(url);const a=link(url,label);if(a)row.append(a);}parent.append(row);}
function sourceBlock(s){const row=node('article',undefined,'evidence-row');row.append(node('strong',s.document_title||sourceName(s.document_id)),node('div',(s.locator||'').replace(/, dòng HTML \d+/g,'')+(s.page&&!s.locator?.includes('Trang PDF')?' · Trang '+s.page:''),'evidence-locator'));if(s.kind?.startsWith('clinical'))row.append(node('p',s.kind==='clinical_reference'?'Tham khảo điều trị; không tự xác nhận thanh toán.':'Chỉ dẫn PDF; chưa dùng nội dung để kết luận.','hint'));for(const f of s.source_review_flags||[])row.append(node('p',f.note,'notice'));addSourceLinks(row,s);const details=node('details',undefined,'citation');details.append(node('summary','Đọc nguyên văn'),node('pre',s.excerpt||''));row.append(details);return row;}
function quoteBlock(q,status){
 // Direct quotation of the source note; marked parts come from positions in the stored text.
 const fig=node('figure',undefined,'source-quote');fig.append(node('figcaption',q.document+' · '+q.locator+(q.page_checked?' · trang PDF '+q.pages.join('–'):'')));
 const bq=document.createElement('blockquote');
 if(q.empty)bq.append(node('em','Ô ghi chú của dòng này trong nguồn để trống.'));
 else{let at=0;for(const h of q.highlights||[]){if(h.start<at)continue;bq.append(document.createTextNode(q.text.slice(at,h.start)));bq.append(node('mark',q.text.slice(h.start,h.end)));at=h.end;}bq.append(document.createTextNode(q.text.slice(at)));}
 fig.append(bq);const row=node('div',undefined,'source-links');
 const a=link(q.pdf_url,q.page_checked?'Mở PDF trang '+q.page+' ↗':'Mở PDF (chưa xác minh số trang) ↗');if(a)row.append(a);const o=link(q.official_url,'Bản công bố ↗');if(o)row.append(o);
 fig.append(row);if(q.highlights?.length)fig.append(node('p',status==='source_condition_not_met'?'Phần tô đậm là điều kiện nguồn yêu cầu; thông tin trong câu hỏi không khớp điều kiện này.':'Phần tô đậm là đoạn câu trả lời dựa vào.','hint'));
 if(q.page_checked)fig.append(node('p',q.page_note||'Số trang đã đối chiếu với ảnh trang PDF (Đỗ Quốc An đọc), chờ Dược xác nhận.','hint'));return fig;}
function evidenceGroup(parent,title,items){if(!items.length)return;const d=node('details',undefined,'citation');d.append(node('summary',title+' · '+items.length+' đoạn'));for(const c of items)d.append(sourceBlock(c));parent.append(d);}
// Which source a reply rests on, for the footer and the copied text alike: a medicine answer never names the lab source.
function sourceStamp(data){const lab=(data.domain==='lab'||data.domain==='mixed')&&data.source_checked_as_of?data.source_checked_as_of.split('-').reverse().join('/'):null;return data.domain==='mixed'?'Nguồn thuốc 06/11/2026 · Nguồn xét nghiệm kiểm tra '+lab:lab?'Nguồn xét nghiệm kiểm tra '+lab:'Theo bộ nguồn BHYT 06/11/2026';}
function reportText(data,question){const out=['Câu hỏi: '+question,data.answer];for(const r of data.results||[]){const a=r.question_answer;if(!a)continue;out.push(r.ingredient,a.conclusion,...a.conditions);for(const q of a.quotes||[])out.push('TRÍCH NGUYÊN VĂN '+q.document+' · '+q.locator+(q.page_checked?' · trang PDF '+q.pages.join('–'):'')+': “'+(q.empty?'(ô ghi chú trống)':q.text)+'”');out.push(a.scope);}for(const r of data.lab_results||[])out.push(r.name,r.conclusion,...(r.reading||[]).map(x=>'Dữ kiện đã đọc — '+x),...r.reasons,...(r.notes||[]),'NGUYÊN VĂN: '+r.conditions.join(' '),...((r.rate||[]).length?['Tỷ lệ, mức giá thanh toán: '+r.rate.join(' ')]:[]),r.scope,'Vị trí nguồn: '+new URL(r.citation.viewer_url,location.origin).href);for(const c of [...(data.citations||[]),...(data.clinical_references||[])]){out.push('NGUỒN '+(c.document_title||sourceName(c.document_id))+' · '+c.locator+' · '+(c.official_url||c.source_url||c.local_url),c.excerpt);for(const f of c.source_review_flags||[])out.push('Giới hạn: '+f.note);}if(data.notice)out.push(data.notice);for(const t of data.brand_notes||[])out.push(t);for(const t of data.hospital_notes||[])out.push(t);out.push(sourceStamp(data)+'; đối chiếu với nguồn, không phải quyết định thanh toán.'+(data.review_note?' '+data.review_note:''));if(data.domain==='lab'||data.domain==='mixed')out.push('Ngày kiểm tra nguồn xét nghiệm không bảo đảm đã rà soát mọi văn bản mới.');return out.join('\n');}
function labBlock(r,data){
 const section=node('section',undefined,'drug-result lab-result');section.append(node('h3',r.name,'drug-heading'),node('p',r.conclusion,'conclusion'));
 if(r.reasons?.length){const reasons=node('ul',undefined,'lab-reasons');for(const t of r.reasons)reasons.append(node('li',t));section.append(reasons);}
 if(r.reading?.length){const rd=node('div',undefined,'answer-block lab-reading');rd.append(node('strong','Chatbot hiểu dữ kiện như sau'));const ul=node('ul');for(const t of r.reading)ul.append(node('li',t));rd.append(ul);
  if(r.pending==='confirm'){const snap=JSON.parse(JSON.stringify(data?.state||{}));const act=node('div',undefined,'actions');const b=node('button','Đúng, đối chiếu theo các dữ kiện này');b.type='button';b.addEventListener('click',()=>send('Đúng, đối chiếu theo các dữ kiện này',snap));act.append(b);rd.append(act,node('p','Nếu chưa đúng, hãy gõ lại dữ kiện cần sửa.','hint'));}
  section.append(rd);}
 for(const t of r.notes||[])section.append(node('p',t,'notice lab-note'));
 // Verbatim source row; the branch compared with the case is marked by its index, never re-typed.
 const used=new Set(r.highlight||[]),paired=r.rate_mode==='paired';
 const block=node('div',undefined,'answer-block lab-quote');block.append(node('strong','Nguyên văn điều kiện trong nguồn'));const list=node('ul');
 r.conditions.forEach((t,i)=>{const li=document.createElement('li');if(used.has(i)){li.append(node('mark',t));li.className='lab-used';}else li.textContent=t;if(paired&&r.rate?.[i])li.append(node('span','Tỷ lệ, mức giá thanh toán: '+r.rate[i],'lab-rate'));list.append(li);});
 block.append(list);if(used.size)block.append(node('p',r.status==='source_condition_not_met'?'Phần tô đậm là nhánh nguồn đang đối chiếu; thông tin đã nêu không khớp nhánh này.':'Phần tô đậm là nhánh đang đối chiếu.','hint'));section.append(block);
 if(r.rate?.length&&!paired){const rate=node('div',undefined,'answer-block lab-rate-block');rate.append(node('strong','Tỷ lệ, mức giá thanh toán (nguyên văn)'));const rl=node('ul');for(const t of r.rate)rl.append(node('li',t));rate.append(rl);section.append(rate);}
 const scan=r.transcription==='scan_read';
 const source=node('div',undefined,'lab-source');source.append(node('p',r.citation.document_title+' · '+r.citation.locator+(scan?' · chép từ bản scan':''),'hint'));const links=node('div',undefined,'source-links');const a=link(r.citation.viewer_url,scan?'Xem ảnh trang nguồn ↗':'Xem vị trí trích dẫn ↗');if(a)links.append(a);const pdf=link(r.citation.local_url+'#page='+r.citation.page,'Mở toàn trang PDF ↗');if(pdf)links.append(pdf);source.append(links);section.append(source,node('p',r.scope+(r.review?' '+r.review.text:''),'scope-note'));return section;
}
function renderReply(data,question){
 const box=node('article',undefined,'assistant');box.tabIndex=-1;box.append(node('h2','Cẩm nang BHYT'));
 const rows=data.results||[];
 if(!rows.length&&!data.lab_results?.length)box.append(node('p',data.answer,'conclusion'));
 if(data.lab_links?.length){const links=node('div',undefined,'source-links');for(const l of data.lab_links){const a=link(l.url,l.label+' ↗');if(a)links.append(a);}box.append(links);}
 for(const r of data.lab_results||[])box.append(labBlock(r,data));
 if(data.domain==='mixed'&&!rows.length){const section=node('section',undefined,'drug-result');section.append(node('h3','Thuốc được hỏi','drug-heading'),node('p',data.answer,'conclusion'));box.append(section);}
 for(const r of rows){const a=r.question_answer;const section=node('section',undefined,'drug-result');section.append(node('h3',r.ingredient,'drug-heading'),node('p',a?.conclusion||data.answer,'conclusion'));for(const q of a?.quotes||[])section.append(quoteBlock(q,a.status));
  if(a?.conditions?.length){const conditions=node('div',undefined,'answer-block');conditions.append(node('strong','Điều kiện trong nguồn'));const list=node('ul');for(const text of a.conditions)list.append(node('li',text));conditions.append(list);section.append(conditions);}
  if(a?.confirm?.length){
   // Unclear conditions are confirmed with buttons; the bot never guesses them from free text.
   const block=node('div',undefined,'confirm-block');block.append(node('strong','Xác nhận để đối chiếu'),node('p','Bấm đúng tình trạng; chọn “Chưa rõ” nếu chưa có kết quả.','hint'));
   const snap=JSON.parse(JSON.stringify(data.state||{}));
   for(const item of a.confirm){const group=node('div',undefined,'confirm-item');group.setAttribute('role','group');group.setAttribute('aria-label',item.label);group.append(node('span',item.label,'confirm-label'));const opts=node('div',undefined,'actions');
    for(const opt of item.options){const b=node('button',opt.label);b.type='button';b.addEventListener('click',()=>{const rid=item.key.split('|')[0];send(item.label+': '+opt.label,(state.selected_ids||[]).includes(rid)?state:snap,{key:item.key,value:opt.value});});opts.append(b);}
    group.append(opts);block.append(group);}
   section.append(block);}
  const sources=(data.citations||[]).filter(c=>r.record_ids?.includes(c.id));evidenceGroup(section,'Căn cứ của thuốc',sources);if(a?.scope)section.append(node('p',a.scope,'scope-note'));box.append(section);
 }
 if(data.suggestions?.length){const choices=node('div',undefined,'actions');for(const name of data.suggestions){const b=node('button',name);b.type='button';b.addEventListener('click',()=>send(data.suggestion_mode==='replace'?name:name+' — '+question));choices.append(b);}box.append(choices);}
 if(data.suggested_followups?.length){const wrap=node('div',undefined,'followup-chips');wrap.append(node('strong','Hỏi tiếp'));const choices=node('div',undefined,'actions');const snap=JSON.parse(JSON.stringify(data.state||{}));for(const q of data.suggested_followups){const b=node('button',q);b.type='button';b.addEventListener('click',()=>send(q,snap));choices.append(b);}wrap.append(choices);box.append(wrap);}
 if(data.brand_notes?.length)for(const t of data.brand_notes)box.append(node('p',t,'notice'));
 if(data.hospital_notes?.length)for(const t of data.hospital_notes)box.append(node('p',t,'notice hospital-note'));
 const legal=(data.citations||[]).filter(c=>!rows.some(r=>r.record_ids?.includes(c.id))&&!data.lab_results?.some(r=>r.citation.id===c.id));evidenceGroup(box,'Quy định BHYT liên quan',legal);evidenceGroup(box,'Tài liệu điều trị tham khảo',data.clinical_references||[]);
 if(data.notice)box.append(node('p',data.notice,'notice'));
 const foot=node('div',undefined,'answer-foot');const copy=node('button','Sao chép câu trả lời');copy.type='button';const text=reportText(data,question);copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(text);copy.textContent='Đã sao chép kèm nguồn';}catch{copy.textContent='Chưa sao chép được';}});foot.append(node('span',sourceStamp(data)+(data.review_label?' · '+data.review_label:'')),copy);box.append(foot);return box;
}
async function send(text,ctx,confirm){
 // ctx: a follow-up chip sends the context of the answer it belongs to, not the latest one.
 // confirm: {key,value} from a confirmation button — a structured fact, not text to parse.
 text=(text??$('#question').value).trim();if(!text||!ready||busy)return;
 busy=true;$('#send').disabled=true;$('#new-chat').disabled=true;$('#loading').hidden=false;$('#error').hidden=true;if(!confirm)$('#question').value='';$('#messages').setAttribute('aria-busy','true');let reply;
 const turn=node('section',undefined,'turn');const user=node('div',undefined,'query-heading');user.append(node('small','Bạn'),node('span',text));turn.append(user);$('#messages').append(turn);$('#welcome').hidden=true;
 try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify(Object.assign({message:text,state:ctx??state,department:'Tất cả các khoa'},confirm?{confirm}:{}))});const data=await response.json();if(!response.ok)throw new Error(data.error||'Chưa xử lý được câu hỏi.');state=JSON.parse(JSON.stringify(data.state||{}));reply=renderReply(data,text);turn.append(reply);}
 catch(e){turn.remove();$('#welcome').hidden=!!$('#messages').children.length;$('#error').textContent=e.message||'Không kết nối được ứng dụng.';$('#error').hidden=false;if(!confirm&&!$('#question').value)$('#question').value=text;}
 finally{busy=false;$('#send').disabled=!ready;$('#new-chat').disabled=false;$('#loading').hidden=true;$('#messages').setAttribute('aria-busy','false');if(reply){reply.focus({preventScroll:true});reply.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});}else $('#error').focus();}
}
function showView(name){name=name==='sources'?'sources':'lookup';const changed=currentView!==name;if(changed&&currentView)viewScroll[currentView]=scrollY;for(const n of document.querySelectorAll('.view'))n.hidden=n.id!=='view-'+name;for(const a of document.querySelectorAll('[data-view]')){if(a.dataset.view===name)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}currentView=name;if(changed)requestAnimationFrame(()=>scrollTo({top:viewScroll[name]||0,behavior:'instant'}));}
window.addEventListener('hashchange',()=>showView(location.hash.slice(1)));
// Keyboard focus inside the conversation must never sit under the sticky header or composer.
document.addEventListener('focusin',e=>{const t=e.target;if(!t.closest||!t.closest('#messages'))return;const r=t.getBoundingClientRect(),c=document.querySelector('.chat-composer')?.getBoundingClientRect(),h=document.querySelector('.topbar')?.getBoundingClientRect();if(c&&r.bottom>c.top)scrollBy({top:r.bottom-c.top+16,behavior:'instant'});else if(h&&r.top<h.bottom)scrollBy({top:r.top-h.bottom-16,behavior:'instant'});});
$('#composer').addEventListener('submit',e=>{e.preventDefault();send();});
$('#question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}});
$('#new-chat').addEventListener('click',()=>{if(busy)return;state={};$('#messages').replaceChildren();$('#welcome').hidden=false;$('#question').value='';$('#error').hidden=true;$('#question').focus();});
for(const b of document.querySelectorAll('[data-query]'))b.addEventListener('click',()=>send(b.dataset.query));
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();location.hash='lookup';showView('lookup');$('#question').focus();}});
function renderSources(m){
 $('#review-status').textContent=m.review_status+'.';for(const text of m.missing)$('#missing-data').append(node('li',text));
 if(m.lab_source?.service_count){const s=m.lab_source, row=node('article',undefined,'source-row');const day=d=>d.split('-').reverse().join('/');
  row.append(node('h3','Xét nghiệm có điều kiện thanh toán riêng · '+s.title+' và 17/VBHN-BYT'),node('p',s.service_count+' dòng xét nghiệm: '+s.text_layer_count+' dòng lấy từ lớp chữ của phụ lục TT39/2024, '+s.scan_read_count+' dòng chép từ ảnh trang của bản hợp nhất 17/VBHN-BYT (bản scan, Đỗ Quốc An đọc).'),node('p','Hiệu lực quy tắc từ '+day(s.effective_from)+' · Kiểm tra '+day(s.checked_as_of)),node('p',s.review_status),node('p',s.review_limitations,'hint'));
  const d=node('details',undefined,'citation');d.append(node('summary','Danh sách '+s.service_count+' xét nghiệm (HbA1c, EGFR, HER2, KRAS, BRAF, CRP, Procalcitonin, HBV, HCV…)'));for(const service of s.services){const a=link(service.viewer_url,service.name+(service.transcription==='scan_read'?' · bản scan':'')+' ↗');if(a){a.className='text-link';d.append(a);}}row.append(d);
  for(const doc of s.documents||[]){const a=link(doc.local_url,doc.title+' ↗');if(a){a.className='text-link';row.append(a);}}
  $('#source-list').append(row);}
 for(const s of m.sources){const row=node('article',undefined,'source-row');row.append(node('h3',s.title),node('p',fmt(s.chunks)+' đoạn trong bộ nguồn BHYT'));addSourceLinks(row,s);$('#source-list').append(row);}
 const update=m.source_update;if(!update)return;const date=s=>s.split('-').reverse().join('/');
 $('#source-update-summary').textContent=`Kiểm tra ${date(update.checked_as_of)} · ${update.documents.length} tài liệu / ${update.archived_pages} trang lưu · ${update.reference_pages} trang cho trích đoạn tham khảo. ${update.scope}`;
 for(const s of update.documents){const row=node('article',undefined,'source-row');row.append(node('h3',s.title),node('p',`${s.decision} · Ban hành ${date(s.published_at)} · ${s.pages} trang`),node('p',s.status_label),node('p','Bản đăng tại: '+s.host+' · Kiểm tra '+date(s.checked_as_of),'hint'));if(s.related_documents.length)row.append(node('p','Đọc cùng: '+s.related_documents.map(id=>update.documents.find(d=>d.id===id)?.decision||id).join(', '),'hint'));const d=node('details',undefined,'citation');d.append(node('summary','Phạm vi và giới hạn nguồn'),node('p',s.limitations));row.append(d);addSourceLinks(row,s);$('#supplemental-source-list').append(row);}
}
async function init(){try{const [hr,mr]=await Promise.all([fetch('/api/health'),fetch('/api/metadata')]);if(!hr.ok||!mr.ok)throw new Error();const h=await hr.json();metadata=await mr.json();if(h.version!=='1.11')throw new Error();token=h.token;ready=true;$('#send').disabled=false;$('#mode').textContent='Tra cứu theo nguồn';renderSources(metadata);}catch{$('#mode').textContent='Chưa kết nối';$('#connection-error').textContent='Chưa kết nối đúng bản chatbot v1.11. Khởi chạy start-windows.bat trong thư mục dự án rồi tải lại trang.';$('#connection-error').hidden=false;}}
showView(location.hash.slice(1));init();
