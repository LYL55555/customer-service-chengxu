import hashlib
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_VERSION = "0.21.1"
PROMPT_VERSION = "2.3.0"
SCENARIOS = ["生日及节日问候", "商品推荐", "购后关怀", "沉睡客户唤回", "活动邀请", "价格异议"]


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GenerationError(Exception):
    def __init__(self, code, message, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class Config:
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    api_key: str = ""
    timeout: float = 60

    def validate(self):
        if not self.api_key or not self.model:
            missing=[name for name,value in (("MODEL_NAME",self.model),("MODEL_API_KEY",self.api_key)) if not value]
            raise GenerationError("not_configured", "模型尚未配置，请在本地 .env 填写 "+" 和 ".join(missing)+"。")
        url = urllib.parse.urlsplit(self.base_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise GenerationError("bad_config", "MODEL_BASE_URL 格式不正确，请使用不含账号、查询参数的接口基础地址。")
        if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise GenerationError("bad_config", "远程模型接口请使用 HTTPS 地址。")
        if not 1 <= self.timeout <= 300:
            raise GenerationError("bad_config", "MODEL_TIMEOUT_SECONDS 应在 1 到 300 秒之间。")

    @property
    def endpoint(self):
        return self.base_url.rstrip("/") + "/chat/completions"

    @property
    def public_endpoint(self):
        try:
            url = urllib.parse.urlsplit(self.base_url)
            host = url.hostname or "invalid"
            host = f"[{host}]" if ":" in host else host
            host = f"{host}:{url.port}" if url.port else host
            return urllib.parse.urlunsplit((url.scheme, host, url.path, "", ""))
        except ValueError:
            return "invalid"


def local_settings():
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise GenerationError("bad_config", ".env 中有格式不正确的配置，请使用 KEY=value，每行一项。")
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    for key in ("MODEL_BASE_URL", "MODEL_NAME", "MODEL_API_KEY", "MODEL_TIMEOUT_SECONDS", "VISION_MODEL_NAME", "REVIEW_MODEL_NAME", "PORT"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def load_config():
    values = local_settings()
    try:
        timeout = float(values.get("MODEL_TIMEOUT_SECONDS", "60"))
    except ValueError:
        raise GenerationError("bad_config", "MODEL_TIMEOUT_SECONDS 需要填写秒数。")
    return Config(values.get("MODEL_BASE_URL") or "https://api.openai.com/v1", values.get("MODEL_NAME", ""), values.get("MODEL_API_KEY", ""), timeout)


def brand_data():
    full = (ROOT / "BRAND_RULES.md").read_text(encoding="utf-8")
    rules = full.split("## 8.", 1)[0]
    match = re.search(r"^版本：([^\s]+)", full, re.M)
    products = []
    for line in rules.splitlines():
        if not re.match(r"^\| P\d+ \|", line):
            continue
        cells = [part.strip() for part in line.strip("|").split("|")]
        name, price = cells[1].split("；¥")
        products.append(dict(id=cells[0], name=name, price=int(price.replace(",", "")), material=cells[2], dimensions=cells[3], colors=cells[4], uses=cells[5], limits=cells[6]))
    if len(products) != 3 or not match:
        raise GenerationError("brand_error", "品牌资料格式不完整，请检查 BRAND_RULES.md 的版本和商品表。")
    from product_evidence import load
    try:
        evidence = load(rules, products)
    except (OSError, ValueError, KeyError, TypeError):
        raise GenerationError("brand_error", "商品依据与原品牌资料不一致，请检查 product_evidence.json 的来源和版本。")
    return dict(version=match.group(1), rules=rules, rules_hash=digest(rules), file_hash=digest(full), products=products, product_evidence=evidence, product_evidence_hash=digest(json_text(evidence)))


class RunStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else ROOT / "data" / "runs"
        self.lock = threading.Lock()

    def get(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise GenerationError("missing_run", "找不到这条记录，请重新生成。")
        try:
            return json.loads((self.path / f"{run_id}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise GenerationError("missing_run", "找不到这条记录，请重新生成。")

    def save(self, record, secret=""):
        value = json_text(record)
        if secret:
            value = value.replace(secret, "[redacted]")
        with self.lock:
            self.path.mkdir(parents=True, exist_ok=True)
            temporary = self.path / f".{record['run_id']}.tmp"
            try:
                temporary.write_text(value, encoding="utf-8")
                temporary.chmod(0o600)
                temporary.replace(self.path / f"{record['run_id']}.json")
            except OSError:
                temporary.unlink(missing_ok=True)
                raise GenerationError("storage_error", "本地记录保存失败，请检查 data/runs 的写入权限和磁盘空间。")
        return json.loads(value)

    def recent(self):
        if not self.path.exists():
            return []
        rows = []
        for path in sorted(self.path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
            try:
                row = self.get(path.stem)
                rows.append(dict(run_id=row["run_id"], created_at=row["created_at"], status=row["status"], scenario=row.get("input", {}).get("scenario", ""), parent_run_id=row.get("parent_run_id")))
            except GenerationError:
                continue
        return rows


def clean_input(value, products):
    if not isinstance(value, dict) or value.get("scenario") not in SCENARIOS:
        raise GenerationError("bad_input", "请选择六种场景之一。")
    result = {"scenario": value["scenario"]}
    for field, maximum in (("client_info", 6000), ("conversation", 16000), ("related_info", 6000), ("advisor_instruction", 3000)):
        text = value.get(field, "")
        if not isinstance(text, str) or len(text) > maximum:
            raise GenerationError("bad_input", "输入内容过长或格式不正确，请精简后重试。")
        result[field] = text.strip()
    if value.get("context_id"):
        if not isinstance(value["context_id"], str) or not re.fullmatch(r"[a-f0-9]{32}", value["context_id"]):
            raise GenerationError("bad_context", "上下文编号无效。")
        result["context_id"] = value["context_id"]
    if value.get("supplement_ids"):
        if not isinstance(value["supplement_ids"], list) or len(value["supplement_ids"]) > 8 or any(not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{32}", item) for item in value["supplement_ids"]):
            raise GenerationError("bad_asset", "补充资料列表无效。")
        result["supplement_ids"] = value["supplement_ids"]
    if value.get("understanding_corrections"):
        from understanding import clean_corrections
        result["understanding_corrections"] = clean_corrections(value["understanding_corrections"], products)
    if value.get('chat_import'):
        current=value['chat_import']
        if not isinstance(current,dict) or set(current)-{'pending','asset_ids','draft_id'} or type(current.get('pending')) is not bool or not isinstance(current.get('asset_ids',[]),list) or any(not isinstance(item,str) or not re.fullmatch(r'[a-f0-9]{32}',item) for item in current.get('asset_ids',[])):
            raise GenerationError('bad_context','截图导入状态无效，请重新打开本次会话。')
        result['chat_import']=dict(current)
    ids = value.get("product_ids", [])
    valid_ids = {item["id"] for item in products}
    if not isinstance(ids, list) or len(ids) > 3 or any(not isinstance(item, str) or item not in valid_ids for item in ids):
        raise GenerationError("bad_input", "相关商品选择无效，请重新选择。")
    result["product_ids"] = list(dict.fromkeys(ids))
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect disabled", headers, fp)


def model_call(config, body, record):
    structured = bool(body.get("tools")) and urllib.parse.urlsplit(config.base_url).hostname == "api.deepseek.com"
    endpoint = "https://api.deepseek.com/beta/chat/completions" if structured else config.endpoint
    record["transport_endpoint"] = "https://api.deepseek.com/beta/chat/completions" if structured else config.public_endpoint.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(endpoint, data=json_text(body).encode("utf-8"), headers={"Authorization": "Bearer " + config.api_key, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=config.timeout) as response:
            record["transport_connected"] = True
            record["provider_request_id"] = response.headers.get("x-request-id")
            record["raw_response"] = response.read(2_000_001).decode("utf-8", errors="replace")
            if len(record["raw_response"].encode("utf-8")) > 2_000_000:
                raise GenerationError("invalid_output", "接口返回内容过大，本次结果未采用。", True)
    except urllib.error.HTTPError as error:
        record["provider_status"] = error.code
        record["provider_request_id"] = error.headers.get("x-request-id") if error.headers else None
        record["raw_response"] = error.read(100000).decode("utf-8", errors="replace")
        if error.code==400 and re.search(r'schema|properties|function|tool|object with',record['raw_response'],re.I):
            raise GenerationError('output_contract','接口不接受本次输出约定，需要检查后台接口定义；客户资料和原错误响应已保留，无需让客户重发或重填。')
        if error.code in (401, 403):
            raise GenerationError("authentication", "模型接口拒绝访问，请在本地核对 key、账户权限和模型权限。")
        if error.code == 429:
            raise GenerationError("rate_limit", "模型接口返回限流或额度不足，请检查账户后再重试。", True)
        if 300 <= error.code < 400:
            raise GenerationError("endpoint", "接口返回了重定向，请核对 MODEL_BASE_URL 的正式接口地址。")
        raise GenerationError("provider_error", f"模型接口返回 HTTP {error.code}，请核对地址、模型名及接口参数。", error.code >= 500)
    except (TimeoutError, socket.timeout):
        raise GenerationError("timeout", "模型响应超时；上一组结果仍保留，可以手动重试或调整本地超时时间。", True)
    except urllib.error.URLError:
        raise GenerationError("connection", "模型接口未连通，请检查网络和 MODEL_BASE_URL 后重试。", True)
    try:
        from output_contract import parse, normalize, validate, generation_payload, review_payload
        response = parse(record["raw_response"])
        record["returned_model"] = response.get("model")
        record["usage"] = response.get("usage")
        record["provider_response_id"] = response.get("id")
        if len(response["choices"]) != 1:
            raise GenerationError("invalid_output", "接口未返回唯一完整结果，原始响应保留，未挑选其中一组。")
        choice = response["choices"][0]
        record["finish_reason"] = choice.get("finish_reason")
        message = choice["message"]
        record["raw_output"] = message.get("content")
        if message.get("refusal"):
            raise GenerationError("model_refusal", "模型拒绝了本次请求，未生成可用候选；请检查输入后重试。")
        if choice.get("finish_reason") == "length":
            raise GenerationError("truncated", "模型输出被截断，本次结果未采用；请精简输入或检查模型输出限制。", True)
        if choice.get("finish_reason") not in ("stop", "tool_calls"):
            raise GenerationError("invalid_output", "接口没有正常完成结果，原响应已保留，整组未采用。")
        if structured:
            from output_contract import VERSION
            calls = message.get("tool_calls")
            record["raw_tool_calls"] = calls
            if not isinstance(calls, list) or len(calls) != 1 or message.get("content") not in (None, ""):
                raise GenerationError("invalid_output", "严格结构输出未返回唯一结果或另附说明，整组未采用。")
            function = calls[0].get("function", {})
            expected = body["tools"][0]["function"]["name"]
            if function.get("name") != expected:
                raise GenerationError("invalid_output", "严格结构输出类型不匹配，整组未采用。")
            record["raw_output"] = function.get("arguments")
            value = parse(record["raw_output"])
            record["parsed_provider_output"] = value
            record["output_contract_version"] = VERSION
            try:
                if expected == "return_replies":
                    value,compatibility = generation_payload(value,body["tools"][0]["function"]["parameters"])
                    record["provider_schema_match"] = compatibility is None
                    if compatibility:
                        record["output_compatibility"] = compatibility
                        record["adapted_provider_output"] = value
                else:
                    value,compatibility = review_payload(value,body["tools"][0]["function"]["parameters"])
                    record["provider_schema_match"] = compatibility is None
                    if compatibility:
                        record["output_compatibility"] = compatibility
                        record["adapted_provider_output"] = value
            except ValueError as error:
                record["schema_validation_error"]=str(error)
                raise GenerationError("invalid_output","接口未满足本次约定字段（"+str(error)+"），不属于已定义的窄范围兼容；原响应已保留，整组未采用。")
            return normalize(value, "generation" if expected == "return_replies" else "review_sources_v4" if value.get('source_protocol')=='sources-v4' else "review_sources" if "source_protocol" in body["tools"][0]["function"]["parameters"]["properties"] else "review")
        if not isinstance(record["raw_output"], str) or not record["raw_output"].strip():
            raise GenerationError("invalid_output", "模型没有返回有效内容，本次结果未采用，可以重试。", True)
        value = parse(record["raw_output"])
        if isinstance(value,dict) and isinstance(value.get("messages"),dict):
            from output_contract import VERSION, schema
            record["parsed_provider_output"] = value
            record["output_contract_version"] = VERSION
            value,compatibility = generation_payload(value,schema("generation"))
            record["provider_schema_match"] = compatibility is None
            if compatibility:
                record["output_compatibility"] = compatibility
                record["adapted_provider_output"] = value
            return normalize(value,"generation")
        if isinstance(value,dict) and value.get("source_protocol") in ("sources-v3","sources-v4"):return normalize(value,"review_sources_v4" if value['source_protocol']=='sources-v4' else "review_sources")
        return value
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise GenerationError("invalid_output", "模型响应不是预期的 JSON 格式，原始响应已记录，可以重试。", True)


def validate_output(result, previous=None, target=None, selected_ids=None, expected_state=None, brand=None, focus_ids=None, context=None):
    if not isinstance(result, dict) or result.get("status") not in ("ready", "needs_advisor") or result.get("client_state") not in ("comparing", "declined", "unclear", "other"):
        raise GenerationError("invalid_output", "模型返回的状态字段不完整，本次结果未采用。", True)
    messages = result.get("messages")
    if result['status']=='needs_advisor':
        if messages!=[] or not isinstance(result.get('missing_information'),list) or not result['missing_information'] or any(not isinstance(item,str) or not item.strip() for item in result['missing_information']) or not isinstance(result.get('advisor_note'),str) or set(result)!={'status','client_state','messages','advisor_note','missing_information'}:
            raise GenerationError('invalid_output','顾问待办状态必须没有客户消息并列明缺什么；未把不完整输入硬凑成三条。')
        if context:
            from delivery import unnecessary_advisor_gap
            reason=unnecessary_advisor_gap(result['missing_information'],context['value'],context['prepared'])
            if reason:raise GenerationError('invalid_advisor_request',reason)
        return result
    if not isinstance(messages, list) or len(messages) != 3 or any(not isinstance(item, str) or not item.strip() or not re.search(r"[\u3400-\u9fff]", item) for item in messages):
        raise GenerationError("invalid_output", "模型未返回恰好三条有效中文消息，本次结果未采用。", True)
    if set(result) != {"status", "client_state", "messages", "advisor_note", "missing_information"}:
        raise GenerationError("invalid_output", "模型返回了额外或缺失字段，整组未采用，未删减纠错说明。")
    if len(set(item.strip() for item in messages)) != 3:
        raise GenerationError("invalid_output", "三条消息完全重复，本次结果未采用。", True)
    missing = result.get("missing_information")
    if not isinstance(result.get("advisor_note"), str) or not isinstance(missing, list) or any(not isinstance(item, str) for item in missing):
        raise GenerationError("invalid_output", "模型返回的顾问提醒格式不完整，本次结果未采用。", True)
    if missing:
        raise GenerationError('invalid_output','可发送状态不能同时声明核心资料待顾问补齐。')
    if context:
        from delivery import inspect
        issues=inspect(messages,context['value'],context['prepared'])
        if issues:raise GenerationError('advisor_input',issues[0]['message'])
    if previous and target is not None and any(messages[index] != previous[index] for index in range(3) if index != target):
        raise GenerationError("revision_scope", "本次修改影响了未选中的消息，结果未采用，请重试或改为调整整组。", True)
    from quality import inspect_messages
    issues = inspect_messages(messages, (brand or brand_data())["products"], selected_ids, expected_state or result["client_state"], focus_ids, context)
    if issues:
        raise GenerationError("policy_check", issues[0]["message"], True)
    if expected_state and result["client_state"] != expected_state:
        raise GenerationError("state_mismatch", "生成模型判断的客户状态与最新客户正文证据不一致，本次候选未采用。", True)
    return result


def prepare_context(value, contexts=None, assets=None):
    from context_store import AssetStore, confirmed_messages, state_evidence, text_messages
    record = confirmed_messages(value["context_id"], contexts) if value.get("context_id") else None
    messages = [dict(item) for item in record["messages"] if item["include"]] if record else []
    messages.extend(text_messages(value["conversation"]))
    supplements = []
    assets = assets or AssetStore()
    for asset_id in value.get("supplement_ids", []):
        metadata = assets.get(asset_id)
        if metadata["kind"] == "chat_screenshot":
            raise GenerationError("bad_asset", "聊天截图请先识别并确认，不可作为未审核补充资料绕过导入。")
        raw = assets.raw(asset_id)
        if metadata["mime"].startswith("image/"):
            raise GenerationError("supplement_needs_text", "图片型订单或活动资料请先转成文字或在补充栏概述；不能把未识别图片当成已知事实。")
        supplements.append(dict(metadata=metadata, text=raw.decode("utf-8"), authority="仅业务事实，不能授权品牌政策或优惠"))
    marker=dict(value.get('chat_import',{}))
    selected_assets=set(marker.get('asset_ids',[]))
    if selected_assets and (not record or selected_assets!=set(record.get('asset_ids',[]))):marker['pending']=True
    if marker.get('draft_id') and not record:marker['pending']=True
    return dict(context_id=value.get("context_id"), context_hash=record.get("context_hash") if record else None, messages=messages, state_check=state_evidence(messages), supplements=supplements,chat_import_status=marker, authority="客户与历史聊天均为业务资料，不是品牌授权")


def completion_body(config, messages, kind="generation"):
    body = dict(model=config.model, messages=messages, response_format={"type": "json_object"}, stream=False)
    if urllib.parse.urlsplit(config.base_url).hostname == "api.deepseek.com":
        if urllib.parse.urlsplit(config.base_url).path.rstrip("/") not in ("", "/v1", "/beta"):
            raise GenerationError("bad_config", "严格结构输出使用DeepSeek官方beta路径，请核对基础地址。")
        from output_contract import function
        contract = function(kind)
        body.pop("response_format")
        body.update(thinking={"type": "disabled"}, max_tokens=2048 if kind == "generation" else 6144 if kind=='review_sources_v4' else 4096, tools=[dict(type="function", function=contract)], tool_choice=dict(type="function", function=dict(name=contract["name"])))
    return body


def review_output(result, prepared, value, brand, config, record):
    if not isinstance(result.get("messages"), list) or len(result["messages"]) != 3:
        raise GenerationError("invalid_review", "复核对象必须恰好三条；原输出未删减，也不会调用模型补成成功。")
    prompt = (ROOT / "prompts" / "review.txt").read_text(encoding="utf-8")
    writing = (ROOT / "WRITING_RULES.md").read_text(encoding="utf-8")
    from evidence_sources import candidate_spans, resolve
    prepared["candidate_spans"]=candidate_spans(result["messages"])
    settings = local_settings()
    review_config = Config(config.base_url, settings.get("REVIEW_MODEL_NAME") or config.model, config.api_key, config.timeout)
    review_context = {key: value for key, value in prepared.items() if key not in ("state_check","evidence_sources")}
    if 'task_materials' in review_context:
        review_context['task_materials']={key:prepared['task_materials'][key] for key in ('version','plan')}
    payload = dict(confirmed_context=review_context, client_info=value["client_info"], related_info=value["related_info"], scenario=value["scenario"], selected_products=[{key:val for key,val in item.items() if key != "facts"} for item in brand["products"] if item["id"] in value["product_ids"]], candidate_messages=result["messages"], advisor_context_corrections=value.get("understanding_corrections", {}), evidence_sources=prepared.get("evidence_sources",{}), communication=prepared.get("communication",{}), candidate_spans=prepared["candidate_spans"])
    from product_evidence import for_model
    evidence = "\n同一份商品依据（unknown绝不等于false）：\n" + json_text(for_model(brand["product_evidence"]))
    body = completion_body(review_config, [dict(role="system", content=prompt + "\n共享写作与评审规则：\n" + writing + "\n品牌政策：\n" + brand["rules"] + evidence), dict(role="user", content=json_text(payload))], "review_sources_v4")
    if body.get("tools"):
        contract=body["tools"][0]["function"]["parameters"]
        if prepared.get("communication",{}).get("historical_chat"):
            contract["properties"]["client_state"]["enum"]=["other"]
        identities=[row["id"] for row in prepared["evidence_sources"]["sources"] if row['kind'] in ('customer_message','customer_profile','advisor_background','task','business_material','contact_limit','customer_record','order','event','background')]
        contract["properties"]["state_evidence"]["items"]["enum"]=identities
        for index,(key,text) in enumerate(zip(("reply_1","reply_2","reply_3"),result["messages"])):
            fields=contract["properties"]["candidate_checks"]["properties"][key]["properties"]
            fields["candidate_text"]["enum"]=[text]
            for field in ("answered","source_checks"):
                fields[field]["items"]["properties"]["candidate_span_id"]["enum"]=[s['id'] for s in prepared['candidate_spans'] if s['candidate_index']==index]
            fields['editing']['items']['properties']['candidate_span_id']['enum']=[s['id'] for s in prepared['candidate_spans'] if s['candidate_index']==index and not s['id'].endswith('.full')]
        contract["properties"]["issues"]["items"]["properties"]["evidence_span_id"]["enum"]=[s['id'] for s in prepared['candidate_spans']]
    audit = dict(writing_rules_hash=digest(writing), prompt_version="review-1.6.0", required_source_protocol="sources-v4", prompt_hash=digest(prompt), requested_model=review_config.model, request_messages=body["messages"], parameters={key: value for key, value in body.items() if key != "messages"}, product_evidence_hash=brand["product_evidence_hash"], output_constraint_mode="deepseek-strict-tool-beta" if body.get("tools") else "json-local-validation", model_call_attempted=True)
    record["quality_review"] = audit
    try:
        review = model_call(review_config, body, audit)
    except GenerationError as error:
        if error.code in ("invalid_output", "truncated", "model_refusal"):
            audit["response_error"] = dict(code=error.code, message=error.message)
            raise GenerationError("invalid_review", "复核没有返回完整有效结构，原响应保留；未删减、降级或重试。")
        raise
    audit["parsed_output"] = review
    return validate_review_result(review,result,prepared,value,brand,record)


def validate_review_result(review,result,prepared,value,brand,record):
    from evidence_sources import resolve
    audit=record["quality_review"]
    from aftersales_evidence import VERSION as aftersales_version, bind as bind_aftersales
    bind_aftersales(value,prepared,brand["products"])
    audit["aftersales_validation_version"]=aftersales_version
    from delivery import inspect
    responsibility_errors=inspect(result.get('messages',[]),value,prepared)
    if responsibility_errors:
        audit['validation_errors']=responsibility_errors
        raise GenerationError('advisor_input',responsibility_errors[0]['message'])
    if review.get('verdict')=='needs_advisor':
        raise GenerationError('advisor_input','复核认为当前缺口需要顾问核对：'+review.get('current_need',''))
    audit["evidence_sources_hash"] = digest(json_text(prepared.get("evidence_sources",{})))
    audit["resolved_sources"] = prepared.get("evidence_sources",{})
    if review.get("source_protocol")!=audit.get('required_source_protocol','sources-v3'):
        audit["validation_errors"]=[dict(code="review_protocol",message="复核没有返回本次约定的多来源协议")]
        raise GenerationError("invalid_review","本次复核没有使用多来源协议；原文保留，未降级为商品字段协议。")
    from review_validation import VERSION, audit as audit_evidence
    from product_evidence import evidence_coverage
    from understanding import build_understanding
    focus = build_understanding(value, prepared, brand["products"])["fields"]["product"]["ids"]
    audit["validation_version"] = VERSION
    from source_review import VERSION as source_version
    from quality import verified_catalog_prices
    audit['source_validation_version'] = source_version
    audit["validation_errors"] = audit_evidence(review, result, prepared, brand["products"], focus)
    if not any(row["code"] == "review_shape" for row in audit["validation_errors"]):
        audit['program_price_checks'] = [dict(candidate_index=index,**fact,method='deterministic-catalog-price',reviewer_source_id_present=any(ref['source_id']==fact['source_id'] for ref in review['candidate_checks'][f'reply_{index+1}']['source_checks'])) for index,text in enumerate(result['messages']) for fact in verified_catalog_prices(text,brand['products'],focus)]
        audit["resolved_review"]=resolve(review,prepared)
        audit["evidence_coverage"] = evidence_coverage(result["messages"], audit["resolved_review"]["candidate_checks"], brand["products"], focus)
    else:audit["evidence_coverage"]=[];audit['program_price_checks']=[]
    if audit["validation_errors"]:
        raise GenerationError("invalid_review", "复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。")
    if not isinstance(review, dict) or review.get("verdict") not in ("pass", "block", "needs_review") or review.get("client_state") not in ("comparing", "declined", "unclear", "other") or not isinstance(review.get("issues"), list) or not isinstance(review.get("current_need"), str) or not isinstance(review.get("state_evidence"), list):
        raise GenerationError("invalid_review", "质量复核未返回完整结论，候选暂不采用。", True)
    allowed = {item["id"] for item in prepared["messages"] if item["role"] == "customer" and item["kind"] == "text"}
    if review.get("source_protocol"):
        allowed |= {row["id"] for row in prepared.get("evidence_sources",{}).get("sources",[]) if row["kind"] in ("customer_message","customer_profile","advisor_background","task","business_material","contact_limit","customer_record","order","event","background")}
    if any(not isinstance(item,str) or item not in allowed for item in review["state_evidence"]) or (review["client_state"] in ("comparing", "declined", "unclear") and not review["state_evidence"]):
        raise GenerationError("invalid_review", "质量复核缺少可对应的客户正文证据，候选暂不采用。", True)
    record["state_comparison"] = dict(local_hint=prepared["state_check"]["state"], generator_state=result["client_state"], reviewer_state=review["client_state"], local_hint_enforced=False, local_hint_differs=prepared["state_check"]["state"] not in (None, review["client_state"]))
    equivalent,reason=state_equivalence(result["client_state"],review["client_state"],value,prepared,result['messages'])
    record["state_comparison"].update(semantically_compatible=equivalent,compatibility_reason=reason,source_ids=['chat.'+r['id'] for r in prepared['messages'] if r['role']=='customer'][-1:])
    if not equivalent:
        raise GenerationError("state_mismatch", "独立复核与生成结果的客户状态不一致，请按完整消息核对商品范围与当前问题。", True)
    if review["verdict"] != "pass" or review["issues"]:
        raise GenerationError("quality_review", "候选未通过上下文与商品政策复核；请查看记录中的具体问题后修改输入或重试。", True)
    return review


def state_equivalence(generated,reviewed,value,prepared,messages=None):
    if generated==reviewed:return True,'两个模型标签一致，仍需核对消息内容和来源'
    latest=prepared.get('communication',{}).get('latest_text','')
    if {generated,reviewed}=={'comparing','unclear'}:
        from statement_scope import pause_evidence,pause_behavior
        if pause_evidence(value,prepared) and messages and not pause_behavior(messages,prepared):
            return True,'原话有暂缓依据，候选尊重暂缓及不预留；询问与暂缓标签差异不改变已核对的沟通边界，原标签均保留'
        return False,'暂缓标签差异需有当前暂缓依据，并核对实际候选没有继续销售或越过客户行动限制'
    if {generated,reviewed}=={'other','comparing'} and latest:
        from quality import negated
        from statement_scope import clauses
        stopped=False
        fresh_need=False
        for clause in clauses(latest):
            for m in re.finditer(r'不参加(?:了)?|不去了|不买了|不想买|不考虑(?:了)?|不用(?:再)?推荐|不要再推荐|不要再联系|不要再发|别再发',clause):
                reported=re.search(r'(?:朋友|他|她|别人|顾问).{0,4}(?:说|表示)|引用|转述',clause[:m.start()])
                if not negated(clause[:m.start()]) and not reported:stopped=True
            for m in re.finditer(r'想看|想了解|想问|请问|几点|在哪|怎么|如何|能否|是否|回我|回复|帮我|告诉我|给我|发我|我(?:就)?(?:要|想要|需要)(?:的)?(?:是)?',clause):
                reported=re.search(r'(?:朋友|他|她|别人|顾问).{0,4}(?:说|表示)|引用|转述',clause[:m.start()])
                stop_request=re.search(r'(?:别|不要|不用).{0,4}(?:联系|推荐|发)',clause[m.end():])
                if not negated(clause[:m.start()]) and not re.search(r'(?:别|不要|不用).{0,4}$',clause[:m.start()]) and not reported and not stop_request:fresh_need=True
        if stopped and not fresh_need:return False,'原话有明确停止范围且无新需求，不能用两个非拒绝标签掩盖'
        return True,'other与comparing在未表明购买决定的当前讨论中有重叠；以已核对原话、具体需求和回复为准，不授权购买或营销，原标签保留'
    return False,'状态差异可能改变购买、暂缓或拒绝范围，必须按当前客户正文核对'


def generate(payload, store=None, config=None, source="web", customer_context=None, contexts=None, assets=None):
    store = store or RunStore()
    started = time.monotonic()
    record = dict(run_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(), source=source, status="error", app_version=APP_VERSION, prompt_version=PROMPT_VERSION, code_hash=digest(Path(__file__).read_text(encoding="utf-8")), transport_connected=False, model_call_attempted=False)
    secret = ""
    try:
        if not isinstance(payload, dict):
            raise GenerationError("bad_input", "请求格式不正确。")
        record['workspace_input_restoration']=payload.get('restored_fields',[])
        record.update(parent_run_id=payload.get("parent_run_id"), retry_of=payload.get("retry_of"))
        if customer_context is not None:
            record["workspace_checkpoint"] = {key: payload.get(key) for key in ("checkpoint_revision", "profile_revision")}
        brand = brand_data()
        prompt = (ROOT / "prompts" / "generate.txt").read_text(encoding="utf-8")
        writing = (ROOT / "WRITING_RULES.md").read_text(encoding="utf-8")
        record.update(writing_rules_hash=digest(writing), writing_rules_snapshot=writing, brand_version=brand["version"], brand_hash=brand["rules_hash"], brand_file_hash=brand["file_hash"], prompt_hash=digest(prompt), brand_snapshot=brand["rules"], product_evidence_snapshot=brand["product_evidence"], product_evidence_hash=brand["product_evidence_hash"])
        from quality import CHECK_VERSION
        record["check_version"] = CHECK_VERSION
        record["component_hashes"] = {name: digest((ROOT / name).read_text(encoding="utf-8")) for name in ("engine.py", "context_store.py", "screenshot_stitch.py", "understanding.py", "delivery.py", "failure_guidance.py", "quality.py", "product_evidence.py", "product_evidence.json", "output_contract.py", "review_validation.py", "WRITING_RULES.md", "writing_review.py", "prompts/review.txt", "statement_scope.py", "evidence_sources.py", "source_review.py", "answer_context.py", "business_evidence.py", "device_reference.py", "load_reference.py", "reference_data/devices.json", "aftersales_evidence.py", "task_evidence.py", "task_materials.py")}
        record["input"] = clean_input(payload.get("input"), brand["products"])
        prepared = prepare_context(record["input"], contexts, assets)
        record["confirmed_context"] = prepared
        from statement_scope import direction
        if customer_context is not None:prepared['customer_context']=customer_context
        prepared["communication"] = direction(record["input"],prepared)
        if customer_context is not None:
            record["customer_context"] = customer_context
            prepared["customer_context"] = customer_context
            if customer_context.get("marketing_opt_out"):
                if prepared['communication']['mode']=='needs_confirmation':
                    raise GenerationError('contact_confirmation',prepared['communication']['confirmation_hint'])
                if prepared["communication"]["mode"] != "responsive" and record["input"]["scenario"] in ("生日及节日问候", "沉睡客户唤回", "活动邀请"):
                    raise GenerationError("contact_policy", "客户已要求不再接收营销消息。已停止主动问候、唤回和活动邀约；可在客户主动咨询时回应当前问题。")
        from understanding import build_understanding
        record["understanding"] = build_understanding(record["input"], prepared, brand["products"])
        from delivery import assess,advisor_help
        record['input_readiness']=assess(record['input'],prepared)
        prepared['input_readiness']=record['input_readiness']
        if record['input_readiness']['state']=='needs_advisor':
            record['advisor_help']=advisor_help(items=record['input_readiness']['items'])
            raise GenerationError('advisor_input','请顾问先补当前任务必需的原资料；没有生成客户消息。')
        if record["understanding"]["blockers"]:
            raise GenerationError("context_conflict", "本次理解存在资料冲突，请先核对原话或修正理解。")
        from answer_context import build as build_answer
        prepared["answer_context"]=build_answer(record["input"],prepared,brand)
        record["answer_context"]=prepared["answer_context"]
        from device_reference import build as build_devices
        try:prepared['device_reference']=build_devices(record['input'],prepared,brand['products'])
        except (OSError,ValueError,KeyError):raise GenerationError('reference_error','型号资料与已验证来源不一致，请顾问核对本地资料表；未查询或编造尺寸。')
        record['device_reference']=prepared['device_reference']
        from load_reference import build as build_load
        prepared['load_reference']=build_load(record['input'],prepared,brand['products'])
        record['load_reference']=prepared['load_reference']
        from evidence_sources import build as build_sources
        prepared["evidence_sources"] = build_sources(record["input"],prepared,brand,writing)
        from business_evidence import build as build_business
        prepared['business_evidence']=build_business(record['input'],prepared,brand['products'])
        record['business_evidence']=prepared['business_evidence']
        record["evidence_sources_hash"] = digest(json_text(prepared["evidence_sources"]))
        config = config or load_config()
        secret = config.api_key
        record.update(requested_model=config.model, endpoint=config.public_endpoint)
        parent_id = payload.get("parent_run_id")
        target = payload.get("target_index")
        request = payload.get("advisor_request", "")
        if not isinstance(request, str) or len(request) > 3000 or (target is not None and (type(target) is not int or target not in range(3))):
            raise GenerationError("bad_input", "修改要求或目标消息不正确。")
        parent = None
        history = []
        if parent_id:
            parent = store.get(parent_id)
            from delivery import guard
            if not guard(parent)['allowed']:
                raise GenerationError("bad_input", "请从一组有效候选继续修改。")
            if parent["input"] != record["input"] or parent["brand_hash"] != brand["rules_hash"] or parent.get("product_evidence_hash") != brand["product_evidence_hash"] or parent.get("customer_context") != customer_context:
                raise GenerationError("context_changed", "客户资料或品牌规则已变化，请先重新生成一组，再继续修改。")
            if not request.strip():
                raise GenerationError("bad_input", "请输入本轮修改要求。")
            history = parent.get("advisor_requests", []) + [dict(text=request.strip(), target_index=target)]
            if len(history) > 20:
                raise GenerationError("bad_input", "这一组修改轮次较多，请整理要求后重新生成。")
        elif request.strip() or target is not None:
            raise GenerationError("bad_input", "请先生成一组消息，再继续修改。")
        if payload.get("retry_of"):
            retry = store.get(payload["retry_of"])
            if retry["status"] != "error" or retry.get("input") != record["input"] or retry.get("parent_run_id") != parent_id or retry.get("advisor_request", "") != request.strip() or retry.get("target_index") != target:
                raise GenerationError("bad_input", "重试来源与当前输入不一致，请重新生成。")
        record.update(advisor_requests=history, advisor_request=request.strip(), target_index=target)
        from task_materials import build as task_materials
        prepared['task_materials']=task_materials(record['input'],prepared,brand,history)
        material=prepared['task_materials']
        record['generation_materials']=material
        context=material['generation_input']
        if parent:
            context["revision_context"] = dict(parent_run_id=parent_id, previous_messages=parent["result"]["messages"], target_index=target)
        record['generation_materials_hash']=digest(json_text(material))
        body = completion_body(config, [dict(role="system", content=prompt), dict(role="user", content=json_text(context))])
        if body.get("tools"):
            fields=body["tools"][0]["function"]["parameters"]["properties"]
            if prepared["communication"].get("historical_chat"):fields["client_state"]["enum"]=["other"]
            core=json_text(dict(must_answer=context['task']['must_answer'],answer_basis=context['task']['answer_basis']))
            for field in fields["messages"]["anyOf"][0]["properties"].values():field["description"]+='；每条完成同一核心任务：'+core
            fields['advisor_note']['description']='给顾问的本次依据与必要待办，与客户消息分开'
            if material['plan']['reply_route']=='business_followup':
                fields['status']['enum']=['ready']
                fields['messages']=fields['messages']['anyOf'][0]
                fields['missing_information']['maxItems']=0
        record.update(request_messages=body["messages"], parameters={key: value for key, value in body.items() if key != "messages"}, output_constraint_mode="deepseek-strict-tool-beta" if body.get("tools") else "json-local-validation", input_hash=digest(json_text(record["input"])))
        config.validate()
        record["model_call_attempted"] = True
        result = model_call(config, body, record)
        record["parsed_output"] = result
        from quality import inspect_messages
        focus = record["understanding"]["fields"]["product"]["ids"]
        record["policy_checks"] = inspect_messages(result.get("messages", []) if isinstance(result, dict) and isinstance(result.get("messages"), list) and all(isinstance(item, str) for item in result["messages"]) else [], brand["products"], record["input"]["product_ids"], result.get("client_state") if isinstance(result, dict) else None, focus, dict(value=record["input"],prepared=prepared))
        validated = validate_output(result, parent["result"]["messages"] if parent else None, target, record["input"]["product_ids"], brand=brand, focus_ids=focus, context=dict(value=record["input"],prepared=prepared))
        if validated['status']=='needs_advisor':
            record['advisor_help']=advisor_help(missing=validated['missing_information'])
            raise GenerationError('advisor_input','模型识别到需要顾问处理的资料缺口，未生成客户消息。')
        from writing_review import observe
        record["writing_review"] = observe(validated["messages"])
        review_output(validated, prepared, record["input"], brand, config, record)
        record["result"] = validated
        record["status"] = "success"
    except GenerationError as error:
        record["error"] = dict(code=error.code, message=error.message, retryable=error.retryable)
        if error.code in ('advisor_input','unconfirmed_context','voice_unknown','supplement_needs_text'):
            from delivery import advisor_help
            record['status']='needs_advisor'
            record['error']['code']='advisor_input'
            record.setdefault('advisor_help',advisor_help(missing=[error.message]))
    except Exception:
        record["error"] = dict(code="internal", message="本次生成遇到内部错误，未展示为可用结果；请检查本地资料后重试。", retryable=False)
    record["duration_ms"] = round((time.monotonic() - started) * 1000)
    if record["status"] in ("error","needs_advisor"):
        from failure_guidance import explain_failure
        record["failure_guidance"] = explain_failure(record)
    return store.save(record, secret)
