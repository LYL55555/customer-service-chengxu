import copy
import hashlib
import json
from datetime import datetime,timezone

VERSION='offline-revalidation-1.2.0'


def refresh_context(record,brand):
    import engine
    from context_store import state_evidence
    from statement_scope import direction
    from understanding import build_understanding
    from answer_context import build as answer
    from device_reference import build as devices
    from evidence_sources import build as sources
    from business_evidence import build as business
    from delivery import assess
    value=record['input'];prepared=copy.deepcopy(record['confirmed_context'])
    for key in ('state_check','communication','answer_context','device_reference','load_reference','evidence_sources','candidate_spans','business_evidence','input_readiness','aftersales_scope','task_materials'):prepared.pop(key,None)
    if record.get('customer_context') is not None:prepared['customer_context']=copy.deepcopy(record['customer_context'])
    prepared['state_check']=state_evidence(prepared.get('messages',[]));prepared['communication']=direction(value,prepared)
    record['understanding']=build_understanding(value,prepared,brand['products']);prepared['input_readiness']=assess(value,prepared)
    prepared['answer_context']=answer(value,prepared,brand);prepared['device_reference']=devices(value,prepared,brand['products'])
    from load_reference import build as loads
    prepared['load_reference']=loads(value,prepared,brand['products'])
    prepared['evidence_sources']=sources(value,prepared,brand,record.get('writing_rules_snapshot',''))
    prepared['business_evidence']=business(value,prepared,brand['products'])
    from task_materials import build as task_materials
    prepared['task_materials']=task_materials(value,prepared,brand)
    record['confirmed_context']=prepared
    return prepared


def revalidate(original):
    import engine
    from delivery import guard
    from evidence_sources import candidate_spans
    record=copy.deepcopy(original)
    metadata=dict(version=VERSION,validator_app_version=engine.APP_VERSION,created_at=datetime.now(timezone.utc).isoformat(),original_run_id=original['run_id'],original_app_version=original['app_version'],original_status=original['status'],original_error=original.get('error'),original_review_validation_errors=original.get('quality_review',{}).get('validation_errors'),original_content_sha256=hashlib.sha256(engine.json_text(original).encode()).hexdigest(),model_requests=0)
    record['record_kind']='offline_revalidation';record['revalidation']=metadata
    metadata['original_policy_checks']=copy.deepcopy(original.get('policy_checks'))
    if record.get('quality_review'):
        record['quality_review']['validation_errors']=[]
        record['quality_review']['offline_revalidated']=False
    try:
        brand=engine.brand_data();value=record['input'];prepared=refresh_context(record,brand);result=record.get('parsed_output') or record.get('result')
        if not isinstance(result,dict):raise engine.GenerationError('missing_original_generation','原记录没有可校验的生成结构；不补写或重新生成。')
        focus=record.get('understanding',{}).get('fields',{}).get('product',{}).get('ids',value.get('product_ids',[]))
        from quality import inspect_messages
        record['policy_checks']=inspect_messages(result.get('messages',[]),brand['products'],selected_ids=value.get('product_ids'),expected_state=result.get('client_state'),focus_ids=focus,context=dict(value=value,prepared=prepared))
        validated=engine.validate_output(result,selected_ids=value.get('product_ids'),brand=brand,focus_ids=focus,context=dict(value=value,prepared=prepared))
        if validated['status']!='ready':raise engine.GenerationError('advisor_input','原结果需要顾问补资料，没有三条有效客户消息。')
        review=record.get('quality_review',{}).get('parsed_output')
        if not isinstance(review,dict):raise engine.GenerationError('missing_original_review','原记录没有完整模型复核；本地重验不能补称已复核。')
        prepared['candidate_spans']=candidate_spans(validated['messages'])
        engine.validate_review_result(review,validated,prepared,value,brand,record)
        record['quality_review']['offline_revalidated']=True
        record.update(status='success',result=validated);record.pop('error',None);record.pop('failure_guidance',None)
    except engine.GenerationError as error:
        record.update(status='error',error=dict(code=error.code,message=error.message,retryable=False))
    metadata['revalidated_status']=record['status'];metadata['delivery_guard']=guard(record)
    metadata['generation_messages_unchanged']=(original.get('parsed_output') or original.get('result') or {}).get('messages')==(record.get('parsed_output') or record.get('result') or {}).get('messages')
    metadata['model_review_unchanged']=original.get('quality_review',{}).get('parsed_output')==record.get('quality_review',{}).get('parsed_output')
    assert metadata['generation_messages_unchanged'] and metadata['model_review_unchanged']
    return record
