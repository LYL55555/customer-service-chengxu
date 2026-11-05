import copy
import re
import unicodedata
from collections import defaultdict

STITCH_VERSION = 'overlap-layout-0.1.0'


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or ''))


def signature(message):
    if message.get('kind') != 'text' or message.get('role') not in ('customer', 'advisor'):
        return None
    return message['role'], normalized(message.get('text')), normalized(message.get('quoted_text'))


def informative(messages):
    sizes = [len(re.sub(r'[^\w]', '', normalized(row.get('text')))) for row in messages]
    return bool(sizes) and (sizes[0] >= 12 if len(sizes) == 1 else max(sizes) >= 6 and sum(sizes) >= 12)


def alignments(left, right):
    matches = []
    for offset in range(1 - len(right), len(left)):
        start, stop = max(0, offset), min(len(left), offset + len(right))
        pairs = [(index, index - offset) for index in range(start, stop)]
        if not pairs or not informative([left[a] for a, _ in pairs]):
            continue
        if all(signature(left[a]) is not None and signature(left[a]) == signature(right[b]) for a, b in pairs):
            matches.append(dict(offset=offset, count=len(pairs), left_positions=[a for a, _ in pairs], right_positions=[b for _, b in pairs]))
    return matches


def stitch_pages(pages, auto_stitch=True):
    asset_ids = [page['asset']['asset_id'] for page in pages]
    rows = [page['draft_messages'] for page in pages]
    if not auto_stitch:
        messages = copy.deepcopy([message for page in rows for message in page])
        for index, message in enumerate(messages):
            message['id'] = f'm{index + 1}'
        return dict(messages=messages, asset_ids=asset_ids, warnings=['已按当前截图顺序逐图保留全部消息；请手动核对先后，重复气泡可取消纳入。'], stitching=dict(version=STITCH_VERSION, mode='keep_all', uploaded_asset_ids=asset_ids, ordered_asset_ids=asset_ids, original_message_count=len(messages), merged_message_count=len(messages), removed_occurrences=0, reordered=False, edges=[], ambiguous_pairs=[], groups=[], authority='逐图保留，待顾问复核'))
    adjacency, edges, ambiguous = defaultdict(list), [], []
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            candidates = alignments(rows[left], rows[right])
            if len(candidates) == 1:
                match = candidates[0]
                adjacency[left].append((right, match['offset']))
                adjacency[right].append((left, -match['offset']))
                edges.append(dict(left_asset_id=asset_ids[left], right_asset_id=asset_ids[right], **match))
            elif candidates:
                ambiguous.append(dict(left_asset_id=asset_ids[left], right_asset_id=asset_ids[right], candidate_offsets=[item['offset'] for item in candidates], reason='重复文字可对应多个位置，未直接合并'))
    groups, visited, messages, ordered = [], set(), [], []
    warnings = []
    for seed in range(len(rows)):
        if seed in visited:
            continue
        offsets, queue, conflict = {seed: 0}, [seed], False
        for current in queue:
            visited.add(current)
            for neighbor, distance in adjacency[current]:
                position = offsets[current] + distance
                if neighbor in offsets:
                    conflict |= offsets[neighbor] != position
                else:
                    offsets[neighbor] = position
                    queue.append(neighbor)
        cells = defaultdict(list)
        for page, offset in offsets.items():
            for index, message in enumerate(rows[page]):
                cells[offset + index].append((page, index, message))
        for occurrences in cells.values():
            if len(occurrences) > 1:
                keys = [signature(item[2]) for item in occurrences]
                conflict |= None in keys or any(key != keys[0] for key in keys)
        order = sorted(offsets, key=lambda page: (offsets[page], page))
        if conflict:
            order = sorted(offsets)
            warnings.append('部分截图的重叠关系互相冲突；这些图保留上传顺序和全部消息，请核对。')
            for page in order:
                messages.extend(copy.deepcopy(rows[page]))
        else:
            for position in sorted(cells):
                occurrences = sorted(cells[position], key=lambda item: (offsets[item[0]], item[0]))
                message = copy.deepcopy(occurrences[0][2])
                if len(occurrences) > 1:
                    message['sources'] = []
                    message['overlap_occurrences'] = []
                    for page, index, original in occurrences:
                        for source in original.get('sources', []):
                            if source not in message['sources']:
                                message['sources'].append(copy.deepcopy(source))
                        message['overlap_occurrences'].append(dict(asset_id=asset_ids[page], page_message_index=index, role=original['role'], text=original['text'], quoted_text=original.get('quoted_text', '')))
                    message['warnings'] = list(dict.fromkeys(warning for _, _, original in occurrences for warning in original.get('warnings', [])))
                messages.append(message)
        ordered.extend(asset_ids[page] for page in order)
        groups.append(dict(asset_ids=[asset_ids[page] for page in order], offsets={asset_ids[page]: offset for page, offset in offsets.items()}, status='conflict' if conflict else 'connected' if len(order) > 1 else 'unconnected'))
    before = sum(map(len, rows))
    removed = before - len(messages)
    if len(pages) > 1:
        if len(groups) > 1:
            warnings.append(f'有{len(groups)}组截图尚无足够重叠证据；组间暂按首次上传位置排列，请核对顺序。未能确认的重复消息均保留，可取消纳入。')
        if ambiguous:
            warnings.append('有重复文字能对应多个位置；未单独据此排序或合并，请对照原图核对。')
        if removed:
            warnings.append(f'依据连续重叠合并{removed}条重复出现，合并消息保留各张原图来源；仍需确认角色、顺序与是否同一条消息。')
    if ordered != asset_ids:
        warnings.insert(0, '依据连续重叠调整了截图顺序：上传第' + ' → 第'.join(str(asset_ids.index(identity) + 1) for identity in ordered) + '张。')
    for index, message in enumerate(messages):
        message['id'] = f'm{index + 1}'
    return dict(messages=messages, asset_ids=ordered, warnings=warnings, stitching=dict(version=STITCH_VERSION, mode='automatic', uploaded_asset_ids=asset_ids, ordered_asset_ids=ordered, original_message_count=before, merged_message_count=len(messages), removed_occurrences=removed, reordered=ordered != asset_ids, edges=edges, ambiguous_pairs=ambiguous, groups=groups, comparison='仅Unicode全半角及空白归一；角色、正文、引用须一致，不模糊改写OCR', authority='待顾问复核的衔接假设，不是已确认聊天'))
