import copy
import re

from output_contract import SLOTS, schema, validate
from product_evidence import coverage, covers, extract, inspect, supported, topics

VERSION = 'review-evidence-0.6.1'


def audit(review,result,prepared,products,focus_ids=None,legacy=False):
    if isinstance(review,dict) and review.get('source_protocol') in ('sources-v3','sources-v4'):
        from source_review import audit as audit_sources
        return audit_sources(review,result,prepared,products,focus_ids)
    errors=[]
    def error(code,message,**details):errors.append(dict(code=code,message=message,**details))
    if not isinstance(review,dict):return [dict(code='review_shape',message='复核不是完整对象')]
    wire=copy.deepcopy(review)
    for issue in wire.get('issues',[]) if isinstance(wire.get('issues'),list) else []:
        if isinstance(issue,dict) and issue.get('candidate_index') is None:issue['candidate_index']=-1
    try:validate(wire,schema('review'))
    except (ValueError,KeyError,TypeError):
        error('review_shape','复核缺少完整候选核对或来源字段')
        if not legacy:return errors
    if review.get('verdict')=='pass' and review.get('issues'):error('contradictory_review_verdict','复核同时给pass和问题清单，结论不一致，不能只采信pass')
    messages=result.get('messages',[])
    if not isinstance(messages,list) or len(messages)!=3:error('candidate_count','复核对象不是恰好三条，不能转为成功')
    customers={item['id']:item['text'] for item in prepared['messages'] if item['role']=='customer' and item['kind']=='text'}
    by_id={p['id']:p for p in products}
    def customer_ref(ref):
        if not isinstance(ref,dict) or ref.get('message_id') not in customers or not isinstance(ref.get('quote'),str) or not ref['quote'].strip() or ref['quote'] not in customers[ref['message_id']]:
            error('customer_reference','复核引用无法对应客户正文',reference=ref);return False
        return True
    def fact_ref(ref):
        if not isinstance(ref,dict):error('fact_reference','复核商品依据格式无效');return
        product=by_id.get(ref.get('product_id'));fact=product.get('facts',{}).get(ref.get('field')) if product else None
        if not fact or ref.get('status')!=fact['status'] or ref.get('value')!=fact['text']:
            error('fact_reference','复核商品依据与同一份授权资料不一致',reference=ref,expected=fact)
    checks=review.get('candidate_checks',{})
    for index,key in enumerate(SLOTS):
        check=checks.get(key,{}) if isinstance(checks,dict) else {}
        if index>=len(messages) or check.get('candidate_text')!=messages[index]:
            error('full_candidate_required','必须核对完整候选，不能只引用前半段',candidate_index=index);continue
        if review.get('verdict')=='pass':
            for conflict in inspect(messages[index],products,focus_ids):error('reviewer_missed_product_fact','复核放过了同一商品资料不支持的断言',candidate_index=index,conflict=conflict)
        for row in check.get('answered',[]):
            if customer_ref(row) and (not row.get('answer_quote') or row['answer_quote'] not in messages[index]):error('answer_reference','回答证据不在完整候选中',candidate_index=index,reference=row)
        for row in check.get('missing',[]):
            if customer_ref(row):
                requested=topics(row['quote']);covered=coverage(messages[index],row['quote'])
                if requested and all(topic in covered for topic in requested):error('false_missing_answer','完整候选已经有对应答复，不能仅凭前半句判漏答',candidate_index=index,answer_evidence=covered,candidate_text=messages[index])
        for claim in extract(messages[index],products,focus_ids):
            if not claim['product']:
                error('unresolved_product_claim','商品断言没有明确对象',candidate_index=index,evidence=claim['evidence']);continue
            if not any(covers(claim,ref) for ref in check.get('fact_checks',[])) and not supported(claim):
                error('unchecked_product_claim','候选商品断言没有对应字段核对',candidate_index=index,product_id=claim['product']['id'],field=claim['field'],evidence=claim['evidence'])
        for ref in check.get('fact_checks',[]):
            fact_ref(ref)
            if not ref.get('claim_quote') or ref['claim_quote'] not in messages[index]:error('claim_reference','商品核对原文不在候选中',candidate_index=index)
    text='\n'.join(customers.values())
    if re.search(r'已(?:经)?(?:决定|确定)(?:要)?购买|已选定[^，。；]{0,5}(?:购买|下单)|已(?:经)?下单|准备购买',review.get('current_need','')):
        commitments=[m for m in re.finditer(r'决定买|确定要买|就买|我要买|准备购买',text) if not re.search(r'没|未|不',text[max(0,m.start()-4):m.start()])]
        if not commitments:error('unsupported_customer_commitment','咨询对象不能升级成已决定或准备购买',evidence=review['current_need'])
    for issue in review.get('issues',[]) if isinstance(review.get('issues'),list) else []:
        if not isinstance(issue,dict):continue
        index=issue.get('candidate_index');index=None if index==-1 else index
        candidate=messages[index] if type(index) is int and 0<=index<len(messages) else None
        evidence=issue.get('evidence')
        if not isinstance(evidence,str) or not evidence or not any(evidence in item for item in ([candidate] if candidate else messages)):
            error('candidate_reference','问题证据不在所指候选中',candidate_index=index,evidence=evidence)
        refs=issue.get('fact_refs',[])
        if issue.get('code') in ('factual_error','unsupported_fact') and not refs:error('missing_fact_reference','事实判错必须指出同一商品字段',candidate_index=index)
        for ref in refs:fact_ref(ref)
        customer_refs=issue.get('customer_refs',[])
        if issue.get('code') in ('context_mismatch','product_scope','incomplete_reply','redundant_question') and not customer_refs:error('missing_customer_reference','上下文判错必须指出客户正文',candidate_index=index)
        for ref in customer_refs:customer_ref(ref)
        if issue.get('code') in ('unsupported_fact','factual_error') and isinstance(evidence,str):
            proposal=re.search(r'(?:可以|能|会|愿意).{0,3}帮.{0,5}(?:确认|核实|查询|核对)',evidence)
            completed=re.search(r'已经|已查|查过|已预留|有货|现货|库存充足|只剩',evidence)
            speculative=re.search(r'暗示|易被|容易被|可能被|尚可|明确尚未|明确未',issue.get('message',''))
            if proposal and not completed and speculative:error('false_completed_action_inference','不能把核实提议猜成已查询或已知库存，来源未支持该判错理由',candidate_index=index,evidence=evidence)
        for conflict in inspect(issue.get('message',''),products,focus_ids):error('reviewer_unsupported_fact','复核理由自身包含无依据的商品断言',candidate_index=index,conflict=conflict)
        from statement_scope import alleges_missing_answer
        if issue.get('code')!='incomplete_reply' and candidate and alleges_missing_answer(issue.get('message','')):
            alleged=[topic for topic in topics(issue.get('message','')) if topic in ('weight','dimensions')]
            answered=coverage(candidate,issue.get('message',''))
            if alleged and all(topic in answered for topic in alleged):error('false_missing_answer','复核理由声称未给出的数值实际在完整候选中',candidate_index=index,candidate_text=candidate,answer_evidence=answered)
        if issue.get('code')=='incomplete_reply' and candidate:
            questions=[r['quote'] for r in customer_refs if isinstance(r,dict) and isinstance(r.get('quote'),str)] or list(customers.values())[-1:]
            for question in questions:
                requested=topics(question);covered=coverage(candidate,question)
                if requested and all(topic in covered for topic in requested):error('false_missing_answer','完整候选已包含所指答复；复核不能只看前半段',candidate_index=index,answer_evidence=covered,candidate_text=candidate)
    return errors
