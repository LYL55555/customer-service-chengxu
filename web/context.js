(() => {
  const el = id => document.getElementById(id);
  const state = {assets: [], supplements: [], draft: null, imported: null, busy: false, vision: false, reviewDirty: false, autoStitch: true};
  let libraryEdit = null;
  const node = (tag, className, text) => { const item = document.createElement(tag); if (className) item.className = className; if (text !== undefined) item.textContent = text; return item; };
  const notify = text => { el("context-import-status").textContent = text; };
  const changed = () => window.dispatchEvent(new Event("contextchanged"));

  async function api(path, data) {
    const response = await window.Workspace.api(path, data === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
    const result = response;
    if (result.status === "error") throw new Error(result.message || result.error?.message || "资料处理未完成，请重试。");
    return result;
  }

  function invalidate() { state.draft = null; state.imported = null; state.reviewDirty=false; notify("截图有变化，请识别草稿并确认后再生成。"); changed(); }

  function renderAssets() {
    el("auto-stitch").checked=state.autoStitch;el("auto-stitch").disabled=state.busy;
    const list = el("screenshot-list");
    list.replaceChildren();
    state.assets.forEach((asset, index) => {
      const row = node("div", "asset-row");
      const image = node("img"); image.src = window.Workspace.url("/api/assets/" + asset.asset_id + "/content"); image.alt = "原始截图" + (index + 1);
      row.append(image, node("span", "asset-name", `${index + 1}. ${asset.filename}`));
      for (const [label, offset] of [["上移", -1], ["下移", 1]]) {
        const button = node("button", "asset-action", label); button.type = "button"; button.disabled = state.busy || index + offset < 0 || index + offset >= state.assets.length;
        button.addEventListener("click", () => { [state.assets[index],state.assets[index + offset]] = [state.assets[index + offset],state.assets[index]]; invalidate(); renderAssets(); });
        row.append(button);
      }
      const remove = node("button", "asset-action", "移除"); remove.type = "button"; remove.disabled = state.busy;
      remove.addEventListener("click", () => { state.assets.splice(index,1); invalidate(); renderAssets(); }); row.append(remove); list.append(row);
    });
    el("extract-chat").disabled = state.busy || state.assets.length === 0;
    el("review-chat").disabled = state.busy || !state.draft;
    el("save-context").disabled = state.busy || !state.imported;
    el("vision-extract").disabled = state.busy || !state.vision || !state.assets.length;
    el("screenshot-files").disabled = state.busy;
  }

  function renderSupplements() {
    el("supplement-list").replaceChildren();
    state.supplements.forEach((asset,index) => {
      const row = node("div","asset-row"); row.append(node("span","asset-name",asset.filename));
      const remove = node("button","asset-action","移除"); remove.type="button";
      remove.addEventListener("click",()=>{state.supplements.splice(index,1);renderSupplements();changed();});row.append(remove);el("supplement-list").append(row);
    });
  }

  async function refreshContextHistory() {
    window.dispatchEvent(new Event("chatschanged"));
  }

  function readData(file) { return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);}); }

  async function upload(files, kind) {
    const items = Array.from(files);
    if (!items.length || state.busy) return;
    if ((kind === "chat_screenshot" ? state.assets.length : state.supplements.length) + items.length > 8) return notify("每组最多8份资料，请分组处理。");
    state.busy = true; renderAssets(); changed();
    try {
      for (const file of items) {
        if (file.size > 4_000_000) throw new Error("每份资料请控制在4MB以内。");
        const screenshot = kind === "chat_screenshot";
        if (screenshot && !["image/png","image/jpeg"].includes(file.type)) throw new Error("聊天截图目前支持PNG和JPEG。");
        if (!screenshot && !/\.(txt|json)$/i.test(file.name)) throw new Error("补充文件目前支持TXT/JSON，图片资料请先在文字栏摘录并注明来源。");
        let data = await readData(file);
        if (!screenshot) data = data.replace(/^data:[^;]*;/, "data:" + (/\.json$/i.test(file.name) ? "application/json" : "text/plain") + ";");
        const asset = await api("/api/assets",{filename:file.name || "粘贴截图.png",kind,data_url:data});
        (screenshot ? state.assets : state.supplements).push(asset);
      }
      if (kind === "chat_screenshot") invalidate(); else { notify("补充资料已保留，作为业务资料使用，不授权品牌优惠或政策。"); changed(); }
    } catch(error) { notify(error.message); }
    finally { state.busy=false;renderAssets();renderSupplements();changed(); }
  }

  function selectSource(assetId, box) {
    el("source-page").value = assetId;
    el("source-image").src = window.Workspace.url("/api/assets/"+assetId+"/content");
    const rect = el("source-box");
    const value = box || [0,0,0,0];
    for(const [key,number] of Object.entries({x:value[0],y:value[1],width:value[2]-value[0],height:value[3]-value[1]})) rect.setAttribute(key,String(number));
  }

  function renderDraft() {
    const list=el("draft-messages");list.replaceChildren();
    state.draft.messages.forEach((message,index)=>{
      if(message.original_kind===undefined){message.original_kind=message.kind;message.original_text=message.text;}
      const bubble=node("article","draft-message");bubble.dataset.role=message.role;bubble.dataset.messageId=message.id;if(!message.include)bubble.classList.add("excluded");
      const header=node("div","draft-header");header.append(node("span","small",`${index+1} · ${message.origin==="manual"?"人工补录":message.id}`));
      const role=node("select");role.setAttribute("aria-label",`第${index+1}条发送者`);
      for(const [value,label] of [["customer","客户"],["advisor","顾问"],["unknown","待确认"],["system","系统信息"]]){const option=node("option","",label);option.value=value;role.append(option);}role.value=message.role;
      role.addEventListener("change",()=>{message.role=role.value;bubble.dataset.role=message.role;});header.append(role);bubble.append(header);
      if(message.origin==="manual")bubble.append(node("p","manual-badge","人工补录 · 顾问对照原图，非OCR提取"));
      const body=node("p","draft-body",message.text);bubble.append(body);
      const quotePreview=node("blockquote","draft-quote",message.quoted_text);quotePreview.hidden=!message.quoted_text;bubble.append(quotePreview);
      if(message.sources?.length>1){
        const positions=[...new Set(message.sources.map(source=>state.assets.findIndex(asset=>asset.asset_id===source.asset_id)+1))];
        bubble.append(node("p","overlap-badge",`重叠合并 · 在第${positions.join("、")}张原图出现`));
      }
      if(message.warnings?.length)bubble.append(node("p","draft-warning",message.warnings.join("；")));
      const details=node("details","draft-editor");details.append(node("summary","","改文字、引用或类型"));
      if(message.origin==="manual"){
        details.open=true;
        const sourceSelect=node("select");sourceSelect.setAttribute("aria-label",`第${index+1}条补录来源截图`);
        state.assets.forEach((asset,position)=>{const option=node("option","",`${position+1}. ${asset.filename}`);option.value=asset.asset_id;sourceSelect.append(option);});sourceSelect.value=message.source_asset_id;
        sourceSelect.addEventListener("change",()=>{message.source_asset_id=sourceSelect.value;message.sources=[{asset_id:sourceSelect.value,source_type:"manual_transcription",note:message.source_note}];selectSource(sourceSelect.value);});
        const note=node("textarea");note.rows=2;note.maxLength=500;note.value=message.source_note;note.placeholder="例如：顾问报价下一条、原图第三个气泡";note.setAttribute("aria-label",`第${index+1}条原图位置说明`);note.addEventListener("input",()=>{message.source_note=note.value;});
        details.append(node("label","","补录来源截图"),sourceSelect,node("label","","原图位置说明（必填）"),note);
      }
      for(const [field,label] of [["text","正文"],["quoted_text","引用内容"]]){const title=node("label","",label);const input=node("textarea");input.rows=2;input.value=message[field];input.setAttribute("aria-label",`第${index+1}条${label}`);input.disabled=message.kind==="voice"&&field==="text";input.addEventListener("input",()=>{message[field]=input.value;if(field==="text")body.textContent=input.value;else{quotePreview.textContent=input.value;quotePreview.hidden=!input.value;}});details.append(title,input);}
      const kind=node("select");kind.setAttribute("aria-label",`第${index+1}条消息类型`);for(const [value,label]of[["text","文字"],["voice","语音（未转写）"],["image","图片占位"],["unreadable","内容未识别"],["system","系统信息"]]){const option=node("option","",label);option.value=value;kind.append(option);}kind.value=message.kind;kind.disabled=message.original_kind==="voice";kind.addEventListener("change",()=>{message.kind=kind.value;if(kind.value==="voice")message.text="[语音消息，未转写]";else if(message.text==="[语音消息，未转写]")message.text=message.original_text;renderDraft();});details.append(node("label","","消息类型"),kind);bubble.append(details);
      const actions=node("div","draft-actions");
      const includeLabel=node("label","include-label");const include=node("input");include.type="checkbox";include.checked=message.include;include.addEventListener("change",()=>{message.include=include.checked;bubble.classList.toggle("excluded",!message.include);});includeLabel.append(include,document.createTextNode("纳入上下文"));actions.append(includeLabel);
      for(const[label,offset]of[["↑",-1],["↓",1]]){const button=node("button","asset-action",label);button.type="button";button.setAttribute("aria-label",`第${index+1}条${offset<0?"上移":"下移"}`);button.disabled=index+offset<0||index+offset>=state.draft.messages.length;button.addEventListener("click",()=>{[state.draft.messages[index],state.draft.messages[index+offset]]=[state.draft.messages[index+offset],state.draft.messages[index]];state.reviewDirty=true;renderDraft();changed();});actions.append(button);}
      if(message.sources.length>1){
        const sources=node("select");sources.className="source-choice";sources.setAttribute("aria-label",`第${index+1}条消息来源`);
        message.sources.forEach((source,position)=>{const option=node("option","",`对照第${state.assets.findIndex(asset=>asset.asset_id===source.asset_id)+1}张原图`);option.value=String(position);sources.append(option);});
        sources.addEventListener("change",()=>{const source=message.sources[Number(sources.value)];selectSource(source.asset_id,source.bbox);});actions.append(sources);
        const locate=node("button","asset-action","定位");locate.type="button";locate.addEventListener("click",()=>{const source=message.sources[Number(sources.value)];selectSource(source.asset_id,source.bbox);});actions.append(locate);
      }else{
        const source=node("button","asset-action","对照原图");source.type="button";source.addEventListener("click",()=>selectSource(message.sources[0].asset_id,message.sources[0].bbox));actions.append(source);
      }
      bubble.append(actions);
      if(message.origin==="manual"&&!message.manual_entry){const remove=node("button","asset-action","移除这条未保存补录");remove.type="button";remove.addEventListener("click",()=>{state.draft.messages.splice(index,1);state.reviewDirty=true;renderDraft();changed();});bubble.append(remove);}
      list.append(bubble);
    });
  }

  function addManualMessage() {
    if(!state.draft||!state.assets.length)return;
    const assetId=el("source-page").value||state.assets[0].asset_id;
    const message={id:"manual_"+crypto.randomUUID().replaceAll("-",""),role:"unknown",kind:"text",text:"",quoted_text:"",include:true,origin:"manual",source_asset_id:assetId,source_note:"",sources:[{asset_id:assetId,source_type:"manual_transcription"}],warnings:[]};
    state.draft.messages.push(message);state.reviewDirty=true;renderDraft();changed();
    const last=el("draft-messages").lastElementChild;last.scrollIntoView({block:"nearest"});last.querySelector("select").focus();
    el("review-error").textContent="已添加未保存的人工补录。请选发送者、填写正文和原图位置，并调整顺序；保存后才进入上下文。";
  }

  function openReview(messageId) {
    if(!state.draft)return;
    el("source-page").replaceChildren();
    state.assets.forEach((asset,index)=>{const option=node("option","",`${index+1}. ${asset.filename}`);option.value=asset.asset_id;el("source-page").append(option);});
    selectSource(state.assets[0].asset_id);
    el("review-warnings").textContent=(state.draft.warnings||[]).join(" ");el("review-error").textContent=state.imported?"从所选版本继续修改；保存前不会影响已确认内容。":"检查无误后一次确认，无需逐条点击。";el("close-review").textContent=libraryEdit?"取消本次修改":"稍后再看";el("confirm-context").textContent=libraryEdit?"保存为新版本":state.imported?"保存新版本并导入":"确认并导入上下文";renderDraft();el("draft-messages").parentElement.scrollTop=0;el("source-page").parentElement.scrollTop=0;el("context-review").showModal();if(typeof messageId==="string"){const bubble=Array.from(el("draft-messages").children).find(row=>row.dataset.messageId===messageId);bubble?.scrollIntoView({block:"center"});const message=state.draft.messages.find(row=>row.id===messageId);if(message?.sources?.[0])selectSource(message.sources[0].asset_id,message.sources[0].bbox);}changed();
  }

  async function extract(vision=false) {
    if(state.busy)return;state.busy=true;renderAssets();changed();notify(vision?"正在请求视觉补充，结果仍需审核…":"正在本机识别文字并整理气泡，首次会初始化OCR…");
    try {state.draft=await api(vision?"/api/contexts/vision":"/api/contexts/extract",{asset_ids:state.assets.map(item=>item.asset_id),auto_stitch:state.autoStitch});state.imported=null;state.reviewDirty=false;state.assets=state.draft.asset_ids.map(id=>state.assets.find(asset=>asset.asset_id===id));notify("草稿已整理，尚未导入。请对照原图确认归类。");changed();refreshContextHistory();openReview();}
    catch(error){notify(error.message);}finally{state.busy=false;renderAssets();changed();}
  }

  async function restore(value) {
    const token=Symbol();state.restoreToken=token;state.reviewDirty=false;state.autoStitch=true;state.imported=null;state.draft=null;state.assets=[];state.supplements=(value.supplement_ids||[]).map(id=>({asset_id:id,filename:"补充资料"}));state.busy=Boolean(value.context_id);renderAssets();renderSupplements();changed();
    if(!value.context_id)notify("先出草稿，顾问复核并确认后才导入。");
    if(value.context_id){try{const record=await api("/api/contexts/"+value.context_id);if(state.restoreToken!==token)return;if(record.status==="confirmed"){state.imported=record;const original=await api("/api/contexts/"+record.parent_context_id);state.draft={...original,messages:JSON.parse(JSON.stringify(record.messages))};}else if(record.status==="draft"){state.draft=record;}else throw new Error("这条上下文没有成功识别，请重新放入截图。");state.autoStitch=state.draft?.stitching?.mode!=="keep_all";state.assets=await Promise.all(record.asset_ids.map(id=>api("/api/assets/"+id)));notify(state.imported?`已载入确认上下文 · ${record.messages.filter(item=>item.include).length}条`:"这是未确认草稿，请先复核并导入。");}catch(error){notify(error.message);}finally{if(state.restoreToken===token){state.busy=false;renderAssets();}}}
    changed();
  }

  async function editSaved(contextId, done) {
    if(state.busy||libraryEdit)throw new Error("资料正在处理，请稍后打开。");
    libraryEdit={backup:{...state},notice:el("context-import-status").textContent,done,result:null};
    await restore({context_id:contextId});
    if(!state.draft){finishLibraryEdit();return;}
    openReview();
  }

  function finishLibraryEdit() {
    if(!libraryEdit)return;
    const session=libraryEdit;libraryEdit=null;Object.assign(state,session.backup);notify(session.notice);renderAssets();renderSupplements();changed();session.done(session.result);
  }

  function checkpoint() {
    const current=libraryEdit?.backup||state;
    return {asset_ids:current.assets.map(item=>item.asset_id),supplement_ids:current.supplements.map(item=>item.asset_id),draft_id:current.draft?.run_id||null,imported_id:current.imported?.run_id||null,messages:current.draft?.messages||[],auto_stitch:current.autoStitch,review_dirty:current.reviewDirty,review_open:!libraryEdit&&el("context-review").open};
  }
  async function restoreCheckpoint(value={}) {
    await restore({context_id:value.imported_id||value.draft_id,supplement_ids:value.supplement_ids||[]});
    if(value.asset_ids?.length)state.assets=await Promise.all(value.asset_ids.map(id=>api("/api/assets/"+id)));
    state.supplements=await Promise.all((value.supplement_ids||[]).map(id=>api("/api/assets/"+id)));
    if(state.draft&&value.messages?.length)state.draft.messages=JSON.parse(JSON.stringify(value.messages));
    state.autoStitch=value.auto_stitch??state.autoStitch;state.reviewDirty=!!value.review_dirty;renderAssets();renderSupplements();
    if(state.reviewDirty)notify("已恢复尚未确认的修改，请继续复核后导入。");
    else if(state.assets.length&&state.imported&&state.autoStitch!==(state.draft?.stitching?.mode!=="keep_all"))notify("截图整理方式已变，请重新识别；原确认版本仍保留。");
    if(value.review_open&&state.draft)openReview();
  }
  for(const event of ["input","change"])el("context-review").addEventListener(event,event=>{if(!event.target.closest(".draft-message")||event.target.classList.contains("source-choice"))return;state.reviewDirty=true;changed();});
  window.ContextImporter={review:openReview,checkpoint,restoreCheckpoint,busy:()=>state.busy||Boolean(libraryEdit),snapshot:()=>{const current=libraryEdit?.backup||state;return {...(current.imported?{context_id:current.imported.run_id}:{}),...(current.supplements.length?{supplement_ids:current.supplements.map(item=>item.asset_id)}:{}),chat_import:{pending:Boolean(current.reviewDirty)||(current.assets.length>0&&(!current.imported||current.autoStitch!==(current.draft?.stitching?.mode!=="keep_all"))),asset_ids:current.assets.map(item=>item.asset_id),draft_id:current.draft?.run_id||null}};},pending:()=>Boolean(libraryEdit)||state.busy||state.reviewDirty||(state.assets.length>0&&(!state.imported||state.autoStitch!==(state.draft?.stitching?.mode!=="keep_all"))),restore,editSaved};
  el("auto-stitch").addEventListener("change",()=>{state.autoStitch=el("auto-stitch").checked;notify("整理方式已变，请重新识别；当前草稿与原图仍保留。");changed();});
  el("screenshot-files").addEventListener("change",event=>{upload(event.target.files,"chat_screenshot");event.target.value="";});
  el("supplement-files").addEventListener("change",event=>{upload(event.target.files,el("supplement-kind").value);event.target.value="";});
  el("screenshot-drop").addEventListener("dragover",event=>{event.preventDefault();el("screenshot-drop").classList.add("dragging");});
  el("screenshot-drop").addEventListener("dragleave",()=>el("screenshot-drop").classList.remove("dragging"));
  el("screenshot-drop").addEventListener("drop",event=>{event.preventDefault();el("screenshot-drop").classList.remove("dragging");upload(event.dataTransfer.files,"chat_screenshot");});
  el("screenshot-drop").addEventListener("keydown",event=>{if(event.key==="Enter")el("screenshot-files").click();});
  document.addEventListener("paste",event=>{const files=Array.from(event.clipboardData?.files||[]).filter(file=>file.type.startsWith("image/"));if(files.length&&!el("context-review").open&&!el("chat-library").open){event.preventDefault();upload(files,"chat_screenshot");}});
  el("extract-chat").addEventListener("click",()=>extract(false));el("review-chat").addEventListener("click",openReview);el("vision-extract").addEventListener("click",()=>extract(true));
  el("add-manual-message").addEventListener("click",addManualMessage);
  el("close-review").addEventListener("click",()=>{el("context-review").close();changed();});el("source-page").addEventListener("change",event=>selectSource(event.target.value));
  el("context-review").addEventListener("close",finishLibraryEdit);
  el("confirm-context").addEventListener("click",async()=>{el("confirm-context").disabled=true;el("close-review").disabled=true;el("add-manual-message").disabled=true;try{const result=await api("/api/contexts/confirm",{draft_id:state.draft.run_id,base_context_id:state.imported?.run_id||null,messages:state.draft.messages.map(({id,role,kind,text,quoted_text,include,origin,source_asset_id,source_note})=>({id,role,kind,text,quoted_text,include,origin,source_asset_id,source_note}))});state.imported=result;state.reviewDirty=false;state.draft.messages=JSON.parse(JSON.stringify(result.messages));if(libraryEdit)libraryEdit.result=result;notify(`已确认导入 · ${result.messages.filter(item=>item.include).length}条消息 · 可继续补充背景并生成`);el("context-review").close();changed();renderAssets();refreshContextHistory();}catch(error){el("review-error").textContent=error.message;}finally{el("confirm-context").disabled=false;el("close-review").disabled=false;el("add-manual-message").disabled=false;}});
  el("context-review").addEventListener("cancel",event=>{if(el("confirm-context").disabled)event.preventDefault();});
  el("save-context").addEventListener("click",()=>{if(!state.imported)return;const link=node("a");link.href=window.Workspace.url("/api/context-bundle/"+state.imported.run_id);link.download="chengxu-context-"+state.imported.run_id+".zip";document.body.append(link);link.click();link.remove();});
  el("check-vision").addEventListener("click",async()=>{el("check-vision").disabled=true;el("vision-state").textContent="正在发送真实测试图片，核对接口能否看到图片…";try{await api("/api/vision/check",{});state.vision=true;el("vision-state").textContent="测试图片已识别，可主动使用视觉补充；仍需复核。";}catch(error){state.vision=false;el("vision-state").textContent=error.message;}finally{el("check-vision").disabled=false;renderAssets();}});
  renderAssets();
  refreshContextHistory();
})();
