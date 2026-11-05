import copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
from workspace_store import WorkspaceStore
from revalidation import revalidate


def main():
    path=ROOT/'data/submission_demo.json'
    if path.exists():
        print('保存结果演示已存在，未覆盖客户或草稿');return
    data=json.loads((ROOT/'demo_materials/final_saved_results.json').read_text())
    ws=WorkspaceStore();advisor=ws.create('advisor',dict(name='提交演示 · 虚构顾问小林'))['id'];sessions=[]
    for case in data['cases']:
        created=ws.create('customer',dict(advisor_id=advisor,name=case['case_id']+' · 虚构演示客户'));customer=created['id'];conversation=next(r['id']for r in created['conversations']if r['customer_id']==customer)
        with ws.connect()as db:db.execute('UPDATE conversations SET title=? WHERE id=?',(case['title']+' · 保存的真实结果',conversation))
        ws.checkpoint(advisor,conversation,dict(mutation_id=uuid.uuid4().hex,revision=0,profile_revision=0,preferences=case['valid'].get('customer_context',{}).get('preferences',''),draft=case['draft']))
        profile=ws.customer_snapshot(advisor,conversation);ids={}
        for key in ('failed','valid'):
            r=copy.deepcopy(case[key]);origin=r['run_id'];r.update(run_id=uuid.uuid4().hex,record_kind='saved-real-result-demo-replay',customer_context=profile,parent_run_id=None)
            r['confirmed_context']['customer_context']=profile
            r['demo_replay']=dict(source_run_id=origin,explicit_case_mapping=case['case_id'],new_model_calls=0,note='保存的真实结果，明确映射虚构演示客户，不是现场生成')
            if key=='valid':
                r=revalidate(r)
                if r['status']!='success':raise RuntimeError('保存结果未通过当前本地校验，请保留记录检查版本')
            r=engine.RunStore().save(r);ws.remember_run(advisor,conversation,r);ids[key]=r['run_id']
        sessions.append(dict(case_id=case['case_id'],customer_id=customer,conversation_id=conversation,**ids))
    path.write_text(engine.json_text(dict(advisor_id=advisor,sessions=sessions)))
    print('已载入3个虚构会话的真实保存结果与旧失败，模型调用0；在顾问文件夹“提交演示 · 虚构顾问小林”查看')


if __name__=='__main__':main()
