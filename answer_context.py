import re
from datetime import date

VERSION='answer-context-0.5.0'


def followup_requested(text):
    return bool(re.search(r'之后|后续|以后|下一场|下次|后面|接下来|再办',text) and re.search(r'活动|类似|安排|还有|再办|还会办|再来一场',text))


def build(value,prepared,brand):
    from understanding import build_understanding
    current=prepared.get('communication',{}).get('latest_text','')
    focus=build_understanding(value,prepared,brand['products'])['fields']['product']['ids']
    topics=[]
    facts=[]
    for name,pattern,field in [('工艺',r'全手工|手工|工艺','craft'),('肩带调节',r'肩带.{0,8}调','strap_adjustable'),('防水',r'防水',None),('A4容量',r'A4', 'a4_fit'),('预留状态',r'预留','stock')]:
        if re.search(pattern,current,re.I):
            topics.append(name)
            if field:
                for p in brand['products']:
                    if p['id'] in focus:facts.append(dict(topic=name,source_id='product.'+p['id']+'.'+field,text=p['facts'][field]['text'],customer_expression=name+'目前还不能确认' if p['facts'][field]['status']=='unknown' else p['facts'][field]['text']))
            elif name=='防水':facts.append(dict(topic=name,source_id='policy.3',text='不保证防水'))
    if value['scenario']=='活动邀请':
        if followup_requested(current):topics.append('后续活动')
        if re.search(r'几点|时[间段]|下午|上午|周[一二三四五六日天]',current):topics.append('活动时段')
        if re.search(r'在哪|地址|地点',current):topics.append('活动地点')
        if re.search(r'朋友|同行|带.{0,3}人',current):topics.append('同行资格')
    calendar=[]
    if value['scenario']=='活动邀请':
        for m in re.finditer(r'(20\d\d)-(\d\d)-(\d\d)',value.get('related_info','')):
            try:d=date(*map(int,m.groups()))
            except ValueError:continue
            calendar.append(dict(date=d.isoformat(),weekday='周'+'一二三四五六日'[d.weekday()],source_id='materials.related_info',method='python-datetime-date.weekday'))
    event_pending=value['scenario']=='活动邀请' and bool(re.search(r'日期.{0,12}时间.{0,12}地点.{0,30}(?:没有确认|未确认|未定|没定)',value.get('related_info','')))
    requested=[]
    for aspect,pattern in [('price',r'多少钱|价格|总价|合计|一共|贵|价差|差了'),('discount',r'折扣|打折|便宜点|优惠|折吗'),('capacity',r'能装|能放|装下|放下|容量|硬币|零钱袋|放得下'),('carry',r'斜挎|怎么背|背法'),('event_experience',r'做什么|体验|内容|了解活动'),('address_only',r'(?:地址|地点).{0,12}(?:别的不用|其他不用|只要地址)')]:
        if re.search(pattern,current):requested.append(aspect)
    use_context=[]
    for name,pattern in [('gift',r'礼物|送人|送给|送同事'),('light_carry',r'少带|轻装|随身')]:
        if re.search(pattern,current):use_context.append(name)
    wants_judgment=bool(re.search(r'推荐|哪款|有什么建议|合适|怎么选|值不值|值得|哪个',current))
    mode='selected_product_fact_query' if focus and requested and not wants_judgment else 'recommendation_or_judgment' if wants_judgment else 'current_task'
    response_scope=dict(current_customer_text=current,scenario=value['scenario'],requested_aspects=requested,use_context_not_extra_questions=use_context,task_mode_hint=mode,source='communication.latest_text；没有新来信时按本次任务与已选背景，不用历史问句替代',authority='非穷尽线索，未命中不等于没有需求，也不强制增加问题',selection_rule='已选商品的事实询问只答所问；礼物/轻装是用途背景，不自动变成需要另答的推荐问题。仅开放推荐才补有用取舍；答完停，不按三个固定角色分配。')
    return dict(version=VERSION,topics=topics,facts=facts,calendar=calendar,event_pending=event_pending,response_scope=response_scope,instruction='三条每条均回应这些核心话题；事实按来源，不为制造差异遗漏，也不因完整而增补无关事项。日历仅由给定日期计算，不新增活动安排。')


def inspect(messages,context):
    value=context.get('value',{});prepared=context.get('prepared',{})
    plan=prepared.get('answer_context',{});issues=[]
    core=[t for t in plan.get('topics',[]) if t in ('工艺','肩带调节','防水','活动时段','活动地点','同行资格')]
    patterns={'工艺':r'手工|工艺','肩带调节':r'肩带|调节','防水':r'防水','活动时段':r'日期|时间|时段|周[一二三四五六日天]|\d{1,2}:\d{2}|[一二三四五六七八九十\d]+点|场次|活动.{0,6}(?:还没定|未定|没有确定)|安排.{0,5}(?:未定|没定|确认中)','活动地点':r'地址|地点|场地|(?:路|街|道|巷)\d+号|精品店|商场|安排.{0,5}(?:未定|没定|确认中)','同行资格':r'朋友|同行|两位|参与(?:条件|安排|资格)|安排.{0,5}(?:未定|没定|确认中)'}
    for i,text in enumerate(messages):
        if '后续活动' in plan.get('topics',[]):
            future=r'后续|之后|以后|下一场|下次|后面|接下来|再办'
            checking=r'核实|确认|问问|问一下|了解|询问|打听'
            pending=bool(re.search(r'(?:'+checking+r')[^。！？]{0,25}(?:'+future+r')|(?:'+future+r')[^。！？]{0,25}(?:'+checking+r')',text))
            records=[r['text'] for r in prepared.get('evidence_sources',{}).get('sources',[]) if r['kind'] in ('business_material','event') and re.search(future,r['text'])]
            arranged=bool(records and re.search(future,text) and re.search(r'\d{1,2}月|20\d{2}[-年]|\d{1,2}:\d{2}|定在|定于|暂无|没有安排|还未安排|还有一场',text))
            if not pending and not arranged:issues.append(dict(code='incomplete_current_answer',candidate_index=i,evidence=text,topic='后续活动',message='客户问后续活动，这条没有回答后续安排或承接核实；介绍本场活动、泛泛以后再联系不能代替。'))
        for topic in core:
            if not re.search(patterns[topic],text):issues.append(dict(code='incomplete_current_answer',candidate_index=i,evidence=text,topic=topic,message='该条没有独立回应当前问题中的'+topic+'，不能靠其他候选补答。'))
        if plan.get('event_pending') and '活动时段' in core and not re.search(r'(?:时间|日期|时段|场次).{0,30}(?:确认|未定|没定|确定|不能)|活动.{0,6}安排.{0,8}(?:未定|没定|确认|确定)',text):
            issues.append(dict(code='incomplete_current_answer',candidate_index=i,evidence=text,topic='时段待确认',message='活动时间尚未确定，必须回应客户提出的时段还需确认，不能只说明地址未定。'))
        for c in plan.get('calendar',[]) if len(plan.get('calendar',[]))==1 else []:
            from statement_scope import clauses
            from quality import negated
            for clause in clauses(text):
                for m in re.finditer(r'周[一二三四五六日天]',clause):
                    before,after=clause[:m.start()],clause[m.end():]
                    if negated(before) or re.match(r'.{0,4}(?:不对|有误|说错|写错)',after):continue
                    if re.search(r'(?:之前|上次|刚才|原先|先前).{0,6}(?:说|提到|写)',before):continue
                    if re.search(r'原定|旧说法|原先|之前说',before) and re.search(r'更正|改为|改成|实际|正确',text):continue
                    availability=bool(re.search(r'您.{0,8}(?:方便|有空)|(?:再|帮您|给您).{0,6}(?:确认|核实|联系)|我.{0,8}(?:确认|核实|回复)',clause))
                    event=bool(re.search(r'活动|场次|开场|开始|\d{1,2}月\d{1,2}日|20\d{2}-\d{2}-\d{2}|\d{1,2}:\d{2}',clause))
                    if availability and not event:continue
                    if m[0].replace('周天','周日')!=c['weekday']:
                        issues.append(dict(code='wrong_event_weekday',candidate_index=i,evidence=clause,expected=c['weekday'],source=c,message='所指活动日期与星期不一致；否定旧说法及其他人的可用时间不按活动日期处理。'))
    return issues
