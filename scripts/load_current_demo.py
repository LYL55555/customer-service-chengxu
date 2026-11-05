import copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
from workspace_store import WorkspaceStore
from revalidation import revalidate
from failure_guidance import explain_failure


def main():
    target=ROOT/'data/current_demo_v0190.json'
    if target.exists():print('0.19.0保存结果已载入，未覆盖客户或草稿');return
    data=json.loads((ROOT/'demo_materials/current_results_v0.19.0.json').read_text());ws=WorkspaceStore()
    advisor=ws.create('advisor',dict(name='0.19.0 保存结果回放 · 虚构顾问小林'))['id'];sessions=[]
    for case in data['cases']:
        created=ws.create('customer',dict(advisor_id=advisor,name=case['customer_name']));customer=created['id'];conversation=next(r['id']for r in created['conversations']if r['customer_id']==customer)
        with ws.connect()as db:db.execute('UPDATE conversations SET title=? WHERE id=?',(case['title']+' · 0.19.0保存结果回放',conversation))
        draft=dict(input=case['input'],context={},revision_text='',target='')
        ws.checkpoint(advisor,conversation,dict(mutation_id=uuid.uuid4().hex,revision=0,profile_revision=0,preferences='',draft=draft))
        profile=ws.customer_snapshot(advisor,conversation);runs=[]
        for source in case['records']:
            original=source['record'];record=copy.deepcopy(original)
            record['customer_context']=profile;record['confirmed_context']['customer_context']=profile
            record=revalidate(record)
            if original['app_version']=='0.19.0'and original['status']=='success'and record['status']!='success':raise RuntimeError('当前保存结果未通过原文校验，已停止，不改为成功')
            record.update(run_id=uuid.uuid4().hex,record_kind='saved-real-result-demo-replay',parent_run_id=None,demo_replay=dict(source_run_id=original['run_id'],source_app_version=original['app_version'],source_status=original['status'],label=source['label'],explicit_case_mapping=case['case_id'],new_model_calls=0,note='保存的真实结果回放，不是本次现场生成'))
            if record['status']!='success':record['failure_guidance']=explain_failure(record)
            record=engine.RunStore().save(record);ws.remember_run(advisor,conversation,record)
            runs.append(dict(run_id=record['run_id'],status=record['status'],source_run_id=original['run_id'],source_version=original['app_version']))
        sessions.append(dict(case_id=case['case_id'],advisor_id=advisor,customer_id=customer,conversation_id=conversation,title=case['title'],runs=runs))
    target.write_text(engine.json_text(dict(app_version=engine.APP_VERSION,advisor_id=advisor,sessions=sessions,new_model_calls=0)))
    print('已载入0.19.0五案原文和历史失败；从“顾问与客户”选择“0.19.0 保存结果回放 · 虚构顾问小林”。模型调用0')


if __name__=='__main__':main()
