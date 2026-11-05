import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from engine import APP_VERSION, ROOT, SCENARIOS, GenerationError, RunStore, brand_data, generate, json_text, load_config, local_settings
from context_store import AssetStore, confirm_context, extract_draft
from chat_library import ChatLibrary
from workspace_store import WorkspaceStore
from workspace_index import WorkspaceIndex
import sqlite3

STORE = RunStore()
ASSETS = AssetStore()
CONTEXTS = RunStore(ROOT / "data" / "contexts")
CHATS = ChatLibrary(CONTEXTS)
WORKSPACE = WorkspaceStore()
WORKSPACE.seed_demo()


def index():
    return WorkspaceIndex(WORKSPACE, CONTEXTS, STORE, ASSETS, CHATS)


CONNECTION = {"identity": None, "state": "unverified"}
STATIC = {"/understanding.js": ("understanding.js", "text/javascript; charset=utf-8"), "/workspace.js": ("workspace.js", "text/javascript; charset=utf-8"), "/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/context.js": ("context.js", "text/javascript; charset=utf-8"), "/history.js": ("history.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}


def saved_examples():
    labels={'N21':'确认库存与预留','N29':'拉链售后处理','N39':'了解活动内容'}
    try:
        manifest=json.loads((ROOT/'data/submission_demo.json').read_text())
        result=[]
        for item in manifest['sessions']:
            advisor=manifest['advisor_id'];conversation=item['conversation_id']
            row=WORKSPACE.open(advisor,conversation)
            if row['customer_id']!=item['customer_id']:continue
            result.append(dict(advisor_id=advisor,conversation_id=conversation,customer_id=row['customer_id'],label=labels.get(item['case_id'],'保存结果示例')))
        return result
    except (OSError,ValueError,KeyError,GenerationError):return []


def status():
    try:
        config = load_config()
        config.validate()
        identity = (config.base_url, config.model, config.api_key)
        state = CONNECTION["state"] if CONNECTION["identity"] == identity else "unverified"
        labels = {"unverified": "已配置，尚未验证连接", "connected": "模型接口已连通", "failed": "模型接口调用失败，请检查配置或网络"}
        return dict(state=state, message=labels[state], model=config.model, host=urlsplit(config.base_url).hostname, app_version=APP_VERSION)
    except GenerationError as error:
        return dict(state="unconfigured" if error.code == "not_configured" else "invalid", message=error.message, app_version=APP_VERSION)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send(self, data, code=200, content_type="application/json; charset=utf-8", filename=None):
        body = data if isinstance(data, bytes) else json_text(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        try:
            return urlsplit("http://" + self.headers.get("Host", "")).hostname in ("localhost", "127.0.0.1")
        except ValueError:
            return False

    def scope(self):
        query = parse_qs(urlsplit(self.path).query)
        advisor = self.headers.get("X-Advisor-ID") or query.get("advisor", [""])[0]
        conversation = self.headers.get("X-Conversation-ID") or query.get("conversation", [""])[0]
        WORKSPACE.scope(advisor, conversation)
        return advisor, conversation

    def authorize(self, kind, identity, pending=False):
        advisor, conversation = self.scope()
        WORKSPACE.allowed(advisor, conversation, kind, identity, pending=pending)

    def do_GET(self):
        if not self.allowed_host():
            return self.send({"message": "仅允许从本机访问。"}, 403)
        path = urlsplit(self.path).path
        try:
            if path in STATIC:
                filename, content_type = STATIC[path]
                return self.send((ROOT / "web" / filename).read_bytes(), content_type=content_type)
            if path == "/api/workspace":
                return self.send(WORKSPACE.tree())
            if path == "/api/workspace/open":
                row=WORKSPACE.open(*self.scope())
                if row.get('last_valid_run_id'):
                    from delivery import guard
                    if not guard(STORE.get(row['last_valid_run_id']))['allowed']:
                        row['stored_last_valid_run_id']=row['last_valid_run_id'];row['last_valid_run_id']=None
                return self.send(row)
            if path == "/api/workspace/pending-preview":
                self.scope()
                query = parse_qs(urlsplit(self.path).query)
                kind, identity = query.get("kind", [""])[0], query.get("id", [""])[0]
                if kind not in ("context", "run") or not WORKSPACE.unassigned(kind, [identity]):
                    raise GenerationError("workspace_scope", "这份资料已归档，请从所属会话打开。")
                resources = index().graph(kind, identity)
                if kind == "context":
                    original = CONTEXTS.get(identity)
                    chat = CHATS.get(identity) if original.get("status") in ("draft", "confirmed") else None
                    record = CONTEXTS.get(chat["latest_context_id"]) if chat else original
                else:
                    record = STORE.get(identity)
                return self.send({"record": record, "linked_count": len(resources)})
            if path == "/api/workspace/pending":
                self.scope()
                return self.send(index().pending())
            if path == "/api/status":
                return self.send(status())
            if path == "/api/vision/status":
                from vision_support import capability_status
                return self.send(capability_status())
            if path == "/api/chats":
                query = parse_qs(urlsplit(self.path).query).get("q", [""])[0]
                advisor, conversation = self.scope()
                owned = WORKSPACE.ids(advisor, conversation, "context")
                return self.send([row for row in CHATS.chats(query) if row["chat_id"] in owned])
            if path.startswith("/api/chats/"):
                identity = path.removeprefix("/api/chats/")
                self.authorize("context", identity)
                return self.send(CHATS.get(identity))
            if path == "/api/context-history":
                owned = WORKSPACE.ids(*self.scope(), "context")
                rows=[]
                if CONTEXTS.path.exists():
                    for file in sorted(CONTEXTS.path.glob("*.json"),key=lambda item:item.stat().st_mtime,reverse=True):
                        if file.stem not in owned: continue
                        row=CONTEXTS.get(file.stem)
                        if row.get("status") in ("draft","confirmed"):
                            rows.append(dict(context_id=row["run_id"],created_at=row["created_at"],status=row["status"],message_count=len(row["messages"]),source=row.get("source")))
                        if len(rows)>=20:break
                return self.send(rows)
            if path.startswith("/api/assets/"):
                asset_id = path.removeprefix("/api/assets/").removesuffix("/content")
                self.authorize("asset", asset_id)
                metadata = ASSETS.get(asset_id)
                return self.send(ASSETS.raw(asset_id), content_type=metadata["mime"]) if path.endswith("/content") else self.send(metadata)
            if path.startswith("/api/contexts/"):
                identity = path.removeprefix("/api/contexts/")
                self.authorize("context", identity)
                return self.send(CONTEXTS.get(identity))
            if path.startswith("/api/context-bundle/"):
                from trace_export import export_context_bundle
                context_id=path.removeprefix("/api/context-bundle/")
                self.authorize("context", context_id)
                return self.send(export_context_bundle(context_id,CONTEXTS,ASSETS),content_type="application/zip",filename=f"chengxu-context-{context_id}.zip")
            if path == "/api/meta":
                brand = brand_data()
                cases = json.loads((ROOT / "dev_cases.json").read_text(encoding="utf-8"))
                return self.send(dict(scenarios=SCENARIOS, products=brand["products"], brand_version=brand["version"], app_version=APP_VERSION, cases=cases, saved_examples=saved_examples()))
            if path == "/api/runs":
                owned = WORKSPACE.ids(*self.scope(), "run")
                rows = [STORE.get(identity) for identity in owned]
                rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
                from delivery import guard
                return self.send([dict(run_id=row["run_id"],created_at=row["created_at"],status=row["status"],scenario=row.get("input",{}).get("scenario"),record_kind=row.get("record_kind"),delivery_allowed=guard(row)['allowed']) for row in rows])
            if path.startswith("/api/runs/"):
                identity = path.removeprefix("/api/runs/")
                self.authorize("run", identity)
                record = STORE.get(identity)
                from delivery import present
                record=present(record)
                if record.get("status") in ("error","needs_advisor"):
                    from failure_guidance import explain_failure
                    record = {**record, "ui_guidance": explain_failure(record)}
                return self.send(record)
            if path.startswith("/api/export/"):
                self.authorize("run", path.removeprefix("/api/export/"))
                record = STORE.get(path.removeprefix("/api/export/"))
                from delivery import present
                record=present(record)
                return self.send(record, filename=f"chengxu-{record['run_id']}.json")
            if path.startswith("/api/bundle/"):
                from trace_export import export_bundle
                run_id=path.removeprefix("/api/bundle/")
                self.authorize("run", run_id)
                return self.send(export_bundle(run_id,STORE,CONTEXTS,ASSETS),content_type="application/zip",filename=f"chengxu-{run_id}.zip")
            return self.send({"message": "页面不存在。"}, 404)
        except GenerationError as error:
            return self.send({"message": error.message}, 404)
        except (OSError, ValueError, sqlite3.Error):
            return self.send({"message": "本地资料读取失败，请检查文件。"}, 500)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if not self.allowed_host() or (origin and origin != "http://" + self.headers.get("Host")):
            return self.send({"message": "请求来源不正确，请从本机页面重试。"}, 403)
        path = urlsplit(self.path).path
        if path not in ("/api/understanding", "/api/workspace/create", "/api/workspace/checkpoint", "/api/workspace/claim", "/api/generate", "/api/assets", "/api/contexts/extract", "/api/contexts/confirm", "/api/chats/rename", "/api/vision/check", "/api/contexts/vision"):
            return self.send({"message": "接口不存在。"}, 404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8_000_000 or self.headers.get_content_type() != "application/json":
                return self.send({"message": "请使用有效的JSON请求，内容不要过长。"}, 400)
            payload = json.loads(self.rfile.read(size))
        except (ValueError, TypeError):
            return self.send({"message": "请求格式不正确。"}, 400)
        try:
            if not isinstance(payload, dict):
                return self.send({"message":"请求格式不正确。"},400)
            if path == "/api/workspace/create":
                return self.send(WORKSPACE.create(payload.get("kind"), payload))
            advisor, conversation = self.scope()
            if path == "/api/understanding":
                from engine import clean_input, prepare_context
                from understanding import build_understanding
                brand = brand_data()
                incoming=payload.get('input') or {}
                if 'chat_import' not in incoming:
                    from delivery import bind_selected
                    incoming,_=bind_selected(incoming,WORKSPACE.open(advisor,conversation),CONTEXTS)
                value = clean_input(incoming, brand["products"])
                if value.get("context_id"): self.authorize("context", value["context_id"])
                for identity in value.get("supplement_ids", []): self.authorize("asset", identity)
                prepared=prepare_context(value,CONTEXTS,ASSETS)
                prepared['customer_context']=WORKSPACE.customer_snapshot(advisor,conversation)
                return self.send(build_understanding(value,prepared,brand["products"]))
            if path == "/api/workspace/checkpoint":
                return self.send(WORKSPACE.checkpoint(advisor, conversation, payload))
            if path == "/api/workspace/claim":
                return self.send(index().claim(advisor, conversation, payload.get("kind"), payload.get("id")))
            if path == "/api/assets":
                result = ASSETS.add(payload)
                WORKSPACE.link(advisor, conversation, [("asset", result["asset_id"])])
                return self.send(result)
            if path == "/api/contexts/extract":
                for identity in payload.get("asset_ids") or []: self.authorize("asset", identity)
                result = extract_draft(payload.get("asset_ids"), ASSETS, CONTEXTS, auto_stitch=payload.get("auto_stitch", True))
                WORKSPACE.link(advisor, conversation, [("context", result["run_id"])])
                return self.send(result)
            if path == "/api/contexts/confirm":
                self.authorize("context", payload.get("draft_id"))
                if payload.get("base_context_id"): self.authorize("context", payload["base_context_id"])
                result = confirm_context(payload.get("draft_id"), payload.get("messages"), ASSETS, CONTEXTS, base_context_id=payload.get("base_context_id"))
                WORKSPACE.link(advisor, conversation, [("context", result["run_id"])])
                return self.send(result)
            if path == "/api/chats/rename":
                self.authorize("context", payload.get("chat_id"))
                return self.send(CHATS.rename(payload.get("chat_id"), payload.get("title")))
            if path == "/api/vision/check":
                from vision_support import check_vision
                return self.send(check_vision())
            if path == "/api/contexts/vision":
                from vision_support import vision_draft
                for identity in payload.get("asset_ids") or []: self.authorize("asset", identity)
                result = vision_draft(payload.get("asset_ids"), ASSETS, CONTEXTS)
                WORKSPACE.link(advisor, conversation, [("context", result["run_id"])])
                return self.send(result)
            value = payload.get("input") or {}
            if value.get("context_id"): self.authorize("context", value["context_id"])
            for identity in value.get("supplement_ids", []): self.authorize("asset", identity)
            for key in ("parent_run_id", "retry_of"):
                if payload.get(key): self.authorize("run", payload[key])
            current = WORKSPACE.open(advisor, conversation)
            checkpoint = payload.get("checkpoint_revision")
            if checkpoint != current["revision"] or payload.get("profile_revision") != current["profile_revision"]:
                raise GenerationError("workspace_conflict", "资料有未保存的变化，请保存后再生成。")
            from delivery import bind_selected
            value,restored=bind_selected(value,current,CONTEXTS)
            if value.get('context_id'):self.authorize('context',value['context_id'])
            marker=value.get('chat_import',{})
            for identity in marker.get('asset_ids',[]):self.authorize('asset',identity)
            if marker.get('draft_id'):self.authorize('context',marker['draft_id'])
            payload={**payload,'input':value,'restored_fields':restored}
            record = generate(payload, store=STORE, customer_context=WORKSPACE.customer_snapshot(advisor, conversation), contexts=CONTEXTS, assets=ASSETS)
            WORKSPACE.remember_run(advisor, conversation, record)
        except GenerationError as error:
            if path in ("/api/contexts/extract", "/api/contexts/confirm", "/api/contexts/vision"):
                import uuid
                from datetime import datetime, timezone
                attempt_id=getattr(error,"context_attempt_id",None)
                if not attempt_id:
                    failure = CONTEXTS.save(dict(run_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(), status="error", source=path, submitted_context_request=payload, error=dict(code=error.code,message=error.message)))
                    attempt_id=failure["run_id"]
                try:
                    WORKSPACE.link(*self.scope(), [("context", attempt_id)])
                except (GenerationError, sqlite3.Error):
                    pass
                return self.send({"message":error.message,"context_attempt_id":attempt_id},422)
            return self.send({"message": error.message, "code": error.code}, 409 if error.code == "workspace_conflict" else 422)
        except (OSError, ValueError, sqlite3.Error):
            return self.send({"message":"本机保存未完成。请保留此页面，检查本地服务或磁盘后重试；不要把本次当作已保存。", "code":"save_failed"},500)
        try:
            config = load_config()
            identity = (config.base_url, config.model, config.api_key)
            code = record.get("error", {}).get("code")
            if record.get("transport_connected"):
                CONNECTION.update(identity=identity, state="connected")
            elif code in ("connection", "timeout", "authentication", "rate_limit", "provider_error", "endpoint"):
                CONNECTION.update(identity=identity, state="failed")
        except GenerationError:
            pass
        self.send(record)


def main():
    try:
        port = int(local_settings().get("PORT", "8765"))
        if not 1024 <= port <= 65535:
            raise ValueError
    except (ValueError, GenerationError):
        print("PORT 配置不正确，请填写 1024 到 65535 之间的端口。", file=sys.stderr)
        return 1
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"本地端口 {port} 无法启动，请在 .env 更换 PORT 后重试。", file=sys.stderr)
        return 1
    print(f"澄序话术助手：http://127.0.0.1:{port}", flush=True)
    print(status()["message"], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
