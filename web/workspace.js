(() => {
  const el = id => document.getElementById(id);
  const state = {tree:null,current:null,revision:0,profileRevision:0,pending:null,dirty:false,loading:true,saving:null,failed:false,conflict:false,token:0,bufferOk:true,examples:[],example:null,startBusy:false};
  const uuid = () => crypto.randomUUID().replaceAll("-", "");
  const key = () => `chengxu.workspace.${state.current.advisor_id}.${state.current.id}`;
  const node = (tag,text) => {const item=document.createElement(tag);if(text!==undefined)item.textContent=text;return item;};
  function headers() {return state.current ? {"X-Advisor-ID":state.current.advisor_id,"X-Conversation-ID":state.current.id} : {};}
  async function api(path, options={}) {
    const response=await fetch(path,{...options,headers:{...headers(),...options.headers}});
    const data=await response.json();
    if(!response.ok){const error=new Error(data.message||"本机保存未完成。");error.code=data.code;throw error;}
    return data;
  }
  const post = (path,data) => api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  function url(path) {const query=new URLSearchParams({advisor:state.current?.advisor_id||"",conversation:state.current?.id||""});return path+(path.includes("?")?"&":"?")+query;}
  function status(text, kind="saving") {el("save-state").textContent=text;el("save-state").dataset.state=kind;el("retry-save").hidden=kind!=="failed"||state.conflict;el("resolve-save").hidden=!state.conflict;window.dispatchEvent(new Event('savestatuschanged'));}
  function snapshot() {return {draft:JSON.parse(JSON.stringify(window.AdvisorEditor.snapshot())),preferences:el("customer-preferences").value,marketing_opt_out:el("marketing-opt-out").checked};}
  function buffer() {
    if(!state.current||state.loading)return;
    if(!state.dirty&&!state.pending)return true;
    try{localStorage.setItem(key(),JSON.stringify({revision:state.revision,profile_revision:state.profileRevision,pending:state.pending,...snapshot()}));state.bufferOk=true;return true;}
    catch(error){state.bufferOk=false;status("恢复副本未保存 · 请保持页面打开并保存到本机", "failed");return false;}
  }
  function changed() {
    if(state.loading||!state.current)return;
    state.dirty=true;state.failed=false;buffer();
    if(!state.conflict)status("尚未保存 · 正在保存…");
    clearTimeout(changed.timer);changed.timer=setTimeout(()=>flush().catch(()=>{}),500);
  }
  function policy() {
    const opted=el("marketing-opt-out").checked;
    el("contact-policy").hidden=!opted;
    el("contact-policy").textContent="此客户不接收营销消息，所有会话共用。可回应客户主动咨询；以前的回复仅供回顾，发送前需重新核对。";
    window.AdvisorEditor?.updateControls();
  }
  function stored(name) {try{return JSON.parse(localStorage.getItem(name)||'null');}catch(error){return null;}}
  function remember(name,value) {try{localStorage.setItem(name,JSON.stringify(value));}catch(error){state.bufferOk=false;}}
  function isExample(conversation) {return state.examples.find(row=>row.conversation_id===conversation);}
  function renderStart() {
    if(!state.tree)return;
    const examples=new Set(state.examples.map(row=>row.customer_id));
    const select=el('current-customer');select.replaceChildren(new Option('选择已有客户',''));
    const preferred=state.current&&!state.example?state.current.advisor_id:stored('chengxu.normal-advisor');
    const mine=node('optgroup');mine.label='我的客户';const others=node('optgroup');others.label='其他已存顾问的客户';
    state.tree.customers.filter(row=>!examples.has(row.id)).forEach(row=>{
      const advisor=state.tree.advisors.find(item=>item.id===row.advisor_id);
      (row.advisor_id===preferred?mine:others).append(new Option(row.name+' · '+(advisor?.name||''),row.id));
    });
    if(mine.children.length)select.append(mine);if(others.children.length)select.append(others);
    select.value=state.example?'':state.current?.customer_id||'';
    const conversations=el('current-conversation');conversations.replaceChildren(new Option('新建或选择客户后开始',''));
    if(state.current&&!state.example){
      conversations.replaceChildren();
      state.tree.conversations.filter(row=>row.customer_id===state.current.customer_id).forEach(row=>conversations.append(new Option(row.title,row.id)));
      conversations.value=state.current.id;
    }
    conversations.disabled=!state.current||Boolean(state.example)||state.startBusy;
    el('start-conversation').disabled=!state.current||Boolean(state.example)||state.startBusy;
    el('quick-create-customer').disabled=state.startBusy;
    select.disabled=state.startBusy;
    el('start-help').textContent=state.example?'正在回放示例；可返回自己的沟通。':state.current?'先选场景，再放截图或输入聊天；已有资料会继续使用。':'只需一个客户称呼即可开始，不用填写完整档案。';
    el('example-banner').hidden=!state.example;
    if(state.example){
      const draft=window.AdvisorEditor.snapshot();
      el('example-title').textContent='保存结果回放 · '+state.example.label+'（不是本次新生成）';
      el('example-materials').textContent=[draft.input.conversation?'文字聊天：已载入':'文字聊天：本例未提供',draft.input.related_info?'相关资料：已载入':'相关资料：本例无需补充',draft.context?.asset_ids?.length?'截图：已载入':'截图：本例未提供，以文字聊天保存',el('customer-preferences').value?'长期偏好：已载入':'长期偏好：本例未提供'].join('；')+'。可以查看当时回复，修改资料后需重新生成。';
    }
  }
  async function home(forget=false) {
    if(state.current)await flush();
    state.loading=true;state.current=null;state.example=null;state.pending=null;state.dirty=false;
    state.revision=0;state.profileRevision=0;el('customer-preferences').value='';el('marketing-opt-out').checked=false;
    if(forget){try{localStorage.removeItem('chengxu.selection');}catch(error){}}
    await window.AdvisorEditor.restore({},{});state.loading=false;
    document.querySelectorAll('#context-form,#revision-form,.customer-profile').forEach(item=>{item.inert=true;});
    el('workspace-path').textContent='还未选择客户 · 新建或选择客户开始';policy();renderStart();status('尚未开始 · 先新建或选择客户','saved');window.AdvisorEditor.updateControls();
  }
  async function startAction(action) {
    if(state.startBusy)return;
    if(window.AdvisorEditor.busy()||window.ContextImporter.busy()){el('start-error').textContent='正在处理当前任务，请完成后再切换。';el('start-error').hidden=false;return;}
    state.startBusy=true;el('start-error').hidden=true;renderStart();
    try{await action();}catch(error){el('start-error').textContent=error.message;el('start-error').hidden=false;}
    finally{state.startBusy=false;renderStart();}
  }
  async function quickCustomer() {
    const name=el('quick-customer-name').value.trim();if(!name)return;
    await startAction(async()=>{
      if(state.current)await flush();
      let advisor=state.current&&!state.example?state.current.advisor_id:stored('chengxu.normal-advisor');
      if(!state.tree.advisors.some(row=>row.id===advisor)){
        const result=await post('/api/workspace/create',{kind:'advisor',name:'我的工作台'});state.tree=result;advisor=result.id;remember('chengxu.normal-advisor',advisor);
      }
      const result=await post('/api/workspace/create',{kind:'customer',name,advisor_id:advisor});state.tree=result;
      const conversation=result.conversations.find(row=>row.customer_id===result.id);
      await open(advisor,conversation.id);el('quick-customer-name').value='';
    });
  }
  async function startConversation() {
    if(!state.current||state.example)return;
    await startAction(async()=>{
      await flush();const result=await post('/api/workspace/create',{kind:'conversation',name:'新沟通 · '+new Date().toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}),advisor_id:state.current.advisor_id,customer_id:state.current.customer_id});state.tree=result;
      await open(state.current.advisor_id,result.id);el('scenario').focus();
    });
  }
  async function chooseCustomer(identity) {
    await startAction(async()=>{
      if(!identity)return home(true);
      const customer=state.tree.customers.find(row=>row.id===identity);if(!customer)return;
      const last=stored('chengxu.customer-session.'+identity);
      const conversation=state.tree.conversations.find(row=>row.customer_id===identity&&row.id===last)||state.tree.conversations.find(row=>row.customer_id===identity);
      if(conversation)await open(customer.advisor_id,conversation.id);
    });
  }
  async function examples() {
    if(state.current)await flush();
    el('saved-examples').replaceChildren();el('examples-error').textContent='';
    for(const row of state.examples){
      const button=node('button',row.label+' · 保存结果');button.type='button';button.className='folder-item';
      button.addEventListener('click',async()=>{try{await open(row.advisor_id,row.conversation_id);el('examples-dialog').close();}catch(error){el('examples-error').textContent=error.message;}});el('saved-examples').append(button);
    }
    if(!state.examples.length)el('saved-examples').append(node('p','尚未载入保存结果示例；正常使用不需要示例。'));
    el('examples-dialog').showModal();
  }
  async function flush() {
    clearTimeout(changed.timer);
    if(state.loading||!state.current)throw new Error("会话正在恢复，请稍等。");
    if(state.conflict)throw new Error("保存版本有冲突，请先比较两个版本。");
    if(state.saving){await state.saving;if(state.dirty)return flush();return;}
    if(!state.dirty&&!state.pending)return;
    const task=(async()=>{
      while(state.dirty||state.pending){
        state.pending ||= {mutation_id:uuid(),revision:state.revision,profile_revision:state.profileRevision,...snapshot()};
        buffer();status("正在保存到本机…");
        const sent=state.pending;
        try{
          const ack=await post("/api/workspace/checkpoint",sent);
          state.revision=ack.revision;state.profileRevision=ack.profile_revision;state.pending=null;
          state.dirty=JSON.stringify(snapshot())!==JSON.stringify({draft:sent.draft,preferences:sent.preferences,marketing_opt_out:sent.marketing_opt_out});
          state.current.marketing_opt_out=ack.marketing_opt_out;if(ack.marketing_opt_out){el("marketing-opt-out").checked=true;policy();}
          state.failed=false;
          if(state.dirty)buffer();else {try{localStorage.removeItem(key());}catch(error){}status("已保存到本机 · "+new Date(ack.updated_at).toLocaleTimeString("zh-CN",{hour12:false}),"saved");}
        }catch(error){
          state.failed=true;state.conflict=error.code==="workspace_conflict";buffer();status((state.conflict?"版本冲突 · 未覆盖已存资料":(state.bufferOk?"未保存到本机 · 已保留本页恢复副本":"未保存到本机 · 浏览器副本也不可用，请保持页面打开"))+"。"+error.message,"failed");throw error;
        }
      }
    })();
    state.saving=task;
    try{await task;}finally{state.saving=null;}
  }
  async function open(advisor, conversation) {
    if(state.switching)throw new Error("会话正在恢复，请稍等。");
    if(state.current&&!state.loading){
      if(window.AdvisorEditor.busy()||window.ContextImporter.busy())throw new Error("资料正在处理，请稍等完成后再切换。");
      await flush();
    }
    state.loading=true;state.switching=true;let restored=false;document.querySelectorAll("#context-form,#revision-form,.customer-profile").forEach(item=>{item.inert=true;});const token=++state.token;
    try{
      state.current={advisor_id:advisor,id:conversation};
      const row=await api("/api/workspace/open");
      if(token!==state.token)return;
      state.current=row;state.example=isExample(conversation)||null;el("consent-form").hidden=true;el("consent-reason").value="";state.revision=row.revision;state.profileRevision=row.profile_revision;state.pending=null;state.dirty=false;state.failed=false;state.conflict=false;
      let recovery=null;
      try{recovery=JSON.parse(localStorage.getItem(key())||"null");}catch(error){status("恢复副本无法读取，请检查浏览器存储。","failed");}
      el("customer-preferences").value=recovery?.preferences??row.preferences;
      el("marketing-opt-out").checked=Boolean(row.marketing_opt_out||recovery?.marketing_opt_out);
      if(recovery){state.revision=recovery.revision;state.profileRevision=recovery.profile_revision;state.pending=recovery.pending;state.dirty=true;}
      await window.AdvisorEditor.restore(recovery?.draft||row.draft,row);
      el("workspace-path").textContent=state.example?'示例回放 · '+state.example.label:`${row.customer_name} / ${row.title}`;
      if(!state.example){remember('chengxu.selection',{advisor,conversation});remember('chengxu.normal-advisor',advisor);remember('chengxu.customer-session.'+row.customer_id,conversation);}
      renderStart();
      policy();status(recovery?"发现未完成草稿 · 正在恢复保存…":row.updated_at?"已恢复 · "+new Date(row.updated_at).toLocaleString("zh-CN",{hour12:false}):"新会话 · 可以直接开始",recovery?"saving":"saved");
      restored=true;
    }catch(error){status("会话未恢复，已停止编辑。请重新打开目标会话。"+error.message,"failed");throw error;}finally{state.loading=!restored;state.switching=false;document.querySelectorAll("#context-form,#revision-form,.customer-profile").forEach(item=>{item.inert=!restored;});window.AdvisorEditor.updateControls();}
    if(restored)await window.Understanding?.refresh();
    if(state.dirty)await flush();
  }
  function renderFolders() {
    const tree=state.tree,advisor=el("folder-advisor").value;
    el("folder-customers").replaceChildren();el("folder-conversations").replaceChildren();
    const customers=tree.customers.filter(row=>row.advisor_id===advisor);
    if(!customers.some(row=>row.id===renderFolders.customer))renderFolders.customer=customers[0]?.id;
    customers.forEach(row=>{const button=node("button",row.name);button.type="button";button.className="folder-item";button.setAttribute("aria-pressed",String(row.id===renderFolders.customer));button.addEventListener("click",()=>{renderFolders.customer=row.id;renderFolders();});el("folder-customers").append(button);});
    tree.conversations.filter(row=>row.customer_id===renderFolders.customer).forEach(row=>{const button=node("button",row.title+(row.id===state.current?.id?" · 当前":""));button.type="button";button.className="folder-item";button.addEventListener("click",async()=>{try{await open(advisor,row.id);el("folders").close();}catch(error){el("folder-error").textContent=error.message;}});el("folder-conversations").append(button);});
  }
  async function folders() {
    el("folder-error").textContent="";state.tree=await api("/api/workspace");el("folder-advisor").replaceChildren();
    state.tree.advisors.forEach(row=>{const option=node("option",row.name);option.value=row.id;el("folder-advisor").append(option);});
    el("folder-advisor").value=state.current?.advisor_id||state.tree.advisors[0]?.id;renderFolders.customer=state.current?.customer_id;renderFolders();el("folders").showModal();
  }
  async function create(kind) {
    try{
      if(state.current)await flush();const input=el("new-"+kind);const name=input.value.trim();
      const result=await post("/api/workspace/create",{kind,name,advisor_id:el("folder-advisor").value,customer_id:renderFolders.customer});input.value="";state.tree=result;
      if(kind==="advisor"){
        const option=node("option",name);option.value=result.id;el("folder-advisor").append(option);el("folder-advisor").value=result.id;renderFolders.customer=null;
      }else if(kind==="customer"){
        renderFolders.customer=result.id;const conversation=result.conversations.find(row=>row.customer_id===result.id);await open(el('folder-advisor').value,conversation.id);el('folders').close();
      }else if(kind==='conversation'){await open(el('folder-advisor').value,result.id);el('folders').close();}
      renderFolders();
    }catch(error){el("folder-error").textContent=error.message;}
  }
  function readable(value) {
    const draft=value.draft||{},input=draft.input||{};
    const lines=[input.scenario?"场景："+input.scenario:"",input.client_info?"本次背景："+input.client_info:"",input.conversation?"聊天：\n"+input.conversation:"",input.related_info?"其他资料："+input.related_info:"",input.advisor_instruction?"给助手的要求："+input.advisor_instruction:"",value.preferences?"长期偏好："+value.preferences:"",value.marketing_opt_out?"联系限制：不接收营销消息":"",draft.revision_text?"待提交修改要求："+draft.revision_text:"",draft.context?.review_dirty?"截图复核有未确认修改":""];
    for(const message of draft.context?.messages||[])lines.push(`${{customer:"客户",advisor:"顾问",unknown:"待确认",system:"系统"}[message.role]}${message.include?"":"（未纳入）"}：${message.text}${message.quoted_text?"\n引用："+message.quoted_text:""}`);
    return lines.filter(Boolean).join("\n\n")||"尚未填写";
  }
  async function pending() {
    try{
      el("pending-list").replaceChildren();el("pending-target").textContent="确认归入："+el("workspace-path").textContent;
      const rows=await api("/api/workspace/pending");
      rows.forEach(row=>{const item=node("div");item.className="pending-item";item.append(node("strong",row.title),node("p",`${row.kind==="context"?row.versions+"个截图版本":"生成尝试"} · ${row.created_at} · ${row.id.slice(0,8)}`));const preview=node("button","先查看内容");preview.className="text-button";const body=node("pre");body.hidden=true;body.className="pending-preview";preview.addEventListener("click",async()=>{try{const result=await api("/api/workspace/pending-preview?kind="+row.kind+"&id="+row.id);body.textContent=`关联${result.linked_count}份资料，归档时一起保留。\n\n`+readable({draft:{input:result.record.input,context:{messages:result.record.messages}}})+(result.record.result?.messages?"\n\n历史候选：\n"+result.record.result.messages.join("\n\n"):"")+(result.record.error?"\n失败原因："+result.record.error.message:"");body.hidden=!body.hidden;}catch(error){el("pending-error").textContent=error.message;}});item.append(preview,body);const button=node("button","确认归入当前会话");button.className="secondary";button.addEventListener("click",async()=>{try{await flush();const result=await post("/api/workspace/claim",{kind:row.kind,id:row.id});item.replaceChildren(node("p",result.message+`（${result.linked_count}份关联资料）`));await window.AdvisorEditor.refreshHistory();}catch(error){el("pending-error").textContent=error.message;}});item.append(button);el("pending-list").append(item);});
      if(!rows.length)el("pending-list").append(node("p","没有待整理的旧资料。"));el("pending-error").textContent="";el("pending-records").showModal();
    }catch(error){el("folder-error").textContent=error.message;}
  }
  async function compare() {
    try{const saved=await api("/api/workspace/open");state.server=saved;el("conflict-local").textContent=readable(snapshot());el("conflict-server").textContent=readable({draft:saved.draft,preferences:saved.preferences,marketing_opt_out:!!saved.marketing_opt_out});el("save-conflict").showModal();}catch(error){status(error.message,"failed");}
  }
  async function init(exampleRows=[]) {
    state.examples=exampleRows;
    el('quick-customer-form').addEventListener('submit',event=>{event.preventDefault();quickCustomer();});
    el('start-conversation').addEventListener('click',startConversation);
    el('current-customer').addEventListener('change',event=>chooseCustomer(event.target.value));
    el('current-conversation').addEventListener('change',event=>{const row=state.tree.conversations.find(item=>item.id===event.target.value&&item.customer_id===state.current?.customer_id);if(row)startAction(()=>open(state.current.advisor_id,row.id));});
    el('open-examples').addEventListener('click',()=>examples().catch(error=>status(error.message,'failed')));
    el('close-examples').addEventListener('click',()=>el('examples-dialog').close());
    el('return-to-work').addEventListener('click',()=>startAction(async()=>{const selection=stored('chengxu.selection');if(selection&&!isExample(selection.conversation))await open(selection.advisor,selection.conversation);else await home();}));
    el("open-folders").addEventListener("click",()=>folders().catch(error=>status(error.message,"failed")));
    el("close-folders").addEventListener("click",()=>el("folders").close());el("folder-advisor").addEventListener("change",()=>{renderFolders.customer=null;renderFolders();});
    for(const kind of ["advisor","customer","conversation"])el("create-"+kind).addEventListener("click",()=>create(kind));
    el("open-pending").addEventListener("click",pending);el("close-pending").addEventListener("click",()=>el("pending-records").close());
    el("customer-preferences").addEventListener("input",changed);
    el("marketing-opt-out").addEventListener("change",()=>{if(state.current.marketing_opt_out&&!el("marketing-opt-out").checked){el("marketing-opt-out").checked=true;el("consent-form").hidden=false;return;}policy();changed();});
    el("restore-consent").addEventListener("click",async()=>{if(el("consent-reason").value.trim().length<4)return status("请记录客户明确恢复同意的来源，至少4字。","failed");try{await flush();state.pending={mutation_id:uuid(),revision:state.revision,profile_revision:state.profileRevision,...snapshot(),marketing_opt_out:false,clear_marketing_opt_out:true,consent_reason:el("consent-reason").value.trim()};state.dirty=true;el("marketing-opt-out").checked=false;await flush();state.current.marketing_opt_out=false;el("consent-form").hidden=true;policy();}catch(error){el("marketing-opt-out").checked=true;policy();}});
    el("retry-save").addEventListener("click",()=>flush().catch(()=>{}));el("resolve-save").addEventListener("click",compare);
    el("close-conflict").addEventListener("click",()=>el("save-conflict").close());
    el("keep-server").addEventListener("click",async()=>{try{localStorage.setItem(key()+".conflict-backup",JSON.stringify(snapshot()));}catch(error){return status("无法保留本页副本，请先复制内容。","failed");}localStorage.removeItem(key());state.dirty=false;state.pending=null;state.conflict=false;el("save-conflict").close();await open(state.current.advisor_id,state.current.id);});
    el("keep-local").addEventListener("click",async()=>{state.revision=state.server.revision;state.profileRevision=state.server.profile_revision;state.pending=null;state.conflict=false;state.dirty=true;if(state.server.marketing_opt_out)el("marketing-opt-out").checked=true;el("save-conflict").close();await flush().catch(()=>{});});
    window.addEventListener("contextchanged",changed);document.addEventListener("input",event=>{if(event.target.closest("#context-form,#revision-form"))changed();});document.addEventListener("change",event=>{if(event.target.closest("#context-form,#revision-form"))changed();});
    window.addEventListener("beforeunload",event=>{if(state.dirty||state.pending||window.ContextImporter.busy()){const copied=buffer();if(!copied||window.ContextImporter.busy()){event.preventDefault();event.returnValue="";}}});
    window.addEventListener("pagehide",buffer);document.addEventListener("visibilitychange",()=>{if(document.hidden&&state.dirty){buffer();flush().catch(()=>{});}});
    const tree=await api("/api/workspace");state.tree=tree;const selection=stored('chengxu.selection');
    const valid=tree.conversations.find(row=>row.id===selection?.conversation&&!isExample(row.id)&&tree.customers.some(customer=>customer.id===row.customer_id&&customer.advisor_id===selection.advisor));
    if(valid)await open(selection.advisor,valid.id);else await home();
  }
  window.Workspace={api,url,init,changed,flush,ready:()=>!state.loading&&!!state.current,versions:()=>({checkpoint_revision:state.revision,profile_revision:state.profileRevision}),optedOut:()=>el("marketing-opt-out").checked,active:()=>state.current,starting:()=>state.startBusy,example:()=>state.example};
})();
