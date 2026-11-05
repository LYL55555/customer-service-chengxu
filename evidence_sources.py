import re

VERSION = 'evidence-sources-0.7.0'


def claim_domains(text):
    domains=set()
    if re.search(r'售价|标价|现价|折扣|打折|[一二三四五六七八九\d]折|议价|优惠|\d{3,6}元|\d{1,3},\d{3}',text):domains.add('pricing')
    if re.search(r'牛皮|棉布|材质|肩背|斜挎|肩带|拉链|卡位|零钱袋|A4|自重|空包|\d\s*(?:克|g)|\d\s*[×xX]\s*\d',text,re.I):domains.add('product')
    if re.search(r'售后|退货|换货|退换|维修|保养|修复|免费保修|酒精|软布|晾干|烘干|热风|(?:7|七)(?:个)?(?:自然)?[天日]',text):domains.add('service')
    if re.search(r'活动|场次|入场|席位|同行|地址|地点|周[一二三四五六日天]|\d{1,2}:\d{2}|(?:路|街|道|巷)\d+号',text):domains.add('event')
    if re.search(r'库存|现货|有货|预留|预约|登记|提交|查询|查过|查到|退款|核实|确认',text):domains.add('action')
    if re.search(r'您(?:说|提到|问|的|平时|预算)|客户|预算|电脑连壳|手机连壳',text):domains.add('context')
    return domains


def source_domains(row):
    identity=row.get('id','');kind=row.get('kind','')
    if identity.startswith('product.'):
        field=identity.split('.')[-1]
        return {'pricing'} if field=='price' else {'action'} if field=='stock' else {'product'}
    if kind=='brand_policy':
        return {'policy.1':{'product'},'policy.2':{'product'},'policy.3':{'product','pricing','action'},'policy.4':{'pricing','action','context'},'policy.5':{'service','action'},'policy.6':{'context','action'},'policy.7':{'task','context'}}.get(identity,{'context'})
    if kind=='derived_calendar':return {'event'}
    if kind=='device_spec':return {'customer_item','context'}
    if kind=='derived_fit':return {'product','customer_item','context'}
    if kind=='derived_load':return {'product','context'}
    if row.get('authority') in ('context_not_authorization','quoted_not_authorization'):return {'context'}
    if kind in ('business_material','event','order','aftersales_record','aftersales_assessment','customer_record','background','advisor_background','customer_profile'):
        domains={'context','task','event','action'}
        if any(record.get('valid') and record.get('facts') for record in row.get('aftersales_records',[])):domains.add('service')
        return domains
    if kind in ('task','contact_limit'):return {'task','context'}
    return {'writing'} if kind=='writing_rule' else {'context'}


def build(value, prepared, brand, writing):
    sources = []
    def add(identity, kind, text, authority):
        if text:sources.append(dict(id=identity, kind=kind, text=text, authority=authority))
    parts = re.split(r'(?m)^(## \d+\.[^\n]+)\n', brand['rules'])
    for i in range(1,len(parts),2):
        n = re.search(r'\d+',parts[i])[0]
        add('policy.'+n,'brand_policy',parts[i]+'\n'+parts[i+1],'brand')
    for product in brand['products']:
        for field,fact in product['facts'].items():
            add('product.'+product['id']+'.'+field,'product_'+fact['status'],fact['text'],'brand')
    add('writing.rules','writing_rule',writing,'writing_only')
    add('task.scenario','task',value['scenario'],'task_only')
    add('task.advisor_instruction','task',value.get('advisor_instruction',''),'task_only')
    add('profile.salutation','customer_profile',prepared.get('customer_context',{}).get('customer_name',''),'context_only')
    add('background.client_info','advisor_background',value.get('client_info',''),'context_only')
    add('materials.related_info','business_material',value.get('related_info',''),'business_facts_not_brand_override')
    for i,row in enumerate(prepared.get('answer_context',{}).get('calendar',[])):
        add('computed.calendar.'+str(i+1),'derived_calendar',row['date']+'是'+row['weekday'],'computed_from_materials')
        sources[-1].update(parent_source_id=row['source_id'],method=row['method'])
    for row in prepared.get('device_reference',{}).get('records',[]):
        add(row['id'],'device_spec',row['model']+'；仅裸机：\n'+row['source_quote'],'official_device_specs_not_brand_policy')
        sources[-1].update(source_url=row['source_url'],verified_on=row['verified_on'],source_quote_sha256=row['source_quote_sha256'])
    for row in prepared.get('device_reference',{}).get('fit_judgments',[]):
        add(row['id'],'derived_fit',row['device_model']+'与'+row['product_id']+'：'+row['customer_expression']+'；'+row['case_inference'],'bounded_everyday_inference_not_internal_measurement')
        sources[-1].update(parent_source_ids=row['source_ids'],method=row['method'])
    for row in prepared.get('load_reference',{}).get('records',[]):
        add(row['id'],'derived_load',row['text'],row['authority'])
        sources[-1].update(parent_source_ids=row['parent_source_ids'],method=row['method'],product_id=row['product_id'],subtotal_g=row['subtotal_g'],excluded_components=row['excluded_components'],volume_source_quote=row['volume_source_quote'])
    profile = prepared.get('customer_context',{})
    add('profile.preferences','customer_profile',profile.get('preferences',''),'context_only')
    if profile.get('marketing_opt_out'):add('profile.contact','contact_limit','marketing_opt_out=true','contact_policy')
    for row in prepared.get('messages',[]):
        if row.get('kind')=='text':
            add('chat.'+row['id'],row['role']+'_message',row['text'],'context_not_authorization')
            sources[-1].update({key:row[key] for key in ('sent_at','message_time','timestamp','timestamp_text','timestamp_source') if row.get(key)})
        add('quote.'+row['id'],'quoted_message',row.get('quoted_text',''),'quoted_not_authorization')
    for i,item in enumerate(prepared.get('supplements',[])):
        metadata=item.get('metadata',{})
        add('supplement.'+str(i+1),item.get('kind') or metadata.get('kind','business_material'),item.get('text',''),'business_facts_not_brand_override')
        if item.get('text'):sources[-1].update(asset_id=metadata.get('asset_id'),filename=metadata.get('filename'),sha256=metadata.get('sha256'))
    index=dict(version=VERSION,sources=sources)
    from aftersales_evidence import bind
    bind(value,prepared,brand['products'],index)
    return index


def check(ref, index):
    row = index.get(ref.get('source_id')) if isinstance(ref,dict) else None
    return bool(row and row['text'])


def candidate_spans(messages):
    spans=[]
    for i,text in enumerate(messages):
        spans.append(dict(id=f'reply_{i+1}.full',candidate_index=i,start=0,end=len(text),text=text))
        for j,m in enumerate(re.finditer(r'[^。！？!?\n]+[。！？!?]?',text)):
            spans.append(dict(id=f'reply_{i+1}.s{j+1}',candidate_index=i,start=m.start(),end=m.end(),text=m[0]))
    return spans


def resolve(review,prepared):
    import copy
    value=copy.deepcopy(review)
    sources={r['id']:r for r in prepared['evidence_sources']['sources']}
    spans={r['id']:r for r in prepared['candidate_spans']}
    for row in value['candidate_checks'].values():
        for edit in row.get('editing',[]):edit['original_sentence']=spans.get(edit['candidate_span_id'],{}).get('text','')
        for key,field in [('answered','answer_quote'),('source_checks','claim_quote')]:
            for ref in row[key]:
                ref[field]=spans.get(ref['candidate_span_id'],{}).get('text','')
                ref['resolved_source']=sources.get(ref['source_id'])
    for issue in value['issues']:
        issue['evidence']=spans.get(issue['evidence_span_id'],{}).get('text','')
        issue['resolved_sources']=[sources.get(r['source_id']) for r in issue['source_refs']]
    return value
