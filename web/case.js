'use strict';
(() => {
 const el=id=>document.getElementById(id);
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const labels={matched:'Khớp dữ kiện nhập',not_matched:'Chưa khớp ghi chú',missing:'Chưa có thông tin',needs_review:'Cần xác minh',recorded:'Đã ghi nhận'};
 let selected=null,schema=null,caseToken='',caseReady=false,queryRevision=0,schemaRevision=0,revision=0,busyCase=false,isExample=false;
 let timer;
 const factIds={product_name:'case-product',registration:'case-registration',diagnosis:'case-diagnosis',stage:'case-stage',biomarkers:'case-biomarkers',treatment:'case-treatment'};
 const coverage=[
  {title:'Danh mục và quy định BHYT',status:'available',detail:'Có trong bộ nguồn hiện có.'},
  {title:'Hướng dẫn chẩn đoán và điều trị',status:'needs_selection',detail:'Đã bổ sung tài liệu theo chủ đề. Chọn thuốc và hướng dẫn để xem phạm vi, bản PDF và những phần cần xác minh.'},
  {title:'Nhãn sản phẩm đã đăng ký',status:'missing',detail:'Chưa xác minh đúng sản phẩm.'},
  {title:'Dược thư Quốc gia',status:'missing',detail:'Chưa có mục thuốc tương ứng.'}
 ];
 function renderCoverage(items){const box=el('case-source-coverage');box.replaceChildren();for(const item of items){const row=make('div',undefined,'coverage-row');row.append(make('span',item.title),make('span',({available:'Có nguồn BHYT',reference:'Có tham khảo',pdf_only:'Chỉ xem PDF',pending:'Chờ xác minh',needs_selection:'Cần chọn chỉ định'})[item.status]||'Còn thiếu','status-label '+(item.status==='available'?'status-matched':'status-missing')),make('p',item.detail));box.append(row);}}
 function error(text){el('case-error').textContent=text;el('case-error').hidden=!text;if(text)el('case-error').focus();}
 function dirty(){
  ++revision;renderCoverage(schema?.source_coverage||coverage);
  if(el('case-result-body').hidden)return;
  el('case-result-body').replaceChildren(make('p','Thông tin đã thay đổi. Bấm “Đối chiếu điều kiện” để xem kết quả mới.','case-dirty'));
  el('case-draft-label').textContent='Cần đối chiếu lại';
 }
 function clearSelection(){selected=null;schema=null;++schemaRevision;el('case-selected').hidden=true;el('case-variant-wrap').hidden=true;el('case-profile').replaceChildren();el('case-submit').disabled=true;el('case-profile-hint').textContent='Chọn thuốc để xem thông tin cần đối chiếu.';dirty();}
 function reset(){
  if(busyCase)return;
  ++queryRevision;clearTimeout(timer);el('case-form').reset();clearSelection();isExample=false;
  el('case-drug-options').hidden=true;el('case-error').hidden=true;
  el('case-result-body').replaceChildren();el('case-result-body').hidden=true;el('case-empty').hidden=false;el('case-draft-label').textContent='Chưa có ca đối chiếu';
  renderCoverage(coverage);el('case-drug-search').focus();
 }
 async function get(path){const r=await fetch(path);const d=await r.json();if(!r.ok)throw new Error(d.error||'Không tải được thông tin.');return d;}
 async function loadSchema(id){
  const version=++schemaRevision;
  el('case-submit').disabled=true;
  const d=await get('/api/case/schema?id='+encodeURIComponent(id));
  if(version!==schemaRevision)return;
  schema=d;renderCoverage(d.source_coverage||coverage);el('case-profile').replaceChildren();
  for(const field of d.fields){
   const wrap=make('div');wrap.dataset.field=field.key;
   const label=make('label',field.label);label.htmlFor='case-answer-'+field.key;
   const select=make('select');select.id=label.htmlFor;select.dataset.answer=field.key;
   select.append(new Option('Chưa có thông tin',''));
   for(const choice of field.choices)select.append(new Option(choice.label,choice.value));
   select.addEventListener('change',()=>{updateConditional();dirty();});
   wrap.append(label,select);el('case-profile').append(wrap);
  }
  updateConditional();
  el('case-profile-hint').textContent=d.has_preliminary_profile?'Có bảng đối chiếu sơ bộ từ ghi chú danh mục; chưa được Dược/BHYT thẩm định.':'Đối chiếu theo nguyên văn ghi chú danh mục và quy định chung cho thuốc này.';
  el('case-submit').disabled=!caseReady||!el('case-variant').value;
 }
 function updateConditional(){
  if(!schema)return;
  for(const field of schema.fields){const wrap=el('case-profile').querySelector('[data-field="'+field.key+'"]');const visible=!field.show_when||Object.entries(field.show_when).every(([k,v])=>el('case-answer-'+k)?.value===v);wrap.hidden=!visible;if(!visible)wrap.querySelector('select').value='';}
 }
 async function choose(item){
  if(busyCase)return;
  ++queryRevision;clearTimeout(timer);dirty();selected=item;isExample=false;
  for(const id of Object.values(factIds))el(id).value='';
  el('case-drug-search').value=item.ingredient;el('case-drug-options').hidden=true;
  el('case-selected').replaceChildren(make('strong',item.ingredient),make('p','Phụ lục '+item.appendix+' · STT '+item.stt));el('case-selected').hidden=false;
  const select=el('case-variant');select.replaceChildren();
  if(item.variants.length>1)select.append(new Option('Chọn dòng thuốc / đường dùng',''));
  for(const variant of item.variants)select.append(new Option(variant.route,variant.id));
  el('case-variant-wrap').hidden=item.variants.length===1;
  el('case-error').hidden=true;
  await loadSchema(select.value||item.id);
 }
 el('case-drug-search').addEventListener('input',()=>{
  clearSelection();isExample=false;clearTimeout(timer);const q=el('case-drug-search').value.trim();const v=++queryRevision;
  if(q.length<2){el('case-drug-options').hidden=true;return;}
  timer=setTimeout(async()=>{try{
   const data=await get('/api/case/drugs?q='+encodeURIComponent(q));if(v!==queryRevision||busyCase)return;
   const box=el('case-drug-options');box.replaceChildren();
   for(const item of data.items){const b=make('button');b.type='button';b.append(make('span',item.ingredient),make('small','Phụ lục '+item.appendix+' · STT '+item.stt+' · '+item.variants.map(x=>x.route).join(' / ')));b.addEventListener('click',()=>choose(item).catch(e=>error(e.message)));box.append(b);}
   if(!data.items.length)box.append(make('p','Chưa tìm thấy hoạt chất. Thử tên hoạt chất thay cho biệt dược.'));
   box.hidden=false;
  }catch(e){if(v===queryRevision)error(e.message);}},220);
 });
 el('case-drug-search').addEventListener('keydown',e=>{if(e.key==='ArrowDown'&&!el('case-drug-options').hidden){e.preventDefault();el('case-drug-options').querySelector('button')?.focus();}if(e.key==='Escape'){++queryRevision;el('case-drug-options').hidden=true;}});
 el('case-drug-options').addEventListener('keydown',e=>{const buttons=[...el('case-drug-options').querySelectorAll('button')];const i=buttons.indexOf(document.activeElement);if(e.key==='Escape'){el('case-drug-options').hidden=true;el('case-drug-search').focus();}if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();const j=i+(e.key==='ArrowDown'?1:-1);if(j<0)el('case-drug-search').focus();else buttons[Math.min(j,buttons.length-1)]?.focus();}});
 el('case-variant').addEventListener('change',()=>{dirty();el('case-product').value='';if(!el('case-variant').value){el('case-submit').disabled=true;return;}loadSchema(el('case-variant').value).catch(e=>error(e.message));});
 for(const id of Object.values(factIds))el(id).addEventListener('input',dirty);
 el('case-department').addEventListener('change',dirty);
 function collect(){
  if(!schema||!selected||!el('case-variant').value)throw new Error('Nhập tên và chọn đúng dòng thuốc để đối chiếu.');
  const facts=Object.fromEntries(Object.entries(factIds).map(([k,id])=>[k,el(id).value.trim()]));
  const answers={};for(const s of el('case-profile').querySelectorAll('select'))if(!s.parentElement.hidden)answers[s.dataset.answer]=s.value;
  return {drug_id:el('case-variant').value,facts,answers,department:el('case-department').value};
 }
 function reportText(r){
  const lines=['ĐỐI CHIẾU SƠ BỘ CA BỆNH',r.drug.ingredient+' · '+r.drug.route,r.headline,r.notice];
  if(isExample)lines.push('Ca minh họa; dữ kiện giả lập.');
  const factLabels={product_name:'Sản phẩm',registration:'Số đăng ký',diagnosis:'Chẩn đoán / chỉ định',stage:'Giai đoạn',biomarkers:'Xét nghiệm',treatment:'Điều trị trước'};
  for(const [k,v] of Object.entries(r.facts))if(v)lines.push((factLabels[k]||k)+': '+v);
  for(const c of r.criteria)lines.push(c.label+' | '+labels[c.status]+' | '+c.value+' | '+c.reason);
  if(r.candidate_source_rate)lines.push('Tỷ lệ trong nhánh nguồn: '+r.candidate_source_rate.percentage+'% · '+r.candidate_source_rate.scope+'; chưa xác nhận mức hưởng cá nhân.');
  lines.push('NGUYÊN VĂN GHI CHÚ',r.conditions_verbatim||'Ô ghi chú trống; không suy ra thanh toán 100%.');
  for(const c of r.citations){lines.push('CĂN CỨ '+c.document_id+' · '+c.locator+' · '+(c.official_url||c.source_url),c.excerpt);for(const f of c.source_review_flags||[])lines.push('Giới hạn nguồn: '+f.note);}
  for(const item of r.source_coverage)lines.push('Bộ nguồn: '+item.title+' · '+item.detail);
  lines.push('Bộ nguồn BHYT '+r.snapshot+'; nguồn bổ sung kiểm tra '+r.source_checked_as_of+'; bảng đối chiếu chưa được Dược/BHYT thẩm định.');
  return lines.join('\n');
 }
 function render(r){
  const body=el('case-result-body');body.replaceChildren();body.hidden=false;el('case-empty').hidden=true;el('case-draft-label').textContent='Đối chiếu sơ bộ';
  if(isExample)body.append(make('p','Ca minh họa · dữ kiện giả lập, không phải bệnh nhân thật','case-example-label'));
  body.append(make('h3',r.headline,'case-headline'),make('p',r.notice,'case-notice'));
  const summary=make('dl',undefined,'case-summary');
  for(const [label,value] of [['Thuốc',r.drug.ingredient+' · '+r.drug.route],['Sản phẩm',r.facts.product_name||'Chưa xác định'],['Chẩn đoán',r.facts.diagnosis||'Chưa cung cấp'],['Khoa',r.department],...Object.entries({registration:'Số đăng ký',stage:'Giai đoạn',biomarkers:'Xét nghiệm',treatment:'Điều trị trước'}).filter(([k])=>r.facts[k]).map(([k,label])=>[label,r.facts[k]])]){
   const row=make('div');row.append(make('dt',label),make('dd',value));summary.append(row);
  }
  body.append(summary);
  const counts=make('div',undefined,'criteria-counts');for(const [k,n] of Object.entries(r.counts))if(n)counts.append(make('span',n+' '+labels[k].toLowerCase(),'status-'+k));body.append(counts);
  const header=make('div',undefined,'criteria-header');header.append(make('span','Điều kiện và trạng thái'),make('span','Thông tin đã nhập'));body.append(header);
  for(const item of r.criteria){
   const row=make('div',undefined,'criterion'),left=make('div'),right=make('div',undefined,'criterion-value');
   left.append(make('strong',item.label),make('div',labels[item.status],'criterion-status status-'+item.status));right.textContent=item.value;
   row.append(left,right);
   const evidence=make('div',undefined,'criterion-evidence');evidence.append(make('p',item.reason));
   if(item.source_ids.length){
    const d=make('details');d.append(make('summary','Xem căn cứ cho điều kiện này'));
    for(const id of item.source_ids){const citation=r.citations.find(c=>c.id===id);if(citation){if(citation.kind?.startsWith('clinical')){d.append(sourceBlock(citation));continue;}d.append(make('blockquote',id===r.drug.id?(r.conditions_verbatim||'Ô ghi chú trống; không suy ra thanh toán 100%.'):citation.excerpt));const a=link(citation.local_url||citation.official_url||citation.source_url,citation.document_id+' · '+citation.locator+' ↗');if(a)d.append(a);}}
    evidence.append(d);
   }
   row.append(evidence);body.append(row);
  }
  if(r.candidate_source_rate){
   const rate=r.candidate_source_rate,box=make('div',undefined,'source-rate');
   box.append(make('strong','Tỷ lệ ghi trong nhánh nguồn: '+rate.percentage+'%'),make('p',rate.scope),make('p','Các dữ kiện chọn khớp nhánh ghi chú này. Còn phải đối chiếu nhãn, quy định chung, chuyển tiếp và phạm vi tại cơ sở; đây chưa phải mức hưởng hay xác nhận thanh toán.'));
   body.append(box);
  }
  const next=make('details',undefined,'case-next');next.append(make('summary','Các thông tin và căn cứ cần bổ sung'));const list=make('ul');for(const text of r.next_steps)list.append(make('li',text));next.append(list);body.append(next);
  const all=make('details',undefined,'citation');all.append(make('summary','Toàn bộ căn cứ liên quan · '+r.citations.length+' đoạn'));for(const c of r.citations)all.append(sourceBlock(c));body.append(all);
  const foot=make('div',undefined,'case-copy-row'),copy=make('button','Sao chép bảng đối chiếu');copy.type='button';
  const text=reportText(r);copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(text);copy.textContent='Đã sao chép đầy đủ căn cứ';}catch{copy.textContent='Chưa sao chép được';}});
  foot.append(make('small','Phiên hiện tại · Không lưu hồ sơ'),copy);body.append(foot);renderCoverage(r.source_coverage);
 }
 async function evaluate(e){
  e?.preventDefault();if(busyCase||!caseReady)return;
  error('');
  let payload;try{payload=collect();}catch(e){error(e.message);return;}
  const v=revision;busyCase=true;el('case-submit').disabled=true;el('case-submit').textContent='Đang đối chiếu…';el('case-result').setAttribute('aria-busy','true');el('case-reset').disabled=true;
  try{
   const response=await fetch('/api/case/evaluate',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':caseToken},body:JSON.stringify(payload)});
   const r=await response.json();if(!response.ok)throw new Error(r.error||'Không đối chiếu được.');if(v!==revision)return;
   render(r);el('case-result').focus({preventScroll:true});el('case-result').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  }catch(e){error(e.message);}finally{busyCase=false;el('case-submit').disabled=!schema||!selected||!el('case-variant').value;el('case-submit').textContent='Đối chiếu điều kiện →';el('case-reset').disabled=false;el('case-result').setAttribute('aria-busy','false');}
 }
 el('case-form').addEventListener('submit',evaluate);el('case-reset').addEventListener('click',reset);
 for(const b of document.querySelectorAll('[data-case-demo]'))b.addEventListener('click',async()=>{
  if(busyCase||!caseReady)return;
  try{
   const name=b.dataset.caseDemo,data=await get('/api/case/drugs?q='+encodeURIComponent(name));
   const item=data.items.find(x=>x.ingredient.toLowerCase()===name);if(!item)throw new Error('Chưa tìm được thuốc minh họa.');
   await choose(item);isExample=true;
   if(name==='trastuzumab'){el('case-diagnosis').value='Ca minh họa: ung thư vú.';el('case-answer-indication').value='breast';}
   if(name==='paclitaxel'){el('case-diagnosis').value='Ca minh họa: cần đối chiếu thêm chỉ định trong hồ sơ.';el('case-answer-formulation').value='liposome';}
   if(name==='metformin'){el('case-diagnosis').value='Ca minh họa: đái tháo đường type 2.';if(el('case-answer-clinical_topic'))el('case-answer-clinical_topic').value='t2d';}
   updateConditional();dirty();await evaluate();
  }catch(e){error(e.message);}
 });
 renderCoverage(coverage);
 Promise.all([get('/api/health'),get('/api/metadata')]).then(([h,m])=>{caseToken=h.token;caseReady=true;for(const name of m.departments)if(name!=='Tất cả các khoa')el('case-department').append(new Option(name,name));}).catch(()=>error('Chưa kết nối được ứng dụng. Khởi chạy chatbot và tải lại trang.'));
})();
