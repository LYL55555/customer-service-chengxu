(() => {
  const el=id=>document.getElementById(id);
  const state={rows:[],chat:null,record:null,token:0};
  const node=(tag,className,text)=>{const item=document.createElement(tag);if(className)item.className=className;if(text!==undefined)item.textContent=text;return item;};
  const date=value=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"时间未记录";
  async function api(path,data){return window.Workspace.api(path,data===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});}
  const error=message=>{el("chat-library-error").textContent=message;};
  function resetDetail(){state.chat=null;state.record=null;el("chat-content").hidden=true;el("chat-empty").hidden=false;}

  function renderList(){
    el("chat-count").textContent=`${state.rows.length}份聊天 · 包含历史消息搜索`;
    el("chat-list").replaceChildren();
    state.rows.forEach(row=>{
      const button=node("button","chat-list-item");button.type="button";button.dataset.chatId=row.chat_id;button.setAttribute("aria-pressed",String(state.chat?.chat_id===row.chat_id));
      button.append(node("strong","",row.title),node("span","",`${row.message_count}条 · ${row.version_count?row.version_count+"个确认版本":"待复核"}`),node("small","",date(row.updated_at)));
      button.addEventListener("click",()=>openChat(row.chat_id));el("chat-list").append(button);
    });
    if(!state.rows.length)el("chat-list").append(node("p","library-empty",el("chat-search").value?"没有匹配的聊天。试试历史消息里的词。":"还没有聊天记录。放入截图并识别后，草稿会自动保存在这里。"));
  }

  async function refresh(){
    const token=++refresh.token;
    try{const rows=await api("/api/chats?q="+encodeURIComponent(el("chat-search").value.trim()));if(token!==refresh.token)return;state.rows=rows;renderList();}catch(problem){error(problem.message);}
  }
  refresh.token=0;

  async function openVersion(contextId){
    const token=++state.token;state.record=null;el("edit-saved-chat").disabled=true;el("use-saved-chat").disabled=true;error("正在读取版本…");
    try{
      const record=await api("/api/contexts/"+contextId);if(token!==state.token)return;state.record=record;
      const version=state.chat.versions.find(row=>row.context_id===contextId);const base=state.chat.versions.find(row=>row.context_id===record.previous_context_id);
      el("chat-version-info").textContent=`${date(record.created_at)} · ${record.messages.length}条消息 · ${record.status==="confirmed"?"已确认":"原始识别草稿，尚未确认"}${base?` · 基于${base.revision?"确认版 v"+base.revision:"原始草稿"}修改`:""}${record.changes?.length?` · ${record.changes.length}条有修改`:""} · ${contextId.slice(0,8)}`;
      el("export-saved-chat").href=window.Workspace.url("/api/context-bundle/"+contextId);el("export-saved-chat").download="chengxu-context-"+contextId+".zip";
      el("saved-messages").replaceChildren();
      record.messages.forEach((message,index)=>{
        const bubble=node("article","draft-message"+(message.include?"":" excluded"));bubble.dataset.role=message.role;
        bubble.append(node("span","small",`${index+1} · ${{customer:"客户",advisor:"顾问",unknown:"待确认",system:"系统信息"}[message.role]} · ${message.origin==="manual"?"人工补录":message.id}`),node("p","draft-body",message.text));
        if(message.origin==="manual")bubble.append(node("p","manual-badge",`人工补录 · 第${record.asset_ids.indexOf(message.source_asset_id)+1}张原图 · ${message.source_note}`));
        if(message.quoted_text)bubble.append(node("blockquote","draft-quote",message.quoted_text));
        if(!message.include)bubble.append(node("span","small","未纳入上下文"));
        el("saved-messages").append(bubble);
      });
      el("edit-saved-chat").disabled=false;el("use-saved-chat").disabled=record.status!=="confirmed";error(version?.revision===0?"原始草稿需复核、保存为确认版本后，才能用于生成。":"仅在本地查看历史，尚未切换当前生成资料。");
    }catch(problem){if(token===state.token)error(problem.message);}
  }

  async function openChat(identity,contextId){
    try{
      const chat=await api("/api/chats/"+identity);state.chat=chat;el("chat-title").value=chat.title;el("chat-version").replaceChildren();
      [...chat.versions].reverse().forEach(version=>{const option=node("option","",`${version.revision?"确认版 v"+version.revision:"原始OCR草稿"} · ${date(version.created_at)}${version.context_id===chat.latest_context_id?" · 最新":""}`);option.value=version.context_id;el("chat-version").append(option);});
      el("chat-version").value=contextId||chat.latest_context_id;el("chat-content").hidden=false;el("chat-empty").hidden=true;renderList();await openVersion(el("chat-version").value);
    }catch(problem){error(problem.message);}
  }

  el("open-chats").addEventListener("click",async()=>{error("");el("chat-library").showModal();await refresh();if(state.chat)await openChat(state.chat.chat_id,state.record?.run_id);else if(state.rows.length)await openChat(state.rows[0].chat_id);else resetDetail();});
  el("close-chats").addEventListener("click",()=>el("chat-library").close());
  el("chat-search").addEventListener("input",()=>{clearTimeout(refresh.timer);refresh.timer=setTimeout(refresh,180);});
  el("chat-version").addEventListener("change",event=>openVersion(event.target.value));
  el("rename-chat").addEventListener("click",async()=>{if(!state.chat)return;el("rename-chat").disabled=true;try{state.chat=await api("/api/chats/rename",{chat_id:state.chat.chat_id,title:el("chat-title").value});await refresh();error("聊天名称已保存在本机。");}catch(problem){error(problem.message);}finally{el("rename-chat").disabled=false;}});
  el("edit-saved-chat").addEventListener("click",async()=>{
    if(!state.record)return;const identity=state.chat.chat_id,contextId=state.record.run_id;el("chat-library").close();
    try{await window.ContextImporter.editSaved(contextId,async result=>{el("chat-library").showModal();await refresh();await openChat(identity,result?.run_id||contextId);if(result)error("已保存为新版本；旧版本和原图保留。点击“用于生成”才会切换工作台。");});}catch(problem){el("chat-library").showModal();error(problem.message);}
  });
  el("use-saved-chat").addEventListener("click",()=>{if(state.record?.status!=="confirmed")return;el("chat-library").close();window.dispatchEvent(new CustomEvent("usechat",{detail:{context_id:state.record.run_id}}));});
  window.addEventListener("workspaceopened",()=>{state.token++;resetDetail();state.rows=[];});
  window.addEventListener("chatschanged",()=>{if(el("chat-library").open)refresh();});
})();
