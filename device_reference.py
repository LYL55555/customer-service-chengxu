import hashlib
import json
import re
from pathlib import Path
from decimal import Decimal

VERSION='device-reference-1.0.1'
MODEL=r'(?:iphone|苹果)\s*\d+\s*(?:pro\s*max|pro|plus|mini)?(?![a-z0-9])'


def canonical(text):return re.sub(r'[^a-z0-9]','',text.lower().replace('苹果','iphone'))


def load(path=None):
    data=json.loads((Path(path) if path else Path(__file__).with_name('reference_data')/'devices.json').read_text())
    for row in data['devices']:
        quote=row['source_quote']
        if hashlib.sha256(quote.encode()).hexdigest()!=row['source_quote_sha256']:raise ValueError('device source quote changed')
        for field,label in [('height','高度'),('width','宽度'),('depth','厚度')]:
            match=re.search(label+r'：\s*(\d+(?:\.\d+)?)\s*毫米',quote)
            if not match or float(match[1])!=row['bare_dimensions_mm'][field]:raise ValueError('device dimensions differ from official excerpt')
        if not row['source_url'].startswith('https://support.apple.com/'):raise ValueError('unverified device source')
    return data


def build(value,prepared,products):
    data=load();index={r['canonical']:r for r in data['devices']};queries=[]
    inputs=[('profile.preferences',prepared.get('customer_context',{}).get('preferences','')),('background.client_info',value.get('client_info',''))]
    inputs += [('supplement.'+str(i+1),row.get('text','')) for i,row in enumerate(prepared.get('supplements',[]))]
    inputs += [('chat.'+row['id'],row['text']) for row in prepared.get('messages',[]) if row['role']=='customer' and row['kind']=='text']
    active=[]
    for row in reversed(prepared.get('messages',[])):
        if row['role']=='advisor':break
        if row['role']=='customer':active.append(row.get('text',''))
    task='\n'.join(active)+'\n'+value.get('advisor_instruction','')
    relevant=bool(re.search(r'手机|iphone|苹果',task,re.I)) or not active and value.get('scenario')=='商品推荐'
    if not relevant:inputs=[]
    for identity,text in inputs:
        for match in re.finditer(MODEL,text,re.I):queries.append(dict(model_text=match[0],canonical=canonical(match[0]),source_id=identity,start=match.start(),end=match.end(),status='found' if canonical(match[0]) in index else 'not_in_verified_table'))
    records=[]
    for query in queries:
        row=index.get(query['canonical'])
        if row and row not in records:records.append(row)
    current=queries[-1]['canonical'] if queries else None;device=index.get(current);fits=[]
    from understanding import build_understanding
    focus=build_understanding(value,prepared,products)['fields']['product']['ids']
    if device:
        phone=sorted([n/10 for n in device['bare_dimensions_mm'].values()],reverse=True)
        bulky=bool(re.search(r'厚(?:壳|防摔)|防摔厚|带(?:卡包|支架|手柄)|外挂|外接',prepared.get('communication',{}).get('latest_text','')))
        for product in products:
            facts=product['facts']
            if product['id'] not in focus or facts['dimensions_cm']['status']!='known' or facts['carry_modes']['status']!='known':continue
            bag=sorted(facts['dimensions_cm']['value'],reverse=True)
            clear=all(a<=b*.8 for a,b in zip(phone,bag))
            fits.append(dict(id='fit.'+product['id']+'.'+current,product_id=product['id'],device_source_id=device['id'],device_model=device['model'],bare_dimensions_cm=[device['bare_dimensions_mm'][k]/10 for k in ('height','width','depth')],bag_outer_dimensions_cm=facts['dimensions_cm']['value'],comparison_margins_cm=[round(b-a,3) for a,b in zip(phone,bag)],ordinary_fit_judgment_supported=clear and not bulky,case_status='未提供具体壳尺寸，不能把裸机数字说成连壳数字',case_inference='明显余量且常规薄壳、无外接配件时，可说通常够放；不是特定壳实测或所有壳保证' if clear and not bulky else '特殊壳/配件或临界余量需针对该配件了解，不让客户重新量已知裸机',source_ids=[device['id'],'product.'+product['id']+'.dimensions_cm','product.'+product['id']+'.capacity'],method='常规形状三轴排序对比，各轴裸机不超过包外尺寸80%为明显余量线索；结合已知日常用途作通常判断，非内部实测/品牌认证。',customer_expression='通常够放；普通薄壳也通常够放' if clear and not bulky else '先答背法/已知容量，对特殊配件针对性确认'))
    return dict(version=VERSION,table_version=data['version'],table_sha256=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),lookup_mode='verified-local-table',queries=queries,current_model=current,records=records,fit_judgments=fits,authority='官方规格只证明裸机；派生适配是有边界的日常判断，不证明内尺寸、包口或所有保护壳；未收录不假装查询成功。')


def inspect(messages,prepared):
    from statement_scope import clauses,modality,owner
    reference=prepared.get('device_reference',{});current=reference.get('current_model')
    if not current:return [dict(code='unverified_device_model',candidate_index=i,evidence=m[0],message='当前没有这个型号的客户来源或已验证查询，不应替客户编手机型号。') for i,text in enumerate(messages) for m in re.finditer(MODEL,text,re.I)]
    device=next((r for r in reference['records'] if r['canonical']==current),None);issues=[]
    for index,text in enumerate(messages):
        for part in clauses(text):
            for match in re.finditer(r'(?P<n1>\d+(?:\.\d+)?)\s*(?P<u1>毫米|厘米|mm|cm)?\s*[×xX*]\s*(?P<n2>\d+(?:\.\d+)?)\s*(?P<u2>毫米|厘米|mm|cm)?\s*[×xX*]\s*(?P<n3>\d+(?:\.\d+)?)\s*(?P<u3>毫米|厘米|mm|cm)?',part,re.I):
                if modality(part,match.start(),match.end())!='asserted' or owner(part,match.start(),match.end(),'spec')!='customer_item':continue
                phone_cues=list(re.finditer(r'iphone|手机|裸机|机身',part[:match.start()],re.I));other_cues=list(re.finditer(r'电脑|文件夹|钱包|包身|包体|托特|肩包',part[:match.start()]))
                if not phone_cues or other_cues and other_cues[-1].start()>phone_cues[-1].start():continue
                named=list(re.finditer(MODEL,part[:match.start()],re.I))
                key=canonical(named[-1][0]) if named else current
                device=next((r for r in reference['records'] if r['canonical']==key),None)
                shell=list(re.finditer(r'连壳|带.{0,6}壳|手机壳|保护壳',part[:match.start()]));bare=list(re.finditer(r'裸机|机身',part[:match.start()]))
                if shell and (not bare or shell[-1].start()>bare[-1].start()):
                    issues.append(dict(code='invented_case_dimensions',candidate_index=index,evidence=match[0],message='官方来源是裸机尺寸，不能说成某个手机壳或连壳尺寸。'));continue
                if not device:
                    issues.append(dict(code='unverified_device_dimensions',candidate_index=index,evidence=match[0],message='该型号未收录于已验证资料表，不能凭模型记忆报尺寸。'));continue
                shared_unit=match['u3'] or match['u2'] or match['u1'] or ('cm' if max(Decimal(match[f'n{k}']) for k in (1,2,3))<30 else 'mm')
                approximate='约' in part[:match.start()] or '大概' in part[:match.start()]
                measurements=[]
                for k in (1,2,3):
                    number=Decimal(match[f'n{k}']);unit=(match[f'u{k}'] or shared_unit).lower()
                    scale=Decimal(10 if unit in ('cm','厘米') else 1)
                    tolerance=scale*Decimal('0.5')*Decimal(10)**number.as_tuple().exponent if approximate else Decimal(0)
                    measurements.append((number*scale,tolerance+Decimal('0.001')))
                measurements.sort(key=lambda row:row[0],reverse=True)
                expected=sorted([Decimal(str(n)) for n in device['bare_dimensions_mm'].values()],reverse=True)
                if any(abs(number-target)>tolerance for (number,tolerance),target in zip(measurements,expected)):
                    issues.append(dict(code='wrong_device_dimensions',candidate_index=index,evidence=match[0],source_id=device['id'],expected_mm=device['bare_dimensions_mm'],message='手机数字与同一份苹果官方裸机规格不符，不能使用旧示意数字或模型记忆。'))
    return issues
