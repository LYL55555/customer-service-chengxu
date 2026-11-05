import base64
import binascii
import hashlib
import io
import json
import platform
import re
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from engine import ROOT, GenerationError, RunStore, digest, json_text

OCR_VERSION = "macos-vision-layout-0.2.0"
ROLES = {"customer", "advisor", "unknown", "system"}
KINDS = {"text", "voice", "image", "unreadable", "system"}
VOICE = "[语音消息，未转写]"
COMPILE_LOCK = threading.Lock()


class AssetStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else ROOT / "data" / "assets"

    def add(self, payload):
        if not isinstance(payload, dict) or payload.get("kind") not in ("chat_screenshot", "customer_record", "order", "event", "background"):
            raise GenerationError("bad_asset", "请选择截图或补充资料类型。")
        value = payload.get("data_url", "")
        if not isinstance(value, str) or len(value) > 6_000_000:
            raise GenerationError("bad_asset", "每份资料请控制在4MB以内。")
        match = re.fullmatch(r"data:(image/png|image/jpeg|text/plain|application/json);base64,([A-Za-z0-9+/=\s]+)", value)
        if not match:
            raise GenerationError("bad_asset", "目前支持PNG、JPEG截图及UTF-8 TXT/JSON资料。")
        try:
            raw = base64.b64decode(re.sub(r"\s", "", match[2]), validate=True)
            if not 0 < len(raw) <= 4_000_000:
                raise ValueError
            mime = match[1]
            if mime.startswith("image/"):
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in ("PNG", "JPEG") or image.width * image.height > 20_000_000:
                        raise ValueError
                    image.verify()
            else:
                raw.decode("utf-8")
                if payload["kind"] == "chat_screenshot":
                    raise ValueError
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
            raise GenerationError("bad_asset", "资料内容或尺寸不符合要求，请使用清晰的PNG/JPEG或UTF-8文本。")
        asset_id = uuid.uuid4().hex
        filename = Path(str(payload.get("filename", "资料"))).name[:150]
        if filename == ".env" or filename.startswith(".env."):
            raise GenerationError("bad_asset", "本地模型配置文件不能作为客户资料上传。")
        metadata = dict(asset_id=asset_id, filename=filename, kind=payload["kind"], mime=mime, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), created_at=datetime.now(timezone.utc).isoformat())
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / f"{asset_id}.bin").write_bytes(raw)
        (self.path / f"{asset_id}.json").write_text(json_text(metadata), encoding="utf-8")
        for suffix in ("bin", "json"):
            (self.path / f"{asset_id}.{suffix}").chmod(0o600)
        return metadata

    def get(self, asset_id):
        if not isinstance(asset_id, str) or not re.fullmatch(r"[a-f0-9]{32}", asset_id):
            raise GenerationError("missing_asset", "找不到原始资料。")
        try:
            return json.loads((self.path / f"{asset_id}.json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise GenerationError("missing_asset", "找不到原始资料。")

    def raw(self, asset_id):
        self.get(asset_id)
        return (self.path / f"{asset_id}.bin").read_bytes()


def native_ocr(path):
    if platform.system() != "Darwin":
        raise GenerationError("ocr_unavailable", "当前本地OCR适配器需要macOS；可接入其他OCR适配器或手动输入文字。")
    source = ROOT / "scripts" / "ocr.swift"
    binary = ROOT / "data" / "bin" / ("ocr-" + hashlib.sha256(source.read_bytes()).hexdigest()[:12])
    with COMPILE_LOCK:
        if not binary.exists():
            binary.parent.mkdir(parents=True, exist_ok=True)
            cache = ROOT / "data" / "module-cache"
            cache.mkdir(parents=True, exist_ok=True)
            try:
                built = subprocess.run(["/usr/bin/swiftc", "-module-cache-path", str(cache), str(source), "-o", str(binary)], capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired):
                raise GenerationError("ocr_unavailable", "本地OCR初始化失败，请检查Swift命令行工具。")
            if built.returncode:
                raise GenerationError("ocr_unavailable", "本地OCR编译失败，请检查系统命令行工具或改用文字输入。")
    try:
        result = subprocess.run([str(binary), str(path)], capture_output=True, timeout=45)
        if result.returncode:
            raise ValueError
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise GenerationError("ocr_failed", "本地OCR没有成功读取这张图片，原图已保留，可以重试或手动输入。", True)


def bubble_regions(image):
    small = image.convert("RGB").copy()
    small.thumbnail((340, 1800))
    width, height = small.size
    pixels = list(small.getdata())
    mask = bytearray(width * height)
    for index, (r, g, b) in enumerate(pixels):
        y = index // width
        if .08 * height < y < .94 * height:
            mask[index] = 2 if g > 160 and g - r > 15 and g - b > 25 else 1 if min(r, g, b) > 245 and max(r, g, b) - min(r, g, b) < 12 else 0
    regions = []
    for start in range(len(mask)):
        color = mask[start]
        if not color:
            continue
        mask[start] = 0
        stack = [start]
        area = 0
        x0 = x1 = start % width
        y0 = y1 = start // width
        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            area += 1
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for neighbor in (index - width if y else -1, index + width if y + 1 < height else -1, index - 1 if x else -1, index + 1 if x + 1 < width else -1):
                if neighbor >= 0 and mask[neighbor] == color:
                    mask[neighbor] = 0
                    stack.append(neighbor)
        box_width, box_height = x1 - x0, y1 - y0
        if area < 100 or box_width < .07 * width or box_height < 10 or box_width > .87 * width or box_height > .55 * height:
            continue
        if box_width < .13 * width and (x0 < .1 * width or x1 > .9 * width):
            continue
        regions.append(dict(bbox=[x0 / width, y0 / height, (x1 + 1) / width, (y1 + 1) / height], color="green" if color == 2 else "white"))
    return sorted(regions, key=lambda item: item["bbox"][1])


def inside(box, container):
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return container[0] <= x <= container[2] and container[1] <= y <= container[3]


def region_role(region):
    box=region["bbox"]
    left,right=box[0],1-box[2]
    if min(left,right)>.3:
        return "unknown",["区域位置不符合左右气泡，请确认发送者或排除"]
    if abs(left-right)<.035:
        return ("advisor" if region["color"]=="green" else "customer"),["气泡较宽，左右位置接近，请确认发送者"]
    return ("customer" if left<right else "advisor"),[]


def draft_from_ocr(ocr, image, asset_id):
    regions = bubble_regions(image)
    blocks = sorted(ocr["blocks"], key=lambda row: (round(row["bbox"][1], 2), row["bbox"][0]))
    messages = []
    assigned = set()
    for region in regions:
        selected = [(index, row) for index, row in enumerate(blocks) if inside(row["bbox"], region["bbox"])]
        role,role_warnings=region_role(region)
        if not selected:
            messages.append(dict(role=role,kind="unreadable",text="[未识别消息区域，内容未知]",quoted_text="",include=True,warnings=role_warnings+["可能是媒体或布局噪声，请对照原图核实，不推断内容"],sources=[dict(asset_id=asset_id,bbox=region["bbox"])],role_basis="左右位置假设，尚未确认"))
            continue
        assigned.update(index for index, _ in selected)
        body, quotes, warnings = [], [], role_warnings.copy()
        for _, row in selected:
            text = row["text"].strip()
            box = row["bbox"]
            sx = min(image.width - 1, max(0, int(box[0] * image.width) - 5))
            sy = min(image.height - 1, max(0, int(box[1] * image.height) - 3))
            pixel = image.convert("RGB").getpixel((sx, sy))
            quote = text.startswith("引用") or (max(pixel) - min(pixel) < 14 and 175 < min(pixel) < 235)
            (quotes if quote else body).append(re.sub(r"^引用\s*", "", text) if quote else text)
            if row["confidence"] < .6:
                warnings.append("有低置信度文字，请对照原图")
        text = "\n".join(body)
        kind = "voice" if re.fullmatch(r"[\s|丨()（）›»‹«◀▶]*\d{1,3}\s*[\"″”'’秒]+[\s|丨()（）›»‹«◀▶]*", text) else "text" if text else "unreadable"
        if kind == "voice":
            text = VOICE
            warnings.append("语音未转写，不能从截图得知内容")
        if not text:
            text = "[正文未识别，请核对]"
            warnings.append("正文未识别，需核对")
        messages.append(dict(role=role, kind=kind, text=text, quoted_text="\n".join(quotes), include=True, warnings=list(dict.fromkeys(warnings)), sources=[dict(asset_id=asset_id, bbox=region["bbox"])], role_basis="左侧先归客户、右侧先归顾问，待审核"))
    for index, row in enumerate(blocks):
        box, text = row["bbox"], row["text"].strip()
        if index in assigned or box[1] < .12 or box[3] > .9 or box[2] < .13 or box[0] > .87:
            continue
        if re.fullmatch(r"(?:今天|昨天|星期[一二三四五六日天]|\d{1,2}月\d{1,2}日)?\s*\d{1,2}[:：]\d{2}", text):
            continue
        if any(inside(box, message["sources"][0]["bbox"]) for message in messages):
            continue
        messages.append(dict(role="unknown", kind="text", text=text, quoted_text="", include=True, warnings=["文字未能归入气泡，请确认发送者或排除非聊天内容"], sources=[dict(asset_id=asset_id, bbox=box)], role_basis="未定位气泡"))
    return sorted(messages, key=lambda item: item["sources"][0]["bbox"][1]), regions


def _extract_draft(asset_ids, assets=None, contexts=None, source="web-ocr", auto_stitch=True):
    assets, contexts = assets or AssetStore(), contexts or RunStore(ROOT / "data" / "contexts")
    if not isinstance(asset_ids, list) or not 1 <= len(asset_ids) <= 8 or len(set(asset_ids)) != len(asset_ids):
        raise GenerationError("bad_asset", "请放入1到8张不同的聊天截图。")
    if type(auto_stitch) is not bool:
        raise GenerationError("bad_context", "请选择有效的截图整理方式。")
    record = dict(run_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(), status="draft", source=source, ocr_version=OCR_VERSION, ocr_code_hash=digest(Path(__file__).read_text(encoding="utf-8")), ocr_helper_hash=digest((ROOT/"scripts"/"ocr.swift").read_text(encoding="utf-8")), asset_ids=asset_ids, pages=[], messages=[], warnings=["默认按顾问本人微信一对一截屏整理，确认后才导入。"])
    for asset_id in asset_ids:
        metadata = assets.get(asset_id)
        if metadata["kind"] != "chat_screenshot" or not metadata["mime"].startswith("image/"):
            raise GenerationError("bad_asset", "聊天识别入口只接受聊天截图，其他资料请放入补充资料入口。")
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(assets.raw(asset_id)))).convert("RGB")
        normalized = assets.path / f"{asset_id}.ocr.png"
        image.save(normalized)
        ocr = native_ocr(normalized)
        raw_path = assets.path / f"{asset_id}.{OCR_VERSION}.ocr.json"
        if not raw_path.exists():
            raw_path.write_text(json_text(ocr), encoding="utf-8")
            raw_path.chmod(0o600)
        messages, regions = draft_from_ocr(ocr, image, asset_id)
        record["pages"].append(dict(asset=metadata, raw_ocr=ocr, bubble_regions=regions, draft_messages=messages))
    from screenshot_stitch import stitch_pages
    stitched = stitch_pages(record["pages"], auto_stitch=auto_stitch)
    record.update(messages=stitched["messages"], asset_ids=stitched["asset_ids"], uploaded_asset_ids=asset_ids, stitching=stitched["stitching"], stitching_code_hash=digest((ROOT/"screenshot_stitch.py").read_text(encoding="utf-8")))
    record["warnings"].extend(stitched["warnings"])
    if not record["messages"]:
        record["warnings"].append("没有定位到可识别聊天，请换清晰截图或使用文字入口。")
    record["draft_hash"] = digest(json_text(record["messages"]))
    return contexts.save(record)


def extract_draft(asset_ids, assets=None, contexts=None, source="web-ocr", auto_stitch=True):
    contexts = contexts or RunStore(ROOT / "data" / "contexts")
    try:
        return _extract_draft(asset_ids, assets, contexts, source, auto_stitch)
    except GenerationError as error:
        failure = contexts.save(dict(run_id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(), status="error", source=source, asset_ids=asset_ids, ocr_version=OCR_VERSION, error=dict(code=error.code,message=error.message)))
        error.context_attempt_id = failure["run_id"]
        raise


def confirm_context(draft_id, edited, assets=None, contexts=None, source="advisor-action", base_context_id=None):
    contexts = contexts or RunStore(ROOT / "data" / "contexts")
    draft = contexts.get(draft_id)
    if draft.get("status") != "draft" or not isinstance(edited, list) or not edited:
        raise GenerationError("bad_context", "请先识别聊天草稿，再检查并确认。")
    base = draft
    if base_context_id:
        base = contexts.get(base_context_id)
        if base.get("status") != "confirmed" or base.get("parent_context_id") != draft_id:
            raise GenerationError("bad_context", "修改版本不属于这份聊天，请重新打开记录。")
    previous = {message["id"]: message for message in base["messages"]}
    ids = [item.get("id") for item in edited if isinstance(item, dict)]
    if len(ids) != len(edited) or any(not isinstance(identity, str) for identity in ids) or len(ids) != len(set(ids)) or not set(previous).issubset(ids) or len(edited) > 500:
        raise GenerationError("bad_context", "消息编号重复或已有消息缺失；请用取消纳入保留旧消息，补录另建消息。")
    record_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    messages, changes = [], []
    for position, item in enumerate(edited):
        old = previous.get(item["id"])
        added = old is None
        if item.get("role") not in ROLES or item.get("kind") not in KINDS or type(item.get("include")) is not bool:
            raise GenerationError("bad_context", "请确认每条消息的发送者、类型和是否纳入上下文。")
        for key in ("text", "quoted_text"):
            if not isinstance(item.get(key), str) or len(item[key]) > 4000:
                raise GenerationError("bad_context", "消息内容格式不正确或过长。")
        if item["include"] and item["role"] == "unknown":
            raise GenerationError("bad_context", "仍有待确认发送者，请改角色或取消纳入这条。")
        if ((old and old["kind"] == "voice") or item["kind"] == "voice") and (item["kind"] != "voice" or item["text"] != VOICE):
            raise GenerationError("voice_unknown", "截图中的语音不能改成已听内容；如有真实转述，请另填补充背景并注明来源。")
        manual = added or old.get("origin") == "manual"
        if added and (not re.fullmatch(r"manual_[a-f0-9]{32}", item["id"]) or item.get("origin") != "manual"):
            raise GenerationError("bad_context", "新增消息必须使用人工补录入口，不可冒充OCR消息。")
        if not manual and item.get("origin") not in (None, "ocr", old.get("origin")):
            raise GenerationError("bad_context", "已有识别消息的来源不可改写；漏识别内容请另行补录。")
        new = {**(old or {}), **{key: item[key] for key in ("id", "role", "kind", "text", "quoted_text", "include")}}
        tracked = ["role", "kind", "text", "quoted_text", "include"]
        if manual:
            asset_id = item.get("source_asset_id", old.get("source_asset_id") if old else None)
            note = item.get("source_note", old.get("source_note") if old else None)
            if asset_id not in draft["asset_ids"] or not isinstance(note, str) or not 1 <= len(note.strip()) <= 500 or not item["text"].strip():
                raise GenerationError("manual_source", "人工补录请填写可见内容，选择本组原图，并说明原图中的位置；不要补出图外内容。")
            new.update(origin="manual", source_asset_id=asset_id, source_note=note.strip(), sources=[dict(asset_id=asset_id, source_type="manual_transcription", note=note.strip())])
            if added:
                new["manual_entry"] = dict(created_in_context_id=record_id, based_on_context_id=base["run_id"], created_at=created_at)
                new["warnings"] = ["顾问对照原图人工补录，非OCR提取"]
            tracked.extend(["source_asset_id", "source_note"])
        messages.append(new)
        if added:
            changes.append(dict(message_id=item["id"], action="add", fields=dict(message=dict(before=None, after=new), position=dict(before=None, after=position))))
            continue
        before_position = next(index for index, row in enumerate(base["messages"]) if row["id"] == item["id"])
        fields = {key: dict(before=old.get(key), after=new.get(key)) for key in tracked if old.get(key) != new.get(key)}
        if before_position != position:
            fields["position"] = dict(before=before_position, after=position)
        if fields:
            changes.append(dict(message_id=item["id"], action="edit", fields=fields))
    if not any(message["include"] and message["role"] in ("customer", "advisor") for message in messages):
        raise GenerationError("bad_context", "请至少保留一条客户或顾问消息，或改用无聊天的文字入口。")
    record = dict(run_id=record_id, created_at=created_at, status="confirmed", source=source, chat_id=draft_id, parent_context_id=draft_id, previous_context_id=base["run_id"], asset_ids=draft["asset_ids"], messages=messages, changes=changes, original_draft_hash=draft["draft_hash"], base_context_hash=base.get("context_hash") or base.get("draft_hash"), context_hash=digest(json_text(messages)), ocr_version=draft.get("ocr_version"), ocr_code_hash=draft.get("ocr_code_hash"), confirmation_code_hash=digest(Path(__file__).read_text(encoding="utf-8")))
    return contexts.save(record)


def confirmed_messages(context_id, contexts=None):
    contexts = contexts or RunStore(ROOT / "data" / "contexts")
    record = contexts.get(context_id)
    if record.get("status") != "confirmed":
        raise GenerationError("unconfirmed_context", "截图仍是待审核草稿，请先确认并导入。")
    return record


def text_messages(conversation):
    messages = []
    timestamp=None
    for line in conversation.splitlines():
        stamp=re.fullmatch(r'\s*\[?(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)\]?\s*',line)
        if stamp:timestamp=stamp[1];continue
        match = re.match(r"\s*(客户|顾客|顾问|客服|引用)\s*[:：]\s*(.*)", line)
        if match and match[1] == "引用" and messages:
            messages[-1]["quoted_text"] += match[2] + "\n"
        elif match:
            messages.append(dict(id=f"t{len(messages) + 1}", role="customer" if match[1] in ("客户", "顾客") else "advisor", kind="text", text=match[2], quoted_text="", include=True, sources=[{"field": "conversation"}]))
            if match[2]==VOICE:messages[-1]['kind']='voice'
            if timestamp:messages[-1].update(timestamp_text=timestamp,timestamp_source='conversation_date_line')
        elif line.strip() and messages:
            messages[-1]["text"] += "\n" + line
        elif line.strip():
            messages.append(dict(id="t1", role="unknown", kind="text", text=line, quoted_text="", include=True, sources=[{"field": "conversation"}]))
    return messages


def state_evidence(messages):
    from quality import negated
    result = dict(version="local-intent-hints-0.3.0", state=None, evidence=[], product_intents=[], signals=[], authority="local_hint_only", requires_semantic_review=True)
    customer = [item for item in messages if item.get("include", True) and item["role"] == "customer"]
    if not customer or customer[-1]["kind"] != "text":
        return dict(result, reason="没有足够的最新客户文字证据，不能推断语音")
    latest = customer[-1]
    text = latest["text"]
    aliases = {"P01": ("日行托特包", "托特包", "托特"), "P02": ("轻行肩包", "肩包"), "P03": ("随行卡夹", "卡夹")}
    refusal = r"不考虑(?:了)?|不买了|不想买|不用(?:再)?推荐|不要再联系|不需要了|不要推荐"
    global_declines, scoped_declines, interested = [], [], []
    has_question = False
    negated_refusal = False
    for clause in re.split(r"(?<=[?？])|[，,。；;！!\n]|但是|不过|然而|而是|但", text):
        products = [identity for identity, names in aliases.items() if any(name in clause for name in names)]
        declines, denied = [], []
        for match in re.finditer(refusal, clause):
            prefix = clause[:match.start()]
            is_negated = negated(prefix) or bool(re.search(r"(?:不是说|并非说|不能说|不代表|不等于|没有说|谈不上)\s*$", prefix))
            (denied if is_negated else declines).append(match[0])
        question = bool(re.search(r"[?？]|想了解|想看|想要|想选|希望了解|多少钱|能.*(?:折|放)|多大|怎么|是否", clause))
        interest = bool(denied) or bool(products and question) or bool(re.search(r"想了解|想看看|多少钱|能.*(?:折|放)|有点贵|比较|再看看|背法|材质|价格", clause))
        has_question |= question
        negated_refusal |= bool(denied)
        if declines:
            (scoped_declines if products else global_declines).append(clause)
        if interest and not declines:
            interested.append(clause)
        for identity in products:
            result["product_intents"].append(dict(product_id=identity, intent="declined" if declines else "question" if question else "not_declined" if denied else "mentioned", message_id=latest["id"], text=clause))
    if negated_refusal:
        result["signals"].append("negated_refusal")
    if scoped_declines:
        result["signals"].append("product_scoped_refusal")
    if has_question:
        result["signals"].append("new_question")
    if (global_declines or scoped_declines) and (interested or has_question):
        result["signals"].append("mixed_intents")
    if global_declines:
        result["state"] = "declined" if not has_question else None
    elif scoped_declines and interested:
        result["state"] = "comparing"
    elif not global_declines and not scoped_declines and (interested or re.search(r"有点贵|比较|再看看|背法|材质|价格", text)):
        result["state"] = "comparing"
    elif not global_declines and not scoped_declines and re.search(r"再想想|考虑一下|以后再说", text):
        result["state"] = "unclear"
    result["evidence"] = [dict(message_id=latest["id"], text=text)]
    result["reason"] = "整段最新客户正文的否定、商品范围与新问题线索；仅供参考，不能作为语义裁决；引用和语音不参与"
    return result
