(() => {
  const el=id=>document.getElementById(id);
  const state={summary:null,corrections:{},loading:false,error:false,token:0,products:[]};
  const node=(tag,className,text)=>{const item=document.createElement(tag);if(className)item.className=className;if(text!==undefined)item.textContent=text;return item;};
  const active=()=>window.Workspace?.active()?.id;
  const labels={stated:'来自原话',inferred:'根据前文推定',unknown:'未明确',uncertain:'待核对',conflict:'有冲突',advisor:'顾问修正',mixed:'原话 / 顾问补充'};
  function editorValues(){return {product:el('understanding-product').value,question:el('understanding-question').value,budget:el('understanding-budget').value,use:el('understanding-use').value};}
  function populateEditor(){
    el('understanding-product').value=Object.hasOwn(state.corrections,'product_ids')?(state.corrections.product_ids[0]||'unknown'):'';
    for(const field of ['question','budget','use'])el('understanding-'+field).value=state.corrections[field]||'';
  }
  function render(){
    const summary=state.summary;
    el('understanding-status').textContent=state.loading?'正在按确认资料整理…':state.error?(state.errorMessage||'本次理解尚未整理成功，请检查本地服务后重新整理'):summary?'按已确认原话整理，可直接核对或纠正':'确认聊天后自动整理；无聊天的场景也可直接补背景。';
    el('understanding-fields').replaceChildren();el('understanding-notices').replaceChildren();
    if(!summary)return;
    for(const [field,title] of [['question','这次要回答'],['product','当前商品'],['budget','本次预算'],['use','已知用途']]){
      const info=summary.fields[field];const row=node('div','understanding-row');row.append(node('dt','',title));
      const content=node('dd');const text=field==='product'?(info.names.join('、')||'尚不确定，不自动认定为旧勾选商品'):info.text;
      content.append(node('span','understanding-value',text),node('small','understanding-tag',labels[info.status]));
      if(info.evidence?.length){
        const detail=node('details','understanding-evidence');detail.append(node('summary','','查看依据'));
        for(const source of info.evidence){
          const number=/^m(\d+)$/.exec(source.message_id||'');const name=source.field==='chat'?(number?`第${number[1]}条`:'聊天')+' · '+({customer:'客户',advisor:'顾问'}[source.role]||'待确认'):source.field==='customer_preferences'?'客户已保存偏好':source.field==='client_info'?'顾问补充背景':'顾问修正';
          detail.append(node('p','',name+'：'+source.text));
          if(source.field!=='understanding_corrections'){
            const button=node('button','text-button','回到这条资料');button.type='button';button.addEventListener('click',()=>{
              if(source.field==='chat'&&window.ContextImporter.snapshot().context_id)window.ContextImporter.review(source.message_id);
              else window.AdvisorEditor.reveal(source.field==='customer_preferences'?'customer-preferences':source.field==='client_info'?'client-info':'conversation');
            });detail.append(button);
          }
        }
        content.append(detail);
      }
      row.append(content);el('understanding-fields').append(row);
    }
    for(const notice of summary.notices)el('understanding-notices').append(node('p','field-note',notice));
    for(const blocker of summary.blockers){const line=node('div','understanding-blocker');line.append(node('span','',blocker.message));const button=node('button','text-button',blocker.field==='corrections'?'已核对，沿用修正':blocker.field==='contact'?'补一句背景确认':'纠正这里');button.type='button';button.addEventListener('click',()=>{if(blocker.field==='corrections'){state.corrections.source_hash=summary.source_hash;window.Workspace.changed();refresh();}else if(blocker.field==='contact')window.AdvisorEditor.reveal('client-info');else focus(blocker.field);});line.append(button);el('understanding-notices').append(line);}
    el('understanding-question').placeholder=summary.fields.question.text;el('understanding-budget').placeholder='例如：20,000元；或写“未明确”';el('understanding-use').placeholder=summary.fields.use.text;
  }
  async function refresh(){
    clearTimeout(refresh.timer);
    if(!window.Workspace?.ready()||!window.AdvisorEditor)return state.summary;
    const input=window.AdvisorEditor.input();const current=active();const token=++state.token;
    if(!input.scenario){state.summary=null;state.loading=false;state.error=false;render();window.AdvisorEditor.updateControls();return null;}
    if(window.ContextImporter.pending()){
      state.loading=false;state.error=false;state.summary=null;render();el('understanding-status').textContent='先确认截图或未完成的修改，再整理本次理解。';window.AdvisorEditor.updateControls();return null;
    }
    if(!input.context_id&&!input.conversation&&!input.client_info&&!input.related_info&&!input.supplement_ids?.length){state.summary=null;state.error=false;state.loading=false;render();window.AdvisorEditor.updateControls();return null;}
    state.loading=true;state.error=false;render();window.AdvisorEditor.updateControls();
    try{
      const result=await window.Workspace.api('/api/understanding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input})});
      if(token!==state.token||current!==active())return null;
      state.summary=result;state.error=false;
    }catch(error){if(token===state.token&&current===active()){state.error=true;state.errorMessage=error.message;}}
    finally{if(token===state.token&&current===active()){state.loading=false;render();window.AdvisorEditor.updateControls();}}
    return state.summary;
  }
  function schedule(){if(!window.Workspace?.ready())return;state.loading=true;window.AdvisorEditor.updateControls();clearTimeout(refresh.timer);refresh.timer=setTimeout(refresh,250);}
  function focus(field='budget') {el('understanding-details').open=true;el('understanding-editor').open=true;window.AdvisorEditor.reveal('understanding-'+(field==='product'?'product':['question','budget','use'].includes(field)?field:'budget'));}
  function edited(){
    const values=editorValues();const corrections={source_hash:state.summary?.source_hash||state.corrections.source_hash};
    if(values.product)corrections.product_ids=values.product==='unknown'?[]:[values.product];
    for(const field of ['question','budget','use'])if(values[field].trim())corrections[field]=values[field].trim();
    state.corrections=Object.keys(corrections).length>1?corrections:{};window.Workspace.changed();schedule();
  }
  for(const field of ['product','question','budget','use'])el('understanding-'+field).addEventListener(field==='product'?'change':'input',edited);
  el('understanding-refresh').addEventListener('click',refresh);el('understanding-edit').addEventListener('click',()=>focus('product'));
  el('understanding-reset').addEventListener('click',()=>{state.corrections={};populateEditor();window.Workspace.changed();refresh();});
  window.addEventListener('contextchanged',schedule);window.addEventListener('workspaceopened',schedule);
  document.addEventListener('input',event=>{if(event.target.closest('#context-form'))schedule();});document.addEventListener('change',event=>{if(event.target.closest('#context-form'))schedule();});
  window.Understanding={refresh,focus,status:()=>({summary:state.summary,loading:state.loading,error:state.error,errorMessage:state.errorMessage}),corrections:()=>JSON.parse(JSON.stringify(state.corrections)),blocked:()=>state.loading||state.error||Boolean(state.summary?.blockers.length),restore:value=>{++state.token;state.summary=null;state.error=false;state.loading=false;state.corrections=value||{};el('understanding-editor').open=false;populateEditor();render();},setMeta:meta=>{state.products=meta.products;for(const product of meta.products){const option=node('option','',product.name);option.value=product.id;el('understanding-product').append(option);}}};
})();
