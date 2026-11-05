import re
from decimal import Decimal

VERSION='load-reference-1.0.1'
WEIGHT_LINK=r'(?:的重量|重量|总重|重|是|为|约|大约|大概|大致|差不多|重约|约重|约为|一共|总共|合计|共|就|加起来|合起来)'


def quantity_owner(text,start,end=None):
    prefix=text[:start].strip()
    if re.search(r'(?:两项|两者|小计|(?:空包|包)(?:本身)?(?:和|与|加上|加)(?:这瓶)?水)'+WEIGHT_LINK+r'{0,5}\s*$',prefix):return 'subtotal'
    if re.search(r'(?:总重|装好后|装物后).{0,10}(?:至少|超过|不止|大于|起码).{0,3}$',prefix):return 'lower_bound'
    if end is not None and re.match(r'(?:的)?(?:矿泉水|饮用水|白开水|水)(?!瓶|杯|壶)',text[end:]):return 'water'
    if re.search(r'(?:水|矿泉水|饮用水|白开水)(?:'+WEIGHT_LINK+r'|有){0,4}\s*$',prefix):return 'water'
    if re.search(r'(?:合计|加起来|合起来)'+WEIGHT_LINK+r'{0,4}\s*$',prefix):return 'subtotal'
    return 'product'


def build(value,prepared,products):
    from task_materials import FACETS
    from statement_scope import modality,clauses
    task=prepared.get('communication',{}).get('latest_text','')+'\n'+value.get('advisor_instruction','')
    active=bool(re.search(FACETS['weight'],task));rows=[]
    inputs=[('background.client_info',value.get('client_info',''))]
    inputs += [('chat.'+r['id'],r.get('text',''))for r in prepared.get('messages',[])if r.get('role')=='customer'and r.get('kind')=='text'and r.get('include',True)]
    for identity,text in inputs:
        for part in clauses(text):
            for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(毫升|mL|ml|升|L)(?:的)?(?:矿泉水|饮用水|白开水|水)(?!杯|瓶|壶)',part):
                if modality(part,match.start(),match.end())!='asserted'or re.search(r'以前|之前|过去|上次|不带|没带|不是|并非',part[:match.start()]):continue
                prefix=part[:match.start()];count=re.search(r'([一二两三四五六七八九\d]+)(?:瓶|杯|壶)\s*$',prefix)
                number=count[1]if count else'1';n=int(number)if number.isdigit()else dict(一=1,二=2,两=2,三=3,四=4,五=5,六=6,七=7,八=8,九=9).get(number)
                if not n:continue
                ml=Decimal(match[1])*(1000 if match[2]in('升','L')else 1)*n
                rows.append(dict(source_id=identity,source_quote=part,volume_ml=float(ml),bottles=n))
    volumes={r['volume_ml']for r in rows};records=[]
    if len(volumes)==1:
        water=rows[-1];volume=Decimal(str(water['volume_ml']))
        from understanding import build_understanding
        focus=build_understanding(value,prepared,products)['fields']['product']['ids']
        for product in products:
            fact=product['facts']['empty_weight_g']
            if product['id']not in focus or fact['status']!='known'or product['facts']['carry_modes']['status']!='known':continue
            empty=Decimal(str(fact['value']));subtotal=empty+volume
            amount=format(volume.normalize(),'f')
            text=f'空包约{empty:g}克，加上{amount}毫升水约{amount}克，两项小计约{subtotal/1000:g}公斤；另加水瓶和资料等实际携带物的重量。'
            records.append(dict(id='computed.load.'+product['id'],product_id=product['id'],empty_weight_g=float(empty),water_volume_ml=float(volume),water_weight_g=float(volume),subtotal_g=float(subtotal),text=text,excluded_components=['水瓶','资料等其他携带物'],parent_source_ids=['product.'+product['id']+'.empty_weight_g',water['source_id']],volume_source_quote=water['source_quote'],method='水按约1克/毫升估算；空包约重+明确水量约重，只计算这两项，不含容器及其他携带物',authority='bounded_component_calculation_not_full_loaded_weight'))
    return dict(version=VERSION,active=active,volume_sources=rows,records=records)


def inspect(messages,prepared,products):
    from statement_scope import clauses,modality
    reference=prepared.get('load_reference',{})
    records=reference.get('records',[]);issues=[]
    for index,text in enumerate(messages):
        for part in clauses(text):
            for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(公斤|千克|kg|克|g)(?![a-z])',part,re.I):
                if modality(part,match.start(),match.end())!='asserted':continue
                owner=quantity_owner(part,match.start(),match.end());before=part[:match.start()]
                complete=bool(re.search(r'(?:装好|装物后|装上这些|整体|整只包|总重|全部重量).{0,12}$',before))and owner not in('subtotal','lower_bound')
                if owner=='product'and not complete:continue
                if len(records)!=1 and owner!='lower_bound':
                    issues.append(dict(code='unsupported_load_calculation',candidate_index=index,evidence=part,message='没有明确水量的同对象计算依据，不能自行给水重、小计或装物总重。'));continue
                row=records[0]if len(records)==1 else None
                if complete:
                    issues.append(dict(code='partial_load_as_total',candidate_index=index,evidence=part,message='只有空包与水的两项小计，尚未包含水瓶和资料，不能说成完整装物总重。'));continue
                scale=Decimal(1000 if match[2].lower()in('公斤','千克','kg')else 1);number=Decimal(match[1]);actual=number*scale
                if row:expected=Decimal(str(row['water_weight_g']if owner=='water'else row['subtotal_g']))
                else:
                    ids=prepared.get('task_materials',{}).get('plan',{}).get('selected_product_ids',[]);selected=[p for p in products if p['id']in ids]
                    if len(selected)!=1:continue
                    expected=Decimal(str(selected[0]['facts']['empty_weight_g']['value']))
                tolerance=scale*Decimal('0.5')*Decimal(10)**number.as_tuple().exponent if re.search(r'约|大概|大约|差不多',before)else Decimal(0)
                wrong=actual>expected+tolerance+Decimal('.001')if owner=='lower_bound'else abs(actual-expected)>tolerance+Decimal('.001')
                if wrong:issues.append(dict(code='wrong_load_calculation',candidate_index=index,evidence=part,source_id=row['id']if row else'product.'+selected[0]['id']+'.empty_weight_g',expected_g=float(expected),message='当前水重、两项小计或已知重量下限与程序依据不符，后接试背建议也不能抵消错误数字。'))
    return issues
