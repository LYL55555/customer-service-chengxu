import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from engine import ROOT, generate, json_text


def main():
    parser = argparse.ArgumentParser(description="使用与网页相同的生成逻辑运行虚构开发案例，不属于正式50例评测。")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--revisions", action="store_true")
    parser.add_argument("--output", default="artifacts/dev_results.json")
    args = parser.parse_args()
    cases = json.loads((ROOT / "dev_cases.json").read_text(encoding="utf-8"))
    selected = [case for case in cases if not args.cases or case["id"] in args.cases]
    if not selected:
        parser.error("没有找到指定案例。")
    rows = []
    for case in selected:
        payload = {"input": case["input"]}
        record = generate(payload, source="development")
        rows.append(dict(case_id=case["id"], expectation=case["expectation"], record=record))
        print(case["id"], record["status"], record.get("error", {}).get("code", record.get("result", {}).get("client_state", "")))
        if args.revisions and record["status"] == "success" and case["id"] in ("DEV-COMPARE", "DEV-DECLINE"):
            payload.update(parent_run_id=record["run_id"], advisor_request="更温暖一点，但尊重客户最新决定。" if case["id"] == "DEV-DECLINE" else "简短一点，保留关键事实。", target_index=None)
            child = generate(payload, source="development")
            rows.append(dict(case_id=case["id"] + "-REVISION", expectation="保留客户状态和政策边界，只调整表达", record=child))
            print(case["id"] + "-REVISION", child["status"], child.get("error", {}).get("code", child.get("result", {}).get("client_state", "")))
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), kind="development-not-formal-evaluation", results=rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_text(report), encoding="utf-8")
    print("报告已写入", output)
    return 0 if all(row["record"]["status"] == "success" for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
