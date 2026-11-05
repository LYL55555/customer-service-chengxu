import copy
import json
import re

from engine import GenerationError, digest
from quality import money_value, product_mentions

SUMMARY_VERSION = 'evidence-summary-0.5.0'
AMOUNT = r'\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:万)?|[零〇一二两三四五六七八九十百千万]+'


def clean_corrections(value, products):
    if value is None or value == {}:
        return {}
    if not isinstance(value, dict) or set(value) - {'source_hash', 'product_ids', 'question', 'budget', 'use'}:
        raise GenerationError('bad_understanding', '理解修正格式不正确，请按原文恢复后重新核对。')
    if not isinstance(value.get('source_hash'), str) or not re.fullmatch('[a-f0-9]{64}', value['source_hash']):
        raise GenerationError('bad_understanding', '请先整理本次理解，再补充修正。')
    result = {'source_hash': value['source_hash']}
    if 'product_ids' in value:
        ids = value['product_ids']
        if not isinstance(ids, list) or len(ids) > 3 or any(not isinstance(identity, str) for identity in ids) or len(set(ids)) != len(ids) or any(identity not in {row['id'] for row in products} for identity in ids):
            raise GenerationError('bad_understanding', '请从品牌商品中选择，或标记尚不确定。')
        result['product_ids'] = ids
    for field, maximum in [('question', 1000), ('budget', 500), ('use', 1000)]:
        if field in value:
            if not isinstance(value[field], str) or len(value[field]) > maximum:
                raise GenerationError('bad_understanding', '理解修正内容过长，请简写。')
            if value[field].strip():
                result[field] = value[field].strip()
    return result if len(result) > 1 else {}


def evidence(message, field='chat'):
    return dict(field=field, message_id=message.get('id'), role=message.get('role'), text=message.get('text', ''))


def budget_in(text, source):
    text = ''.join(text.split())
    if re.match(r'^(引用|转述|别人说)[：:]', text):
        return []
    uncertain = bool(re.search(r'预算.{0,8}(未明确|没说|不清楚|未提供|不确定|未知|可能|待确认)|(?:没说|未明确|未提供).{0,4}预算', text))
    found = []
    for match in re.finditer(r'预算(?:上限)?(?:改为|改成|调整为|调整到|为|是|在|约|大约|控制在|最多|不超过|：|:)?\s*(' + AMOUNT + r')\s*(?:元|人民币)?', text):
        raw = match[1]
        trailing = text[match.end():match.end()+12]
        denied = bool(re.search(r'不是|并非|没说|不代表', text[max(0,match.start()-8):match.start()]))
        ranged = bool(re.match(r'[-—至到~～]', trailing) or re.search(r'一两|两三|三四|四五', raw))
        try:
            amount = None if uncertain or ranged or denied else money_value(raw)
        except (ValueError, OverflowError):
            amount = None
        found.append(dict(amount=amount, raw=match[0], source=source, uncertain=uncertain or ranged or denied))
    if not found and uncertain:
        found.append(dict(amount=None, raw=text, source=source, uncertain=True))
    return found


def build_understanding(value, prepared, products):
    rows = [row for row in prepared.get('messages', []) if row.get('include', True)]
    source_hash = digest(json.dumps(dict(context_hash=prepared.get('context_hash'), messages=rows, client_info=value.get('client_info', ''), related_info=value.get('related_info', ''), supplements=prepared.get('supplements', []),preferences=prepared.get('customer_context',{}).get('preferences','')), ensure_ascii=False, sort_keys=True))
    corrections = clean_corrections(value.get('understanding_corrections'), products)
    customers = [row for row in rows if row.get('role') == 'customer']
    latest = customers[-1] if customers else None
    current_turn = [latest] if latest else []
    if latest and latest.get('kind') == 'text':
        for earlier in reversed(rows[:rows.index(latest)]):
            if earlier.get('role') != 'customer' or earlier.get('kind') != 'text':
                break
            current_turn.insert(0, earlier)
    last_text = '\n'.join(row.get('text', '') for row in current_turn) if latest and latest.get('kind') == 'text' else ''
    question = dict(text='\n'.join(''.join(row.get('text', '').split()) for row in current_turn) if last_text else ('最新一条是未转写语音，内容未知' if latest and latest.get('kind') == 'voice' else '尚无可确定的客户问题，可补充背景或按当前场景开始'), status='stated' if last_text else 'unknown', evidence=[evidence(row) for row in current_turn])
    topic_words = [('重量/自重', r'自重|重量|多重|多少克'), ('肩背/背法', r'肩背|背法|怎么背|斜挎'), ('尺寸/容量', r'尺寸|容量|能放|放得下|放不下'), ('价格/预算', r'多少钱|售价|价格|预算|折扣|打折')]
    question['topics'] = [label for label, pattern in topic_words if re.search(pattern, last_text)]
    explicit = list(dict.fromkeys(row['id'] for _, row in product_mentions(last_text, products)))
    intents = prepared.get('state_check', {}).get('product_intents', [])
    rejected = list(dict.fromkeys(row['product_id'] for row in intents if row.get('intent')=='declined'))
    explicit = [identity for identity in explicit if identity not in rejected]
    product_sources, candidates, status = [], explicit, 'stated' if explicit else 'unknown'
    if len(explicit) > 1:
        intents = prepared.get('state_check', {}).get('product_intents', [])
        interested = list(dict.fromkeys(row['product_id'] for row in intents if row.get('intent') in ('question', 'interested')))
        if len(interested) == 1:
            candidates, status = interested, 'inferred'
    if explicit and latest:
        product_sources = [evidence(latest)]
    elif last_text:
        earlier = [row for row in rows if row.get('kind') == 'text']
        named = [(row, product) for row in earlier for _, product in product_mentions(row.get('text', ''), products)]
        known = list(dict.fromkeys(product['id'] for _, product in named if product['id'] not in rejected))
        if len(known) == 1:
            candidates, status = known, 'inferred'
            product_sources = [evidence(named[-1][0])]
    selected=[identity for identity in value.get('product_ids',[]) if identity not in rejected]
    if not candidates and len(selected)==1:
        candidates,status=selected,'selected'
        product_sources=[dict(field='product_ids',text=selected[0],role='advisor')]
    product = dict(ids=candidates, names=[row['name'] for row in products if row['id'] in candidates], status=status, evidence=product_sources, rejected_ids=rejected)
    chat_budgets = []
    for row in customers:
        if row.get('kind') == 'text':
            values = budget_in(row.get('text', ''), evidence(row))
            if values:
                chat_budgets = values
    background = budget_in(value.get('client_info', ''), dict(field='client_info', text=value.get('client_info', ''), role='advisor'))
    chosen = chat_budgets or background
    amounts = list(dict.fromkeys(row['amount'] for row in chosen if row['amount'] is not None))
    budget = dict(text=f'{amounts[0]:,}元' if len(amounts) == 1 and not any(row['uncertain'] for row in chosen) else '范围或金额待核对' if chosen else '未明确；若本次只答商品问题，无需额外追问', amount=amounts[0] if len(amounts) == 1 else None, status='stated' if len(amounts) == 1 else 'uncertain' if chosen else 'unknown', evidence=[row['source'] for row in chosen], observations=chosen)
    blockers = []
    combined = {row['amount'] for row in chat_budgets + background if row['amount'] is not None}
    if len(combined) > 1:
        budget['status'] = 'conflict'
        budget['text'] = '聊天与本次背景出现不同预算：' + ' / '.join(f'{amount:,}元' for amount in sorted(combined))
        blockers.append(dict(field='budget', message='聊天与背景的预算不一致，请明确哪一个适用于本次；不会直接重试生成。', evidence=chat_budgets + background))
    uses = [row for row in customers if row.get('kind') == 'text' and re.search(r'通勤|周末|上班|A4|水杯|水瓶|手机|钥匙|口红|送礼', row.get('text', ''))]
    use = dict(text='；'.join(''.join(row['text'].split()) for row in uses[-2:]) or '未明确；只在影响这次回复时再确认', status='stated' if uses else 'unknown', evidence=[evidence(row) for row in uses[-2:]])
    if value.get('client_info', '').strip():
        use['text'] += '\n顾问补充：' + value['client_info'].strip()
        use['evidence'].append(dict(field='client_info',text=value['client_info'].strip(),role='advisor'))
        use['status'] = 'mixed'
    preferences=prepared.get('customer_context',{}).get('preferences','').strip()
    if preferences:
        use['text']+='\n客户长期偏好：'+preferences
        use['evidence'].append(dict(field='customer_preferences',text=preferences,role='advisor'))
        use['status']='mixed'
    fields = dict(product=product, question=question, budget=budget, use=use)
    if corrections:
        if corrections['source_hash'] != source_hash:
            blockers.append(dict(field='corrections', message='原文或背景已变化，以前的理解修正需要重新核对。'))
        else:
            for key in ('question', 'budget', 'use'):
                if key in corrections:
                    fields[key] = dict(text=corrections[key], status='advisor', evidence=[dict(field='understanding_corrections', text=corrections[key], role='advisor')], original=copy.deepcopy(fields[key]))
                    if key == 'budget':
                        blockers = [item for item in blockers if item['field'] != 'budget']
            if 'product_ids' in corrections:
                fields['product'] = dict(ids=corrections['product_ids'], names=[row['name'] for row in products if row['id'] in corrections['product_ids']], status='advisor', evidence=[dict(field='understanding_corrections', text='顾问修正当前商品', role='advisor')], original=product)
    notices = []
    simple_answer=bool(re.search(r'多少钱|售价|价格|打折|折扣|容量|能放|放得下|材质|自重|多重|尺寸',last_text) and not re.search(r'预算|推荐|选哪|挑选|适合|买哪',last_text))
    if simple_answer and any(row['field']=='budget' for row in blockers):
        blockers=[row for row in blockers if row['field']!='budget']
        notices.append('预算来源有冲突，但不影响当前参数或价格问题；这次不据此判断预算匹配，无需先补齐。')
    if product['status'] == 'inferred':
        notices.append('商品根据前文推定，可对照来源纠正；不是新的客户陈述。')
    if set(value.get('product_ids', [])) - set(fields['product']['ids']) and fields['product']['ids']:
        notices.append('相关商品勾选含其他款式；不会用旧勾选覆盖最新客户问题。')
    if any(row.get('kind') == 'voice' for row in rows):
        notices.append('存在未转写语音，不把语音内容当作已知事实。')
    from statement_scope import direction
    communication=direction(value,prepared)
    if communication['mode']=='needs_confirmation':
        notices.append(communication['basis']+'；'+communication['confirmation_hint'])
        if prepared.get('customer_context',{}).get('marketing_opt_out'):blockers.append(dict(field='contact',message='客户有营销拒收设置，需先确认这是不是本次主动来信。'+communication['confirmation_hint']))
    from delivery import assess
    return dict(version=SUMMARY_VERSION, source_hash=source_hash, fields=fields, blockers=blockers, notices=notices, corrections=corrections, communication=communication, readiness=assess(value,prepared),scope='仅本次会话；不更新客户长期偏好', authority='原话与顾问补充的证据摘要；推定仅作线索，不能代替独立语义复核')
