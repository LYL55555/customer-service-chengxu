import re

VERSION = 'task-evidence-1.1.0'


def domains(text, prepared):
    from evidence_sources import claim_domains
    result = claim_domains(text)
    task = next((r['text'] for r in prepared.get('evidence_sources', {}).get('sources', []) if r['id'] == 'task.scenario'), '')
    if 'event' in result and task != '活动邀请' and not re.search(r'活动|场次|入场|席位|同行|活动地址|活动地点', text):
        result.discard('event')
    return result


def product_slice(source, text, products, focus, context_products=None):
    from product_evidence import extract, supported
    from quality import product_mentions
    _, identity, field = source['id'].split('.', 2)
    product = next((p for p in products if p['id'] == identity), None)
    if not product:
        return False
    atoms = extract(text, products, focus)
    if any((a.get('product') or {}).get('id') == identity and a['field'] == field and supported(a) for a in atoms):
        return True
    mentioned = {p['id'] for _, p in product_mentions(text, products)}
    if not mentioned and re.search(r'这(?:三|些|几)|三个|三款|哪种', text):
        mentioned = set(context_products or [])
    if identity not in (mentioned or set(focus or [])):
        return False
    fact = product['facts'].get(field, {})
    if fact.get('status') != 'known':
        return False
    if field == 'colors':
        return any(color in text for color in fact['value'])
    if field in ('capacity', 'card_slots'):
        return bool(re.search(r'收纳|怎么装|怎么用|分开放|卡片|银行卡|手机|资料|水杯', text))
    if field == 'limitations':
        return bool(re.search(r'淋雨|沾水|防水', text))
    if field == 'material':
        return bool(re.search(r'牛皮|皮面|材质', text))
    if field == 'closure':
        return fact['value'] in text or fact['value'] == '拉链' and bool(re.search(r'拉合|开合', text))
    return False


def event_exclusions(messages, prepared):
    sources = [r for r in prepared.get('evidence_sources', {}).get('sources', []) if r['kind'] in ('business_material', 'event') and r.get('authority') not in ('context_not_authorization', 'quoted_not_authorization')]
    errors = []
    for index, text in enumerate(messages):
        if 'event' not in domains(text, prepared):
            continue
        for match in re.finditer(r'(?:不讲|不介绍|不涉及|不包括|不包含)([^，。；！？]{2,14})', text):
            topic = re.split(r'也|所以|因此', match[1])[0]
            if not any(re.search(r'(?:不讲|不介绍|不涉及|不包括|不包含)' + re.escape(topic), s['text']) for s in sources):
                errors.append(dict(code='unsupported_event_exclusion', candidate_index=index, evidence=match[0], message='活动资料没有支持这项排除安排；可以介绍已知体验，不能从未提及推成明确不提供。'))
    return errors
