import copy
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine
from workspace_store import WorkspaceStore
from revalidation import revalidate


def main():
    target = ROOT / 'data/submission_replay_v0211.json'
    if target.exists():
        print('提交回放已载入，未覆盖已有客户、草稿或回复')
        return
    data = json.loads((ROOT / 'demo_materials/submission_replay_v0.21.1.json').read_text())
    workspace = WorkspaceStore()
    advisor = workspace.create('advisor', dict(name='提交回放 · 虚构顾问小林'))['id']
    sessions = []
    for case in data['cases']:
        created = workspace.create('customer', dict(advisor_id=advisor, name=case['customer_name']))
        customer = created['id']
        conversation = next(row['id'] for row in created['conversations'] if row['customer_id'] == customer)
        with workspace.connect() as db:
            db.execute('UPDATE conversations SET title=? WHERE id=?', (case['title'] + ' · 保存结果回放', conversation))
        workspace.checkpoint(advisor, conversation, dict(mutation_id=uuid.uuid4().hex, revision=0, profile_revision=0, preferences='', draft=dict(input=case['input'], context={}, revision_text='', target='')))
        profile = workspace.customer_snapshot(advisor, conversation)
        runs = []
        for item in case['records']:
            original = item['record']
            record = copy.deepcopy(original)
            record['customer_context'] = profile
            record['confirmed_context']['customer_context'] = profile
            record = revalidate(record)
            expected = item['expected_status']
            if record['status'] != expected:
                raise RuntimeError('保存回放的当前校验状态与封装记录不符，已停止；未改候选或改成成功')
            record.update(run_id=uuid.uuid4().hex, parent_run_id=None, record_kind='submission-saved-real-result-replay', demo_replay=dict(source_run_id=original['run_id'], source_app_version=original['app_version'], source_status=original['status'], source_record=item['source_record'], label=item['label'], explicit_case_mapping=case['case_id'], new_model_calls=0, note='原文保存回放；仅新建明确归属的虚构演示会话，不是现场生成'))
            record = engine.RunStore().save(record)
            workspace.remember_run(advisor, conversation, record)
            runs.append(dict(run_id=record['run_id'], expected_status=expected, source_run_id=original['run_id'], source_version=original['app_version']))
        sessions.append(dict(case_id=case['case_id'], advisor_id=advisor, customer_id=customer, conversation_id=conversation, runs=runs))
    target.write_text(engine.json_text(dict(app_version=engine.APP_VERSION, advisor_id=advisor, sessions=sessions, new_model_calls=0)))
    print('已载入保存结果回放；从当前客户选择“提交回放 · 虚构顾问小林”下的客户，模型调用0')


if __name__ == '__main__':
    main()
