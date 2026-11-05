import re

from engine import APP_VERSION


def explain_failure(record):
    error = record.get('error') or {}
    code = error.get('code', 'internal')
    if code=='provider_error' and record.get('provider_status')==400 and re.search(r'schema|properties|function|tool|object with',record.get('raw_response',''),re.I):code='output_contract'
    review = record.get('quality_review') if isinstance(record.get('quality_review'), dict) else {}
    parsed = review.get('resolved_review') or review.get('parsed_output')
    review_issues = parsed.get('issues', []) if isinstance(parsed, dict) else []
    validation_errors = review.get('validation_errors') or []
    checks = validation_errors or record.get('policy_checks') or review_issues or []
    if not isinstance(checks, list):
        checks = []
    issues = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        index = item.get('candidate_index')
        title = f'第{index+1}条候选' if type(index) is int and index in range(3) else '整组候选'
        if validation_errors:title = '复核器问题 · ' + title
        conflict = item.get('conflict') or item
        expected = conflict.get('expected')
        if isinstance(expected, dict):expected = expected.get('text')
        issues.append(dict(candidate_index=index, title=title, evidence=conflict.get('evidence', item.get('candidate_text', '')), message=item.get('message', ''), expected=expected, product_id=conflict.get('product_id')))
    phase = 'review' if review.get('model_call_attempted') else 'generation' if record.get('model_call_attempted') else 'preflight'
    actions, category, title, advice, retry = [], 'system', '这次没有生成可用回复', error.get('message', '请查看失败记录。'), False
    if code in ('connection', 'timeout', 'rate_limit', 'provider_error', 'authentication', 'endpoint', 'not_configured', 'bad_config'):
        category, title = 'connection', '接口连接或配置未完成'
        advice = '客户资料和草稿仍保留，无需重新填写。先检查本机接口配置、网络或账户状态。'
        if code == 'timeout':
            advice += '响应超时不表示请求一定未处理；先查看历史是否完成，再决定是否手动重试。'
        actions = [dict(action='connection', label='查看接口状态')]
        retry = code in ('connection', 'timeout', 'rate_limit', 'provider_error') and bool(error.get('retryable')) and phase != 'review'
        if phase == 'review':
            title = '候选已生成，但复核接口未完成'
            advice = '候选和原始响应已保留，尚未通过复核，暂不可采用。无需重填客户资料；先检查连接，本工具不会自动重做整组请求。'
    elif code=='invalid_advisor_request':
        category,title='output','模型把可回复任务误判为资料缺失'
        advice='请查看具体原因。无需为这个错误待办重填资料；原输出保留，没有把它交给顾问或客户处理，也不会自动重试。'
    elif code=='output_contract':
        category,title='output','模型接口不接受输出约定'
        advice='需要开发者检查接口定义，不是客户正文或预算缺失。原始响应与客户草稿保留；不要让客户重发，也不要反复重试。'
    elif code=='advisor_input':
        category,title='input','需要顾问补充原资料'
        advice='这是给顾问的待办，不是客户消息。请先使用已有且选中的聊天或客户记录，只补当前任务缺的最少内容；不用请客户重发。'
        tasks=record.get('advisor_help',{}).get('items',[])
        actions=[dict(action=row['action'],label=row['label']) for row in tasks] or [dict(action='chat',label='补入或复核聊天'),dict(action='background',label='补一句已核对背景')]
        issues=[dict(title='顾问待办',message=row['message'],evidence='') for row in tasks]
    elif code=='contact_confirmation':
        category,title='input','先确认这是不是本次来信'
        advice='未请求模型。保留原消息，在本次背景补一句说明是刚收到的咨询，还是历史记录；消息导入时间不代表发送时间。'
        actions=[dict(action='background',label='补一句背景确认')]
    elif code in ('context_conflict', 'bad_understanding', 'understanding_stale'):
        category, title = 'input', '先纠正本次理解中的冲突'
        advice = '这次尚未请求模型。核对标出的原话与背景，纠正后再生成；重试连接不能解决资料冲突。'
        actions = [dict(action='understanding', label='核对本次理解')]
        issues += [dict(title='需确认', message=row['message'], evidence='', field=row.get('field')) for row in record.get('understanding', {}).get('blockers', [])]
    elif code in ('policy_check', 'quality_review', 'state_mismatch', 'revision_scope'):
        category, title = 'quality', '候选未通过内容检查'
        advice = '先查看具体候选、原话与品牌依据。模型写错报价或承诺时，不要为了放行去改客户原话；旧结果保留。'
        actions = [dict(action='understanding', label='核对本次理解'), dict(action='chat', label='对照聊天原话')]
    elif code == 'contact_policy':
        category, title = 'policy', '客户联系限制阻止了主动营销'
        advice = '请尊重该客户的联系选择；如客户主动咨询，改为回应本次问题。新建会话不会清除限制。'
        actions = [dict(action='profile', label='查看联系设置')]
    elif code in ('bad_context', 'unconfirmed_context', 'manual_source', 'voice_unknown', 'supplement_needs_text', 'bad_asset'):
        category, title = 'input', '聊天或补充资料需要先核对'
        advice = '到原图复核文字、角色和纳入范围；语音截图无法提供音频内容。只补充本次必需且已知的资料。'
        actions = [dict(action='chat', label='回到聊天复核'), dict(action='background', label='补充必要背景')]
    elif code in ('invalid_output', 'truncated', 'model_refusal', 'invalid_review'):
        category, title = 'output', '模型没有返回完整可用的三条消息'
        advice = '原始响应已保留；这不表示客户资料需要重填。先查看失败详情，再决定是否手动重新生成。'
        if code == 'invalid_review':
            title = '复核没有返回完整结论'
            advice = '候选和原始复核响应已保留，尚未通过复核，暂不可采用；无需为了响应格式错误改客户原话。'
            if validation_errors:
                title = '复核依据没有通过核对'
                advice = '下面列的是复核器自身的问题，不能当作已证实的候选缺陷。原候选和原复核保留；不要为了迎合错误复核改客户原话或品牌资料。'
    elif code == 'diagnostic_only':
        category, title = 'diagnostic', '原始输出的诊断复核（没有重新生成）'
        advice = '模型复核意见仍需对照品牌表，不能当作品牌授权或购买意愿证明。原始4条没有转为可用结果，不能复制发送。'
        for item in issues:
            item['title'] = '复核器意见 · ' + item['title']
    else:
        actions = [dict(action='understanding', label='核对当前资料')]
    output = record.get('parsed_output')
    messages = output.get('messages') if isinstance(output, dict) else None
    if code == 'invalid_output' and isinstance(messages, list) and len(messages) != 3:
        title = f'模型返回{len(messages)}条，整组暂未采用'
        advice = '需要恰好三条独立备选。没有自动删减、挑选或把自我纠错另当备选；这不是客户资料缺失，无需重填背景。'
        issues.insert(0, dict(title='输出数量',message=f'实际返回{len(messages)}条，要求3条。原始内容完整保留。',evidence=''))
    return dict(category=category, phase=phase, simulated=bool(record.get("simulated")), title=title, reason=error.get('message', ''), advice=advice, issues=issues, actions=actions, retry_allowed=retry, historical=record.get('app_version') not in (None, APP_VERSION), record_version=record.get('app_version'), presentation_version=APP_VERSION)
