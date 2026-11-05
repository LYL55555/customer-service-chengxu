from datetime import datetime, timezone

from engine import ROOT, GenerationError, RunStore


def chat_id(record):
    return record.get("chat_id") or record.get("parent_context_id") or record["run_id"]


class ChatLibrary:
    def __init__(self, contexts=None, metadata=None):
        self.contexts = contexts or RunStore(ROOT / "data" / "contexts")
        self.metadata = metadata or RunStore(ROOT / "data" / "chats")

    def records(self):
        return [self.contexts.get(file.stem) for file in self.contexts.path.glob("*.json")]

    def chats(self, query=""):
        groups = {}
        for record in self.records():
            if record.get("status") in ("draft", "confirmed"):
                groups.setdefault(chat_id(record), []).append(record)
        rows = []
        for identity, records in groups.items():
            records.sort(key=lambda row: (row.get("created_at", ""), row["run_id"]))
            root = next((row for row in records if row["run_id"] == identity), records[0])
            confirmed = [row for row in records if row["status"] == "confirmed"]
            latest = confirmed[-1] if confirmed else root
            title = f"聊天 · {identity[:6]}"
            if root.get("pages"):
                title = root["pages"][0].get("asset", {}).get("filename") or title
            if (self.metadata.path / f"{identity}.json").exists():
                title = self.metadata.get(identity)["title"]
            versions = [dict(context_id=row["run_id"], status=row["status"], revision=index, created_at=row.get("created_at"), previous_context_id=row.get("previous_context_id"), message_count=len(row["messages"])) for index, row in enumerate([root] + confirmed)]
            row = dict(chat_id=identity, title=title, created_at=root.get("created_at"), updated_at=latest.get("created_at"), status=latest["status"], latest_context_id=latest["run_id"], message_count=len(latest["messages"]), version_count=len(confirmed), versions=versions)
            searchable = title + "\n" + "\n".join(message.get("text", "") + message.get("quoted_text", "") for record in records for message in record["messages"])
            if not query or query.casefold() in searchable.casefold():
                rows.append(row)
        return sorted(rows, key=lambda row: (row.get("updated_at") or "", row["chat_id"]), reverse=True)

    def get(self, identity):
        self.contexts.get(identity)
        for row in self.chats():
            if row["chat_id"] == identity:
                return row
        raise GenerationError("bad_chat", "这份聊天记录不存在。")

    def rename(self, identity, title):
        self.get(identity)
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 80:
            raise GenerationError("bad_chat", "请填写80字以内的聊天名称。")
        self.metadata.save(dict(run_id=identity, title=title.strip(), updated_at=datetime.now(timezone.utc).isoformat()))
        return self.get(identity)
