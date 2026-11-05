const byId = id => document.getElementById(id);
const state = {meta: null, valid: null, active: null, chain: [], busy: false, pending: null, failed: null, allowGeneration: true, operation: ""};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toast(text) {
  byId("toast").textContent = text;
  byId("toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { byId("toast").hidden = true; }, 3200);
}

async function request(path, options) {
  return window.Workspace.api(path, options);
}

function inputValue() {
  return {
    scenario: byId("scenario").value,
    client_info: byId("client-info").value.trim(),
    conversation: byId("conversation").value.trim(),
    related_info: byId("related-info").value.trim(),
    advisor_instruction: byId("advisor-instruction").value.trim(),
    product_ids: Array.from(document.querySelectorAll("#products input:checked"), node => node.value),
    ...(window.ContextImporter?.snapshot() || {}),
    ...(Object.keys(window.Understanding.corrections()).length?{understanding_corrections:window.Understanding.corrections()}:{})
  };
}

function stable(value){return JSON.stringify(value, Object.keys(value||{}).sort());}

function revealField(id) {
  const target=byId(id);
  for(let parent=target.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
  target.scrollIntoView({block:'center'});
  target.focus();
}

function replyStatus(dirty, pendingContext) {
  const understanding=window.Understanding.status();
  const summary=understanding.summary;
  const question=summary?.fields.question;
  const outbound=summary?.communication.mode==='outbound';
  const goals={'生日及节日问候':'送上一句生日或节日祝福','商品推荐':'结合已知需要，推荐合适的商品','购后关怀':'关心已购商品的使用情况','沉睡客户唤回':'轻量问候，接续客户关系','活动邀请':'邀请客户了解已确认的门店活动','价格异议':'准备回应客户的价格顾虑'};
  byId('reply-question-label').textContent=outbound?'本次沟通目标 · 主动发起':question?.status==='advisor'?'本次要回答 · 顾问修正':'本次要回答';
  byId('reply-question').textContent=outbound&&question?.status!=='advisor'?goals[byId('scenario').value]:question?.text||(pendingContext?'先确认截图里的聊天':byId('client-info').value.trim()?byId('scenario').value+' · 按本次背景开始':'放入聊天，或补一句背景开始');
  const product=summary?.fields.product;
  const budget=summary?.fields.budget;
  const selected=Array.from(document.querySelectorAll('#products input:checked'),input=>state.meta?.products.find(row=>row.id===input.value)?.name).filter(Boolean);
  const bits=[byId('scenario').value,product?.names.length?product.names.join('、')+(product.status==='inferred'?'（根据前文推定）':''):outbound&&selected.length?'相关商品：'+selected.join('、')+'（顾问资料）':'',budget?.text&&budget.status!=='unknown'?`预算：${budget.text}`:''];
  byId('reply-context').textContent=bits.filter(Boolean).join(' · ');
  const background=(outbound||understanding.loading?byId('client-info').value.trim():summary?.fields.use?.text)||byId('client-info').value.trim();
  byId('reply-background').textContent=background?(outbound?'本次背景：':'背景 / 用途：')+background:'';
  byId('reply-background').hidden=!background;
  const status=byId('reply-status'),resolve=byId('reply-resolve');
  resolve.hidden=true;resolve.onclick=null;status.dataset.state='ready';
  const action=(label,callback)=>{resolve.hidden=false;resolve.textContent=label;resolve.onclick=callback;};
  if(!window.Workspace.active()){status.textContent='先新建或选择客户，再准备聊天。';action('填写客户称呼',()=>byId('quick-customer-name').focus());}
  else if(!window.Workspace.ready())status.textContent='正在恢复客户资料，请稍候…';
  else if(!byId('scenario').value)status.textContent='先选择这次沟通的场景。';
  else if(state.busy)status.textContent=state.operation==='generate'?'正在生成并核对三条回复，请稍候…':'正在读取已保存记录…';
  else if(pendingContext){status.textContent='截图或修改尚未确认，先核对聊天再生成。';status.dataset.state='attention';action('去复核聊天',()=>failureAction('chat'));}
  else if(understanding.loading)status.textContent='正在按本次资料整理理解…';
  else if(summary?.readiness?.state==='needs_advisor'){status.textContent='请顾问先补当前任务需要的原资料，暂不生成客户消息。';status.dataset.state='attention';action(summary.readiness.items[0].label,()=>failureAction(summary.readiness.items[0].action));}
  else if(understanding.error){status.textContent='本次理解尚未整理成功：'+understanding.errorMessage;status.dataset.state='attention';action('重新整理理解',()=>window.Understanding.refresh());}
  else if(summary?.blockers.length){status.textContent=summary.blockers.map(item=>item.message).join(' ');status.dataset.state='attention';action('去确认 / 纠正',()=>{const blocker=summary.blockers[0];if(blocker.field==='contact')revealField('client-info');else if(blocker.field==='corrections')revealField('understanding-notices');else window.Understanding.focus(blocker.field);});}
  else if(byId('save-state').dataset.state==='failed'){status.textContent=byId('save-state').textContent;status.dataset.state='attention';action('处理保存问题',()=>{byId('save-state').scrollIntoView({block:'center'});});}
  else if(!state.allowGeneration){status.textContent=byId('connection').textContent;status.dataset.state='attention';action('检查接口配置',()=>failureAction('connection'));}
  else if(!byId('error').hidden&&(!state.pending?.input||sameInput(inputValue(),state.pending.input))){status.textContent=byId('error-title').textContent+'，具体原因和处理入口见下方。';status.dataset.state='attention';}
  else if(dirty){status.textContent='资料已修改，下方仍是上次回复。重新生成后才能复制。';status.dataset.state='attention';}
  else status.textContent=state.valid?'选一条复制，或单独调整。':'扫一眼理解，无误即可生成。';
  byId('generate').textContent=state.busy&&state.operation==='generate'?'正在生成…':dirty?'按新资料重新生成 ↗':'生成三条回复 ↗';
}

function sameInput(left, right) {
  return ["scenario", "client_info", "conversation", "related_info", "advisor_instruction"].every(key => left[key] === right[key]) && JSON.stringify(left.product_ids) === JSON.stringify(right.product_ids) && (left.context_id||"")===(right.context_id||"") && JSON.stringify(left.supplement_ids||[])===JSON.stringify(right.supplement_ids||[]) && stable(left.understanding_corrections||{})===stable(right.understanding_corrections||{});
}

function deliverable(record){return record?.status==='success'&&record.result?.status==='ready'&&record.result.messages?.length===3&&record.delivery_guard?.allowed!==false;}

function renderAdvisorHelp(pendingContext){
  const understanding=window.Understanding.status();
  const current=understanding.loading?null:understanding.summary?.readiness;
  const oldHelp=state.active?.advisor_help;
  const items=pendingContext?[{message:'已选截图或文字修正尚未确认，请先对照原图复核。',action:'chat',label:'识别 / 复核已选截图'}]:current?.state==='needs_advisor'?current.items:oldHelp&&(!state.active.input||sameInput(inputValue(),state.active.input))?oldHelp.items:[];
  byId('advisor-help').hidden=!items.length;
  byId('advisor-help-items').replaceChildren();byId('advisor-help-actions').replaceChildren();
  for(const item of items){byId('advisor-help-items').append(element('p','',item.message));const button=element('button','secondary',item.label);button.type='button';button.addEventListener('click',()=>failureAction(item.action));byId('advisor-help-actions').append(button);}
  return Boolean(items.length);
}

async function fillInput(value, context) {
  window.Understanding.restore(value.understanding_corrections);
  if(context!==undefined)await window.ContextImporter.restoreCheckpoint(context);else await window.ContextImporter.restore(value);
  byId("scenario").value = value.scenario;
  for (const [field, id] of [["client_info", "client-info"], ["conversation", "conversation"], ["related_info", "related-info"], ["advisor_instruction", "advisor-instruction"]]) byId(id).value = value[field] || "";
  document.querySelectorAll("#products input").forEach(node => { node.checked = (value.product_ids || []).includes(node.value); });
}

function updateControls() {
  const dirty = state.valid && (!sameInput(inputValue(), state.valid.input)||Boolean(state.valid.customer_context&&state.valid.customer_context.profile_revision!==window.Workspace.versions().profile_revision));
  const pendingContext = window.ContextImporter?.pending();
  const needsAdvisor=renderAdvisorHelp(pendingContext);
  byId("generate").disabled = state.busy || pendingContext || needsAdvisor || !window.Workspace.ready() || window.Understanding.blocked() || !state.allowGeneration || !byId('scenario').value;
  byId("generate-mobile").disabled = byId("generate").disabled;
  byId("generate-mobile").textContent = state.busy&&state.operation==='generate'?'正在生成并复核…':'生成三条回复';
  byId("download").disabled = state.busy || !state.active;
  byId("revise").disabled = state.busy || !state.valid || dirty || pendingContext || !state.allowGeneration;
  byId("revision").disabled = state.busy || !state.valid || dirty;
  byId("target").disabled = state.busy || !state.valid || dirty;
  byId("example").disabled = state.busy;
  if(!window.Workspace.active())byId('example').disabled=true;
  for(const id of ['current-customer','current-conversation','start-conversation','quick-create-customer']){
    const item=byId(id);item.disabled=state.busy||Boolean(window.Workspace.starting?.())||(id!=='current-customer'&&id!=='quick-create-customer'&&(!window.Workspace.active()||Boolean(window.Workspace.example?.())));
  }
  byId("history").disabled = state.busy;
  byId("open-chats").disabled = state.busy;
  byId("retry").disabled = state.busy || !state.allowGeneration;
  byId("loading").hidden = !state.busy;
  byId("empty").hidden=Boolean(state.valid||state.failed||state.busy||needsAdvisor);
  byId('result').hidden=!state.valid||needsAdvisor;
  const facts=inputValue();const informed=Boolean(facts.context_id||facts.conversation||facts.client_info||facts.related_info||facts.supplement_ids?.length);
  byId("empty-title").textContent=informed?'核对理解后，生成三条备选':'先了解客户，再找到合适的话';
  byId("empty-help").textContent=informed?'已知信息不必重复填写。只纠正有误或缺少的内容，再按以上理解生成。':'放入截图或写一句背景即可开始；生日问候也可没有聊天记录。';
  byId("context-notice").textContent = dirty ? "资料已修改。请点击生成新的一组，旧记录仍保留。" : "所有案例均为虚构，发送前由顾问确认。";
  document.querySelectorAll(".copy").forEach(button=>{button.disabled=Boolean(dirty)||state.busy||pendingContext||needsAdvisor||!deliverable(state.valid);button.title=dirty?"本次资料已变化，请重新生成后核对":"";});
  byId("previous-result-note").hidden=!dirty;
  const oldFailure=Boolean(state.pending?.input&&!sameInput(inputValue(),state.pending.input));
  const failurePanel=byId('failure-panel');
  failurePanel.hidden=byId('error').hidden;
  byId('failure-summary').textContent=oldFailure?'上次失败记录 · 本次资料已修改':byId('error-title').textContent;
  if(failurePanel.dataset.state!==(oldFailure?'previous':'current')){failurePanel.dataset.state=oldFailure?'previous':'current';failurePanel.open=!oldFailure&&state.failed?.status!=='success';}
  byId("revision-panel").hidden=!state.valid||needsAdvisor;
  byId("result-details").hidden=!state.valid||needsAdvisor;
  byId('revision-panel').querySelector('summary').textContent=byId('revision').value.trim()?'调整回复 · 有未提交草稿':'调整这组回复';
  document.querySelectorAll('.select-target').forEach(button=>{button.disabled=state.busy||Boolean(dirty)||pendingContext;});
  replyStatus(dirty,pendingContext);
  byId("revision-help").textContent = dirty ? "客户背景有变化，请先生成新的一组。" : state.valid ? "修改会保存为新一轮，原结果保留。" : "先生成一组消息，再继续调整。";
  document.querySelectorAll(".quick-actions button").forEach(node => { node.disabled = state.busy || !state.valid || dirty; });
}

async function refreshStatus() {
  try {
    const status = await request("/api/status");
    byId("connection").textContent = status.message + (status.model ? ` · ${status.model}` : "");
    byId("connection").dataset.state = status.state;
    state.allowGeneration=status.generation_allowed!==false;updateControls();
  } catch (error) {
    byId("connection").textContent = "本地服务未连通，请先启动 python3 app.py。";
    byId("connection").dataset.state = "failed";
  }
}

async function refreshHistory() {
  const select = byId("history");
  select.replaceChildren(element("option", "", "当前会话的生成记录"));
  select.firstChild.value = "";
  if(!window.Workspace.active())return;
  const records = await request("/api/runs");
  records.forEach(record => {
    const time = new Date(record.created_at).toLocaleString("zh-CN", {hour12: false});
    const option = element("option", "", `${record.record_kind === "diagnostic-review-only"?"诊断复核（无新生成）":record.delivery_allowed===false?"需核对":record.status === "success" ? "✓" : "!"} ${time} · ${record.scenario || "输入错误"} · ${record.run_id.slice(0, 6)}`);
    option.value = record.run_id;
    select.append(option);
  });
}

async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const area = element("textarea", "", text);
      document.body.append(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      if (!copied) throw new Error();
    }
    toast("消息已复制，请确认后再发送。");
  } catch (error) {
    toast("暂时无法访问剪贴板，请选中文字手动复制。");
  }
}

function render() {
  byId("empty").hidden = Boolean(state.valid);
  byId("result").hidden = !state.valid;
  const turns = byId("turns");
  turns.replaceChildren();
  state.chain.slice(0, -1).forEach((record, index) => {
    const details = element("details", "turn");
    details.append(element("summary", "", `第${index + 1}轮 · ${record.advisor_request || "首次生成"} · 查看此前三条`));
    record.result.messages.forEach((text, i) => details.append(element("p", "old-message", `${i + 1}. ${text}`)));
    details.append(element("span", "small", `记录 ${record.run_id}`));
    turns.append(details);
  });
  if (state.valid) {
    const record = state.valid;
    const result = record.result;
    if (record.advisor_request) turns.append(element("div", "turn", `本轮生成采用的修改要求：${record.advisor_request}`));
    const labels = {comparing: "仍在比较", declined: "已明确不考虑", unclear: "给客户考虑空间", other: "回应当前场景"};
    byId("result-state").textContent = result.status === "needs_info" ? "信息待补 · 以下用于核实" : labels[result.client_state];
    byId("result-id").textContent = `第${state.chain.length}轮 · ${record.run_id.slice(0, 8)}`+(record.generation_replay?` · 原生成${record.generation_replay.source_app_version} / 本次只补复核`:'');
    const notes = [record.quality_review?.parsed_output?.current_need ? "当前需求："+record.quality_review.parsed_output.current_need : "", record.state_comparison?.local_hint_differs ? "本地文字线索与语义判断不同，请核对客户原话和当前关注的商品。" : "", result.advisor_note, ...result.missing_information.map(item => "待核实：" + item)].filter(Boolean);
    byId("advisor-note").textContent = notes.join("\n");
    byId("advisor-note").hidden = notes.length === 0;
    byId("review-detail").textContent=JSON.stringify(record.quality_review?.parsed_output||{},null,2);
    const cards = byId("cards");
    cards.replaceChildren();
    result.messages.forEach((text, index) => {
      const card = element("article", "message-card");
      card.dataset.index = String(index);
      const heading = element("div", "card-heading");
      heading.append(element("span", "", `备选 ${index + 1}`), element("span", "", `${text.length} 字符`));
      const actions = element("div", "card-actions");
      const select = element("button", "select-target", "仅修改这条");
      select.type = "button";
      select.addEventListener("click", () => { byId("target").value = String(index); window.Workspace.changed(); updateTarget(); revealField('revision'); });
      const copy = element("button", "copy", "复制消息");
      copy.type = "button";
      copy.addEventListener("click", () => {
        if(!deliverable(record)||window.ContextImporter.pending()||window.Understanding.status().summary?.readiness?.state==='needs_advisor'||!sameInput(inputValue(),record.input))return toast('当前资料或这组历史回复尚不能发送，请先处理顾问待办。');
        if(window.Workspace.optedOut()&&(!record.customer_context?.marketing_opt_out||record.customer_context.profile_revision!==window.Workspace.versions().profile_revision))return toast("联系限制已变化。这是历史回复，请按当前客户主动问题重新生成并核对。");
        copyText(text);
      });
      actions.append(select, copy);
      card.append(heading, element("p", "message-text", text), actions);
      cards.append(card);
    });
  }
  updateTarget();
  updateControls();
}

function updateTarget() {
  document.querySelectorAll(".message-card").forEach(node => node.classList.toggle("selected", node.dataset.index === byId("target").value));
}

function failureAction(action){
  if(action==='understanding')window.Understanding.focus();
  else if(action==='chat'){if(window.ContextImporter.checkpoint().draft_id)window.ContextImporter.review();else if(window.ContextImporter.pending())revealField('extract-chat');else revealField('conversation');}
  else if(action==='background')revealField('client-info');
  else if(action==='conversation')revealField('conversation');
  else if(action==='materials')revealField('related-info');
  else if(action==='profile'){document.querySelector('.customer-profile').open=true;byId('marketing-opt-out').scrollIntoView({block:'center'});}
  else if(action==='save')byId('save-state').scrollIntoView({block:'center'});
  else if(action==='connection'){refreshStatus();byId('connection').scrollIntoView({block:'center'});}
}

function showFailure(record, payload) {
  state.failed=record;state.pending=payload;byId('error').hidden=false;
  byId('failure-panel').open=true;
  const guidance=record.ui_guidance||record.failure_guidance||(record.delivery_guard?.allowed===false?{title:'这组历史回复不可发送',reason:record.delivery_guard.reason,advice:'旧原文仅作证据保留。请在工具中处理资料缺口，不向客户转嫁。',actions:(record.delivery_guard.items||[]).map(item=>({action:item.action,label:item.label})),retry_allowed:false}:null);
  byId('error-title').textContent=guidance?.title||'这次没有生成可用结果';
  byId('error-message').textContent=[guidance?.simulated?'本地开发故障模拟，不是真实模型失败。':'',guidance?.reason||record.error?.message,guidance?.advice,guidance?.historical?`这是${record.app_version}版本当时的失败结果；当前规则不重新改写这份记录。`:'',state.valid?'下方仍保留上一组有效结果。':''].filter(Boolean).join('\n');
  byId('error-id').textContent=`失败记录 ${record.run_id.slice(0,8)}`;
  byId('retry').hidden=!(guidance?.retry_allowed??record.error?.retryable)||!state.allowGeneration;
  byId('error-issues').replaceChildren();byId('error-actions').replaceChildren();byId('error-original').replaceChildren();
  for(const issue of guidance?.issues||[]){const line=element('p','error-issue',`${issue.title}：${issue.message}${issue.evidence?'\n被标出的内容：“'+issue.evidence+'”':''}${issue.expected?'\n当时检查依据：'+issue.expected.toLocaleString('zh-CN')+'元':''}`);byId('error-issues').append(line);}
  for(const action of guidance?.actions||[]){const button=element('button','secondary',action.label);button.type='button';button.addEventListener('click',()=>failureAction(action.action));byId('error-actions').append(button);}
  if(record.input){for(const [key,label] of [['client_info','当时背景'],['conversation','当时补充聊天'],['related_info','当时其他资料']])if(record.input[key])byId('error-original').append(element('p','',label+'：'+record.input[key]));}
  const rejected=record.parsed_output?.messages||[];rejected.forEach((text,index)=>byId('error-original').append(element('p','',`未采用候选${index+1}：${text}`)));
  byId('error-details').open=false;
}

async function submit(payload) {
  if (state.busy) return;
  state.busy = true;
  state.operation = 'generate';
  byId("error").hidden = true;
  updateControls();
  try {
    await window.Understanding.refresh();
    if(window.Understanding.blocked()){const error=new Error('本次理解还有冲突或尚未整理完成，请先核对标出的资料。');error.code='understanding_pending';throw error;}
    payload={...payload,input:inputValue()};
    await window.Workspace.flush();
    const record = await request("/api/generate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({...payload,...window.Workspace.versions()})});
    state.active = record;
    if (record.status === "success") {
      state.chain = payload.parent_run_id ? [...state.chain, record] : [record];
      state.valid = deliverable(record)?record:null;
      state.failed = null;
      state.pending = null;
      byId("revision").value = "";
      byId("target").value = "";
      byId('revision-panel').open=false;
      byId('result-details').open=false;
      render();window.Workspace.changed();
      byId("result").scrollIntoView({behavior: "smooth", block: "nearest"});
    } else {
      showFailure(record, payload);
    }
    await Promise.all([refreshHistory(), refreshStatus()]);
  } catch (error) {
    state.failed=null;state.pending={...payload,input:payload.input||inputValue()};
    byId("error").hidden = false;
    byId('failure-panel').open=true;
    const contentError=error.code==='understanding_pending';
    const savingError=['workspace_conflict','save_failed'].includes(error.code)||byId('save-state').dataset.state==='failed';
    byId("error-title").textContent=contentError?'本次理解需要确认':savingError?'先完成保存或处理版本冲突':'未收到本次请求的最终确认';
    byId("error-message").textContent=error.message+(state.valid?' 上一组有效结果仍保留。':'')+(contentError?' 请核对本次理解中标出的资料，确认后再生成。':savingError?' 本次资料尚未确认保存，请处理顶部保存状态后再生成。':' 客户资料无需重填。若服务中断，先从历史记录检查是否已经完成。');
    byId("error-issues").replaceChildren();byId("error-actions").replaceChildren();byId("error-original").replaceChildren();byId("error-details").open=false;
    const action=element('button','secondary',contentError?'核对本次理解':savingError?'处理保存状态':'查看连接与保存状态');action.type='button';action.addEventListener('click',()=>failureAction(contentError?'understanding':savingError?'save':'connection'));byId('error-actions').append(action);
    byId("error-id").textContent = "本次尚未收到最终确认";
    byId("retry").hidden = true;
  } finally {
    state.busy = false;
    updateControls();
  }
}

async function loadRecord(id, restoreInput=false) {
  state.busy = true;
  state.operation = 'load';
  updateControls();
  try {
    const record = await request("/api/runs/" + id);
    let current = deliverable(record) ? record : record.parent_run_id ? await request("/api/runs/" + record.parent_run_id) : null;
    const chain = [];
    while (current && chain.length < 21) {
      if(!deliverable(current))break;
      chain.unshift(current);
      current = current.parent_run_id ? await request("/api/runs/" + current.parent_run_id) : null;
    }
    state.chain = chain;
    state.valid = chain.at(-1) || null;
    state.active = record;
    state.failed = null;
    state.pending = null;
    if (restoreInput && record.input) await fillInput(record.input);
    byId("error").hidden = true;
    byId("revision").value = "";
    byId("target").value = "";
    byId("example").value = "";
    if (!deliverable(record)) {
      const payload = {input: record.input, parent_run_id: record.parent_run_id || null, advisor_request: record.advisor_request || "", target_index: record.target_index ?? null};
      const display=record.error?record:{...record,error:{code:'advisor_input',message:record.delivery_guard?.reason||'这组历史回复需要重新核对，已停止复制。'},ui_guidance:{title:'这组历史回复不可发送',reason:record.delivery_guard?.reason,advice:'原文保留在下方证据中；不会重新开放为客户消息。',actions:(record.delivery_guard?.items||[]).map(item=>({action:item.action,label:item.label})),issues:[],retry_allowed:false}};
      showFailure(display, payload);
    }
    render();
  } catch (error) {
    toast(error.message);
  } finally {
    state.busy = false;
    updateControls();
  }
}

async function init() {
  byId('open-background').addEventListener('click',()=>revealField('client-info'));
  byId('open-chat-materials').addEventListener('click',()=>{byId('materials-panel').open=true;byId('chat-materials').open=true;revealField('screenshot-drop');});
  byId("context-form").addEventListener("submit", event => { event.preventDefault(); submit({input: inputValue()}); });
  byId("context-form").addEventListener("input", updateControls);
  window.addEventListener("contextchanged", updateControls);
  window.addEventListener('savestatuschanged',updateControls);
  byId('revision-form').addEventListener('input',updateControls);
  window.addEventListener("usechat", async event => {
    if(state.busy)return toast("请等待当前生成完成。");
    await window.ContextImporter.restore({...inputValue(),context_id:event.detail.context_id});
    render();window.Workspace.changed();toast("已用于当前会话，原背景、备注和上一组结果仍保留。");
  });
  byId("context-form").addEventListener("change", updateControls);
  byId("revision-form").addEventListener("submit", event => {
    event.preventDefault();
    if (!state.valid || !sameInput(inputValue(), state.valid.input)) return toast("请先生成一组消息，再继续修改。");
    if (!byId("revision").value.trim()) return toast("请先写一句修改要求。");
    submit({input: inputValue(), parent_run_id: state.valid.run_id, advisor_request: byId("revision").value.trim(), target_index: byId("target").value === "" ? null : Number(byId("target").value)});
  });
  byId("target").addEventListener("change", updateTarget);
  byId("refresh").addEventListener("click", refreshStatus);
  byId("history").addEventListener("change", event => { if (event.target.value) loadRecord(event.target.value); });
  document.querySelectorAll("[data-request]").forEach(button => button.addEventListener("click", () => { byId("revision").value = button.dataset.request; window.Workspace.changed(); byId("revision").focus(); }));
  byId("retry").addEventListener("click", () => {
    if (!state.failed || !state.pending) return;
    if (!sameInput(inputValue(), state.pending.input)) return toast("资料已变化，请点击生成新的一组。");
    submit({...state.pending, retry_of: state.failed.run_id});
  });
  byId("download").addEventListener("click", () => {
    if (!state.active) return;
    const link = element("a");
    const hasContext=Boolean(state.active.input?.context_id);
    link.href = window.Workspace.url((hasContext?"/api/bundle/":"/api/export/") + state.active.run_id);
    link.download = `chengxu-${state.active.run_id}.${hasContext?"zip":"json"}`;
    document.body.append(link);
    link.click();
    link.remove();
  });
  byId("example").addEventListener("change", async event => {
    const item = state.meta.cases.find(row => row.id === event.target.value);
    if (!item) return;
    await fillInput(item.input);
    state.valid = null;
    state.active = null;
    state.chain = [];
    state.pending = null;
    state.failed = null;
    byId("error").hidden = true;
    byId("revision").value = "";
    render();window.Workspace.changed();
  });
  try {
    state.meta = await request("/api/meta");
    window.Understanding.setMeta(state.meta);
    byId("version").textContent = `规则 ${state.meta.brand_version}`;
    state.meta.scenarios.forEach(name => { const option = element("option", "", name); option.value = name; byId("scenario").append(option); });
    state.meta.cases.forEach(row => { const option = element("option", "", row.label); option.value = row.id; byId("example").append(option); });
    state.meta.products.forEach(product => {
      const label = element("label", "product");
      const input = element("input");
      input.type = "checkbox";
      input.value = product.id;
      const info = element("span", "product-info");
      const name = element("span", "", product.name);
      name.append(element("small", "", {P01: "通勤带资料 · 能放A4", P02: "轻便外出 · 肩背或斜挎", P03: "小件收纳 · 四个卡位"}[product.id]));
      info.append(name, element("span", "product-price", "¥" + product.price.toLocaleString("en-US")));
      label.append(input, info);
      byId("products").append(label);
    });
    await window.Workspace.init(state.meta.saved_examples||[]);
    await Promise.all([refreshStatus(), refreshHistory()]);
    render();await window.Understanding.refresh();
  } catch (error) {
    byId("connection").textContent = "页面资料加载失败，请检查本地服务后刷新。";
    toast(error.message);
    byId("generate").disabled = true;
  }
}

window.AdvisorEditor={
  snapshot:()=>({input:{...inputValue(),client_info:byId("client-info").value,conversation:byId("conversation").value,related_info:byId("related-info").value,advisor_instruction:byId("advisor-instruction").value},context:window.ContextImporter.checkpoint(),revision_text:byId("revision").value,target:byId("target").value}),
  restore:async(draft,row)=>{
    state.valid=null;state.active=null;state.chain=[];state.pending=null;state.failed=null;byId("error").hidden=true;
    await fillInput(draft.input||{scenario:''},draft.context?.imported_id||draft.context?.draft_id||!draft.input?.context_id?draft.context||{}:{...(draft.context||{}),imported_id:draft.input.context_id});
    byId('revision-panel').open=false;byId('result-details').open=false;byId('understanding-details').open=false;
    if(row.last_valid_run_id)await loadRecord(row.last_valid_run_id);
    if(row.last_run_id&&row.last_run_id!==row.last_valid_run_id){const failed=await request("/api/runs/"+row.last_run_id);state.active=failed;showFailure(failed,{input:failed.input,parent_run_id:failed.parent_run_id||null,advisor_request:failed.advisor_request||"",target_index:failed.target_index??null});}
    byId("revision").value=draft.revision_text||"";byId("target").value=draft.target||"";byId("example").value="";render();await refreshHistory();window.dispatchEvent(new Event("workspaceopened"));
  },input:inputValue,busy:()=>state.busy,updateControls,refreshHistory,reveal:revealField
};
init();
