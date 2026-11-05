from engine import GenerationError
from chat_library import chat_id


class WorkspaceIndex:
    def __init__(self, workspace, contexts, runs, assets, chats):
        self.workspace, self.contexts, self.runs, self.assets, self.chats = workspace, contexts, runs, assets, chats

    def graph(self, kind, identity):
        pending = [(kind, identity)]
        found = set()
        context_records = {row['run_id']: row for row in self.chats.records()}
        run_records = {file.stem: self.runs.get(file.stem) for file in self.runs.path.glob('*.json')}
        while pending:
            kind, identity = pending.pop()
            if not identity or (kind, identity) in found:
                continue
            found.add((kind, identity))
            if kind == 'context':
                record = self.contexts.get(identity)
                root = chat_id(record)
                pending += [('context', row['run_id']) for row in context_records.values() if chat_id(row) == root]
                pending += [('asset', value) for value in record.get('asset_ids', [])]
                request = record.get('submitted_context_request') or {}
                pending += [('context', request.get(key)) for key in ('draft_id', 'base_context_id')]
                pending += [('asset', value) for value in request.get('asset_ids', [])]
                pending += [('context', row['run_id']) for row in context_records.values() if any((row.get('submitted_context_request') or {}).get(key) == identity for key in ('draft_id', 'base_context_id'))]
                for row in run_records.values():
                    if any(row.get(field, {}).get('context_id') == identity for field in ('input', 'generation_input') if isinstance(row.get(field, {}), dict)):
                        pending.append(('run', row['run_id']))
            elif kind == 'run':
                record = self.runs.get(identity)
                pending += [('run', record.get(key)) for key in ('parent_run_id', 'retry_of', 'generation_reused_from', 'revalidation_of')]
                for field in ('input', 'generation_input'):
                    value = record.get(field) or {}
                    pending.append(('context', value.get('context_id')))
                    pending += [('asset', value) for value in value.get('supplement_ids', [])]
                pending += [('run', row['run_id']) for row in run_records.values() if any(row.get(key) == identity for key in ('parent_run_id', 'retry_of', 'generation_reused_from', 'revalidation_of'))]
            elif kind == 'asset':
                self.assets.get(identity)
        return sorted(found)

    def pending(self):
        chats = self.chats.chats()
        roots = set(self.workspace.unassigned('context', [row['chat_id'] for row in chats]))
        rows = [{'kind': 'context', 'id': row['chat_id'], 'title': row['title'], 'versions': len(row['versions']), 'created_at': row['created_at']} for row in chats if row['chat_id'] in roots]
        records = self.chats.records()
        root_by_id = {row['run_id']: chat_id(row) for row in records}
        loose_contexts = set(self.workspace.unassigned('context', [row['run_id'] for row in records if row.get('status') == 'error']))
        for row in records:
            if row['run_id'] in loose_contexts and root_by_id.get((row.get('submitted_context_request') or {}).get('draft_id')) not in roots:
                rows.append({'kind':'context','id':row['run_id'],'title':'资料处理失败 · '+row['run_id'][:8],'versions':1,'created_at':row.get('created_at')})
        runs = [self.runs.get(file.stem) for file in self.runs.path.glob('*.json')]
        loose = set(self.workspace.unassigned('run', [row['run_id'] for row in runs]))
        rows += [{'kind': 'run', 'id': row['run_id'], 'title': '生成记录 · ' + row['run_id'][:8], 'status': row['status'], 'created_at': row['created_at']} for row in runs if row['run_id'] in loose and not (row.get('input') or {}).get('context_id')]
        return rows

    def claim(self, advisor, conversation, kind, identity):
        if kind not in ('context', 'run'):
            raise GenerationError('workspace_input', '请选择聊天或生成记录。')
        resources = self.graph(kind, identity)
        self.workspace.link(advisor, conversation, resources)
        runs = [self.runs.get(value) for resource, value in resources if resource == 'run']
        runs.sort(key=lambda row: row.get('created_at', ''))
        current = self.workspace.scope(advisor, conversation)
        if not current["last_run_id"] and not current["last_valid_run_id"]:
            for row in runs:
                self.workspace.remember_run(advisor, conversation, row)
        return {'linked_count': len(resources), 'message': '归属已确认。旧文件和修改版本保留；当前未完成草稿未被替换。'}
