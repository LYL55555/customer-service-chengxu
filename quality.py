import re

CHECK_VERSION = "1.5.1"


def unknown_cleaner_in(text):
    return bool(re.search(r'(?:不清楚|不知道|不明|未知|不确定|不详|不认识).{0,12}(?:成分|配方|清洁剂)|(?:成分|配方).{0,8}(?:不清楚|不知道|不明|未知|不确定|不详)|(?:这瓶|手头|家里).{0,8}清洁剂',text))


def stain_advice(text,reference):
    from statement_scope import clauses,modality,prohibits_action
    if not unknown_cleaner_in(reference) or not re.search(r'污渍|污点|蹭|脏',reference):return []
    issues=[]
    for clause in clauses(text):
        for match in re.finditer(r'(?:用|拿|先|可以).{0,18}(?:软布|干布|纸巾).{0,10}(?:擦|拂|搓)|干擦|擦拭|轻拂|搓洗',clause):
            if modality(clause,match.start(),match.end())=='asserted' and not prohibits_action(clause,match.start(),match.end()):
                issues.append(dict(code='unsupported_stain_treatment',evidence=clause,message='当前为污渍与未知清洁剂咨询，没有本案去渍操作依据；沾水吸干不能授权干擦或拂擦污渍。'))
    return issues


def product_mentions(text, products):
    aliases = {}
    for product in products:
        for name in product.get("aliases", [product["name"]] + [suffix for suffix in ("托特包", "肩包", "卡夹") if product["name"].endswith(suffix)]):
            aliases.setdefault(name, []).append(product)
    mentions = []
    occupied = []
    for name in sorted(aliases, key=len, reverse=True):
        if len(aliases[name]) != 1:
            continue
        for match in re.finditer(re.escape(name), text):
            if any(start <= match.start() and match.end() <= end for start, end in occupied):
                continue
            mentions.append((match.start(), aliases[name][0]))
            occupied.append(match.span())
    return sorted(mentions, key=lambda item: item[0])


def negated(prefix):
    prefix = prefix[-12:]
    match = re.search(r"((?:(?:不能|无法|没法|不会|并非|不是|没有|不|未)(?:直接|随意|擅自|再|先|马上|这样|向您)?)+)$", prefix)
    if not match:
        return False
    words = re.findall(r"不能|无法|没法|不会|并非|不是|没有|不|未", match[1])
    return len(words) % 2 == 1


def money_value(raw):
    cleaned = raw.replace(",", "").replace("，", "").replace(" ", "")
    if re.fullmatch(r"[零〇一二两三四五六七八九十百千万]+", cleaned):
        digits = dict(zip("零〇一二两三四五六七八九", (0,0,1,2,2,3,4,5,6,7,8,9)))
        units = {"十":10,"百":100,"千":1000,"万":10000}
        total = section = number = 0
        for char in cleaned:
            if char in digits:
                number = digits[char]
            elif char == "万":
                total += (section + number) * 10000
                section = number = 0
            else:
                section += (number or 1) * units[char]
                number = 0
        return total + section + number
    return round(float(cleaned[:-1]) * 10000) if cleaned.endswith("万") else round(float(cleaned))


def scoped_product_clauses(text,products,initial=None):
    from statement_scope import clauses
    current=initial;anchor=None;previous_subject=None
    for clause in clauses(text):
        named=product_mentions(clause,products)
        comparison=re.search(r'比|相较于|相比于|相对于',clause)
        subjects=[row for row in named if comparison and row[0]<comparison.start()]
        if comparison and named:
            named=subjects
        subject=previous_subject if previous_subject and re.match(r'^(?:它|这款|这个包|该款)',clause.strip()) else current
        yield clause,named,subject
        if named:
            proposed=re.search(r'建议|推荐|我会选|我更选',clause)
            historical=re.search(r'之前|原先|上次|过去',clause)
            if len({row['id'] for _,row in named})==1 and proposed and not negated(clause[:proposed.start()]) and not historical:anchor=named[0][1]
            previous_subject=named[-1][1]
            excluded=re.search(r'不适合|不合适|不考虑|放不下|不能放|不推荐|不建议',clause)
            current=anchor if anchor and named[-1][1]['id']!=anchor['id'] and excluded else named[-1][1]
        else:previous_subject=subject


def total_quantity(prefix):
    match=re.search(r'([一二两三四五六七八九十\d]+)(?:只|件|个)(?:的)?(?:就是|合计(?:是|为)?|总计(?:是|为)?|一共|共计|共|是|为)?\s*$',prefix)
    return money_value(match[1]) if match else None


def price_bindings(text, products, selected_ids=None, focus_ids=None):
    from statement_scope import clauses, modality, owner, rejected_offer
    selected = [product for product in products if product['id'] in (focus_ids if focus_ids is not None else selected_ids or [])]
    bindings = []
    cursor=0
    for clause,named,current_product in scoped_product_clauses(text,products):
        offset=text.find(clause,cursor);cursor=offset+len(clause)
        for match in re.finditer(r"(?:[¥￥]\s*)?(\d{1,3}(?:[,，]\d{3})+|\d{4,6}|\d+(?:\.\d+)?万|[零〇一二两三四五六七八九十百千万]+(?=元))\s*(?:元|人民币)?", clause):
            prefix = clause[:match.start()]
            if total_quantity(prefix) is not None:continue
            if negated(prefix) or rejected_offer(clause,match.start(),match.end()) or modality(clause,match.start(),match.end()) != 'asserted' or owner(clause,match.start(),match.end(),'money') in ('budget','competitor','customer_item','customer_reference','order','rejected_price'):
                continue
            price_cues = [found.start() for found in re.finditer(r'价格|售价|标价|报价|现价', prefix)]
            other_cues = [found.start() for found in re.finditer(r'预算|别家|另一款|对方|实付|退款|差价|您(?:提到|说)', prefix)]
            if (other_cues and (not price_cues or max(other_cues) > max(price_cues))) or re.match(r'(?:的)?预算', clause[match.end():]):
                continue
            preceding = [entry for entry in named if entry[0] < match.start()]
            product = preceding[-1][1] if preceding else current_product
            product = product or (selected[0] if len(selected) == 1 and re.search(r'这款|价格|售价|标价|报价|现价|(?:按|以)$', prefix) else None)
            amount = money_value(match[1])
            bindings.append(dict(evidence=match[0],clause=clause,start=offset+match.start(),end=offset+match.end(),value=amount,expected=product['price'] if product else None,product_id=product['id'] if product else None,product_name=product['name'] if product else None,source_id='product.'+product['id']+'.price' if product else None))
    return bindings


def verified_catalog_prices(text, products, focus_ids=None):
    from evidence_sources import claim_domains
    if claim_domains(text).intersection({'service','event'}) or re.search(r'[一二三四五六七八九十\d]+(?:[.点]\d+)?折|折扣|优惠|议价|赠品|免邮|分期|旧价|实付|退款|定金|不含税|税前|成本|差价|竞品|别家|另一家|对方', text):
        return []
    bindings = price_bindings(text,products,focus_ids=focus_ids)
    return bindings if bindings and all(row['product_id'] and row['value'] == row['expected'] for row in bindings) else []


def inspect_messages(messages, products, selected_ids=None, expected_state=None, focus_ids=None, context=None):
    from statement_scope import clauses, modality, owner, completed_actions, rejected_offer
    issues = []
    from load_reference import inspect as inspect_load
    issues.extend(inspect_load(messages,(context or {}).get('prepared',{}),products))
    selected = [product for product in products if product["id"] in (focus_ids if focus_ids is not None else selected_ids or [])]
    for index, text in enumerate(messages):
        from product_evidence import inspect
        issues.extend(inspect(text, products, focus_ids if focus_ids is not None else selected_ids, index,(context or {}).get('prepared',{}).get('communication',{}).get('latest_text','')))
        history = [r.get('text','') for r in (context or {}).get('prepared',{}).get('messages',[]) if r.get('role')=='advisor']
        historical_correction = bool(history and re.search(r'更正|说错|之前|刚才|前面',text))
        if re.search(r'第[一二三123]条候选|(?:前一条|上一条).{0,4}(?:候选|备选)',text) or (not historical_correction and re.search(r'(?:前一条|上一条|刚才那条).{0,8}(?:我|回复|说错|不对)|我把.{0,12}说错', text)):
            issues.append(dict(code="cross_candidate_reference", candidate_index=index, evidence=text, message="候选含跨条纠错或引用其他备选，不能独立发送；应在原候选内部修正，不能附加一条。"))
        names={p['id']:p for _,p in product_mentions(text,products)}
        total_product=next(iter(names.values())) if len(names)==1 else selected[0] if len(selected)==1 else None
        if total_product:
            for total in re.finditer(r'(?:(?:合计|总计|一共|总价|总额)(?:是|为)?|[一二两三四五六七八九十\d]+(?:只|件|个)(?:的)?(?:就是|合计(?:是|为)?|总计(?:是|为)?|一共|共计|共|是|为)?)\s*(\d{1,3}(?:,\d{3})+|\d{3,6})\s*元',text):
                cursor=0
                for part in clauses(text):
                    offset=text.find(part,cursor);cursor=offset+len(part)
                    if offset<=total.start()<cursor:
                        if modality(part,total.start()-offset,total.end()-offset)!='asserted':break
                        break
                else:continue
                if modality(part,total.start()-offset,total.end()-offset)!='asserted':continue
                if owner(part,total.start()-offset,total.end()-offset,'money') in ('budget','competitor','customer_reference'):continue
                quantities=list(re.finditer(r'([一两二三四五六七八九十\d]+)(?:只|件|个)',text[:total.start(1)]))
                if quantities:
                    expected=money_value(quantities[-1][1])*total_product['price']
                    if money_value(total[1])!=expected:issues.append(dict(code='wrong_total',candidate_index=index,evidence=total[0],expected=expected,product_id=total_product['id'],message='明确数量与目录单价算出的总额不一致，不能用总额暗示优惠。'))
        for clause in clauses(text):
            named = product_mentions(clause, products)
            for diagnosis in re.finditer(r'(?:属于|就是|确定是|认定是|是)(?:产品)?质量(?:问题|缺陷)|(?:肯定|确定)(?:是)?做工问题',clause):
                if modality(clause,diagnosis.start(),diagnosis.end())!='asserted' or re.match(r'(?:的)?(?:评估|核实|处理|咨询|流程|范畴)',clause[diagnosis.end():]):continue
                materials=(context or {}).get('value',{}).get('related_info','')+'\n'+'\n'.join(row.get('text','') for row in (context or {}).get('prepared',{}).get('supplements',[]))
                confirmed=False
                for source in clauses(materials):
                    match=re.search(r'售后.{0,12}(?:已确认|确认存在|评估确认).{0,10}质量(?:问题|缺陷)',source)
                    if match and modality(source,match.start(),match.end())=='asserted':confirmed=True
                if not confirmed:issues.append(dict(code='unsupported_service_diagnosis',candidate_index=index,evidence=diagnosis[0],message='故障表现不等于售后已确认质量问题；按政策先评估，不能自行诊断或认定责任。'))
            explanation=re.search(r'(?:差价|价差|价格差|定价|价格|贵|\d[\d,]*\s*元(?:的)?差别).{0,14}(?:(?:主要|更多)(?:不在|来自|在于|在|对应|因为|源于|是由|带来)|来自|在于|对应|因为|源于|是由|体现|反映|取决于|贵在)|(?:差价|价差).{0,10}(?:不是|并非).{0,8}(?:皮|材质|等级)',clause)
            if explanation and modality(clause,explanation.start(),explanation.end())=='asserted' and not re.search(r'不能|无法|不应|不等于|未有依据|没有依据',clause[:explanation.start()]):
                issues.append(dict(code='unsupported_price_cause',candidate_index=index,evidence=clause,message='没有定价原因资料，尺寸、材质名称或重量差异不能证明差价的原因；可比较已知参数，不要替品牌编定价解释。'))
            grade_pattern=r'(?:皮革|皮质|牛皮|材质|皮料|皮面)?(?:等级|级别|档次|品质)(?:完全)?(?:相同|一样|一致|更高|更好|更低|不同)|(?:相同|一样|同一)(?:的)?(?:皮革等级|皮质等级|皮料等级)|(?:不存在|并不是|不是).{0,10}(?:皮料|皮革|用皮|皮质).{0,8}(?:更好|不同|差异)|(?:托特|肩包|两款).{0,8}(?:用皮|皮质|皮料).{0,5}(?:更好|更差|一样|相同)'
            for grade in re.finditer(grade_pattern,clause):
                epistemic=re.search(r'不能|无法|不代表|不等于|没有依据|尚不清楚|不清楚|未确定',clause[:grade.end()])
                if modality(clause,grade.start(),grade.end())=='asserted' and not epistemic:
                    issues.append(dict(code='unsupported_leather_grade',candidate_index=index,evidence=grade[0],message='资料只给材质名称，没有皮革等级或品质比较依据，肯定或否定等级差异都不能从材质名称推出。'))
            for scope in re.finditer(r'(?:只|仅)(?:支持|接受|办理|提供)(?:在)?门店(?:购买)?(?:场景下)?(?:的)?(?:退换|退货|换货)|(?:退换|退货|换货)(?:只|仅)(?:支持|能|限)(?:在)?门店',clause):
                if modality(clause,scope.start(),scope.end())=='asserted' and not negated(clause[:scope.start()]):
                    issues.append(dict(code='unsupported_service_scope',candidate_index=index,evidence=scope[0],message='资料仅覆盖门店购买政策，未授权排除其他渠道售后。'))
            discounts = list(re.finditer(r"(?:享受|给您|为您|申请|打|提供|做到|按|可获|优惠至|优惠到).{0,6}?(?:[一二三四五六七八九十\d]+(?:[.点]\d+)?折|折扣)|[一二三四五六七八九\d]+(?:[.点]\d+)?折|(?:送您|赠送|附赠).{0,8}(?:礼品|赠品)|(?:终身)?免费(?:保养|维修|保修)|随时可退", clause))
            for match in discounts:
                attributed_and_rejected = (re.search(r"您(?:提到|说)|引用", clause[:match.start()]) and re.search(r"未授权|没有授权|未确认|需要核实|没有折扣|不能承诺", text)) or re.match(r".{0,8}(?:没有被授权|未获授权|无法确认|不能确认|未确认)",clause[match.end():])
                if not attributed_and_rejected and not negated(clause[:match.start()]) and not rejected_offer(clause,match.start(),match.end()) and modality(clause,match.start(),match.end())=='asserted':
                    issues.append(dict(code="unauthorized_benefit", candidate_index=index, evidence=match[0], message="候选包含未授权的折扣、赠品或终身服务承诺。"))
            for match in re.finditer(r"(?:保证|确保|绝对|一定|肯定).{0,8}(?:不累|轻松|舒服|舒适|不压肩)", clause):
                if not negated(clause[:match.start()]) and not re.search(r"未必.{0,3}$", clause[:match.start()]):
                    issues.append(dict(code="unsupported_promise", candidate_index=index, evidence=match[0], message="不能保证个人舒适或不累；没有写免责声明本身不构成问题。"))
            for match in re.finditer(r"(?:保证|确保|绝对|完全|可以|能)防水|已经(?:给您|为您)预留", clause):
                if not negated(clause[:match.start()]) and modality(clause,match.start(),match.end())=='asserted':
                    issues.append(dict(code="unsupported_promise", candidate_index=index, evidence=match[0], message="候选包含无依据的防水或已完成行动承诺。"))
            for match in re.finditer(r'(?:它|这款|包身|包体|包袋|包)(?:是)?不?防水|(?:确实|完全|绝对|可以|能)不?防水|防水(?:没问题|性能好|效果好)|是(?:一)?(?:款|个)?防水(?:包|设计)',clause):
                prefix=clause[:match.start()]
                if modality(clause,match.start(),match.end())=='asserted' and not re.search(r'(?:不能|无法|不|没法)保证.{0,5}$',prefix):
                    if not any(e.get('candidate_index')==index and e.get('code')=='unsupported_promise' and '防水' in e.get('evidence','') for e in issues):
                        issues.append(dict(code='unsupported_promise',candidate_index=index,evidence=clause,message='资料不支持肯定或否定防水性能；不保证防水可如实说明。'))
            for match in re.finditer(r'(?:用|使用).{0,3}酒精|热风(?:烘干|吹)|(?:用|使用).{0,8}烘干',clause):
                if modality(clause,match.start(),match.end())=='asserted' and not re.search(r'不要|不能|不建议|先别|避免|别|不适合',clause[:match.start()]):
                    issues.append(dict(code='unsafe_care_advice',candidate_index=index,evidence=match[0],message='保养政策不建议酒精或烘干，不能将历史错误建议变成操作指示。'))
        for binding in price_bindings(text,products,selected_ids,focus_ids):
            if binding['product_id'] and binding['value'] != binding['expected']:
                issues.append(dict(code='wrong_price',candidate_index=index,evidence=binding['evidence'],expected=binding['expected'],product_id=binding['product_id'],message=f"{binding['product_name']}的品牌现价为{binding['expected']:,}元，候选报价不一致。"))
        material = (context or {}).get('value',{}).get('related_info','')
        for clause in clauses(text):
            for match in re.finditer(r'(?:没有|无|有|不存在)[^，。；！？]{0,16}?(?:预留|预约|退款|提交)(?:的)?记录',clause):
                before=clause[max(0,match.start()-12):match.start()]
                if modality(clause,match.start(),match.end())!='asserted' or re.search(r'资料|输入|未提供|尚未确认|可确认|如果|假如|若',before) or re.search(r'已确认|可确认|确认过',match[0]) or match[0] in material:continue
                issues.append(dict(code='unsupported_record_state',candidate_index=index,evidence=match[0],message='未提供业务记录不等于记录存在或不存在；需要实际记录结果，或说明尚未确认。'))
        supplied=(context or {}).get('value',{})
        prepared=(context or {}).get('prepared',{})
        customer_sources='\n'.join(r.get('text','') for r in prepared.get('messages',[]) if r.get('role')=='customer')
        care_context='\n'.join([supplied.get('conversation',''),supplied.get('client_info',''),customer_sources])
        unknown_cleaner=unknown_cleaner_in(care_context)
        issues.extend(dict(item,candidate_index=index) for item in stain_advice(text,care_context))
        from statement_scope import prohibits_action
        for clause in clauses(text):
            for trial in re.finditer(r'(?:隐蔽|角落|边角|小块|不显眼|不显处|小面积).{0,15}(?:试用|试擦|擦试|试一|测试|点.{0,6}试)|(?:试用|试擦|擦试|测试).{0,15}(?:隐蔽|角落|边角|小块|不显眼|小面积)',clause):
                if unknown_cleaner and modality(clause,trial.start(),trial.end())=='asserted' and not prohibits_action(clause,trial.start(),trial.end()):
                    issues.append(dict(code='unsafe_care_advice',candidate_index=index,evidence=trial[0],message='当前清洁剂成分未知，角落试用仍是自行使用；按保养政策先不要用，由售后核实。'))
        source_context='\n'.join([supplied.get('client_info',''),supplied.get('related_info',''),customer_sources,prepared.get('customer_context',{}).get('preferences','')]+[r.get('text','') for r in prepared.get('supplements',[])])
        service_request=prepared.get('communication',{}).get('latest_text',customer_sources)
        explicit_lookup_failure=bool(re.search(r'(?:门店|顾问|售后).{0,12}(?:已核实|确认|已查).{0,12}(?:无法定位|找不到|未找到|缺少订单号)',source_context))
        if re.search(r'上次|之前|前次|已(?:经)?提交',service_request) and re.search(r'售后|维修',service_request) and re.search(r'单号|进度|编号',service_request) and not explicit_lookup_failure:
            for request in re.finditer(r'(?:麻烦|请|方便|能否|能不能|可以).{0,15}(?:把.{0,18})?(?:售后涉及|商品|故障|问题).{0,15}(?:说|描述|提供|发|告诉)|(?:麻烦|请|方便|能否|能不能|可以).{0,15}(?:再|重新).{0,12}(?:说|描述|提供|发|告诉).{0,15}(?:问题|故障|情况|哪里|什么包)|(?:什么|哪款)包.{0,8}(?:什么|哪里).{0,6}问题',text):
                issues.append(dict(code='customer_repeats_missing_tool_history',candidate_index=index,evidence=request[0],message='客户问已提交售后的单号/进度，工具缺旧详情由顾问查记录，不能要求客户重新描述故障。'))
        from business_evidence import inspect as inspect_business
        from aftersales_evidence import audit as audit_aftersales
        if context:issues.extend(dict(row,candidate_index=index) for row in audit_aftersales([text],(context or {}).get('prepared',{}),products,value=(context or {}).get('value')))
        issues.extend(dict(row,candidate_index=index) for row in inspect_business([text],products,supplied,prepared))
        for action in completed_actions(text):
            from aftersales_evidence import supports_record_read
            if supports_record_read(action,text,(context or {}).get('prepared',{}),products):continue
            if action not in material or re.search(r'未|没有|尚未',material[max(0,material.find(action)-6):material.find(action)]):
                issues.append(dict(code='unsupported_completed_action',candidate_index=index,evidence=action,message='没有实际执行记录支持这项已查询或已完成动作；未来协助不等于已执行。'))
        if re.search(r'旧备注|内部备注|发送前请|顾问(?:应|需|可)|具体哪天发这条|这次就不多提|关系熟悉程度',text):
            issues.append(dict(code='internal_note_leak',candidate_index=index,evidence=text,message='顾问内部备注或发送安排进入客户消息，应放在顾问提醒。'))
        if (context or {}).get('prepared',{}).get('customer_context',{}).get('marketing_opt_out') and re.search(r'(?:以后|下次|今后).{0,12}(?:给您发|通知您|再联系|推送)|欢迎.{0,8}(?:到店|参加)|恢复.{0,5}(?:推广|营销)',text):
            issues.append(dict(code='marketing_after_opt_out',candidate_index=index,evidence=text,message='主动咨询只授权回答当前问题，不能恢复营销或追加推广。'))
        if expected_state == "declined" and re.search(r"[?？]|要不要|再给您看看|我推荐|不妨|试背|试一下|(?:再看看|再介绍).{0,8}(?:款|包|卡夹)", text):
            issues.append(dict(code="selling_after_decline", candidate_index=index, evidence=text, message="客户最新正文已明确拒绝，候选仍追问或继续销售。"))
    if context:
        from task_evidence import event_exclusions
        issues.extend(event_exclusions(messages,context.get("prepared",{})))
        from device_reference import inspect as inspect_devices
        issues.extend(inspect_devices(messages,context.get('prepared',{})))
        from answer_context import inspect as inspect_answer
        issues.extend(inspect_answer(messages,context))
    return issues
