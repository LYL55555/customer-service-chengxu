import hashlib
import json
import re
from decimal import Decimal

VERSION='aftersales-evidence-1.1.0'
CASE=r'(?:售后(?:单|记录)|维修单|评估单)(?:号)?\s*(?:为|是)?[：:\s]*([A-Za-z0-9][A-Za-z0-9_-]{2,})'


def case_ids(text):return re.findall(CASE,text,re.I)


def facts(text):
    from quality import money_value
    from statement_scope import modality,owner
    rows=[]
    patterns=[('fee',r'(\d+(?:[,，]\d{3})*(?:\.\d+)?|[零〇一二两三四五六七八九十百千万]+)\s*元'),('duration',r'(\d+(?:\.\d+)?|[一二两三四五六七八九十百]+)\s*(?:个)?(工作日|自然日|天)'),('repairable',r'可以维修|可维修|可以修|可修|能修'),('started',r'(?:尚未|还没(?:有)?|没有|未)(?:开始维修|开始修|开修)|(?:已经|已|正在)(?:开始维修|开始修|开修|维修)|维修已经开始'),('agreed',r'(?:尚未|还没(?:有)?|没有|未)(?:同意维修|确认维修|同意|确认)|(?:您|客户)(?:已经|已)(?:同意维修|确认维修)'),('completed',r'(?:已经|已)(?:修好|修复完成|完成维修)'),('received',r'(?:已经|已)(?:收件|收到)|(?:包|商品)(?:已经|已)到(?:了)?门店'),('testing',r'(?:正在|在|处于)?(?:售后)?检测中|(?:正在|仍在)(?:进行)?检测')]
    for field,pattern in patterns:
        for match in re.finditer(pattern,text):
            if field=='received' and re.fullmatch(r'(?:已经|已)收到',match[0]):
                before=text[max(0,match.start()-18):match.start()];after=text[match.end():match.end()+12]
                if re.search(r'凭证|订单|照片|消息|资料|单据',before+after) or not re.search(r'包|商品|实物|皮具',before+after):continue
            if field=='started' and re.match(r'(?:评估|检测|咨询)',text[match.end():]):continue
            if field=='agreed' and re.match(r'(?:报价|费用|时间|方案)',text[match.end():]):continue
            if field in ('fee','duration') and modality(text,match.start(),match.end())!='asserted':continue
            if field=='fee':
                if owner(text,match.start(),match.end(),'money') in ('budget','competitor','customer_reference','customer_item'):continue
                raw=match[1].replace(',','').replace('，','');value=format(Decimal(raw if re.fullmatch(r'\d+(?:\.\d+)?',raw) else money_value(raw)).normalize(),'f');unit='CNY'
            elif field=='duration':
                before=re.split(r'[，,。；;\n]',text[:match.start()])[-1][-24:];after=text[match.end():match.end()+12]
                timing=list(re.finditer(r'维修|修理|修复|修好|工期|周期|预计|耗时|需(?:要)?',before))
                other=list(re.finditer(r'购买|买了|买后|退换|退货|换货|超过|超出|超了',before))
                if other and (not timing or other[-1].start()>timing[-1].start()):continue
                if not timing and not re.match(r'(?:内)?(?:修好|完成维修|完成修复)',after):continue
                raw=match[1];value=format(Decimal(raw if re.fullmatch(r'\d+(?:\.\d+)?',raw) else money_value(raw)).normalize(),'f');unit='workday' if match[2]=='工作日' else 'day'
            else:
                if modality(text,match.start(),match.end()) in ('question','unresolved','requirement'):continue
                value=not bool(re.match(r'尚未|还没|没有|未',match[0]));unit=None
            rows.append(dict(field=field,value=value,unit=unit,start=match.start(),end=match.end(),quote=match[0],estimated=bool(re.search(r'预计|估计|大约|大概|约',text[max(0,match.start()-10):match.start()])),guaranteed=bool(re.search(r'保证|一定|确保|固定|最迟',text[max(0,match.start()-12):match.end()+8]))))
    return rows


def bind(value,prepared,products,index=None):
    from quality import product_mentions
    from business_evidence import order_ids
    index=index or prepared.get('evidence_sources',{})
    if value is None:
        by_id={r['id']:r for r in index.get('sources',[])}
        value=dict(related_info=by_id.get('materials.related_info',{}).get('text',''),product_ids=[])
    profile=prepared.get('customer_context',{});customer=profile.get('customer_id');active=prepared.get('communication',{}).get('latest_text','')
    wanted=set(case_ids(active))
    if profile.get('aftersales_case_id'):wanted.add(str(profile['aftersales_case_id']))
    wanted_orders=set(order_ids(active))
    if profile.get('current_order_id'):wanted_orders.add(str(profile['current_order_id']))
    selected=set(value.get('product_ids',[]));mentioned={p['id'] for _,p in product_mentions(active,products)}
    focus=mentioned or selected
    records=[]
    for source in index.get('sources',[]):
        source.pop('aftersales_records',None)
        if source['kind'] not in ('business_material','order','aftersales_record','aftersales_assessment'):continue
        if source.get('authority') in ('context_not_authorization','quoted_not_authorization'):continue
        metadata={};selected_source=True
        if source['id']=='materials.related_info':
            selected_source=source['text']==value.get('related_info','')
        elif source['id'].startswith('supplement.'):
            position=int(source['id'].split('.')[-1])-1;items=prepared.get('supplements',[])
            if position>=len(items):selected_source=False
            else:
                item=items[position];metadata=item.get('metadata',{})
                selected_source=item.get('include',True) and item.get('selected',True) and item.get('text')==source['text']
        else:selected_source=False
        matches=list(re.finditer(CASE,source['text'],re.I))
        for position,match in enumerate(matches):
            end=matches[position+1].start() if position+1<len(matches) else len(source['text'])
            start=0 if position==0 else match.start();text=source['text'][start:end];reasons=[]
            if not selected_source:reasons.append('source_not_selected_or_changed')
            if metadata.get('customer_id') and metadata['customer_id']!=customer:reasons.append('different_customer')
            if re.search(r'其他客户|另一位?客户|别的客户|不属于本客户|不是本客户|其他订单|另一(?:笔|个|张)?(?:订单|售后单)',text):reasons.append('foreign_scope')
            if re.search(r'客户(?:说|称|希望|要求|表示)|顾客(?:说|称|要求)|客户原话|转述客户|引用客户',text):reasons.append('customer_report_not_assessment')
            if re.search(r'(?:属于|客户|顾客|户名)[：:]?[^，。；\n]{0,12}(?:女士|先生)',text) and not re.search(r'属于本客户|本客户的|当前客户',text) and not metadata.get('customer_id'):reasons.append('unbound_named_customer')
            ids={p['id'] for _,p in product_mentions(text,products)}
            if len(ids)!=1:reasons.append('unresolved_product')
            product=next(iter(ids)) if len(ids)==1 else None
            if focus and product not in focus:reasons.append('different_product')
            if metadata.get('product_id') and metadata['product_id']!=product:reasons.append('different_product_metadata')
            identity=match[1]
            linked_orders=set(order_ids(text))
            if wanted and identity not in wanted:reasons.append('different_case')
            if wanted_orders and not wanted_orders.intersection(linked_orders|{identity}):reasons.append('different_order')
            if metadata.get('aftersales_case_id') and str(metadata['aftersales_case_id'])!=identity:reasons.append('different_case_metadata')
            if metadata.get('order_id') and str(metadata['order_id']) not in linked_orders|{identity}:reasons.append('different_order_metadata')
            if not re.search(r'评估|检测|核实|确认|收件|收到了',text):reasons.append('no_assessment_or_progress')
            rows=facts(text);values={r['field']:r for r in rows}
            if not values:reasons.append('no_case_facts')
            record=dict(source_id=source['id'],case_id=identity,order_ids=sorted(linked_orders),customer_id=customer or 'current-task-customer',product_id=product,binding='explicit_current_customer' if re.search(r'属于本客户|本客户的|当前客户',text) else 'matching_metadata' if metadata.get('customer_id') else 'selected_current_conversation_record',source_start=start,source_end=end,source_quote=text,facts=values,valid=not reasons,reasons=reasons)
            records.append(record);source.setdefault('aftersales_records',[]).append(record)
    eligible=[r for r in records if r['valid']]
    if len({r['case_id'] for r in eligible})>1 and not wanted:
        for record in eligible:record['valid']=False;record['reasons'].append('ambiguous_current_case')
    scope=dict(version=VERSION,customer_id=customer,focus_product_ids=sorted(focus),current_case_ids=sorted(wanted),records=records)
    prepared['aftersales_scope']=scope
    from evidence_sources import source_domains
    for source in index.get('sources',[]):source['domains']=sorted(source_domains(source))
    scope['binding_hash']=hashlib.sha256(json.dumps(scope,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return scope


def claims(text,products,focus):
    from quality import product_mentions
    active=bool(re.search(r'维修|修理|修好|修复|开修|开了修|费用|评估|收件|检测',text))
    if not active:return []
    named={p['id'] for _,p in product_mentions(text,products)};ids=named or set(focus)
    current=next(iter(ids)) if len(ids)==1 else None
    result=[]
    for part in re.finditer(r'[^，,。；;！？!?\n]+[！？!?]?',text):
        local={p['id'] for _,p in product_mentions(part[0],products)}
        if len(local)==1:current=next(iter(local))
        for fact in facts(part[0]):
            fact.update(start=part.start()+fact['start'],end=part.start()+fact['end'],product_ids=sorted(local) if len(local)>1 else [current] if current else [],case_ids=case_ids(text))
            result.append(fact)
    return result


def audit(messages,prepared,products,value=None,checks=None):
    scope=bind(value,prepared,products) if value is not None or not prepared.get('aftersales_scope') else prepared['aftersales_scope']
    records=[r for r in scope['records'] if r['valid']];issues=[]
    for index,text in enumerate(messages):
        for claim in claims(text,products,scope['focus_product_ids']):
            witnesses=[]
            for record in records:
                if len(claim['product_ids'])!=1:continue
                if claim['product_ids'] and record['product_id'] not in claim['product_ids']:continue
                if claim['case_ids'] and record['case_id'] not in claim['case_ids']:continue
                fact=record['facts'].get(claim['field'])
                if fact and fact['value']==claim['value'] and fact['unit']==claim['unit'] and not (claim['guaranteed'] and fact['estimated']):witnesses.append(record)
            detail=dict(candidate_index=index,evidence=claim['quote'],field=claim['field'],value=claim['value'],unit=claim['unit'])
            if not witnesses:
                issues.append(dict(code='unsupported_aftersales_case_fact',message='这项维修费用、预计周期或处理状态没有当前客户、商品及售后单的对应评估支持；客户转述和通用政策不能证明本单结论。',**detail));continue
            contrary=[r for r in records if r['case_id'] in {w['case_id'] for w in witnesses} and r['product_id'] in {w['product_id'] for w in witnesses} and claim['field'] in r['facts'] and (r['facts'][claim['field']]['value'],r['facts'][claim['field']]['unit'])!=(claim['value'],claim['unit'])]
            if contrary:
                issues.append(dict(code='conflicting_aftersales_case_fact',message='同一售后单的有效评估记录存在冲突，不能选择其中一个值当作已核实。',**detail));continue
            if checks is not None:
                refs=checks[f'reply_{index+1}']['source_checks'];spans={s['id']:s for s in prepared.get('candidate_spans',[])}
                cited=any(ref['source_id'] in {w['source_id'] for w in witnesses} and ref['candidate_span_id'] in spans and spans[ref['candidate_span_id']]['start']<=claim['start'] and spans[ref['candidate_span_id']]['end']>=claim['end'] for ref in refs)
                if not cited:issues.append(dict(code='missing_aftersales_case_reference',message='具体评估值和状态须引用这张当前售后单；通用售后政策不能替代本单评估引用。',**detail))
    return issues


def supports_record_read(action,text,prepared,products):
    if not re.search(r'查过|查到|查询过|核对过|核实过',action):return False
    if re.search(r'刚刚|刚才|刚(?:向|与|跟)|刚查|刚问|致电|打(?:过)?电话|联系(?:了|过)|刷新|实时|最新查询|向门店|跟门店|向售后',text):return False
    if re.search(r'库存|现货|有货|预留|报名|预约|退款',text):return False
    if not re.search(r'售后|收件|收到|检测|维修|工期|费用|完成时间',text):return False
    from quality import product_mentions
    named={p['id'] for _,p in product_mentions(text,products)}
    return any(r['valid'] and (not named or r['product_id'] in named) for r in prepared.get('aftersales_scope',{}).get('records',[]))
