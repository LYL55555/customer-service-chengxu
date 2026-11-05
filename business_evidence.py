import re

VERSION='business-evidence-0.2.1'


def sources(value,prepared):
    rows=[]
    def add(identity,kind,text,metadata=None):
        if text:rows.append(dict(source_id=identity,kind=kind,text=text,metadata=metadata or {}))
    add('background.client_info','advisor_background',value.get('client_info',''))
    add('materials.related_info','business_material',value.get('related_info',''))
    add('profile.preferences','customer_profile',prepared.get('customer_context',{}).get('preferences',''))
    for row in prepared.get('messages',[]):
        if row.get('role')=='customer' and row.get('kind')=='text':add('chat.'+row['id'],'customer_message',row.get('text',''),row)
    for i,row in enumerate(prepared.get('supplements',[]),1):
        metadata=row.get('metadata',{})
        if row.get('include',True) is False or row.get('selected',True) is False:continue
        customer=prepared.get('customer_context',{}).get('customer_id')
        if customer and metadata.get('customer_id') and metadata['customer_id']!=customer:continue
        add('supplement.'+str(i),row.get('kind') or metadata.get('kind','business_material'),row.get('text',''),metadata)
    return rows


def parts(text):
    for sentence in re.finditer(r'[^。！？!?\n]+',text):
        for part in re.finditer(r'[^，,；;]+',sentence[0]):
            yield sentence.start()+part.start(),part[0],sentence[0]


def purchases(rows,products):
    from quality import product_mentions
    from statement_scope import modality
    events=[]
    for source in rows:
        for offset,part,_ in parts(source['text']):
            if re.search(r'如果|假如|要是|没说|未说明|未提供|没有.{0,6}(?:记录|资料)',part):continue
            verbs=list(re.finditer(r'买过|购买过|买了|购买了|购入|已购|带走|正在用|在用|用着|购买|买',part))
            for pos,product in product_mentions(part,products):
                before=[v for v in verbs if v.end()<=pos]
                after=[v for v in verbs if v.start()>=pos+1]
                verb=before[-1] if before else after[0] if after else None
                if not verb or abs(verb.start()-pos)>22:continue
                prefix=part[max(0,verb.start()-12):verb.start()]
                if re.search(r'想|考虑|打算|准备|希望|打听|问|是否|可能|计划',prefix) or modality(part,verb.start(),verb.end()) in ('unresolved','requirement','question'):continue
                if verb[0] in ('买','购买') and not re.search(r'上次|之前|前|去年|以前|曾|上月|上周|本月|本周',part[:verb.start()]):continue
                negative=bool(re.search(r'没(?:有)?|未|不曾|从未|尚未|不是|并非',prefix))
                events.append(dict(product_id=product['id'],positive=not negative,event='use' if verb[0] in ('正在用','在用','用着') else 'purchase',source_id=source['source_id'],source_kind=source['kind'],source_quote=part,start=offset,end=offset+len(part)))
    return events


def purchase_claims(text,products):
    from quality import product_mentions
    from statement_scope import clauses,modality
    rows=[]
    pattern=r'您(?:之前|上次)(?:买|购入|购买|带走)(?:过|了)?的|(?:您)?之前那(?:只|个)包|您那(?:只|个)|最近用包.{0,6}(?:顺手|习惯)|之前的皮具'
    for part in clauses(text):
        for m in re.finditer(pattern,part):
            if re.search(r'如果|假如|要是|若',part[:m.start()]) or modality(part,m.start(),m.end()) not in ('asserted','question'):continue
            if re.match(r'您那(?:只|个)',m[0]) and not re.search(r'包|卡夹|皮具',re.split(r'大概|能|可以|会|要|用|放|装|多长|多宽|多厚|[？?]',part[m.end():])[0]):continue
            named=product_mentions(part,products)
            following=[p for pos,p in named if pos>=m.start()]
            preceding=[p for pos,p in named if pos<m.start()]
            product=following[0] if following else preceding[-1] if preceding else None
            ids=[product['id']] if product else ['P01','P02'] if re.search(r'包|托特|肩包',part) else [p['id'] for p in products]
            rows.append(dict(product_ids=ids,evidence=part,explicit_product_id=product['id'] if product else None,claim_kind='referenced_item' if re.match(r'您那(?:只|个)',m[0]) else 'purchase_or_use'))
    return rows


def purchase_support(claim,facts):
    if claim.get('claim_kind')=='referenced_item':
        possessed=[row for row in facts.get('referenced_items',[]) if row['product_id'] in claim['product_ids']]
        if possessed:return possessed
    last={}
    for row in facts['purchases']:
        if row['product_id'] in claim['product_ids']:last[(row['source_id'],row['product_id'])]=row
    positive=[row for row in last.values() if row['positive']]
    negative={row['product_id'] for row in last.values() if not row['positive']}
    return [row for row in positive if row['product_id'] not in negative]


def order_ids(text):
    return re.findall(r'订单(?:号)?\s*[：:#]?\s*([A-Za-z][A-Za-z0-9_-]*|\d{3,})',text)


def service_claims(text):
    from statement_scope import modality
    patterns=[('free_shipping',r'免邮|包邮|免运费|邮费全免|运费全免'),('interest_free_installments',r'免息分期'),('installments',r'(?<!免息)分期'),('shipping',r'配送')]
    result=[]
    for offset,part,_ in parts(text):
        for service,pattern in patterns:
            for m in re.finditer(pattern,part):
                before,after=part[:m.start()],part[m.end():]
                if re.match(r'(?:服务|权益)?(?:的)?(?:资料|信息|说明|依据)',after):continue
                if modality(part,m.start(),m.end()) not in ('asserted',):continue
                if re.search(r'是否|需.{0,3}确认|待核实|尚未确认|还没确认|不确定|没确认|不知道',before[-18:]+after[:12]):continue
                positive=not bool(re.search(r'(?:没有|不提供|不支持|不设|不能|不可|不可以|无法|不会|未提供|不|无)(?:免费)?$',before) or re.match(r'(?:服务|权益)?(?:不提供|不支持|没有|不行)',after))
                predicate=bool(re.search(r'(?:可以|可|能|支持|提供|享受|没有|不提供|不支持|不设|不能|不可|不可以|无法|不会|未提供|不|无|有|确认[：:]?)(?:免费)?$',before) or re.search(r'(?:本次|这次|本单|这笔|本笔|当前)(?:的)?(?:订单|单)?$',before) or re.search(r'订单(?:号)?[：:# ]*[A-Za-z0-9_-]+$',before) or re.search(r'邮费全免|运费全免',m[0]))
                if not predicate:continue
                result.append(dict(service=service,positive=positive,evidence=part,order_ids=order_ids(part),scope='all' if re.search(r'所有|每(?:笔|个|一)|一律|今后|以后|一直|永远',part) else 'current',start=offset+m.start(),end=offset+m.end()))
    return result


def confirmations(rows):
    from statement_scope import modality
    result=[]
    for source in rows:
        if source['kind'] in ('customer_message','customer_profile','quoted_message'):continue
        for offset,part,sentence in parts(source['text']):
            confirmation=re.search(r'(?:门店|品牌|服务人员|售后).{0,12}(?:已确认|已核实|确认过|确认[：:]|核实结果)',sentence)
            if not confirmation:continue
            prefix=sentence[:confirmation.start()]
            if re.search(r'客户(?:说|称|要求|希望|转述|表示)|顾客(?:说|要求)|引用|转发客户|客户原话',sentence[:confirmation.end()]) or re.search(r'猜测|猜想|估计|大概|可能|听说|据说|如果|假如',prefix+confirmation[0]) or re.search(r'需要|尚未|没有|未|待|准备',confirmation[0]) or prefix.count('“')>prefix.count('”'):continue
            if modality(sentence,confirmation.start(),confirmation.end())!='asserted':continue
            for fact in service_claims(part):
                if re.search(r'其他客户|另一(?:位)?客户|其他订单|另一(?:笔|个)订单|上次订单|旧订单|历史订单',sentence):continue
                result.append(dict(fact,source_id=source['source_id'],source_kind=source['kind'],source_quote=part,source_start=offset,source_end=offset+len(part),confirmation_quote=confirmation[0],order_ids=order_ids(part) or order_ids(sentence) or ([source['metadata']['order_id']] if source['metadata'].get('order_id') else []),current_order=bool(re.search(r'本次|这次|本单|这笔|本笔|当前订单',sentence)),scope='order' if order_ids(sentence) or source['metadata'].get('order_id') else 'current' if re.search(r'本次|这次|本单|这笔|本笔|当前订单',sentence) else 'general',asset_id=source['metadata'].get('asset_id')))
    return result


def service_support(claim,facts):
    supported=[]
    current_orders=set(facts['current_order_ids'])
    wanted=set(claim['order_ids']) or current_orders
    if claim['order_ids'] and current_orders and not set(claim['order_ids']).intersection(current_orders):return []
    for row in facts['services']:
        if row['service']!=claim['service'] or row['positive']!=claim['positive']:continue
        if claim['scope']=='all' and row['scope']!='general':continue
        if row['order_ids'] and (wanted and not set(row['order_ids']).intersection(wanted) or not wanted and not row.get('current_order')):continue
        contrary=[r for r in facts['services'] if r['service']==row['service'] and r['positive']!=row['positive'] and (not r['order_ids'] or bool(wanted.intersection(r['order_ids'])))]
        if not contrary:supported.append(row)
    return supported


def build(value,prepared,products):
    rows=sources(value,prepared)
    current='\n'.join(row['text'] for row in rows if row['kind']=='customer_message')+'\n'+value.get('client_info','')
    referenced=[dict(product_id=r['product_id'],source_id=r['source_id'],case_id=r['case_id'],source_quote=r['source_quote']) for r in prepared.get('aftersales_scope',{}).get('records',[]) if r['valid']]
    return dict(version=VERSION,purchases=purchases(rows,products),referenced_items=referenced,services=confirmations(rows),current_order_ids=order_ids(current),authority='仅当前明确选用资料；售后物件引用不证明购买；服务核实绑定项目、状态、来源和订单范围')


def from_prepared(prepared,products):
    if prepared.get('business_evidence',{}).get('version')==VERSION:return prepared['business_evidence']
    index={row['id']:row for row in prepared.get('evidence_sources',{}).get('sources',[])}
    value=dict(client_info=index.get('background.client_info',{}).get('text',''),related_info=index.get('materials.related_info',{}).get('text',''))
    return build(value,prepared,products)


def inspect(messages,products,value=None,prepared=None,facts=None):
    prepared=prepared or {}
    facts=facts or (build(value,prepared,products) if value is not None else from_prepared(prepared,products))
    issues=[]
    for index,text in enumerate(messages):
        for claim in purchase_claims(text,products):
            if not purchase_support(claim,facts):issues.append(dict(code='invented_purchase_history',candidate_index=index,evidence=claim['evidence'],product_ids=claim['product_ids'],message='没有该商品的购买或使用依据；其他商品的已购记录不能支持这项已购预设。'))
        for claim in service_claims(text):
            if not service_support(claim,facts):issues.append(dict(code='unsupported_service_availability',candidate_index=index,evidence=claim['evidence'],service=claim['service'],scope=claim['scope'],message='这项服务、肯定或否定状态及适用订单范围没有同一份已核实业务记录支持；客户要求不是门店确认。'))
    return issues
