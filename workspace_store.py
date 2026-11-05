import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

from engine import GenerationError, ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def opt_out_evidence(draft):
    from context_store import text_messages
    messages = text_messages(draft.get('input', {}).get('conversation', ''))
    context = draft.get('context', {})
    if context.get('imported_id') and not context.get('review_dirty'):
        messages += context.get('messages', [])
    found = []
    for message in messages:
        text = message.get('text', '')
        if message.get('role') != 'customer' or message.get('kind') != 'text' or not message.get('include', True):
            continue
        if re.match(r'^\s*(引用|转述|对方原话)[：:]', text):
            continue
        if re.search(r'不是.{0,6}(不要|不想)|并非|不是说', text):
            continue
        if re.search(r'(以后|今后|后续|再也|别再|不要再).{0,12}(不要|不用|不想|停止|别).{0,10}(营销|推广|活动|联系|发消息)|(?:不要再|别再).{0,8}(营销|推广|联系|发消息)|(?:不要|不用).{0,6}(?:给我发|发送|发).{0,6}(营销|推广)', text):
            found.append({'message_id': message.get('id'), 'text': text})
    return found


class WorkspaceStore:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / 'data' / 'workspace.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS advisors(id TEXT PRIMARY KEY,name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,advisor_id TEXT NOT NULL REFERENCES advisors(id),name TEXT NOT NULL,preferences TEXT NOT NULL DEFAULT '',marketing_opt_out INTEGER NOT NULL DEFAULT 0,profile_revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),title TEXT NOT NULL,created_at TEXT NOT NULL,last_run_id TEXT,last_valid_run_id TEXT);
                CREATE TABLE IF NOT EXISTS drafts(conversation_id TEXT PRIMARY KEY REFERENCES conversations(id),revision INTEGER NOT NULL,data TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),revision INTEGER NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(conversation_id,revision));
                CREATE TABLE IF NOT EXISTS mutations(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,response TEXT NOT NULL,payload_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profile_versions(id INTEGER PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),revision INTEGER NOT NULL,preferences TEXT NOT NULL,marketing_opt_out INTEGER NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS contact_evidence(customer_id TEXT NOT NULL REFERENCES customers(id),evidence_hash TEXT NOT NULL,source TEXT NOT NULL,PRIMARY KEY(customer_id,evidence_hash));
                CREATE TABLE IF NOT EXISTS resources(kind TEXT NOT NULL,id TEXT NOT NULL,conversation_id TEXT NOT NULL REFERENCES conversations(id),PRIMARY KEY(kind,id));
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _scope(self, db, advisor_id, conversation_id):
        row = db.execute('SELECT v.*,c.advisor_id,c.name customer_name,c.preferences,c.marketing_opt_out,c.profile_revision,a.name advisor_name FROM conversations v JOIN customers c ON c.id=v.customer_id JOIN advisors a ON a.id=c.advisor_id WHERE v.id=? AND c.advisor_id=?', (conversation_id, advisor_id)).fetchone()
        if row is None:
            raise GenerationError('workspace_scope', '请选择正确的顾问与客户会话，资料未跨客户打开。')
        return dict(row)

    def scope(self, advisor_id, conversation_id):
        with self.connect() as db:
            return self._scope(db, advisor_id, conversation_id)

    def tree(self):
        with self.connect() as db:
            return {'advisors': [dict(row) for row in db.execute('SELECT * FROM advisors ORDER BY rowid')], 'customers': [dict(row) for row in db.execute('SELECT id,advisor_id,name FROM customers ORDER BY rowid')], 'conversations': [dict(row) for row in db.execute('SELECT id,customer_id,title,created_at FROM conversations ORDER BY created_at DESC')]}

    def create(self, kind, payload):
        identity = uuid.uuid4().hex
        name = payload.get('name', '').strip()
        if not name or len(name) > 80:
            raise GenerationError('workspace_input', '名称请填写1到80个字。')
        with self.connect() as db:
            if kind == 'advisor':
                db.execute('INSERT INTO advisors VALUES(?,?)', (identity, name))
            elif kind == 'customer':
                if not db.execute('SELECT 1 FROM advisors WHERE id=?', (payload.get('advisor_id'),)).fetchone():
                    raise GenerationError('workspace_input', '请先选择顾问。')
                db.execute('INSERT INTO customers(id,advisor_id,name) VALUES(?,?,?)', (identity, payload['advisor_id'], name))
                self._create_conversation(db, payload['advisor_id'], identity, '本次沟通')
            elif kind == 'conversation':
                self._create_conversation(db, payload.get('advisor_id'), payload.get('customer_id'), name, identity)
            else:
                raise GenerationError('workspace_input', '文件夹类型不正确。')
        return {'id': identity, **self.tree()}

    def _create_conversation(self, db, advisor, customer, title, identity=None):
        if not db.execute('SELECT 1 FROM customers WHERE id=? AND advisor_id=?', (customer, advisor)).fetchone():
            raise GenerationError('workspace_scope', '客户不属于当前顾问。')
        identity = identity or uuid.uuid4().hex
        db.execute('INSERT INTO conversations(id,customer_id,title,created_at) VALUES(?,?,?,?)', (identity, customer, title, now()))
        return identity

    def seed_demo(self):
        if self.tree()['advisors']:
            return
        for name, clients in [('演示顾问 · 小林', ['虚构林女士', '虚构周先生']), ('演示顾问 · 小陈', ['虚构林女士', '虚构许女士'])]:
            advisor = self.create('advisor', {'name': name})['id']
            for client in clients:
                self.create('customer', {'advisor_id': advisor, 'name': client})

    def open(self, advisor, conversation):
        with self.connect() as db:
            scope = self._scope(db, advisor, conversation)
            draft = db.execute('SELECT * FROM drafts WHERE conversation_id=?', (conversation,)).fetchone()
            scope.update(draft=json.loads(draft['data']) if draft else {}, revision=draft['revision'] if draft else 0, updated_at=draft['updated_at'] if draft else None)
            return scope

    def _link(self, db, conversation, kind, identity):
        old = db.execute('SELECT conversation_id FROM resources WHERE kind=? AND id=?', (kind, identity)).fetchone()
        if old and old[0] != conversation:
            raise GenerationError('workspace_scope', '这份资料已属于其他会话，不能交叉使用。')
        db.execute('INSERT OR IGNORE INTO resources VALUES(?,?,?)', (kind, identity, conversation))

    def link(self, advisor, conversation, resources):
        with self.connect() as db:
            self._scope(db, advisor, conversation)
            for kind, identity in resources:
                self._link(db, conversation, kind, identity)

    def allowed(self, advisor, conversation, kind, identity, pending=False):
        with self.connect() as db:
            self._scope(db, advisor, conversation)
            owner = db.execute('SELECT conversation_id FROM resources WHERE kind=? AND id=?', (kind, identity)).fetchone()
            if owner and owner[0] == conversation or pending and owner is None:
                return
            raise GenerationError('workspace_scope', '资料不属于当前会话。旧资料请先到待整理区确认归属。')

    def ids(self, advisor, conversation, kind):
        with self.connect() as db:
            self._scope(db, advisor, conversation)
            return {row[0] for row in db.execute('SELECT id FROM resources WHERE conversation_id=? AND kind=?', (conversation, kind))}

    def unassigned(self, kind, identities):
        with self.connect() as db:
            assigned = {row[0] for row in db.execute('SELECT id FROM resources WHERE kind=?', (kind,))}
            return [identity for identity in identities if identity not in assigned]

    def checkpoint(self, advisor, conversation, payload):
        mutation = payload.get('mutation_id')
        if not isinstance(mutation, str) or not re.fullmatch(r'[a-f0-9]{32}', mutation):
            raise GenerationError('workspace_input', '保存编号无效，请重新保存。')
        draft = payload.get('draft')
        if not isinstance(draft, dict) or len(encoded(draft)) > 1_500_000:
            raise GenerationError('workspace_input', '草稿过长或格式不正确。')
        fingerprint = hashlib.sha256(encoded(payload).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            scope = self._scope(db, advisor, conversation)
            prior = db.execute('SELECT * FROM mutations WHERE id=?', (mutation,)).fetchone()
            if prior:
                if prior['conversation_id'] != conversation or prior['payload_hash'] != fingerprint:
                    raise GenerationError('workspace_conflict', '保存请求编号冲突，请重新打开会话。')
                response = json.loads(prior['response'])
                latest = db.execute('SELECT revision FROM drafts WHERE conversation_id=?', (conversation,)).fetchone()
                if latest[0] != response['revision'] or scope['profile_revision'] != response['profile_revision']:
                    raise GenerationError('workspace_conflict', '上次保存已完成，但之后另一个页面又修改了资料。请比较版本后继续。')
                return response
            current = db.execute('SELECT revision FROM drafts WHERE conversation_id=?', (conversation,)).fetchone()
            revision = current[0] if current else 0
            if payload.get('revision') != revision or payload.get('profile_revision') != scope['profile_revision']:
                raise GenerationError('workspace_conflict', '此会话或客户偏好已在其他页面更新。本页未覆盖；请先比较保存的版本。')
            prefs = payload.get('preferences', scope['preferences'])
            if not isinstance(prefs, str) or len(prefs) > 5000:
                raise GenerationError('workspace_input', '长期偏好请控制在5000字以内。')
            context = draft.get('context', {})
            for identity in context.get('asset_ids', []) + context.get('supplement_ids', []):
                self._assert_link(db, conversation, 'asset', identity)
            for identity in [context.get('draft_id'), context.get('imported_id')]:
                if identity:
                    self._assert_link(db, conversation, 'context', identity)
            policy = bool(scope['marketing_opt_out'])
            if payload.get('marketing_opt_out') is True:
                policy = True
            if payload.get('clear_marketing_opt_out'):
                reason = payload.get('consent_reason', '').strip()
                if len(reason) < 4:
                    raise GenerationError('workspace_input', '恢复营销联系需记录客户明确同意的来源，至少4字。')
                policy = False
            evidence = opt_out_evidence(draft)
            for item in evidence:
                evidence_key = hashlib.sha256(encoded({'conversation': conversation, **item}).encode()).hexdigest()
                inserted = db.execute('INSERT OR IGNORE INTO contact_evidence VALUES(?,?,?)', (scope['customer_id'], evidence_key, encoded(item))).rowcount
                if inserted:
                    policy = True
            profile_revision = scope['profile_revision']
            if prefs != scope['preferences'] or policy != bool(scope['marketing_opt_out']):
                profile_revision += 1
                db.execute('UPDATE customers SET preferences=?,marketing_opt_out=?,profile_revision=? WHERE id=?', (prefs, int(policy), profile_revision, scope['customer_id']))
                db.execute('INSERT INTO profile_versions(customer_id,revision,preferences,marketing_opt_out,source,created_at) VALUES(?,?,?,?,?,?)', (scope['customer_id'], profile_revision, prefs, int(policy), encoded({'conversation_id': conversation, 'evidence': evidence, 'manual': payload.get('marketing_opt_out'), 'consent_reason': payload.get('consent_reason')}), now()))
            timestamp = now()
            revision += 1
            db.execute('INSERT INTO drafts VALUES(?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET revision=excluded.revision,data=excluded.data,updated_at=excluded.updated_at', (conversation, revision, encoded(draft), timestamp))
            db.execute('INSERT INTO checkpoints(conversation_id,revision,data,created_at) VALUES(?,?,?,?)', (conversation, revision, encoded(draft), timestamp))
            response = {'revision': revision, 'profile_revision': profile_revision, 'marketing_opt_out': policy, 'updated_at': timestamp}
            db.execute('INSERT INTO mutations VALUES(?,?,?,?)', (mutation, conversation, encoded(response), fingerprint))
            return response

    def _assert_link(self, db, conversation, kind, identity):
        if not db.execute('SELECT 1 FROM resources WHERE kind=? AND id=? AND conversation_id=?', (kind, identity, conversation)).fetchone():
            raise GenerationError('workspace_scope', '草稿中的资料未归属当前会话，保存没有完成。')

    def remember_run(self, advisor, conversation, record):
        with self.connect() as db:
            self._scope(db, advisor, conversation)
            self._link(db, conversation, 'run', record['run_id'])
            db.execute('UPDATE conversations SET last_run_id=? WHERE id=?', (record['run_id'], conversation))
            from delivery import guard
            if guard(record)['allowed']:
                db.execute('UPDATE conversations SET last_valid_run_id=? WHERE id=?', (record['run_id'], conversation))

    def customer_snapshot(self, advisor, conversation):
        row = self.scope(advisor, conversation)
        return {key: row[key] for key in ('advisor_id', 'customer_id', 'customer_name', 'preferences', 'marketing_opt_out', 'profile_revision')} | {'conversation_id': conversation}
