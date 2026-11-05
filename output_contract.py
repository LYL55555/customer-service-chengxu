import copy
import json

VERSION = 'task-delivery-0.11.0'
SLOTS = ('reply_1', 'reply_2', 'reply_3')
STATES = ['comparing', 'declined', 'unclear', 'other']


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def string(values=None):
    return dict(type='string', **({'enum': values} if values else {}))


def array(items):
    return dict(type='array', items=items)


def schema(kind):
    from statement_scope import STATE_DESCRIPTION
    if kind == 'generation':
        from writing_review import MODES
        return obj(dict(status=string(['ready', 'needs_advisor']), client_state=dict(string(STATES),description=STATE_DESCRIPTION), messages=dict(anyOf=[obj({key:dict(string(),description=MODES[key]) for key in SLOTS}),array(string())],description='ready时三个固定字段；needs_advisor时空数组[]，零条客户消息；数组不得有元素'), advisor_note=string(), missing_information=dict(array(string()),description='仅阻断生成、需顾问先补的原资料；ready时必须[]；正常向客户补问同行称呼或必要物品尺寸不属于此字段')))
    if kind in ('review_sources','review_sources_v4'):
        ref = obj(dict(source_id=string()))
        answer = obj(dict(source_id=string(),candidate_span_id=string()))
        fact = obj(dict(product_id=string(),field=string(),status=string(['known','unknown']),value=string(),claim_quote=string()))
        source_check = obj(dict(source_id=string(),candidate_span_id=string()))
        check = obj(dict(candidate_text=string(),answered=array(answer),missing=array(ref),source_checks=array(source_check)))
        issue = obj(dict(code=string(['factual_error','unsupported_fact','context_mismatch','product_scope','incomplete_reply','insufficient_choice','redundant_question','unnatural_tone','policy_error','output_structure']),candidate_index=dict(type='integer',enum=[-1,0,1,2]),evidence_span_id=string(),message=string(),source_refs=array(ref)))
        if kind=='review_sources_v4':
            check['properties']['editing']=array(obj(dict(candidate_span_id=string(),purpose=string(['answer','judgment','help','necessary_limit','relationship','none']),action=dict(string(['keep','polish','remove','revise']),description='有边界的日常判断和正常服务收尾可keep；表达笼统、内部自述或可省展开用polish；事实权益错误、无条件保证或无依据操作才用revise/remove'),delete_effect=dict(string(['loses_answer','misleads','optional_help','still_complete']),description='判断删除句段后的影响，不是原句是否误导；去掉错误或多余尾句、余下仍答完整用still_complete'),reason=dict(string(),description='简短说明此片段的作用和删改影响，不重复候选全文'))))
            check['required'].append('editing')
            issue['properties']['code']['enum'].append('irrelevant_information')
        return obj(dict(source_protocol=string(['sources-v4' if kind=='review_sources_v4' else 'sources-v3']),verdict=string(['pass','block','needs_review','needs_advisor']),client_state=dict(string(STATES),description=STATE_DESCRIPTION),state_evidence=array(string()),current_need=string(),candidate_checks=obj({key:copy.deepcopy(check) for key in SLOTS}),issues=array(issue)))
    fact = obj(dict(product_id=string(), field=string(), status=string(['known', 'unknown']), value=string()))
    customer = obj(dict(message_id=string(), quote=string()))
    answer = obj(dict(message_id=string(), quote=string(), answer_quote=string()))
    checked_fact = obj(dict(product_id=string(), field=string(), status=string(['known', 'unknown']), value=string(), claim_quote=string()))
    check = obj(dict(candidate_text=string(), answered=array(answer), missing=array(customer), fact_checks=array(checked_fact)))
    issue = obj(dict(code=string(['factual_error','unsupported_fact','context_mismatch','product_scope','incomplete_reply','insufficient_choice','redundant_question','unnatural_tone','policy_error','output_structure']), candidate_index=dict(type='integer', enum=[-1,0,1,2]), evidence=string(), message=string(), fact_refs=array(fact), customer_refs=array(customer)))
    return obj(dict(verdict=string(['pass','block','needs_review']), client_state=string(STATES), state_evidence=array(string()), current_need=string(), candidate_checks=obj({key:copy.deepcopy(check) for key in SLOTS}), issues=array(issue)))


def validate(value, contract, path='$'):
    if 'anyOf' in contract:
        for variant in contract['anyOf']:
            try:validate(value,variant,path);return
            except ValueError:pass
        raise ValueError(path+' variants')
    expected=contract['type']
    valid={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),'integer':type(value) is int}[expected]
    if not valid:raise ValueError(path+' type')
    if 'enum' in contract and value not in contract['enum']:raise ValueError(path+' enum')
    if expected=='object':
        if set(value)!=set(contract['properties']):raise ValueError(path+' fields')
        for key,child in contract['properties'].items():validate(value[key],child,path+'.'+key)
    if expected=='array':
        for i,item in enumerate(value):validate(item,contract['items'],path+f'[{i}]')


def parse(text):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate field: '+key)
            result[key]=value
        return result
    return json.loads(text,object_pairs_hook=unique)


def generation_payload(value, contract):
    try:
        validate(value,contract)
        generation_state(value)
        return value, None
    except ValueError as error:
        original_error=str(error)
    messages=value.get('messages') if isinstance(value,dict) else None
    extras=set(messages)-set(SLOTS)if isinstance(messages,dict)else set()
    empty_note=extras=={'client_state_note'}and messages['client_state_note']==''
    ignored_target=extras=={'target_index'}and type(messages['target_index'])is int and messages['target_index']in range(3)
    if not isinstance(messages,dict)or set(messages)!=set(SLOTS)|extras or not(empty_note or ignored_target)or any(key not in messages or not isinstance(messages[key],str)or not messages[key].strip()for key in SLOTS):
        raise ValueError(original_error)
    adapted=copy.deepcopy(value)
    field='target_index'if ignored_target else'client_state_note'
    del adapted['messages'][field]
    validate(adapted,contract)
    generation_state(adapted)
    audit=dict(version=VERSION,action='ignore_model_scope_metadata'if ignored_target else'omit_empty_internal_field',path='$.messages.'+field,original_value=messages[field],original_schema_error=original_error,candidates_unchanged=all(adapted['messages'][key]==messages[key]for key in SLOTS))
    if ignored_target:audit.update(reason='模型附加的修改索引没有业务效力；只兼容这一个已知元数据字段，完整候选与当次结构仍校验',model_target_adopted=False,scope_authority='user_request_only',provider_native_schema_match=False)
    return adapted,audit


def generation_state(value):
    if value['status']=='needs_advisor':
        if value['messages']!=[] or not value['missing_information']:raise ValueError('advisor state requires zero customer messages and specific missing information')
    elif not isinstance(value['messages'],dict) or set(value['messages'])!=set(SLOTS) or value['missing_information']:
        raise ValueError('ready requires three fixed fields and no advisor-blocking gap')


def review_payload(value, contract):
    try:
        validate(value, contract)
        return value, None
    except ValueError as error:
        original_error = str(error)
    fields = contract.get('properties', {})
    fixed = fields.get('source_protocol', {})
    if not isinstance(value, dict) or set(value) != set(fields) - {'source_protocol'} or fixed.get('type') != 'string' or fixed.get('enum') != ['sources-v4'] or 'source_protocol' not in contract.get('required', []):
        raise ValueError(original_error)
    adapted = copy.deepcopy(value)
    adapted['source_protocol'] = 'sources-v4'
    validate(adapted, contract)
    return adapted, dict(version=VERSION, action='restore_requested_protocol_constant', path='$.source_protocol', original_field_present=False, value='sources-v4', requested_enum=['sources-v4'], original_schema_error=original_error, provider_native_schema_match=False, candidate_and_review_content_unchanged=True)


def normalize(value,kind):
    validate(value,schema(kind))
    normalized=copy.deepcopy(value)
    if kind=='generation':
        generation_state(value)
        if value['status']=='needs_advisor':
            if value['messages'] or not value['missing_information']:raise ValueError('advisor state requires no customer messages and specific missing information')
            normalized['messages']=[]
        else:
            if set(value['messages'])!=set(SLOTS) or value['missing_information']:raise ValueError('ready requires all three replies and no advisor-blocking gap')
            normalized['messages']=[value['messages'][key] for key in SLOTS]
    elif kind=='review':
        for issue in normalized['issues']:
            if issue['candidate_index']==-1:issue['candidate_index']=None
    return normalized


def function(kind):
    return dict(name='return_replies' if kind=='generation' else 'return_review',description='返回最终三条独立候选，不执行外部操作' if kind=='generation' else '返回有来源、逐条完整核对的复核，不执行外部操作',strict=True,parameters=schema(kind))
