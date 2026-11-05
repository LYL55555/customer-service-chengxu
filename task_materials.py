import copy
import re

VERSION = 'task-materials-2.5.0'
FACETS = {
    'price': r'多少钱|价格|售价|总价|合计|一共|贵|价差|比.{0,10}(?:预想|预期|想的|预计).{0,5}(?:高|多)|超(?:出|过).{0,6}(?:预期|预计)',
    'discount': r'折扣|打折|优惠|便宜(?:点|一点|些)|便宜吗|折吗|能少',
    'carry': r'斜挎|肩背|背法|怎么背',
    'weight': r'重不重|多重|太沉|会沉|重量|自重|多少克|负重|费劲|吃力|背.{0,5}累|走路|步行|走.{0,5}(?:分钟|刻钟)',
    'capacity': r'能装|能放|装下|放下|容量|放得下|装得下|银行卡|卡位|A4|水杯|手机|钥匙|文件夹',
    'coin': r'硬币|零钱|零钱袋',
    'material': r'材质|什么皮|牛皮|皮质|皮面|纹理',
    'dimensions': r'尺寸|长宽|多大|多宽|多高|多厚',
    'colors': r'颜色|配色|黑色|墨黑|米白|暖棕',
    'waterproof': r'防水|淋雨|进水',
    'craft': r'手工|工艺|产地|哪里做|皮革等级',
}
EVENT = {
    'event_experience': r'演示|体验|展示',
    'event_time': r'20\d{2}[-年]|\d{1,2}:\d{2}|周[一二三四五六日天]|时段|全程|短暂',
    'event_location': r'地址|地点|精品店|[路街道巷场]\d+号',
    'event_registration': r'同行|朋友|登记|报名|参加人|门店确认',
    'event_followup': r'之后|后续|以后|下一场|下次|再办',
}


def fragments(text):
    return [(m.start(),m.end(),m[0]) for m in re.finditer(r'[^。！？!?\n]+[。！？!?]?',text)]


def build(value, prepared, brand, revisions=None):
    from understanding import build_understanding
    from quality import product_mentions
    understanding=build_understanding(value,prepared,brand['products'])
    fields=understanding['fields'];communication=prepared.get('communication',{})
    current=communication.get('latest_text','')
    question=fields['question']['text'] if fields['question']['status'] in ('stated','advisor') and not communication.get('historical_chat') else ''
    instructions=value.get('advisor_instruction','')
    revisions=revisions or []
    task_text='\n'.join([question or current,instructions]+[row['text'] for row in revisions])
    use='\n'.join([fields['use']['text'],prepared.get('customer_context',{}).get('preferences','')])
    focus=fields['product']['ids'][:]
    facets={key for key,pattern in FACETS.items() if re.search(pattern,task_text,re.I)}
    event=value['scenario']=='活动邀请' or bool(re.search(r'活动|场次|小聚',task_text))
    from answer_context import followup_requested
    followup=event and followup_requested(task_text)
    cleaner=bool(re.search(r'清洁剂|去污剂',task_text))
    wet=bool(re.search(r'(?:沾|溅|淋)(?:到|了)?水|淋雨|淋湿|湿了',task_text) and re.search(r'怎么办|怎么|处理|护理',task_text))
    zipper=bool(re.search(r'拉链.{0,12}(?:卡|坏|不顺)|(?:卡|坏).{0,6}拉链',task_text))
    service=bool(re.search(r'售后|退换|退货|换货|维修|修理|修好|进度|处理到|单号|拉链',task_text)) or cleaner
    praise=bool(re.search(r'顺手|好用|舒服|满意|好找|刚好放',current)) and not bool(re.search(r'[？?]|吗|怎么|能否|是否|但是|不过|就是|卡顿|坏|不顺|不舒服',current))
    recommendation=not(event or service or praise) and bool(re.search(r'推荐|哪款|哪一款|帮我看看|选个|选一|买个|通勤包|上班用的|礼物',task_text) or value['scenario']=='商品推荐' and not current) and not bool(focus and facets and re.search(r'多少钱|能放|装得下|装下|放下|能装|斜挎|卡位',question or current))
    judgment=not(event or service or praise) and bool(re.search(r'合适|适合|怎么选|值不值|值得|太沉|会不会.{0,4}沉',task_text))
    if praise:mode='positive_feedback';facets=set()
    elif cleaner:mode='cleaner';facets=set()
    elif wet:mode='wet_care';facets=set()
    elif zipper:mode='zipper_fault';facets=set()
    elif event:mode='event_followup' if followup else 'event_registration' if re.search(r'报名|报一下名|登记|帮我约|给我约',task_text) else 'event_query' if current else 'event_invitation';facets=set()
    elif service:mode='aftersales';facets=set()
    elif recommendation:mode='recommendation'
    elif judgment:mode='usage_judgment'
    elif current:mode='fact_query'
    else:mode='relationship'
    from statement_scope import pause_evidence
    fresh_question=bool(re.search(r'[？?]|怎么|多少|能否|能不能|是否|想了解|想问|帮我看看|给我看看',current))
    if not fresh_question and pause_evidence(value,prepared):mode='deferred';facets=set()
    elif not fresh_question and prepared.get('state_check',{}).get('state')=='declined':mode='declined';facets=set()
    if mode=='recommendation':
        needs_a4=bool(re.search(r'A4|带文件|带资料',use,re.I))
        gift=bool(re.search(r'礼物|送人|送给|送同事',task_text+'\n'+use))
        cards=bool(re.search(r'卡夹|银行卡|卡片',task_text+'\n'+use))
        ids=['P01'] if needs_a4 else ['P03'] if gift or cards else ['P02'] if re.search(r'轻装|少带|手机|钥匙|小包',use+'\n'+task_text) else [p['id'] for p in brand['products'] if p['id'] in (value.get('product_ids') or ['P01','P02'])]
        budget=fields['budget'].get('amount') if fields['budget']['status'] in ('stated','advisor') else None
        focus=[p['id'] for p in brand['products'] if p['id'] in ids and (budget is None or p['facts']['price']['value']<=budget)]
        facets.update(['price','capacity'])
        if re.search(r'背|肩|斜挎|轻装|手机|钥匙',task_text+'\n'+use):facets.add('carry')
        if re.search(r'颜色|黑|棕|白|花|低调|标识|简洁',task_text+'\n'+use):facets.add('design')
    if mode=='usage_judgment':
        facets.add('capacity')
    if mode in ('recommendation','usage_judgment'):
        preference_text=task_text+'\n'+use+'\n'+value.get('client_info','')
        if re.search(r'低调|小标识|小logo|大标识|大logo|简洁',preference_text,re.I):facets.add('design')
        if mode=='recommendation'and re.search(FACETS['colors'],preference_text):facets.add('colors')
    if mode=='fact_query' and 'capacity' in facets and not re.search(r'能装|能放|装下|放下|容量|放得下|装得下|卡位',task_text) and facets.intersection({'price','carry'}):
        facets.discard('capacity')
    if mode=='fact_query' and not facets and focus:
        facets={'material'} if re.search(r'质感|手感|摸|皮',task_text) else {'price','capacity'} if re.search(r'了解|介绍|看看|看下',task_text) else set()
    audit=[];facts=[];next_steps=[];required=[]
    sources={row['id']:row for row in prepared.get('evidence_sources',{}).get('sources',[])}
    def take(identity,text,reason,status='known',scope=None,transform=None,original=None,start=None,end=None,audience='customer'):
        if not text:return
        source=sources.get(identity,{})
        audience='internal_validation'if status=='unknown'else audience
        facts.append(dict(source_id=identity,kind=source.get('kind','product_fact'),authority=source.get('authority','brand'),status=status,text=text,audience=audience,**({'scope':scope} if scope else {})))
        audit.append(dict(source_id=identity,reason=reason,selected_text=text,source_text=original if original is not None else source.get('text',''),start=start,end=end,transformation=transform or 'exact_source_text',audience=audience))
    def product_field(identity,field,reason):
        product=next((p for p in brand['products'] if p['id']==identity),None)
        if not product or field not in product['facts']:return
        fact=product['facts'][field];text=fact['text'];transform=None
        if field=='capacity':
            if identity=='P03':text=text.split('；')[0];transform='card_capacity_clause'
            else:
                wanted=[token for pattern,token in [(r'A4','A4纸质资料'),(r'水杯|水瓶|一瓶水','500 mL水杯'),(r'手机|iphone','普通手机'),(r'钥匙','钥匙'),(r'口红','口红'),(r'伞','折叠伞')] if re.search(pattern,task_text+'\n'+use,re.I) and (token in text or token=='A4纸质资料' and 'A4' in text)]
                if wanted:text='可放'+ '、'.join(wanted);transform='select_supported_items_matching_current_use'
        if field=='a4_fit' and fact['status']=='known':text='可放A4纸质资料' if fact['value'] else '放不下完整A4资料';transform='single_A4_proposition'
        if field=='colors' and fact['status']=='known':
            color_context=task_text+'\n'+use if mode=='recommendation' else task_text
            wanted=[color for color in fact['value'] if color in color_context or color=='墨黑' and '黑色' in color_context]
            if wanted:text='、'.join(wanted);transform='requested_catalog_color_only'
        if field=='limitations':
            text='；'.join(part for part in fact['text'].split('；') if re.search(r'防水',part));transform='waterproof_clause_only'
        take('product.'+identity+'.'+field,text,reason,fact['status'],dict(product_id=identity,product_name=product['name'],field=field),transform)
    dependencies={
        'price':['price'],'discount':[],'carry':['carry_modes','strap_adjustable'],'weight':['empty_weight_g','loaded_weight_g','loaded_comfort'],
        'capacity':['capacity'],'coin':['coin_pocket'],'material':['material'],'dimensions':['dimensions_cm'],
        'colors':['colors'],'waterproof':['limitations'],'craft':['craft'],'design':[],
    }
    if mode not in ('positive_feedback','relationship','deferred','declined'):
        for identity in focus:
            for facet in sorted(facets):
                for field in dependencies.get(facet,[]):product_field(identity,field,'回答当前'+facet)
    if mode in ('recommendation','usage_judgment') and re.search(r'A4',use+'\n'+task_text,re.I):
        for identity in focus:product_field(identity,'a4_fit','当前用途包含A4')
    if 'weight' in facets:
        for identity in focus:
            product=next(p for p in brand['products'] if p['id']==identity)
            if '不称为超轻' in product['facts']['limitations']['text']:
                take('product.'+identity+'.limitations','不称为超轻','只供内部检查重量分类',scope=dict(product_id=identity,product_name=product['name'],field='limitations'),transform='weight_limit_clause_only',audience='internal_validation')
        for row in prepared.get('load_reference',{}).get('records',[]):
            take(row['id'],row['text'],'根据当前明确水量和品牌空重计算两项小计',scope=dict(product_id=row['product_id'],subtotal_g=row['subtotal_g'],parent_source_ids=row['parent_source_ids']),transform='program_component_sum',original=row['text'])
    if mode=='fact_query' and re.search(r'A4',task_text,re.I):
        for identity in focus:product_field(identity,'a4_fit','客户直接问A4容量')
    if 'design' in facets:
        policy=sources.get('policy.2',{}).get('text','')
        m=re.search(r'三款均使用小尺寸压印品牌标识',policy)
        if m:take('policy.2',m[0],'当前低调/小标识偏好',start=m.start(),end=m.end())
    if 'discount' in facets:
        policy=sources.get('policy.4',{}).get('text','')
        for phrase in ['三款均无折扣','顾问无议价权限']:
            m=re.search(phrase,policy)
            if m:take('policy.4',m[0],'客户明确询问优惠',start=m.start(),end=m.end(),audience='internal_validation'if phrase=='顾问无议价权限'else'customer')
    if mode=='cleaner':
        take('policy.5','成分未知的清洁剂先不要使用，也不要先在角落试用。','回答清洁剂能否使用',transform='negative_care_permission_from_policy',original=sources.get('policy.5',{}).get('text',''))
        next_steps.append(dict(owner='customer_then_advisor',action='请提供瓶身标签或成分信息，顾问交售后判断处理方式。',reason='当前清洁剂成分未知，需查看后处理',source_ids=['policy.5']))
        required=['能否用这瓶清洁剂','安全的下一步处理']
    elif mode=='wet_care':
        source=sources.get('policy.5',{}).get('text','')
        m=re.search(r'沾水后用干燥软布轻轻吸干，在通风处自然晾干',source)
        if m:take('policy.5',m[0],'当前确为沾水护理问题',start=m.start(),end=m.end())
        required=['回应当前沾水情况及已有护理步骤']
    elif mode=='zipper_fault':
        next_steps.append(dict(owner='customer_then_advisor',action='首次反馈且未有处理记录时，请拍拉链卡顿的拉合视频，顾问转交售后确认处理方式。',reason='查看实际问题，不作故障诊断',source_ids=['policy.5']))
        required=['承接拉链卡顿的处理']
    elif mode=='positive_feedback':required=['接住客户本次正面使用反馈']
    elif mode=='deferred':required=['尊重当前暂缓及行动限制，简短承接']
    elif mode=='declined':required=['确认当前拒绝范围并停止相应推荐']
    elif mode=='event_followup':required=['后续类似活动的安排；已有确认就转述，否则承接向门店核实后回复']
    elif mode=='event_registration':required=['承接本次参加人数与登记需求']
    elif event:required=['本次活动可以看到或体验什么'] if mode=='event_query' else ['活动体验价值、已确认时间地点与自然邀请']
    else:
        labels={'price':'价格或当前合计','discount':'客户问的优惠','carry':'是否支持所问背法','weight':'自重与当前负重顾虑','capacity':'当前物品容量','coin':'是否有独立零钱袋','material':'材质','dimensions':'商品外尺寸','colors':'所问颜色','waterproof':'防水边界','craft':'所问工艺','design':'已有外观偏好'}
        required=[labels[f] for f in sorted(facets) if f in labels]
        if mode in ('recommendation','usage_judgment'):required.insert(0,'结合已有用途和约束给出选择判断')
        if not required:required=['完成顾问本次关系沟通任务']
    stock=bool(re.search(r'库存|有货|现货|留一个|留一只|留一下|预留|留货',task_text)) and mode not in ('event_registration','positive_feedback')
    if stock:
        next_steps.append(dict(owner='advisor',action='核实当前所问商品颜色的库存'+('及能否按客户到店计划预留' if re.search(r'留|预留',task_text) else '')+'，确认后回复。',reason='当前选用资料尚需核对实时库存或预留状态',source_ids=['policy.4']))
        required=['承接客户所问库存'+('和能否预留' if re.search(r'留|预留',task_text) else '')]
    from business_evidence import sources as business_sources
    rows=business_sources(value,prepared)
    event_aspects=[]
    if event:
        if mode=='event_followup':event_aspects=['event_followup']
        elif mode=='event_registration':event_aspects=['event_registration']
        else:
            event_aspects=['event_experience']
            if mode=='event_invitation' or re.search(r'什么时候|几点|哪天|周几|时间|半小时|一会|全程',task_text):event_aspects.append('event_time')
            if mode=='event_invitation' or re.search(r'在哪|地址|地点|哪里',task_text):event_aspects.append('event_location')
            if re.search(r'朋友|同行|报名|登记|带.{0,3}人',task_text):event_aspects.append('event_registration')
    for row in rows:
        if row['kind'] in ('customer_message','customer_profile'):continue
        for start,end,part in fragments(row['text']):
            why=[]
            if event and any(re.search(EVENT[facet],part) for facet in event_aspects):why.append('本次活动问题：'+','.join(event_aspects))
            if mode in ('aftersales','zipper_fault') and re.search(r'售后|维修|单号|评估|开修|工作日|\d+元|卡顿|订单',part):why.append('当前已选售后/订单记录')
            if stock and re.search(r'库存|有货|现货|预留|留货',part):why.append('当前业务核实记录')
            if re.search(r'免邮|包邮|配送|分期',task_text) and re.search(r'免邮|包邮|配送|分期',part):why.append('客户所问服务项目的核实资料')
            if why:take(row['source_id'],part,'；'.join(why),scope=dict(kind=row['kind'],metadata=row.get('metadata',{})),start=start,end=end)
    if followup and not any(re.search(EVENT['event_followup'],r['text']) for r in facts if r['source_id'].startswith(('materials.','supplement.'))):
        next_steps.append(dict(owner='advisor',action='向门店核实后续类似活动的安排，再回复客户。',reason='当前选用活动资料只涵盖本场，不能推断现实中没有后续安排',source_ids=['policy.6']))
    if mode=='aftersales':
        policy=sources.get('policy.5',{}).get('text','')
        wanted=r'未使用商品退换|条件不全或超过7日' if re.search(r'退货|换货|退换',task_text) else r'维修' if re.search(r'修|费用|周期',task_text) else r'质量或损坏问题'
        for start,end,part in fragments(policy):
            if re.search(wanted,part):take('policy.5',part,'与当前售后事项相关的政策',start=start,end=end)
        required=['利用本客户当前售后记录回答所问进度或处理事项']
    if re.search(r'手机|iphone',task_text,re.I) and 'capacity' in facets and prepared.get('device_reference',{}).get('records'):
        for item in prepared.get('device_reference',{}).get('records',[]):
            take(item['id'],item['model']+'；仅裸机：'+item['source_quote'],'客户提供手机型号，系统使用已核验官方资料',scope=dict(source_url=item['source_url']))
        for item in prepared.get('device_reference',{}).get('fit_judgments',[]):
            take(item['id'],item['customer_expression']+'；'+item['case_inference'],'依官方机身与当前商品作容量判断')
        for identity in focus:product_field(identity,'dimensions_cm','与已查手机型号做尺寸比较')
    if re.search(r'文件夹|厚.{0,4}(?:文件|资料)',task_text) and 'capacity' in facets:
        next_steps.append(dict(owner='customer',action='已知A4容量先答，只有厚文件夹尺寸尚未提供时再问它的长宽厚。',reason='厚文件夹不同于已确认的普通A4资料',source_ids=['policy.3']))
    unique=[];seen=set()
    for fact in facts:
        key=(fact['source_id'],fact['text'])
        if key not in seen:unique.append(fact);seen.add(key)
    facts=unique
    for fact in facts:
        field=fact.get('scope',{}).get('field')
        if fact['status']=='unknown'and field not in ('loaded_weight_g','loaded_comfort'):
            action='核实客户所问的'+brand['product_evidence']['labels'].get(field,field or'商品信息')+'，确认后回复。'
            next_steps.append(dict(owner='advisor',action=action,reason='当前具体属性待核实',source_ids=[fact['source_id']]))
    context=dict()
    profile=prepared.get('customer_context',{})
    if profile.get('customer_name'):context['salutation']=dict(text=profile['customer_name'],source_id='profile.salutation')
    if value.get('client_info'):context['advisor_background']=dict(text=value['client_info'],source_id='background.client_info')
    if profile.get('preferences'):context['long_term_preferences']=dict(text=profile['preferences'],source_id='profile.preferences')
    if fields['budget']['status'] in ('stated','advisor') and mode in ('recommendation','usage_judgment'):context['current_budget']=dict(text=fields['budget']['text'],evidence=fields['budget']['evidence'])
    chat=[]
    for row in prepared.get('messages',[]):
        if row.get('include',True):chat.append({key:row[key] for key in ('id','role','kind','text','quoted_text','sent_at','message_time','timestamp','timestamp_text') if key in row})
    contact=dict(marketing_opt_out=bool(profile.get('marketing_opt_out')),communication={key:communication.get(key) for key in ('mode','historical_chat','latest_customer_id','message_date','source_ids')},current_product_intents=prepared.get('state_check',{}).get('product_intents',[]))
    plan=dict(mode=mode,current_request=question or current or instructions,scenario=value['scenario'],consulted_product_ids=fields['product']['ids'],selected_product_ids=focus,must_answer=required,necessary_next_steps=next_steps)
    if 'weight' in facets:plan['must_answer']=['空包自重，以及结合已知携带物品和步行情况的负重取舍']
    plan['answer_basis']=answer_basis(mode,facets,facts,next_steps,brand['products'])
    business_followup=bool(current and prepared.get('input_readiness',{}).get('state')=='ready' and any(row['owner']=='advisor' for row in next_steps))
    plan['reply_route']='business_followup' if business_followup else 'normal'
    if business_followup:plan['reply_readiness']='已有当前问题，可以回复承接顾问的后续业务核实；不是导入原资料缺失'
    customer_facts=[{key:val for key,val in row.items()if key!='audience'}for row in facts if row['audience']=='customer']
    internal_facts=[row for row in facts if row['audience']=='internal_validation']
    writer_plan=copy.deepcopy(plan);writer_plan.pop('reply_readiness',None)
    writer_basis=writer_plan['answer_basis'];writer_basis.pop('relevant_unknown',None)
    writer_basis['known_fact_ids']=list(dict.fromkeys(row['source_id']for row in customer_facts))
    if 'weight'in facets:
        writer_basis['judgment_scope']='结合空包重量、实际携带物和步行情境，说明日常适配与重量取舍'
        writer_basis['completion']='给出日常负重判断和有帮助的重量依据即可；相关试背与服务收尾可自然保留'
    generation=dict(task=writer_plan,chat=chat,context=context,contact_constraints=contact,facts=customer_facts,advisor_instructions=dict(initial=instructions,revisions=revisions),revision_context=None)
    selected={row['source_id'] for row in customer_facts}
    selection=dict(version=VERSION,selected=audit,selected_source_ids=sorted(selected),internal_source_ids=sorted({row['source_id']for row in internal_facts}),omitted_source_ids=[identity for identity in sources if identity not in selected],full_source_count=len(sources),selected_fact_count=len(customer_facts),authority='对客事实用于生成；内部口径与unknown仅保存、校验和复核，不经工具schema回灌生成')
    names=[]
    if stock:names.append('stock_reservation')
    if mode in ('cleaner','zipper_fault','positive_feedback'):names.append(mode)
    if re.search(r'文件夹',task_text):names.append('bulky_folder')
    if re.search(r'别家|另一家|别的牌子',task_text):names.append('competitor')
    if mode=='event_registration':names.append('registration')
    if re.search(r'两只|两件|两个|三只',task_text):names.append('quantity_offer')
    return dict(version=VERSION,plan=plan,generation_input=generation,internal_validation=dict(facts=internal_facts),selection_audit=selection,hints=[dict(task=name)for name in names])


def answer_basis(mode,facets,facts,next_steps,products):
    from quality import product_mentions
    known=[row['source_id'] for row in facts if row['status']=='known']
    unknown=[dict(source_id=row['source_id'],scope=row.get('scope',{})) for row in facts if row['status']=='unknown']
    basis=dict(known_fact_ids=list(dict.fromkeys(known)),relevant_unknown=unknown,completion='回答当前核心后即可结束；正常服务收尾可以保留')
    if 'weight' in facets:
        basis.update(judgment_scope='结合已知空包重量、实际携带物和步行情境给有边界的日常负重判断，不要求实测证明；不把判断变成无条件舒适保证',ordinary_inference=dict(conclusion='说明这个携带量和路程是否适合日常使用，并自然点出空包与装物后的重量取舍',basis='已知空包重量、客户携带物和使用情境'),optional_help=dict(action='顾问可陪客户装入常带物品试背',usage='相关可选帮助；三条各自独立，同一个合理建议可分别出现'),completion='给出使用判断并说明相关重量取舍即可；准备过程与数据缺口留advisor_note')
    elif mode=='usage_judgment':
        basis.update(judgment_scope='把客户已经说的用途与容量事实对照，给出日常适配判断；售价只用于报价',response_focus='用已知携带物直接说明日常是否合适，保留正常礼貌和服务收尾',completion='用途适配和价格已回答就完整；不额外安排比较选款或再把价格判断交还客户')
    elif mode=='cleaner':
        basis.update(action_policy=dict(stage='售后判断前的信息收集',supported_actions=next_steps,treatment_assessment='尚未取得本案去渍方法的评估依据'),completion='停用未知清洁剂、取得标签信息并交售后判断，已构成完整处理答复')
    elif mode in ('event_query','event_invitation'):
        named=list(dict.fromkeys(product['name'] for row in facts for _,product in product_mentions(row['text'],products)))
        basis.update(event_objects=dict(collection_name='商品',names=named),completion='介绍材料中已给的演示与体验方式，即回答活动内容；具体安排按客户实际所问提供')
    elif any(row['owner']=='advisor' for row in next_steps):
        basis.update(action_policy=dict(stage='可回复承接的业务核实',supported_actions=next_steps,execution='顾问后续执行，确认后回复客户'),completion='承接核实即可形成有效微信，无需先完成核实再生成')
    else:basis['action_policy']=dict(supported_actions=next_steps,scope='业务操作建议；不限制正常礼貌与服务收尾')
    return basis
