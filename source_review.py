import re

from evidence_sources import check,claim_domains,source_domains
from output_contract import SLOTS, schema, validate
from product_evidence import coverage, extract, inspect, supported, topics
from task_evidence import domains as task_domains, product_slice, event_exclusions

VERSION = 'source-review-0.9.1'


def audit(review,result,prepared,products,focus_ids=None):
    errors=[]
    def error(code,message,**details):errors.append(dict(code=code,message=message,**details))
    try:validate(review,schema('review_sources_v4' if review.get('source_protocol')=='sources-v4' else 'review_sources'))
    except (ValueError,TypeError,KeyError):return [dict(code='review_shape',message='多来源复核结构不完整')]
    sources={row['id']:row for row in prepared.get('evidence_sources',{}).get('sources',[])}
    messages=result.get('messages',[])
    if set(review['candidate_checks'])!=set(SLOTS):return [dict(code='review_shape',message='客户候选复核必须完整核对三条；空检查仅用于顾问待办状态')]
    if len(messages)!=3:return [dict(code='candidate_count',message='复核对象必须恰好三条')]
    from aftersales_evidence import audit as audit_aftersales
    errors.extend(audit_aftersales(messages,prepared,products,checks=review['candidate_checks']))
    errors.extend(event_exclusions(messages,prepared))
    if review['verdict']=='pass' and review['issues']:error('contradictory_review_verdict','pass不能同时包含待处理问题')
    if review['verdict']!='pass' and not review['issues']:error('unexplained_review_verdict','未通过必须给出可对照的问题')
    for identity in review['state_evidence']:
        row=sources.get(identity)
        if not row or row['kind'] not in ('customer_message','customer_profile','advisor_background','task','business_material','contact_limit','customer_record','order','event','background'):error('state_reference','状态引用来源无效',source_id=identity)
    communication=prepared.get('communication',{})
    from business_evidence import from_prepared,inspect as inspect_business,service_claims,service_support
    business=from_prepared(prepared,products)
    if review['verdict']=='pass':
        from load_reference import inspect as inspect_load
        for conflict in inspect_load(messages,prepared,products):error('reviewer_missed_load_calculation','复核放过错误小计或将两项小计当完整负重',conflict=conflict)
        for conflict in inspect_business(messages,products,facts=business):error('reviewer_missed_business_fact','复核放过了没有同对象或同范围业务依据的断言',conflict=conflict)
        from quality import stain_advice
        for index,text in enumerate(messages):
            for conflict in stain_advice(text,communication.get('latest_text','')):error('reviewer_missed_care_action','复核放过了没有去渍操作依据的处理建议',candidate_index=index,conflict=conflict)
        from answer_context import inspect as inspect_answer
        for conflict in inspect_answer(messages,dict(prepared=prepared)):
            error('reviewer_missed_current_answer','复核放过了当前任务的漏答',conflict=conflict)
    if review['client_state']=='unclear':
        if not any(sources.get(i,{}).get('kind') in ('customer_message','advisor_background','customer_record') for i in review['state_evidence']):error('unsupported_pause_state','暂缓要引用客户当前表达或顾问提供的客户背景，业务资料缺项不能作为客户态度依据')
        if re.search(r'购(?:买)?意向.{0,6}(?:未知|不明|不清楚)|无法判断.{0,5}是否购买',review['current_need']) and not re.search(r'暂缓|考虑|想想|琢磨|以后|稍后',review['current_need']):error('unsupported_pause_reason','不知道购买意向不等于客户明确暂缓；请核对原话，不凭关键词没命中限制模型')
    if communication.get('latest_text') and communication.get('latest_customer_id') and 'chat.'+communication['latest_customer_id'] not in review['state_evidence']:
        error('current_state_anchor','当前状态需要最新客户正文作为锚点，长期偏好或联系限制只能补充，不能替代当前需求')
    def source_ref(ref):
        if not check(ref,sources):error('source_reference','来源编号不存在，不能拼入说明或冒用其他资料',reference=ref);return False
        return True
    spans={s['id']:s for s in prepared.get('candidate_spans',[])}
    def span_ref(identity,index):
        span=spans.get(identity)
        if not span or span['candidate_index']!=index or span['text']!=messages[index][span['start']:span['end']]:
            error('candidate_reference','候选片段编号、所属候选或原文位置不匹配',candidate_index=index,reference=identity)
            return ''
        return span['text']
    customer_text='\n'.join(s['text'] for s in sources.values() if s['kind']=='customer_message')
    if re.search(r'已(?:经)?(?:决定|确定)(?:要)?购买|已选定[^，。；]{0,5}(?:购买|下单)|已(?:经)?下单|准备购买',review['current_need']) and not re.search(r'决定买|确定要买|我要买|就买|下单',customer_text):
        error('unsupported_customer_commitment','提问或条件式购买不能升级为已决定购买')
    for index,key in enumerate(SLOTS):
        candidate=messages[index];row=review['candidate_checks'][key]
        if row['candidate_text']!=candidate:error('full_candidate_required','需要完整候选原文',candidate_index=index)
        if review['source_protocol']=='sources-v4':
            expected={s['id'] for s in spans.values() if s['candidate_index']==index and not s['id'].endswith('.full')}
            received=[r['candidate_span_id'] for r in row['editing']]
            if set(received)!=expected or len(received)!=len(set(received)):error('sentence_editing_coverage','逐句编辑需覆盖每个原文句段且不重复，不能只给整体语气结论',candidate_index=index)
            for edit in row['editing']:
                span_ref(edit['candidate_span_id'],index)
                if not edit['reason'].strip():error('empty_editing_reason','逐句判断须说明作用及删后影响',candidate_index=index)
                if edit['action']=='remove' and edit['delete_effect']!='still_complete':error('contradictory_editing','建议删除不能同时认为删后漏答或误导',candidate_index=index)
                if review['verdict']=='pass' and edit['action'] in ('remove','revise'):error('contradictory_review_verdict','pass不能同时列出需删除或修正的原句；轻微措辞润色可单列polish',candidate_index=index)
                if edit['purpose']=='none' and edit['action']=='keep':error('contradictory_editing','没有当前作用不能同时判定必须保留',candidate_index=index)
        if not row['answered']:error('missing_task_check','每条复核需指出回应的任务或客户需求来源，不能全空后直接通过',candidate_index=index)
        if review['verdict']=='pass' and row['missing']:error('contradictory_review_verdict','pass不能同时列出未回答的核心问题',candidate_index=index)
        if review['verdict']=='pass':
            for conflict in inspect(candidate,products,focus_ids,reference_text=communication.get('latest_text','')):error('reviewer_missed_product_fact','复核放过不支持的商品事实',candidate_index=index,conflict=conflict)
        for answer in row['answered']:
            source_ref(answer)
            span_ref(answer['candidate_span_id'],index)
        checked_domains=set()
        checked_source_ids={ref['source_id'] for ref in row['source_checks']}
        for claim in service_claims(candidate):
            witnesses=service_support(claim,business)
            if witnesses and not checked_source_ids.intersection(r['source_id'] for r in witnesses):error('missing_business_confirmation_check','已核实服务需引用同一服务与范围的真实业务来源，不能只引用通用政策或客户要求',candidate_index=index,service=claim['service'])
        for ref in row['source_checks']:
            exists=source_ref(ref)
            claim=span_ref(ref['candidate_span_id'],index)
            if exists:
                source=sources[ref['source_id']];allowed=source_domains(source);claimed=task_domains(claim,prepared)
                from quality import product_mentions
                event_products={p['id'] for s in sources.values() if s['kind'] in ('business_material','event') and '活动' in s['text'] for _,p in product_mentions(s['text'],products)}
                unrelated_product=source['id'].startswith('product.') and bool(claimed.intersection({'service','event'})) and not product_slice(source,claim,products,focus_ids,event_products)
                companion_domains=set()
                for companion in row['source_checks']:
                    other=sources.get(companion['source_id'])
                    if other and other.get('kind')!='writing_rule' and companion['candidate_span_id']==ref['candidate_span_id']:
                        companion_domains.update(source_domains(other))
                unsupported_writing_authority=source.get('kind')=='writing_rule' and bool(claimed.intersection({'product','pricing','service','event'})-companion_domains)
                if unsupported_writing_authority or unrelated_product:error('source_domain_mismatch','来源需支持片段中自己的断言：商品参数不能证明售后或活动政策，同句可由不同来源各自支持对应内容',candidate_index=index,source_id=source['id'],claim_domains=sorted(claimed),source_domains=sorted(allowed))
                if source['id'].startswith('product.') and source['id'].endswith('.price'):
                    from quality import price_bindings
                    span=spans[ref['candidate_span_id']]
                    bindings=[item for item in price_bindings(candidate,products,focus_ids=focus_ids) if item['product_id'] and span['start']<=item['start'] and item['end']<=span['end']]
                    if bindings and not any(item['source_id']==source['id'] and item['value']==item['expected'] for item in bindings):error('price_source_mismatch','引用的商品价格与该片段的商品/数值不符，不能用其他商品价格作依据',candidate_index=index,source_id=source['id'])
                checked_domains.update(allowed)
        required=task_domains(candidate,prepared).intersection({'pricing','service','event'})
        if 'pricing' in required:
            from quality import price_bindings
            if not price_bindings(candidate,products,focus_ids=focus_ids) and not re.search(r'售价|标价|现价|单价|折扣|打折|优惠|议价|赠品|[一二三四五六七八九\d]折',candidate):required.discard('pricing')
        if re.search(r'售后(?:提交|申请)?单号|单号',candidate) and not re.search(r'维修|退换|退货|换货|保养|收费|费用|周期',candidate):required.discard('service')
        no_discount=r'(?:没有|无|不设|不提供)(?:新增|设|设置)?(?:[^，。；！？]{0,12}[、和或])?(?:折扣|优惠价|优惠)'
        if re.search(no_discount,candidate) and any(sources.get(ref['source_id'],{}).get('kind') in ('business_material','event') and re.search(no_discount,sources[ref['source_id']]['text']) for ref in row['source_checks']):
            if any(s.get('kind')=='brand_policy' and re.search(r'无折扣|没有折扣',s['text']) for s in sources.values()):checked_domains.add('pricing')
        if extract(candidate,products,focus_ids):required.add('product')
        from quality import verified_catalog_prices
        if verified_catalog_prices(candidate,products,focus_ids):checked_domains.add('pricing')
        if required-checked_domains:error('missing_authoritative_check','相关商品/价格/售后/活动断言没有对应类型的依据核对，客户原话不能授权品牌事实',candidate_index=index,domains=sorted(required-checked_domains))
        for ref in row['missing']:
            if source_ref(ref):
                question=sources.get(ref['source_id'],{}).get('text','');requested=topics(question);covered=coverage(candidate,question)
                if requested and all(t in covered for t in requested):error('false_missing_answer','完整候选已有所指答案',candidate_index=index)
    from statement_scope import completed_actions
    for issue in review['issues']:
        index=issue['candidate_index'];candidate=messages[index] if index in (0,1,2) else None
        span=spans.get(issue['evidence_span_id'])
        evidence=span_ref(issue['evidence_span_id'],index if candidate else span['candidate_index'] if span else 0)
        refs=issue['source_refs']
        if issue['code'] not in ('insufficient_choice','unnatural_tone','output_structure') and not refs:error('missing_source_reference','事实、政策或上下文判错需要适合类型的来源',candidate_index=index)
        issue_domains=task_domains(evidence,prepared)
        issue_sources=[sources.get(ref.get('source_id'),{}) for ref in refs]
        if issue['code']=='policy_error':
            authority=any(s.get('kind')=='brand_policy' or s.get('authority') not in ('context_not_authorization','quoted_not_authorization') and bool(source_domains(s).intersection(issue_domains.intersection({'service','event'}))) or s.get('id','').endswith('.stock') and re.search(r'库存|预留|有货',issue['message']) for s in issue_sources)
            if not authority:error('issue_source_authority','政策判错须有对应政策或有效业务依据，客户和商品参数只能支持自己的上下文/属性，不能授权售后或活动',candidate_index=index)
        for ref in refs:
            if source_ref(ref):
                source=sources[ref['source_id']];domains=source_domains(source)
                if issue['code']=='incomplete_reply' and source.get('kind') in ('product_known','product_unknown','writing_rule'):error('issue_source_type','漏答应指向任务或客户问题，不是任意商品字段',candidate_index=index,source_id=source['id'])
                if issue['code'] in ('factual_error','unsupported_fact','policy_error') and issue_domains and not issue_domains.intersection(domains) and source.get('authority') not in ('context_not_authorization','quoted_not_authorization') and source.get('kind')!='brand_policy':error('issue_source_type','判错依据的类型与候选断言不符',candidate_index=index,source_id=source['id'])
        if re.search(r'已完成|已执行|已经(?:登记|提交|查询)|声称已|像已提交',issue['message']) and not completed_actions(evidence):
            if re.search(r'先|现在就|准备|可以|会|帮您|一起提交|有结果',evidence):error('false_completed_action_inference','未来意向或协助不能被推成完成',candidate_index=index,evidence=evidence)
        if candidate and re.search(r'约数|近似',issue['message']) and re.search(r'比较|比电脑|比包|方向性',issue['message']) and re.search(r'比|窄|小|大',evidence) and re.search(r'核实|确认|实测|不能.{0,3}保证|不好.{0,4}保证',candidate):
            error('false_precision_objection','约数参数可以做注明边界的数值比较，不能据此保证实际装入；不能把前者直接判成无依据',candidate_index=index)
        if issue['code']=='incomplete_reply' and candidate:
            for ref in refs:
                if sources.get(ref['source_id'],{}).get('kind') in ('product_known','product_unknown','writing_rule'):continue
                question=sources.get(ref['source_id'],{}).get('text','');requested=topics(question);covered=coverage(candidate,question)
                if requested and all(t in covered for t in requested):error('false_missing_answer','不能忽略完整候选里已有的回答',candidate_index=index)
        from statement_scope import alleges_missing_answer
        if issue['code']!='incomplete_reply' and candidate and alleges_missing_answer(issue['message']):
            requested=[t for t in topics(issue['message']) if t in ('weight','dimensions')]
            covered=coverage(candidate,issue['message'])
            if requested and all(t in covered for t in requested):error('false_missing_answer','数值实际在完整候选中，不能借语气意见假称漏答',candidate_index=index)
    return errors
