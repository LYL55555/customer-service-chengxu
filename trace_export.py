import hashlib
import io
import json
import zipfile

from context_store import AssetStore
from engine import ROOT, RunStore, json_text


def context_files(context_id,contexts,assets):
    files={}
    confirmed=contexts.get(context_id)
    current=context_id
    seen=set()
    while current and current not in seen:
        row=contexts.get(current)
        seen.add(current)
        files[f"contexts/{current}.json"]=json_text(row).encode("utf-8")
        current=row.get("previous_context_id")
    parent=confirmed.get("parent_context_id")
    if parent:
        files[f"contexts/{parent}.json"]=json_text(contexts.get(parent)).encode("utf-8")
    for asset_id in confirmed.get("asset_ids",[]):
        metadata=assets.get(asset_id)
        extension="png" if metadata["mime"]=="image/png" else "jpg"
        files[f"assets/{asset_id}.{extension}"]=assets.raw(asset_id)
        files[f"assets/{asset_id}.metadata.json"]=json_text(metadata).encode("utf-8")
    return files


def zip_files(files,manifest):
    manifest["files"]={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
        archive.writestr("manifest.json",json_text(manifest))
    return output.getvalue()


def export_context_bundle(context_id,contexts=None,assets=None):
    contexts=contexts or RunStore(ROOT/"data"/"contexts")
    assets=assets or AssetStore()
    return zip_files(context_files(context_id,contexts,assets),dict(kind="context-review-bundle",context_id=context_id,includes_model_key=False))


def export_bundle(run_id, runs=None, contexts=None, assets=None):
    runs=runs or RunStore()
    contexts=contexts or RunStore(ROOT/"data"/"contexts")
    assets=assets or AssetStore()
    files={}
    asset_ids=set()
    seen_runs=set()
    current=run_id
    while current and current not in seen_runs and len(seen_runs)<21:
        record=runs.get(current)
        seen_runs.add(current)
        files[f"runs/{current}.json"]=json_text(record).encode("utf-8")
        value=record.get("input",{})
        asset_ids.update(value.get("supplement_ids",[]))
        context_id=value.get("context_id")
        if context_id:
            confirmed=contexts.get(context_id)
            files.update(context_files(context_id,contexts,assets))
            asset_ids.update(confirmed.get("asset_ids",[]))
            parent=confirmed.get("parent_context_id")
            if parent:
                draft=contexts.get(parent)
                files[f"contexts/{parent}.json"]=json_text(draft).encode("utf-8")
        current=record.get("parent_run_id")
    for asset_id in sorted(asset_ids):
        metadata=assets.get(asset_id)
        extension={"image/png":"png","image/jpeg":"jpg","text/plain":"txt","application/json":"json"}[metadata["mime"]]
        files[f"assets/{asset_id}.{extension}"]=assets.raw(asset_id)
        files[f"assets/{asset_id}.metadata.json"]=json_text(metadata).encode("utf-8")
    manifest=dict(kind="local-trace-bundle",root_run_id=run_id,includes_model_key=False,files={name:hashlib.sha256(data).hexdigest() for name,data in files.items()})
    return zip_files(files,manifest)
