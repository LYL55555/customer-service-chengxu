import copy
import re

VERSION='input-responsibility-0.4.0'

QUOTES={'“':'”','「':'」','『':'』','‘':'’','"':'"'}
REPORTER=r'(客户|顾客|对方|她|他|顾问|客服)[^，,。；;：:“”「」\n]*?(?:说|表示|提到|反馈|告诉|确认|原话|的话|[：:])'
REFERENCE=r'(?:按|根据|参照|结合|以).{0,16}(?:聊天|截图|语音|消息|原文|摘要|刚才|前文|之前|最新(?:要求|需求))|(?:聊天|截图|语音|消息).{0,12}(?:里|中|为准|正文|要求|需求)|(?:刚发|刚收到|最新|这段|同一段|这次|本次).{0,12}(?:聊天|截图|消息|语音)'


def quoted_ranges(text):
    stack=[];ranges=[]
    for index,char in enumerate(text):
        if stack and char==QUOTES[stack[-1][0]]:
            _,start=stack.pop();ranges.append((start,index+1))
        elif char in QUOTES:stack.append((char,index))
    return ranges+[(start,len(text)) for _,start in stack]


def speaker_at(text,position,default='advisor'):
    containers=sorted((span for span in quoted_ranges(text) if span[0]<position<span[1]),reverse=True)
    boundary=containers[0][0] if containers else position
    prefix=re.split(r'[。；;\n]',text[:boundary])[-1]
    reports=[(match.start(),match.start()+len(match[1]),match[2]) for match in re.finditer('(?=('+REPORTER+'))',prefix)]
    if reports:
        role='advisor' if reports[-1][2] in ('顾问','客服') else 'customer'
        tail=prefix[reports[-1][1]:]
        if not containers and re.search(r'(?:但|而|不过|另外)(?:我|顾问)(?:自己|本人|这边)?',tail):return 'advisor'
        return role
    if containers:return 'unknown'
    return default


def current_event(text,position,row):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo('America/New_York')).date()
    for key in ('sent_at','message_time','timestamp','timestamp_text'):
        stamp=re.search(r'(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})',str(row.get(key,'')))
        if stamp:
            try:
                if datetime(*map(int,stamp.groups())).date()!=today:return False
            except ValueError:return False
    cues=list(re.finditer(r'去年|前年|上次|之前|以前|昨天|昨日|历史|上个月|\d+天前|\d+个月前|今天|本次|这次|现在|刚才|刚刚|20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}',text[:position]))
    if not cues:return True
    stamp=re.fullmatch(r'(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})',cues[-1][0])
    if stamp:
        try:return datetime(*map(int,stamp.groups())).date()==today
        except ValueError:return False
    return cues[-1][0] in ('今天','本次','这次','现在','刚才','刚刚')


def task_details(text,source_id):
    details=[]
    patterns={
        'use':r'通勤|上班|周末|出差|送礼|(?:带|放|装|收纳).{0,12}(?:A4|水杯|水瓶|电脑|文件|手机|钥匙|口红|卡片)',
        'preference':r'(?:喜欢|偏好|不喜欢|不考虑|不要|不想要).{0,12}(?:低调|大标|标识|墨黑|岩灰|砂棕|包|卡夹|轻|重)|(?:低调|墨黑|岩灰|砂棕).{0,8}(?:风格|颜色|色系)',
        'budget':r'预算.{0,8}[一二三四五六七八九十两百千万\d]+|[一二三四五六七八九十两百千万\d]+元.{0,4}(?:以内|以下|左右)',
        'question':r'(?:多少钱|怎么保养|能否维修|七天|退换|拉链.{0,8}卡|接缝.{0,8}裂)|(?:问|询问|想了解|了解|核对).{0,12}(?:价格|售价|容量|尺寸|材质|重量|背法|肩背|斜挎|维修|售后|活动时间|活动地址)|(?:包|卡夹).{0,8}(?:能放|能装|放得下|多重|多大)|(?:买什么|选什么|推荐什么).{0,6}(?:包|卡夹)',
        'need':r'(?:想买|想选|想挑|需要|想要).{0,8}(?:包袋|包|卡夹)|(?:买过|购买了|买了|到店试过).{0,12}(?:包|卡夹)',
    }
    for clause in re.split(r'[，,。；;\n！？?]',text):
        if re.search(r'(?:没有|没|未|尚未|不清楚|不知道).{0,10}(?:提供|识别|转写|拿到|写明|说明|看见|看到)|(?:用途|预算|偏好|问题|内容|正文).{0,5}(?:不清楚|未知|未明确|没写)',clause):continue
        for kind,pattern in patterns.items():
            matches=list(re.finditer(pattern,clause))
            if not matches:continue
            if kind=='use' and re.search(REFERENCE,clause) and not re.search(REPORTER,clause) and not any(re.search(r'带|放|装|收纳',match[0]) for match in matches):continue
            details.append(dict(source_id=source_id,kind=kind,quote=clause.strip()))
    return details


def summary_content(text,source_id):
    found=[row for row in task_details(text,source_id) if row['kind']!='budget']
    labelled=bool(re.search(r'摘要|实际问题|原话是|已核对|已听完|已转写',text))
    statement=r'(?:客户|顾客|她|他)(?:本次|这次|刚才|现在|刚刚|刚|目前)?(?:问|希望|想要|需要|想了解|说|表示|反馈|觉得|想)'
    for clause in re.split(r'[，,。；;\n！？?]',text):
        if re.search(r'(?:没|未|没有).{0,10}(?:识别|导入|转写|提供|拿到).{0,8}(?:正文|内容|原文|摘要)',clause):continue
        match=re.search(statement,clause)
        if not match and not labelled:continue
        content=clause[match.end():] if match else clause
        content=re.sub(r'^.*?(?:摘要|实际问题|原话是|已核对|已听完|已转写)[的了：:\s]*','',content)
        if re.search(REFERENCE,content):continue
        if re.search(r'(?:没收到|没有收到|听不清).{0,10}(?:消息|正文|内容|语音)|(?:正文|内容|消息|语音).{0,8}(?:没收到|听不清)',content):continue
        content=content.strip('：: “”“「」『』‘’')
        if re.fullmatch(r'(?:了|几个|好几个|几项|一些|几条|这些|那些|最新|本次|刚才|的|都|很多|不少|具体|什么)*(?:问题|要求|条件|需求|用途|偏好|内容)(?:了|而已)?',content):continue
        if re.fullmatch(r'(?:预算|金额|上限).{0,6}[一二三四五六七八九十两百千万\d,，]+元?',content):continue
        if len(content)>2:found.append(dict(source_id=source_id,kind='unparsed_summary',quote=clause.strip()))
    return found


def body_dependencies(text,source_id):
    found=[]
    statement=r'(?:客户|顾客|她|他)(?:本次|这次|刚才|现在|刚刚|刚|目前)?(?:问|希望|想要|需要|想了解)'
    for clause in re.split(r'[，,。；;\n]',text):
        if re.search(r'(?:无|没有|未有|没收到).{0,8}(?:新来信|来信|新消息|客户消息)|不需要.{0,6}(?:聊天|原文|正文)',clause):continue
        if re.search(REFERENCE,clause) or re.search(statement,clause):found.append(dict(source_id=source_id,quote=clause.strip()))
    return found


def task_evidence(value,prepared):
    sources=[('background.client_info',value.get('client_info','')),('materials.related_info',value.get('related_info',''))]
    sources += [('supplement.'+str(i+1),row.get('text','')) for i,row in enumerate(prepared.get('supplements',[]))]
    correction=value.get('understanding_corrections',{}).get('question','')
    summary=summary_content(value.get('client_info',''),'background.client_info')+summary_content(correction,'understanding_corrections.question')
    available=[detail for identity,text in sources for detail in task_details(text,identity)]+task_details(correction,'understanding_corrections.question')
    profile=prepared.get('customer_context',{}).get('preferences','')
    if profile:sources.append(('profile.preferences',profile))
    if value.get('scenario')=='商品推荐':available+=task_details(profile,'profile.preferences')
    dependencies=body_dependencies(value.get('client_info',''),'background.client_info')
    if not any(value.get(key,'').strip() for key in ('client_info','conversation','related_info')):
        dependencies+=body_dependencies(profile,'profile.preferences')
    source_materials=[dict(source_id=identity,text=text) for identity,text in sources if text.strip()]
    return dict(summary=summary,available=available,sources=source_materials,body_dependencies=dependencies,parse_scope='字段提取非穷尽；未命中不能证明资料缺失')


def external_gap_evidence(value,prepared):
    sources=[dict(source='background.client_info',text=value.get('client_info',''))]
    if not prepared.get('communication',{}).get('historical_chat'):
        sources += [dict(source='chat.'+row.get('id',''),text=row.get('text',''),row=row) for row in prepared.get('messages',[]) if row.get('include',True) and row.get('role')=='advisor' and row.get('kind')=='text']
    evidence=[]
    for source in sources:
        text=source['text']
        for match in re.finditer(r'(?:没收到|没有收到|收不到).{0,10}(?:消息|内容|正文|文字|语音)|听不清',text):
            start=max(text.rfind(char,0,match.start()) for char in '，,。；;\n')+1
            end=min([p for char in '，,。；;\n' if (p:=text.find(char,match.end()))>=0] or [len(text)])
            clause=text[start:end]
            if speaker_at(text,match.start())!='advisor' or not current_event(text,match.start(),source.get('row',{})):continue
            if re.search(r'不是.{0,5}(?:没收|听不清)|并非|不确定|不知道|是否|可能|如果|假如|要是|万一|不能(?:说|认定)|不代表|(?:没有|缺少|未有).{0,8}(?:证据|依据|确认)',clause):continue
            own_subject=re.search(r'我|顾问|客服',clause[:match.start()-start])
            explicit_audio=re.search(r'语音.{0,8}(?:确实|实际)听不清',clause)
            if not own_subject and not explicit_audio:continue
            evidence.append(dict(source_id=source['source'],quote=clause,kind='actual_unintelligible_audio' if '听不清' in match[0] else 'actual_delivery_gap',speaker='advisor',event='current'))
    return evidence


def assess(value,prepared):
    items=[]
    def need(code,message,action,label):
        items.append(dict(code=code,owner='advisor',message=message,action=action,label=label))
    rows=[row for row in prepared.get('messages',[]) if row.get('include',True)]
    customer=[row for row in rows if row.get('role')=='customer']
    text=[row for row in customer if row.get('kind')=='text' and row.get('text','').strip()]
    background=value.get('client_info','')
    gap=external_gap_evidence(value,prepared)
    imported=prepared.get('chat_import_status',value.get('chat_import',{}))
    if imported.get('pending'):
        need('chat_confirmation','已选截图尚未识别或确认；先在工具中核对，不能让客户重发。','chat','识别 / 复核已选截图')
    evidence=task_evidence(value,prepared)
    supplied_summary=bool(evidence['summary'])
    birthday=value.get('scenario')=='生日及节日问候'
    if not gap and not birthday and customer and customer[-1].get('kind') in ('voice','image','unknown','unreadable') and not supplied_summary:
        only_text=re.search(r'只(?:需|要)?(?:回答|回应|处理).{0,8}(?:文字|价格|容量)|语音.{0,8}(?:无关|不影响|不用)',background)
        if not only_text:
            need('voice_transcription' if customer[-1].get('kind')=='voice' else 'chat_body','当前要回复的内容尚未成为可用文字；请顾问查看原消息，补必要转写或摘要。','conversation','补充原消息文字 / 摘要')
    reference=bool(evidence['body_dependencies'])
    if not birthday and not text and not gap and reference and not supplied_summary and not imported.get('pending'):
        need('chat_body','本次背景引用了客户聊天，但工具尚未拿到正文。请导入已选聊天、粘贴原文或补已核对的摘要；这不表示客户没有发送。','conversation','补入聊天正文')
    if text:
        latest=text[-1]
        earlier='\n'.join(row.get('text','') for row in text[:-1])+'\n'+background
        budget_reference=re.search(r'(?:按|照|以).{0,12}(?:刚才|前面|之前|上次|我说的).{0,8}预算',latest.get('text',''))
        if budget_reference:
            from understanding import budget_in
            if not budget_in(earlier,{}):need('prior_chat','客户明确引用了先前预算，但工具中没有该来源。请顾问补入那一段或已核对摘要，不让客户重复报预算。','conversation','补入被引用的前文')
    relevant_ocr_gap=re.search(r'(?:关键|要回复的|当前问题|本次问题).{0,12}(?:漏识别|漏句|没识别|未识别|漏掉)|(?:漏识别|漏句|没识别|未识别|漏掉).{0,12}(?:关键|要回复的|当前问题|本次问题)',background)
    if relevant_ocr_gap and not supplied_summary and not imported.get('pending'):
        need('ocr_gap','当前问题有关键漏句，请顾问对照原图补录该句；不用重整整段聊天。','chat','对照原图补录漏句')
    if not birthday and not rows and not gap and not evidence['sources'] and not items:
        need('task_background','还没有本次任务的可用背景；补一句要做什么即可，不需要完整客户档案。','background','补一句本次任务')
    return dict(version=VERSION,state='needs_advisor' if items else 'ready',items=items,external_gap_evidence=gap,task_evidence=evidence,known_customer_text_ids=[row.get('id') for row in text],principle='按当前任务判断；无预算不阻止推荐，工具未知不等于客户没说或业务未定')


def unnecessary_advisor_gap(missing,value,prepared):
    from statement_scope import direction
    current=prepared.get('communication',direction(value,prepared)).get('latest_text','') or value.get('client_info','')
    reason='；'.join(missing)
    if prepared.get('task_materials',{}).get('plan',{}).get('reply_route')=='business_followup':return '当前正文完整，可以回复承接后续业务核实；模型把业务核实误当作导入原资料缺口，未采用这次待办。'
    if value.get('scenario')=='生日及节日问候' and re.search(r'日期|当天|生日|预算|商品',reason):return '生日祝福不需要为工具补具体发送日、预算或商品；这次是模型缺项判断错误，不是顾问资料待办。'
    if re.search(r'预算',reason) and assess(value,prepared)['state']=='ready':return '当前任务可以使用已知事实作答或推荐，无需补预算；模型把可选字段当成必填，未采用这次待办。'
    if re.search(r'电脑|手机|钱包',current) and re.search(r'装|放|适配|能进',current) and re.search(r'尺寸|长宽|厚度',reason):return '已有真实适配问题，必要的客户物品尺寸可以中性澄清；模型不应要求顾问替客户补这项需求。'
    return ''


def inspect(messages,value,prepared):
    readiness=assess(value,prepared)
    errors=[]
    if readiness['state']=='needs_advisor':
        return [dict(code='input_responsibility',candidate_index=None,evidence='',message=item['message'],owner=item['owner'],action=item['action']) for item in readiness['items']]
    source='\n'.join([value.get('client_info',''),value.get('related_info','')]+[row.get('text','') for row in prepared.get('messages',[]) if row.get('include',True)]+[row.get('text','') for row in prepared.get('supplements',[])])
    from statement_scope import direction
    current=prepared.get('communication',direction(value,prepared)).get('latest_text','')
    business_source='\n'.join([value.get('client_info',''),value.get('related_info','')]+[row.get('text','') for row in prepared.get('supplements',[])])
    from statement_scope import modality
    business_unset=False
    for clause in re.split(r'[。；\n]',business_source):
        match=re.search(r'(?:活动|时间|日期|地点|场次|安排).{0,18}(?:还没定|尚未|没有确认|未确认|未定|没定|没有确定)',clause)
        if match and modality(clause,match.start(),match.end())=='asserted' and not re.search(r'客户(?:说|问|猜)|她(?:说|问)|他(?:说|问)',clause):business_unset=True
    for index,text in enumerate(messages):
        reason=None
        resend=re.search(r'(?:重发|再发|重新发).{0,12}(?:消息|正文|聊天|内容|语音)|(?:消息|正文|聊天|内容|语音).{0,16}(?:再发|重发|发一次)|(?:没看到|没有看到|没收到|没有收到).{0,10}(?:正文|消息|内容)|(?:这条聊天|截图|识别|转写).{0,8}(?:没有|没|缺|失败)',text)
        if resend and not readiness['external_gap_evidence']:reason='工具未读到正文不能变成客户重发请求；没有顾问在微信实际未收到或听不清的来源。'
        kinds={row['kind'] for row in readiness['external_gap_evidence']}
        if re.search(r'(?:我|这边).{0,10}(?:没收到|没有收到|没看到|没有看到).{0,8}(?:内容|正文|消息)',text) and 'actual_delivery_gap' not in kinds:reason='听不清语音或工具未导入不能证明顾问在微信没有收到消息。'
        if re.search(r'(?:我|这边).{0,8}听不清',text) and 'actual_unintelligible_audio' not in kinds:reason='没有顾问实际听不清的来源，不能把语音未转写说成听不清。'
        if re.search(r'(?:您|你).{0,8}(?:没说|没有说|没发|没有发).{0,8}(?:预算|用途|消息|正文)',text):reason='没有读到资料不能断言客户没说或没发。'
        event_unset=re.search(r'(?:活动|时间|日期|地点|场次).{0,10}(?:还没定|尚未确定|尚未定|还未确定|没有确定|未定)',text)
        if value.get('scenario')=='活动邀请' and event_unset and not business_unset:reason='工具没拿到活动安排不能证明业务尚未确定；应由顾问先核实，不能把缺来源当未定事实。'
        ask_budget=re.search(r'(?:预算.{0,6}(?:多少|几|是\?|呢|？)|(?:告诉|说|说明|提供|报).{0,12}预算)',text)
        if ask_budget and current and re.search(r'多少钱|售价|价格|打折|折扣',current) and not re.search(r'推荐|挑|选|预算|适合',current):reason='当前只问价格/折扣，无需向客户追问预算。'
        if ask_budget:
            from understanding import budget_in
            if any(row['amount'] is not None for row in budget_in(source,{})):reason='已有预算来源应先复用，不能让客户为工具重复报预算。'
        if re.search(r'(?:请您|麻烦您|您能|您方便).{0,15}(?:核实|提供|告诉|确认).{0,12}(?:库存|维修费用|售后政策|品牌政策)',text):reason='库存、维修费用或品牌政策应由顾问或门店核实，不能让客户提供品牌授权。'
        if reason:errors.append(dict(code='input_responsibility',candidate_index=index,evidence=text,message=reason))
    return errors


def advisor_help(items=None,missing=None):
    if not items:
        items=[]
        for text in (missing or ['请顾问核对当前资料，再生成客户消息。']):
            action,label,owner='background','补充必要背景','advisor'
            if re.search(r'正文|语音|转写|原话',text):action,label='conversation','补入已核对的聊天文字'
            elif re.search(r'截图|识别|漏句|漏录',text):action,label='chat','对照原图复核 / 补录'
            elif re.search(r'库存|维修|政策|活动|售后',text):action,label,owner='materials','核对商品、订单或活动资料','store'
            items.append(dict(code='model_input_gap',owner=owner,message=text,action=action,label=label))
    return dict(version=VERSION,state='needs_advisor',items=items)


def guard(record):
    result=record.get('result') or record.get('parsed_output') or {}
    prepared=record.get('confirmed_context',{})
    readiness=assess(record.get('input',{}),prepared)
    issues=inspect(result.get('messages',[]),record.get('input',{}),prepared) if isinstance(result.get('messages'),list) else []
    allowed=record.get('status')=='success' and result.get('status')=='ready' and isinstance(result.get('messages'),list) and len(result['messages'])==3 and not issues
    return dict(version=VERSION,allowed=allowed,reason='资料缺口需要顾问处理；旧原文保留作证据，不能作为客户消息复制。' if not allowed else '',items=readiness['items'] or [dict(code=row['code'],owner='advisor',message=row['message'],action=row.get('action','background'),label='核对原资料') for row in issues],legacy_needs_info=result.get('status')=='needs_info')


def present(record):
    output=copy.deepcopy(record);output['delivery_guard']=guard(record)
    if output['delivery_guard']['legacy_needs_info'] and not output['delivery_guard']['items']:
        output['delivery_guard']['items']=advisor_help(missing=(record.get('result') or {}).get('missing_information'))['items']
    return output


def bind_selected(value,current,contexts=None):
    value=copy.deepcopy(value)
    draft=current.get('draft',{});context=draft.get('context',{})
    selected=context.get('imported_id') or draft.get('input',{}).get('context_id')
    restored=[]
    if selected and not value.get('context_id'):
        value['context_id']=selected;restored.append('context_id')
    if context:
        pending=bool(context.get('review_dirty') or context.get('asset_ids') and not selected)
        if contexts and context.get('draft_id') and 'auto_stitch' in context:
            original=contexts.get(context['draft_id'])
            pending=pending or context['auto_stitch']!=(original.get('stitching',{}).get('mode')!='keep_all')
        incoming=value.get('chat_import',{})
        value['chat_import']=dict(pending=pending or bool(incoming.get('pending')),asset_ids=context.get('asset_ids',[]) or incoming.get('asset_ids',[]),draft_id=context.get('draft_id') or incoming.get('draft_id'))
    return value,restored
