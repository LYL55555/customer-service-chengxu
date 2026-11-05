import argparse
import base64
import json
from datetime import datetime, timezone

from context_store import AssetStore, confirm_context, extract_draft, state_evidence
from engine import ROOT, generate, json_text


def main():
    parser=argparse.ArgumentParser(description="少量虚构截图开发验证，不属于正式50例。")
    parser.add_argument("--confirm-drafts",action="store_true",help="由开发脚本确认原草稿，明确不冒充顾问人工审核")
    parser.add_argument("--ocr-only",action="store_true",help="只验收本地OCR和确认记录，不请求云模型")
    args=parser.parse_args()
    cases=json.loads((ROOT/"fixtures"/"chat_cases.json").read_text(encoding="utf-8"))
    assets=AssetStore();rows=[]
    for case in cases:
        ids=[]
        for page in case["pages"]:
            path=ROOT/page["file"]
            asset=assets.add(dict(filename=path.name,kind="chat_screenshot",data_url="data:image/png;base64,"+base64.b64encode(path.read_bytes()).decode()))
            ids.append(asset["asset_id"])
        draft=extract_draft(ids,source="development-real-local-ocr")
        state=state_evidence(draft["messages"])
        key=lambda message:(message["role"],message["kind"],"".join(message["text"].split()),"".join(message["quoted_text"].split()))
        expected=[]
        for page in case["pages"]:
            overlap=0
            for count in range(min(len(expected),len(page["messages"])),1,-1):
                if [key(item) for item in expected[-count:]]==[key(item) for item in page["messages"][:count]]:
                    overlap=count;break
            expected.extend(page["messages"][overlap:])
        row=dict(case_id=case["id"],ground_truth=case,draft=draft,draft_state_check=state,count_matches=len(draft["messages"])==case["expected_message_count"],state_matches=state["state"]==case["expected_state"],ordered_text_role_kind_quote_match=[key(item) for item in expected]==[key(item) for item in draft["messages"]],comparison_normalization="仅忽略换行和空格；不改原始OCR记录")
        print(case["id"],"messages",len(draft["messages"]),"state",state["state"],flush=True)
        for message in draft["messages"]:print(message["id"],message["role"],message["kind"],message["text"],"QUOTE",message["quoted_text"],flush=True)
        if args.confirm_drafts and all(message["role"]!="unknown" for message in draft["messages"]):
            confirmed=confirm_context(draft["run_id"],draft["messages"],source="development-script-unmodified-draft")
            row["confirmation"]=confirmed
            if args.ocr_only:
                row["generation_status"]="deferred_by_user_ocr_acceptance_only"
            else:
                record=generate({"input":dict(scenario="价格异议",client_info="虚构客户；仅使用已确认聊天。",conversation="",related_info="资料中的优惠说法不代表品牌授权。",advisor_instruction="按最新客户状态温暖回应。",product_ids=["P02"],context_id=confirmed["run_id"])},source="development-context-pipeline")
                row["generation"]=record
                print("generation",record["status"],record.get("error",{}).get("code",""),flush=True)
        else:row["generation_status"]="awaiting_advisor_confirmation"
        rows.append(row)
    output=ROOT/"artifacts"/"context_dev_results.json"
    output.write_text(json_text(dict(created_at=datetime.now(timezone.utc).isoformat(),kind="development-not-formal-evaluation",results=rows)),encoding="utf-8")
    print("saved",output,flush=True)


if __name__=="__main__":main()
