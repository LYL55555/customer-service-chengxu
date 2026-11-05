import base64
import json
from pathlib import Path

from context_store import AssetStore, confirm_context, extract_draft
from engine import ROOT, RunStore, json_text
from screenshot_stitch import normalized
from trace_export import export_context_bundle


def main():
    output=ROOT/'artifacts'/'stitch_real_ocr_v0.5.1.json'
    if output.exists():
        raise SystemExit('已有本轮结果，停止执行，避免覆盖或自动重跑。')
    data=ROOT/'artifacts'/'stitch_ocr_data'
    assets,contexts=AssetStore(data/'assets'),RunStore(data/'contexts')
    cases=json.loads((ROOT/'fixtures'/'overlap_cases.json').read_text())
    rows=[]
    key=lambda row:(row['role'],row['kind'],normalized(row['text']),normalized(row.get('quoted_text')))
    for case in cases:
        ids=[]
        for page in case['pages']:
            file=ROOT/page['file']
            asset=assets.add(dict(kind='chat_screenshot',filename=file.name,data_url='data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()))
            ids.append(asset['asset_id'])
        draft=extract_draft(ids,assets,contexts,source='development-real-local-ocr-overlap')
        filenames={asset_id:page['file'] for asset_id,page in zip(ids,case['pages'])}
        ordered=[filenames[identity] for identity in draft['asset_ids']]
        checks=dict(messages_match=[key(row) for row in draft['messages']]==[key(row) for row in case['expected_messages']],order_match=ordered==case['expected_order'],removed_match=draft['stitching']['removed_occurrences']==case['expected_removed'],raw_pages_intact=all(len(message['sources'])==1 for page in draft['pages'] for message in page['draft_messages']))
        result=dict(case_id=case['id'],checks=checks,passed=all(checks.values()),draft_id=draft['run_id'],ordered_files=ordered,draft=draft,cloud_calls=0)
        if result['passed']:
            confirmed=confirm_context(draft['run_id'],draft['messages'],assets,contexts,source='development-script-unmodified-ocr-stitch-draft')
            result['confirmed_id']=confirmed['run_id']
            bundle=ROOT/'artifacts'/('stitch_'+case['id'].lower()+'_v0.5.1.zip')
            bundle.write_bytes(export_context_bundle(confirmed['run_id'],contexts,assets))
            result['bundle']=str(bundle.relative_to(ROOT))
        rows.append(result)
        print(case['id'],checks,flush=True)
    output.write_text(json_text(dict(kind='development-real-local-ocr-not-model-evaluation',results=rows,all_passed=all(row['passed'] for row in rows),cloud_calls=0)))
    return 0 if all(row['passed'] for row in rows) else 1


if __name__=='__main__':
    raise SystemExit(main())
