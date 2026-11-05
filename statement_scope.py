import re

VERSION = 'statement-scope-0.7.1'
STATE_DESCRIPTION = '描述客户当前立场，不是顾问是否拒绝承诺。comparing=客户正在比较/询问，不代表决定购买；declined=客户明确拒绝对应商品/推荐范围，顾问拒绝打折不属于此类；unclear=客户明确表示暂缓/稍后考虑且无新问题，不是购买意向未知或业务资料不全；other=其他任务或没有购买态度依据。other与comparing可交叠，拒绝/暂缓必须有当前来源'
PERSONAL = r'(?:您(?:的|这款|这个|这只|这台|这部)?|客户(?:的)?|我(?:的)?)(?:电脑|手机|水杯|文件夹|长钱包|钱包|笔记本)|电脑连壳|手机连壳'
OTHER = r'别家|竞品|另一(?:款|家)|对方|那款'


def clauses(text):
    parts=[part for part in re.split(r'(?<!\d)[，,]|[，,](?!\d{3}(?:\D|$))|[。；;！!\n]|(?<=[？?])|但是|不过|然而|而是|并且|而且|同时|另外|且|而|(?<!不)但', text) if part.strip()]
    rows=[]
    cursor=0
    for part in parts:
        start=text.find(part,cursor);end=start+len(part);cursor=end
        if rows and (re.match(r'这(?:一点|个|些|几项|两点).{0,12}(?:不能|无法|没法|需|要).{0,8}(?:保证|确认|承诺|核实)',part) or re.fullmatch(r'(?:我还?|这点)?(?:需要|还需|需|待)(?:核实|确认)(?:后.{0,12})?',part.strip())):rows[-1]=(rows[-1][0],end)
        else:rows.append((start,end))
    return [text[start:end] for start,end in rows]


def modality(text, start=0, end=None):
    end = len(text) if end is None else end
    before, after = text[:start], text[end:]
    if re.search(r'您(?:平时|通常)?更?(?:习惯|喜欢|偏好|倾向).{0,18}还是',text) and re.search(r'习惯|喜欢|偏好|倾向',before):return 'question'
    near = before[-18:] + text[start:end]
    if re.match(r'的话|方面',after) and not re.search(r'(?:可|可以|能|支持|只能|不支持)$',before):return 'topic'
    if re.search(r'(?:要|想|希望)(?:能|可以)?$',before):return 'requirement'
    if re.search(r'(?:谈不上|并非|不是)(?:是)?$',before) and not re.search(r'不能|无法|不能确认',before[-16:]):return 'asserted'
    if re.search(r'(?:(?:不能|无法|不|没法)(?:保证|承诺|当作)|不建议当作).{0,8}$',before):return 'unresolved'
    if re.match(r'(?:方面|性能).{0,8}(?:不能承诺|不保证|需核实)',after):return 'unresolved'
    if re.search(r'(?:没有|未提供).{0,12}(?:信息|资料|依据)\s*$',before[-24:]):return 'unresolved'
    if re.search(r'(?:资料|信息|依据)(?:里|中)?(?:没有|未提供)\s*$',before):return 'unresolved'
    if re.search(r'(?:关于|至于|您问的)\s*$',before) and not after.strip():return 'topic'
    if re.search(r'(?:没有|找不到|不存在|无).{0,30}(?:选择|匹配|符合|的包|包袋|商品|款式)',text) and re.search(r'以内|以下|同时|符合|匹配',text):return 'constraint'
    for match in re.finditer(r'“[^”]*”|「[^」]*」|‘[^’]*’',text):
        if match.start()<=start<match.end() and re.search(r'不能|无法|不要|未|您(?:说|提到|发)|引用|转述',text[:match.start()]):return 'attributed'
    if re.search(r'是否|能否|能不能|会不会|有没有|是不是|可不可以|不能确认|无法确认|不确定|未提供|未明确|未说明|资料没有|没有资料', near):
        return 'unresolved'
    tail=re.sub(r'^(?:\s|[，,]|元|人民币|的|制作|工艺|性能|方面|这点|这一点|这方面)*','',after)
    pending=r'(?:目前|现在)?(?:还|仍|尚)?(?:未提供|未明确|未说明|没有资料|不在资料|待核实|待确认|核实后|确认后|需(?:要|进一步)?(?:核实|确认)|我(?:先|会|需要|需)?(?:帮您)?(?:确认|核实))'
    if re.match(pending+r'(?=$|[，。；？?]|后|再|一下|才能)',tail) or re.match(r'(?:和|及|、)[^，。；]{1,16}(?:我核实后|我确认后)',tail):
        return 'unresolved'
    if re.match(r'还是.{1,18}[，,](?:需要|需|待)(?:核实|确认)(?:后.{0,12})?$',after):return 'unresolved'
    if re.match(r'.{0,18}这(?:两|三|几)点.{0,12}(?:没有|未提供|不在).{0,4}资料',after):return 'unresolved'
    if re.search(r'(?:吗|呢|[?？])\s*$', after):
        return 'question'
    if re.search(r'必须|要求|您要|您希望|想要',before[-12:]):return 'requirement'
    if re.search(r'这(?:两|三|几)?点.{0,8}(?:不能|无法|没法).{0,4}(?:确认|回|答)',after):return 'unresolved'
    if re.search(r'这(?:一点|个|些|几项|两点).{0,12}(?:不能|无法|没法).{0,8}(?:保证|确认|承诺)',after):return 'unresolved'
    if re.search(r'(?:我|我们)(?:可以|能|会)(?:做到|给您|兑现|结算|提供)',after):return 'asserted'
    if re.search(r'您(?:提到|说)|客户(?:说|称)|引用|转述', before) and not re.search(r'但|不过|实际上|目前|我们', before[re.search(r'您(?:提到|说)|客户(?:说|称)|引用|转述', before).end():]):
        return 'attributed'
    return 'asserted'


def rejected_offer(text,start,end):
    before,after=text[:start],text[end:]
    return bool(re.search(r'(?:不能|无法|没法|不|没有办法)(?:直接|先|马上|向您|给您|再|这样|答应|按|以){0,4}$',before) or re.search(r'^.{0,18}(?:不能|无法|没法|没有办法|不)(?:直接|先|马上|向您|给您|再|这样){0,4}(?:回|发|给|答应|按.{0,6}结算|结算|兑现|提供|做到)',after))


def prohibits_action(text,start,end):
    before,after=text[:start],text[end:]
    return bool(re.search(r'不要|不能|不建议|不推荐|先别|避免|别|不适合',before) or re.match(r'^(?:也|都|仍然|仍|同样)?(?:不建议|不推荐|不可以|不可取|不能)(?:的|了)?\s*$',after))


def alleges_missing_answer(text):
    return bool(re.search(r'(?:候选|回复|原文|这条|该条).{0,8}(?:没有|未).{0,3}(?:回答|给出|提供)|(?:没有|未).{0,3}回答|漏答',text))


def owner(text, start, end, category):
    before, after = text[:start], text[end:]
    cues = []
    for kind, pattern in [('customer_item', PERSONAL), ('competitor', OTHER), ('budget', r'预算|上限|最多|不超过|控制在'), ('product', r'包体|包身|本品|这款|售价|标价|现价|价格|结算')]:
        if category != 'money' and kind == 'budget':
            continue
        personal=list(re.finditer(PERSONAL,before))
        cues.extend((m.start(), kind) for m in re.finditer(pattern, before) if kind!='product' or not any(p.start()<=m.start()<p.end() for p in personal))
    if category != 'money':
        cues.extend((m.start(),'customer_item') for m in re.finditer(r'iphone\s*\d+(?:\s*pro\s*max|\s*pro|\s*plus|\s*mini)?|裸机|机身|手机(?:的)?(?:尺寸|大小|长宽)|手机连壳|手机壳|保护壳',before,re.I))
    if category == 'money':
        if re.search(r'您(?:会|在)?(?:拿|用)$',before) and re.match(r'(?:元)?(?:来|去)?(?:衡量|比较|考虑|评估)',after):return 'customer_reference'
        if re.match(r'(?:元)?(?:的)?(?:差价|价差|差别|价格差)',after) or re.search(r'合计|总计|一共|总价|总额|价差',before):
            nearest=max(cues,default=(-1,'product'))[1]
            return nearest if nearest in ('budget','competitor','customer_reference') else 'order'
        if re.search(r'(?:不能|无法|没法|不)(?:直接|马上|现在|今天|先|答应|承诺|再|给您){0,4}(?:按|以)$',before):return 'rejected_price'
        if re.match(r'(?:元)?(?:的)?(?:预算|上限)', after):return 'budget'
        if re.match(r'(?:元)?(?:那款|那家)', after):return 'competitor'
        if re.match(r'(?:元)?(?:以内|以下)', after) and not re.search(r'这款|包(?:价格|售价)?|标价|售价',before):return 'budget'
        if re.match(r'(?:元)?(?:今天|现在|目前)?(?:无法|不能|没法)(?:结算|成交|购买|做到)',after):return 'rejected_price'
        if re.search(r'实付|退款|差价|订单金额', before):return 'order'
    return max(cues, default=(-1, 'product'))[1]


def completed_actions(text):
    pattern = r'(?:刚才|刚刚)?(?:我|我这边|我们)?(?:已经|刚刚|刚|已)?(?:致电|打电话给|联系了|刷新了)[^，。；！？]{0,22}(?:查过|查到|核实过|查询过)|(?:我|我们)(?:刚刚|刚|已经)?刷新了[^，。；！？]{0,16}系统|(?:已经|已)(?:为您|给您|帮您|替您)?(?:查询|查库|查过|查到|核实|确认|登记|提交|预留|预约|退款|留位|留好)|(?:我|我这边|我们)(?:已经|刚刚|刚)?(?:查过|查到|没有查到|没查到|核对过|核实过|查询过)|(?:(?:给您|为您|帮您|替您))?(?:登记|提交|预留|预约|退款|留位)(?:好了|完成了?|成功了?|办妥了?|完毕)'
    found = []
    positioned=[]
    cursor=0
    for part in clauses(text):
        offset=text.find(part,cursor);positioned.append((offset,part));cursor=offset+len(part)
    for match in re.finditer(pattern, text):
        before = text[max(0,match.start()-12):match.start()]
        if re.search(r'(?:未|没有|尚未|不能|不代表|不等于|无法|不是|别|不要)(?:直接|说|声称|回复|表示)?[“「]?$', before):continue
        if re.search(r'(?:可以|会|准备|计划|打算|希望|需要)(?:先|再|帮您|替您|为您|给您)?$',before) or re.match(r'后|以后|之后',text[match.end():]):continue
        if before.count('“') > before.count('”') or before.count('「') > before.count('」'):continue
        if re.search(r'确认|核实',match[0]) and re.match(r'(?:的)?(?:信息|资料|内容|事实)',text[match.end():]):continue
        offset,clause=next(((pos,c) for pos,c in positioned if pos<=match.start()<pos+len(c)),(match.start(),match[0]))
        start=match.start()-offset
        own_query=match[0].startswith('我') and not re.search(r'(?:您|客户)(?:说|提到)[：:]?$',before)
        question=bool(re.search(r'[?？]|是否|能否|不知道|不能确认|不确定',clause))
        if modality(clause,start,start+len(match[0]))!='asserted' and not (own_query and not question):continue
        found.append(match[0])
    return found


def direction(value, prepared):
    from datetime import date,datetime
    from zoneinfo import ZoneInfo
    rows = [r for r in prepared.get('messages', []) if r.get('role') == 'customer' and r.get('kind') == 'text']
    background = value.get('client_info', '')
    latest=rows[-1] if rows else None
    old_context=bool(re.search(r'去年|前年|半年前|\d+个月前|\d+年前|(?:旧|历史)(?:聊天|记录)|(?:聊天|记录).{0,12}(?:20\d{2}年|20\d{2}[-年])',background))
    no_new=bool(re.search(r'(?:没有|无|未有|没收到).{0,12}(?:新.{0,5}(?:消息|来信|咨询)|互动|联系|近期来信)',background))
    current=any(not re.search(r'(?:没有|无|不是|并非|未收到).{0,4}$',background[:m.start()]) for m in re.finditer(r'(?:这|本)次(?:是|为)?客户主动|客户(?:刚刚|刚|今天|本次).{0,8}(?:发来|来信|问|主动咨询)|这是(?:刚收到|本次客户|客户刚发)',background))
    timestamp=None;timestamp_field=None
    if latest:
        for field in ('sent_at','message_time','timestamp','timestamp_text'):
            raw=latest.get(field)
            if not isinstance(raw,str):continue
            match=re.search(r'(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})',raw)
            if match:
                try:timestamp=date(*map(int,match.groups()));timestamp_field=field;break
                except ValueError:pass
    age=(datetime.now(ZoneInfo('America/New_York')).date()-timestamp).days if timestamp else None
    historical=old_context and no_new and not current and not (age is not None and 0<=age<=7)
    ambiguous=bool(latest and ((age is not None and (age>30 or age<0)) or old_context and not no_new or no_new and not old_context or old_context and no_new and current)) and not historical
    if latest and not timestamp and prepared.get('context_id') and not current and not historical:ambiguous=True
    mode='outbound' if historical or not latest else 'needs_confirmation' if ambiguous else 'responsive'
    if current and not (old_context and no_new) and age is None:mode='responsive'
    uncertainty='发送日期为'+timestamp.isoformat()+'，需确认是否仍是本次要回复的咨询' if age is not None and (age>30 or age<0) else '截图未保留可确定的消息发送日期' if prepared.get('context_id') and not timestamp else '背景中的新旧来信说明不够明确或相互冲突'
    basis='背景明确旧记录且无新来信' if historical else uncertainty if mode=='needs_confirmation' else '按本次输入的客户正文作回应；未发现历史标注，不以问号为准' if mode=='responsive' else '没有本次客户来信，按主动联系处理'
    return dict(mode=mode,historical_chat=historical,latest_customer_id=latest['id'] if latest else None,latest_text=latest['text'] if latest and not historical else '',basis=basis,message_date=timestamp.isoformat() if timestamp else None,message_date_field=timestamp_field,message_age_days=age,source_ids=(['chat.'+latest['id']] if latest else [])+(['background.client_info'] if background else []),confirmation_hint='请在本次背景补一句“这是客户刚发来的消息”或“这是历史记录，本次没有新来信”' if mode=='needs_confirmation' else '')


def pause_evidence(value,prepared):
    if prepared.get('communication',{}).get('historical_chat'):return []
    texts=[prepared.get('communication',{}).get('latest_text',''),value.get('client_info','')]
    found=[]
    for text in texts:
        for match in re.finditer(r'(?:还|再)?(?:得|要)?想想|再考虑|考虑一下|考虑考虑|以后再说|过段时间|下次再|先等等|暂缓|缓一缓|先放一放|晚点再|有空再|稍后.{0,4}(?:决定|说)|明天再.{0,4}(?:决定|说)|过几天再',text):
            from quality import negated
            if not negated(text[:match.start()]):found.append(match[0])
    return found


def pause_behavior(messages,prepared):
    from quality import negated
    latest=prepared.get('communication',{}).get('latest_text','')
    errors=[]
    no_reservation=bool(re.search(r'(?:别|不要|不用|不必).{0,5}(?:预留|留|留货)',latest))
    for index,text in enumerate(messages):
        if re.search(r'[?？]|要不要|我推荐|不妨|试背|再给您看看|再介绍.{0,8}(?:款|包|卡夹)',text):
            errors.append(dict(code='selling_during_pause',candidate_index=index,evidence=text,message='客户暂缓时回复仍主动推进选购。'))
        if no_reservation:
            for part in clauses(text):
                for m in re.finditer(r'(?:帮您|为您|替您|给您).{0,4}(?:预留|留(?:一|好|货|包))|已经.{0,8}(?:预留|留好)',part):
                    if not negated(part[:m.start()]):errors.append(dict(code='reservation_against_request',candidate_index=index,evidence=part,message='客户要求不预留，回复仍表示将预留或已经预留。'))
    return errors
