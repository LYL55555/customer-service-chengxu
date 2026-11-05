import json
import re
from pathlib import Path

VERSION = 'product-evidence-0.2.1'


def load(rules,products,path=None):
    data=json.loads((Path(path) if path else Path(__file__).with_name('product_evidence.json')).read_text())
    if data['version']!=VERSION or data['brand_version']!='v0.4' or {p['id'] for p in data['products']}!={p['id'] for p in products}:raise ValueError('product evidence version')
    for quote in data['sources'].values():
        if quote not in rules:raise ValueError('product evidence source changed')
    for fact in data.get('service_facts',{}).values():
        if fact['status'] not in ('known','unknown') or fact['source_quote'] not in data['sources'][fact['source_id']] or fact['status']=='unknown' and fact['value'] is not None:raise ValueError('service evidence source')
    by_id={p['id']:p for p in data['products']}
    for product in products:
        aliases=by_id[product['id']]['aliases']
        if not aliases or any(not isinstance(alias,str) or not alias or alias not in product['name'] for alias in aliases):raise ValueError('product aliases')
        product['aliases']=aliases
        facts=by_id[product['id']]['facts']
        if set(facts)!=set(data['labels']):raise ValueError('product evidence fields')
        for fact in facts.values():
            if fact['status'] not in ('known','unknown') or not fact['source_quote'] or fact['source_quote'] not in data['sources'][fact['source_id']]:raise ValueError('product evidence source')
            if fact['status']=='unknown' and fact['value'] is not None:raise ValueError('unknown is not negative')
        if facts['price']['value']!=product['price']:raise ValueError('product evidence price')
        product['facts']=facts
    return data


def reference(product,field):
    fact=product['facts'][field]
    return dict(product_id=product['id'],field=field,status=fact['status'],value=fact['text'])


def claims(text):
    from statement_scope import modality, owner
    found=[]
    def add(pattern,field,value):
        for match in re.finditer(pattern,text,re.I):
            resolved=field
            prefix=text[:match.start()]
            if field=='dimensions_cm':
                if re.search(r'(?:内尺寸|内部尺寸|包内(?:尺寸|空间)?|内腔).{0,8}$',prefix):resolved='inner_dimensions_cm'
                elif re.search(r'(?:包口|开口|袋口).{0,8}$',prefix):resolved='opening_dimensions_cm'
            if field=='closure' and match[0] in ('拉链','磁扣','敞口') and not re.search(r'(?:配有|采用|使用|带有|设有|没有|不使用|无|有|为|是)$',prefix[-8:]) and not re.match(r'开合|闭合|结构|设计',text[match.end():]):continue
            if modality(text,match.start(),match.end())!='asserted':continue
            if field=='loaded_comfort' and re.search(r'您(?:说|提到|觉得|反馈)|听您(?:这么)?说',prefix[-14:]):continue
            historical=re.search(r'(?:上次|之前|曾经|当时).{0,16}(?:看过|看了|看的|看中的|试过|试了)|(?:上次|之前).{0,8}(?:您)?在店里看',text[:match.end()]) if field=='colors' else None
            if historical and not re.search(r'现在|目前|这次|本次|可选|有|提供',text[historical.end():match.start()]):continue
            if owner(text,match.start(),match.end(),'spec') in ('customer_item','competitor'):continue
            if field in ('empty_weight_g','dimensions_cm'):
                if field=='empty_weight_g':
                    from load_reference import quantity_owner
                    if quantity_owner(text,match.start(),match.end())in('water','subtotal','lower_bound'):continue
                if re.search(r'您(?:提到|说|称)|客户|您希望|能接受',prefix):continue
                if field=='dimensions_cm' and re.search(r'(?:手机|电脑|水杯|文件夹|钱包).{0,6}(?:尺寸|大小|长宽)',prefix):continue
                if field=='dimensions_cm' and re.search(r'(?:您|客户)(?:给的|给出的|提供的|报的)',prefix) and not re.search(r'包|本品|产品',prefix):continue
                if field=='empty_weight_g' and re.search(r'装物后|装好后|装入.{0,12}后|装好|装物总重|负重后',prefix):resolved='loaded_weight_g'
            resolved_value=value(match)
            if field=='a4_fit' and re.search(r'没有|无',prefix[-3:]):resolved_value=False
            found.append(dict(field=resolved,value=resolved_value,evidence=match[0],start=match.start()))
    add(r'(?:肩带(?:长度)?(?:为|是)?[^，。；！？（）()]{0,8}?(?:不可调节|不能调节|无法调节|不能调整|无法调整|不可调整|可以调整|可调整|不能调|不可调|固定|可以调节|可调节|能调节|可调|调节长度)|(?:没有|无)(?:可调(?:节)?(?:长度)?的?)肩带|可调(?:节)?肩带)', 'strap_adjustable',lambda m:not bool(re.search(r'不可|不能|无法|没有|无|固定|并非|不是',m[0])))
    add(r'(?:没有|无|不使用)?拉链(?:开合)?|磁扣(?:开合)?|敞口(?:设计)?','closure',lambda m:'非拉链' if re.match(r'没有|无|不使用',m[0]) else '拉链' if '拉链' in m[0] else '磁扣' if '磁扣' in m[0] else '敞口')
    add(r'(?:不能|不可|不支持|只能|仅能|可|可以|支持)?(?:肩背|斜挎)','carry_modes',lambda m:dict(mode='斜挎' if '斜挎' in m[0] else '肩背',positive=not bool(re.match(r'不能|不可|不支持',m[0])),exclusive=bool(re.match(r'只能|仅能',m[0]))))
    add(r'(?:放不下|不能放|可放下|可放|能放下|能放|容纳)\s*A4(?:纸质)?(?:资料)?','a4_fit',lambda m:not bool(re.match(r'放不下|不能放',m[0])))
    add(r'没有内衬|无内衬|内衬(?:是|为)?(?:棉布|真皮|涤纶|尼龙)','lining',lambda m:False if re.match(r'没有|无',m[0]) else m[0].replace('内衬','').lstrip('是为'))
    add(r'羊皮|牛皮|鳄鱼皮','material',lambda m:m[0])
    add(r'(?:没有|无|有)(?:单独的?|专门的?)?零钱袋','coin_pocket',lambda m:m[0].startswith('有'))
    add(r'(?:有|提供|可选|颜色(?:为|是)?)(?:墨黑|暖棕|米白|栗棕)|(?:墨黑|暖棕|米白|栗棕)款','colors',lambda m:re.search(r'墨黑|暖棕|米白|栗棕',m[0])[0])
    add(r'全手工|纯手工|手工制作','craft',lambda m:m[0])
    add(r'(?:肩带|受力|重物位置)[^，。；！？]{0,20}(?:减轻肩部压力|分散压力|更舒服|更省力)','loaded_comfort',lambda m:m[0])
    add(r'(?:约)?(\d+(?:\.\d+)?)\s*(?:克|g)(?![a-z])','empty_weight_g',lambda m:float(m[1]))
    add(r'(\d+(?:\.\d+)?)\s*[×x*]\s*(\d+(?:\.\d+)?)\s*[×x*]\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?','dimensions_cm',lambda m:[float(m[i]) for i in (1,2,3)])
    for field,pattern in [('inner_flat_pockets',r'(\d+)个平口袋'),('card_slots',r'(\d+)个(?:独立)?卡位')]:add(pattern,field,lambda m:int(m[1]))
    return sorted(found,key=lambda row:row['start'])


def comfort_guarantees(text):
    from statement_scope import modality
    from quality import negated
    rows=[]
    feeling=r'(?:不累|不会累|不会吃力|不吃力|不费力|轻松|舒服|舒适|不压肩|没有负担)'
    patterns=[r'(?:保证|确保|绝对|一定|肯定|永远|始终)[^。；;！？!?\n]{0,20}'+feeling,r'(?:不管|无论|不论|装多少|背多久|任何人|所有人|谁背)[^。；;！？!?\n]{0,45}(?:都|也|总是)[^。；;！？!?\n]{0,10}'+feeling,r'(?:背|走|步行).{0,8}(?:一整天|多久|多远|再久).{0,8}(?:都|也)'+feeling]
    for part in re.split(r'[。；;！？!?\n]',text):
        for pattern in patterns:
            for match in re.finditer(pattern,part):
                if not negated(part[:match.start()]) and not re.search(r'不一定|未必|不保证|不能保证',match[0]) and modality(part,match.start(),match.end())=='asserted':rows.append(dict(evidence=match[0]))
    return rows


def extract(text,products,focus_ids=None,reference_text=''):
    from quality import product_mentions,scoped_product_clauses
    selected=[p for p in products if p['id'] in (focus_ids or [])]
    current=selected[0] if len(selected)==1 else None
    rows=[]
    for clause,named,current in scoped_product_clauses(text,products,current):
        for claim in claims(clause):
            preceding=[p for pos,p in named if pos<=claim['start']]
            product=preceding[-1] if preceding else named[0][1] if len(named)==1 else current
            if not preceding and len(selected)>1 and re.search(r'两款|这两|两件|这几款|都',clause[:claim['start']]):
                rows.extend(dict(claim,product=p) for p in selected)
                continue
            rows.append(dict(claim,product=product))
    references=[]
    for _,product in product_mentions(reference_text,products):
        if product not in references:references.append(product)
    if len(references)==2 and re.search(r'两者|二者|两款|这两',text) and '分别' in text:
        for field in ('empty_weight_g','dimensions_cm'):
            pending=[row for row in rows if row['field']==field and row['product'] is None]
            if len(pending)==2:
                for row,product in zip(pending,references):row['product']=product
    return rows


def inspect(text,products,focus_ids=None,candidate_index=None,reference_text=''):
    issues=[]
    from statement_scope import clauses,modality
    for row in comfort_guarantees(text):
        issues.append(dict(code='unsupported_comfort_guarantee',candidate_index=candidate_index,evidence=row['evidence'],message='无条件或全人群的舒适保证没有依据；结合已知重量、携带物和步行情境的日常判断不属于此项。'))
    for part in clauses(text):
        for m in re.finditer(r'(?:属于|归为|算是).{0,5}(?:偏轻|轻量|轻型)|(?:中等|同类|同档|一般|普通).{0,5}偏轻',part):
            if modality(part,m.start(),m.end())!='asserted':continue
            if re.search(r'不.{0,3}(?:称|算|保证)|不能.{0,4}(?:称|保证)|没有.{0,5}基准',part[:m.start()]):continue
            if not re.search(r'包|克|750|420|45|重量|自重|空包',part) and not focus_ids:continue
            issues.append(dict(code='unsupported_weight_judgment',candidate_index=candidate_index,evidence=part,message='没有轻重分级或比较基准，单款自重不能变成轻重等级分类。'))
    for match in re.finditer(r'比(?:一般|普通|常见|同类)(?:的)?[^，,。；;！？!?]{0,12}?(?:更轻|更重|有分量|轻便|耐用|高级|划算|轻|重)',text):
        prefix=text[max(0,match.start()-10):match.start()]
        if re.search(r'(?:不能|无法|不便|不宜|没有依据|未有依据).{0,5}$',prefix):continue
        issues.append(dict(code='unsupported_comparison',candidate_index=candidate_index,evidence=match[0],message='没有一般、普通或同类商品的比较基准，不能由单款参数推出轻重、品质或价值优势。'))
    for claim in extract(text,products,focus_ids,reference_text):
        if claim['field']=='loaded_comfort' and claim['evidence'] in reference_text:
            position=text.find(claim['evidence'])
            if re.search(r'您(?:说|提到|觉得|反馈)|听您(?:这么)?说',text[max(0,position-14):position]):continue
        product=claim['product']
        if not product or 'facts' not in product:
            issues.append(dict(code='unresolved_product_fact',candidate_index=candidate_index,evidence=claim['evidence'],message='该商品断言没有明确对应商品，请先核对当前对象；未按旧勾选猜测。'))
            continue
        fact=product['facts'][claim['field']]
        known=fact['status']=='known'
        if supported(claim):continue
        message=f"{product['name']}的{claim['field']}依据为：{fact['text']}；该断言没有同一商品资料支持，未知不能解释成没有。"
        issues.append(dict(code='unsupported_product_fact' if not known or claim['field']=='carry_modes' else 'wrong_product_fact',candidate_index=candidate_index,product_id=product['id'],field=claim['field'],evidence=claim['evidence'],expected=fact['text'],fact_ref=reference(product,claim['field']),source_quote=fact['source_quote'],message=message))
    return issues


def supported(claim):
    product=claim.get('product')
    if not product or 'facts' not in product:return False
    fact=product['facts'][claim['field']]
    if fact['status']!='known':return False
    value=claim['value']
    if claim['field']=='material':return fact['value'].endswith(value)
    if claim['field']=='colors':return value in fact['value']
    if claim['field']=='carry_modes':return value['positive'] and not value['exclusive'] and value['mode'] in fact['value']
    return fact['value']==value


def covers(claim,ref):
    product=claim.get('product')
    if not product or ref.get('product_id')!=product['id'] or claim['evidence'] not in ref.get('claim_quote',''):return False
    fact=product['facts'].get(ref.get('field'))
    if not fact or ref.get('status')!=fact['status'] or ref.get('value')!=fact['text']:return False
    if ref['field']==claim['field']:return True
    if fact['status']!='known':return False
    return any(atom['field']==claim['field'] and atom['value']==claim['value'] for atom in claims(fact['text']))


def evidence_coverage(messages,checks,products,focus_ids=None):
    rows=[]
    for index,text in enumerate(messages):
        refs=list(checks.get(f'reply_{index+1}',{}).get('fact_checks',[]))
        for ref in checks.get(f'reply_{index+1}',{}).get('source_checks',[]):
            parts=ref.get('source_id','').split('.')
            product=next((p for p in products if len(parts)==3 and p['id']==parts[1]),None)
            if parts and parts[0]=='product' and product and parts[2] in product['facts']:
                refs.append(dict(reference(product,parts[2]),claim_quote=ref.get('claim_quote','')))
        for claim in extract(text,products,focus_ids):
            witness=next((ref for ref in refs if covers(claim,ref)),None)
            valid=supported(claim)
            rows.append(dict(candidate_index=index,evidence=claim['evidence'],product_id=claim['product']['id'] if claim['product'] else None,field=claim['field'],supported=valid,method='reviewer-source-reference' if witness else 'deterministic-product-index' if valid else 'unverified',source=reference(claim['product'],claim['field']) if claim['product'] else None,reviewer_reference=witness))
    return rows


def topics(text):
    result=[]
    if re.search(r'自重|多重|重量|多少克',text):result.append('weight')
    if re.search(r'尺寸|多大|长宽',text):result.append('dimensions')
    if re.search(r'肩背.{0,10}(?:方便|合适|使用)',text):result.append('shoulder_use')
    if re.search(r'肩背.{0,10}(?:舒服|舒适)|背.{0,6}累|舒不舒服|负重|费劲|吃力|会不会太沉',text):result.append('personal_comfort')
    elif re.search(r'背法|怎么背|能.{0,3}斜挎',text):result.append('carry')
    return result


def coverage(text,question):
    result={}
    patterns={'weight':r'(?:约)?\d+(?:\.\d+)?\s*(?:克|g)','dimensions':r'\d+(?:\.\d+)?\s*[×xX]\s*\d+(?:\.\d+)?\s*[×xX]\s*\d+(?:\.\d+)?','carry':r'肩背|斜挎','shoulder_use':r'肩背|上肩','personal_comfort':r'试背|试一试|试一下|试一次|背着.{0,10}(?:走|感受)|(?:舒适度|舒不舒服|累不累|感受).{0,10}(?:因人|个人|实际|负重|装物)|不会太吃力|不算.{0,5}(?:负担|吃力)|(?:日常|通勤|步行).{0,20}(?:合适|问题不大)|不能保证.{0,6}(?:舒服|轻松|不累)'}
    for topic in topics(question):
        hits=[m[0] for m in re.finditer(patterns[topic],text,re.I) if not re.search(r'不能|无法|没有',text[max(0,m.start()-4):m.start()])]
        if hits:result[topic]=hits
    return result


def for_model(data):
    return dict(version=data['version'],authority=data['authority'],labels=data['labels'],sources=data['sources'],service_facts=data.get('service_facts',{}),price_basis=data['sources']['common.price_basis'],products=[dict(id=p['id'],aliases=p['aliases'],facts={field:dict(status=f['status'],value=f['text'],source_id=f['source_id']) for field,f in p['facts'].items()}) for p in data['products']])
