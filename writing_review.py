import re

VERSION = 'writing-observations-0.7.0'
MODES = {key:'一条独立完整、可直接发送的中文微信；完成task.must_answer，选择来自自然措辞和适当详略，三条没有固定分工' for key in ('reply_1','reply_2','reply_3')}


def observe(messages):
    observations=[]
    trial=[]
    brief=[]
    for index,text in enumerate(messages):
        cues=[m[0] for m in re.finditer(r'试背|背一下|背一背|上肩走|走一段|试一下|试一次|体感.{0,8}(?:准确|判断|体验)|(?:实际|亲自).{0,3}体验',text)]
        if cues:trial.append(index)
        internal=[m[0] for m in re.finditer(r'目录里|目录写|明确可肩背|明确的背法|核对背负(?:感觉|感受)|不便替.{0,5}下结论',text)]
        defensive=[m[0] for m in re.finditer(r'我(?:没法|无法|不能).{0,6}保证|不便替.{0,5}下结论',text)]
        if defensive:observations.append(dict(code='capability_disclaimer',candidate_index=index,evidence=defensive,message='在客户消息中解释顾问的能力限制，需核对是否真正必要。'))
        if internal:observations.append(dict(code='internal_audit_language',candidate_index=index,evidence=internal,message='审核信息或措辞进入客户消息，留给顾问判断自然程度。'))
        if len(text)<=80 and not cues and not internal and not re.search(r'不能保证|无法保证|因人而异|自行判断|需要您.{0,5}(?:判断|体会)',text):brief.append(index)
    if not brief:observations.append(dict(code='no_brief_answer_option',message='未看到简短选项，此线索不证明有错；按本次任务逐句检查是否有多余内容。'))
    return dict(version=VERSION,tone_status='heuristic_hints_only',observations=observations,trial_suggestion_indices=trial,brief_answer_indices=brief,authority='有限文字线索和开发观察，不等于语气通过；不改写候选原文')
