from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET

UTC = dt.timezone.utc
TEXT_SUFFIXES = {
    '.txt', '.md', '.json', '.jsonl', '.csv', '.tsv', '.ini', '.toml', '.yaml', '.yml', '.py', '.ps1'
}


def iso_utc(value: dt.datetime | None = None) -> str:
    return (value or dt.datetime.now(UTC)).isoformat().replace('+00:00', 'Z')


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        data = archive.read('word/document.xml')
    root = ET.fromstring(data)
    parts: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith('}t') and elem.text:
            parts.append(elem.text)
        elif elem.tag.endswith('}p'):
            parts.append('\n')
    return ''.join(parts)


def read_text(path: Path, max_bytes: int = 16 * 1024 * 1024) -> tuple[str, bool]:
    if path.suffix.lower() == '.docx':
        return _docx_text(path), True
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return '', False
    size = path.stat().st_size
    if size > max_bytes:
        with path.open('rb') as handle:
            head = handle.read(max_bytes // 2)
            handle.seek(max(size - max_bytes // 2, 0))
            tail = handle.read(max_bytes // 2)
        payload = head + b'\n[...TRUNCATED_FOR_SIGNATURE...]\n' + tail
        return payload.decode('utf-8', errors='replace'), False
    return path.read_text(encoding='utf-8-sig', errors='replace'), True


def classify_content(path: Path, text: str) -> str:
    normalized_path = str(path).replace('\\', '/').lower()
    stripped = text.lstrip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if stripped.startswith('# SYSTEMPACK_') and '# >>> segment_' in text:
        return 'SYSTEMPACK_PROJECT_CORPUS'
    if 'zxcvbndata/' in normalized_path or 'zxcvbndata\\' in normalized_path:
        if lines:
            single_token = sum(1 for line in lines[:5000] if len(line.split()) == 1 and len(line) <= 80)
            if single_token / min(len(lines), 5000) >= 0.95:
                return 'ZXC_VBN_WORDLIST'
    if 'source: conversations-' in text.lower() and re.search(r'(?m)^chat\s+\d+:', text, re.I):
        return 'CHAT_EXPORT'
    if stripped.startswith('КОНСОЛИДИРОВАННЫЙ ОТЧЁТ') or 'CONSOLIDATED REPORT' in text[:2000].upper():
        return 'CONSOLIDATED_FORENSIC_REPORT'
    if lines and lines[0].lower().startswith('"root","root_label","relative_path"'):
        return 'HANDOFF_CANDIDATES_LEDGER'
    if path.name.lower() == 'pytest.ini':
        return 'TEST_DISCOVERY_CONFIG'
    if path.name.lower().endswith('.template.json'):
        return 'TEMPLATE_CONFIG'
    if 'name: healthcare-providers-enrich' in text[:1000]:
        return 'UNRELATED_PLUGIN_HEALTHCARE'
    if '# Content Gap Analysis' in text[:1000]:
        return 'UNRELATED_PLUGIN_SEO'
    if path.suffix.lower() == '.docx':
        return 'DOCX_REPORT'
    if path.suffix.lower() in TEXT_SUFFIXES:
        return 'GENERIC_TEXT'
    return 'BINARY_OR_UNKNOWN'


def inspect_file(path: Path, max_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    resolved = path.resolve()
    text, full_read = read_text(resolved, max_bytes=max_bytes)
    stat = resolved.stat()
    return {
        'path': str(resolved),
        'name': resolved.name,
        'suffix': resolved.suffix.lower(),
        'size_bytes': stat.st_size,
        'mtime_utc': dt.datetime.fromtimestamp(stat.st_mtime, UTC).isoformat().replace('+00:00', 'Z'),
        'sha256': sha256_file(resolved),
        'content_class': classify_content(resolved, text),
        'content_signature_verified': bool(text) or resolved.suffix.lower() in TEXT_SUFFIXES | {'.docx'},
        'full_text_read': full_read,
        'text_characters_read': len(text),
        'line_count_read': text.count('\n') + (1 if text else 0),
        'first_nonempty_lines': [line.strip() for line in text.splitlines() if line.strip()][:5],
        'last_nonempty_lines': [line.strip() for line in text.splitlines() if line.strip()][-5:],
    }


def iter_files(values: Sequence[str | Path], allowed_suffixes: set[str] | None = None) -> Iterable[Path]:
    suffixes = allowed_suffixes or (TEXT_SUFFIXES | {'.docx'})
    seen: set[str] = set()
    for raw in values:
        path = Path(raw).expanduser()
        if not path.exists():
            continue
        candidates = [path] if path.is_file() else path.rglob('*')
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in suffixes:
                continue
            key = str(candidate.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            yield candidate


def discover_same_name_collisions(files: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for item in files:
        by_name.setdefault(str(item['name']).lower(), []).append(item)
    collisions: list[dict[str, Any]] = []
    for name, rows in sorted(by_name.items()):
        hashes = sorted({str(row['sha256']) for row in rows})
        if len(hashes) > 1:
            collisions.append({
                'name': name,
                'hashes': hashes,
                'versions': [
                    {
                        'path': row['path'],
                        'sha256': row['sha256'],
                        'size_bytes': row['size_bytes'],
                        'mtime_utc': row['mtime_utc'],
                        'content_class': row['content_class'],
                    }
                    for row in sorted(rows, key=lambda r: (str(r['mtime_utc']), str(r['path'])))
                ],
            })
    return collisions



def inspect_file_cached(
    path: Path,
    cache: Mapping[str, Any] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.resolve()
    stat = resolved.stat()
    key = str(resolved).casefold()
    cached = dict((cache or {}).get(key, {}))
    if (
        cached.get('size_bytes') == stat.st_size
        and cached.get('mtime_ns') == stat.st_mtime_ns
        and isinstance(cached.get('record'), dict)
    ):
        record = dict(cached['record'])
        return record, {
            'size_bytes': stat.st_size,
            'mtime_ns': stat.st_mtime_ns,
            'record': record,
        }
    record = inspect_file(resolved, max_bytes=max_bytes)
    return record, {
        'size_bytes': stat.st_size,
        'mtime_ns': stat.st_mtime_ns,
        'record': record,
    }


def scan_frontier_pair(
    origin_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    processed = processed_hashes or set()
    cache = inventory_cache or {}
    next_cache: dict[str, Any] = {}

    def scan(paths: Sequence[str | Path]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in iter_files(paths):
            record, cache_row = inspect_file_cached(path, cache=cache, max_bytes=max_bytes)
            rows.append(record)
            next_cache[str(path.resolve()).casefold()] = cache_row
        return rows

    origin_items = scan(origin_paths)
    current_items = scan(current_paths)
    origin_unseen = [row for row in origin_items if row['sha256'] not in processed]
    current_unseen = [row for row in current_items if row['sha256'] not in processed]
    origin = min(origin_unseen, key=lambda r: (r['mtime_utc'], r['path'])) if origin_unseen else None
    current = max(current_unseen, key=lambda r: (r['mtime_utc'], r['path'])) if current_unseen else None
    all_items = origin_items + current_items
    pair = {
        'schema_version': 1,
        'generated_at': iso_utc(),
        'origin': origin,
        'current': current,
        'origin_files_seen': len(origin_items),
        'current_files_seen': len(current_items),
        'same_name_collisions': discover_same_name_collisions(all_items),
        'status': 'PAIR_READY' if origin and current else 'FRONTIER_INCOMPLETE',
        'inventory_cache_entries': len(next_cache),
        'can_trade': False,
    }
    return pair, next_cache

def select_frontier_pair(
    origin_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
) -> dict[str, Any]:
    pair, _ = scan_frontier_pair(
        origin_paths,
        current_paths,
        processed_hashes=processed_hashes,
        max_bytes=max_bytes,
    )
    return pair


def archive_frontier_event(pair: Mapping[str, Any]) -> dict[str, Any]:
    origin = pair.get('origin')
    current = pair.get('current')
    evidence_refs = []
    for side, item in [('ORIGIN', origin), ('CURRENT', current)]:
        if item:
            evidence_refs.append({
                'type': f'ARCHIVE_{side}',
                'path': item['path'],
                'sha256': item['sha256'],
                'content_class': item['content_class'],
                'evidence_class': 'VERIFIED_FACT',
            })
    return {
        'schema_version': 1,
        'event_id': 'AF-' + hashlib.sha256(json.dumps(pair, sort_keys=True).encode('utf-8')).hexdigest()[:20],
        'timestamp': pair.get('generated_at', iso_utc()),
        'task_id': 'BIDIRECTIONAL_ARCHIVE_FRONTIER',
        'step_id': f"{origin['name'] if origin else 'NONE'}__{current['name'] if current else 'NONE'}",
        'event_type': 'ARCHIVE_FRONTIER_ADVANCE',
        'actor': 'HANRI_R25',
        'goal': 'Advance oldest unresolved and newest current archive frontiers in the same bounded cycle.',
        'human_summary': (
            f"Origin: {origin['name'] if origin else 'NONE'}; "
            f"Current: {current['name'] if current else 'NONE'}."
        ),
        'checks': {
            'changed_evidence': bool(origin or current),
            'origin_frontier_processed': bool(origin),
            'current_frontier_processed': bool(current),
            'content_signature_verified': all(
                item and item.get('content_signature_verified') for item in (origin, current)
            ) if origin and current else False,
            'same_name_multiple_hashes': bool(pair.get('same_name_collisions')),
            'version_lineage_recorded': bool(pair.get('same_name_collisions')),
        },
        'payload': dict(pair),
        'evidence_refs': evidence_refs,
        'recursion_depth': 0,
        'can_trade': False,
    }



def _scope_manifest_rows(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in items:
        key = (str(item['path']).casefold(), str(item['sha256']))
        unique[key] = item
    return [
        {
            'path': str(item['path']),
            'sha256': str(item['sha256']),
            'size_bytes': int(item['size_bytes']),
            'content_class': str(item.get('content_class', 'UNKNOWN')),
            'full_text_read': bool(item.get('full_text_read', False)),
        }
        for item in sorted(unique.values(), key=lambda row: (str(row['path']).casefold(), str(row['sha256'])))
    ]


def build_scope_coverage_certificate(
    scope_id: str,
    items: Sequence[Mapping[str, Any]],
    *,
    evidence_ceiling: str = 'PHYSICAL_FILE_METADATA_AND_TEXT_READ',
    required_full_text: bool = True,
) -> dict[str, Any]:
    if not scope_id.strip():
        raise ValueError('scope_id is required')
    rows = _scope_manifest_rows(items)
    denominator = len(rows)
    numerator = sum(1 for row in rows if row['full_text_read']) if required_full_text else denominator
    manifest_sha256 = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return {
        'schema_version': 1,
        'scope_id': scope_id,
        'generated_at': iso_utc(),
        'scope_manifest_sha256': manifest_sha256,
        'numerator': numerator,
        'denominator': denominator,
        'coverage_ratio': f'{numerator}/{denominator}',
        'coverage_percent': round((numerator / denominator * 100.0), 6) if denominator else 0.0,
        'required_full_text': required_full_text,
        'evidence_ceiling': evidence_ceiling,
        'status': 'COMPLETE' if denominator > 0 and numerator == denominator else 'PARTIAL',
        'files': rows,
        'can_trade': False,
    }


def scan_causal_spine(
    origin_paths: Sequence[str | Path],
    pivot_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Mapping[str, Any] | None = None,
    scope_id: str = 'ARCHIVE_CAUSAL_SPINE',
) -> tuple[dict[str, Any], dict[str, Any]]:
    processed = processed_hashes or set()
    cache = inventory_cache or {}
    next_cache: dict[str, Any] = {}

    def scan(paths: Sequence[str | Path]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in iter_files(paths):
            record, cache_row = inspect_file_cached(path, cache=cache, max_bytes=max_bytes)
            rows.append(record)
            next_cache[str(path.resolve()).casefold()] = cache_row
        return rows

    origin_items = scan(origin_paths)
    pivot_items = scan(pivot_paths)
    current_items = scan(current_paths)

    def unseen(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if row['sha256'] not in processed]

    origin_candidates = unseen(origin_items)
    pivot_candidates = unseen(pivot_items)
    current_candidates = unseen(current_items)

    origin = min(origin_candidates, key=lambda r: (r['mtime_utc'], r['path'])) if origin_candidates else None
    pivot = min(pivot_candidates, key=lambda r: (r['mtime_utc'], r['path'])) if pivot_candidates else None
    current = max(current_candidates, key=lambda r: (r['mtime_utc'], r['path'])) if current_candidates else None

    all_items = origin_items + pivot_items + current_items
    scope = build_scope_coverage_certificate(
        scope_id,
        all_items,
        evidence_ceiling='REGISTERED_CAUSAL_FRONTIER_FILES_ONLY',
        required_full_text=False,
    )
    spine = {
        'schema_version': 1,
        'generated_at': iso_utc(),
        'scope_id': scope_id,
        'origin': origin,
        'pivot': pivot,
        'current': current,
        'origin_files_seen': len(origin_items),
        'pivot_files_seen': len(pivot_items),
        'current_files_seen': len(current_items),
        'same_name_collisions': discover_same_name_collisions(all_items),
        'coverage_certificate': scope,
        'status': 'SPINE_READY' if origin and pivot and current else 'CAUSAL_SPINE_INCOMPLETE',
        'inventory_cache_entries': len(next_cache),
        'causal_claim_authority': 'NONE_UNTIL_HUMAN_OR_PRIMARY_EVIDENCE_ADJUDICATION',
        'can_trade': False,
    }
    return spine, next_cache


def causal_spine_event(spine: Mapping[str, Any]) -> dict[str, Any]:
    origin = spine.get('origin')
    pivot = spine.get('pivot')
    current = spine.get('current')
    evidence_refs = []
    for side, item in [('ORIGIN', origin), ('PIVOT', pivot), ('CURRENT', current)]:
        if item:
            evidence_refs.append({
                'type': f'ARCHIVE_{side}',
                'path': item['path'],
                'sha256': item['sha256'],
                'content_class': item['content_class'],
                'evidence_class': 'VERIFIED_FACT',
            })
    scope = spine.get('coverage_certificate', {})
    digest = hashlib.sha256(json.dumps(spine, sort_keys=True).encode('utf-8')).hexdigest()
    names = [item['name'] if item else 'NONE' for item in (origin, pivot, current)]
    return {
        'schema_version': 1,
        'event_id': 'ACS-' + digest[:20],
        'timestamp': spine.get('generated_at', iso_utc()),
        'task_id': 'ARCHIVE_CAUSAL_SPINE',
        'step_id': '__'.join(names),
        'event_type': 'ARCHIVE_CAUSAL_SPINE',
        'actor': 'HANRI_R28',
        'goal': 'Advance origin, correction/pivot and current frontiers without collapsing archive scope or authority.',
        'human_summary': f"Origin: {names[0]}; Pivot: {names[1]}; Current: {names[2]}.",
        'checks': {
            'changed_evidence': bool(origin or pivot or current),
            'origin_frontier_processed': bool(origin),
            'pivot_frontier_processed': bool(pivot),
            'current_frontier_processed': bool(current),
            'content_signature_verified': all(
                item and item.get('content_signature_verified') for item in (origin, pivot, current)
            ) if origin and pivot and current else False,
            'same_name_multiple_hashes': bool(spine.get('same_name_collisions')),
            'version_lineage_recorded': bool(spine.get('same_name_collisions')),
            'completeness_claim_present': True,
            'coverage_scope_bound': bool(scope.get('scope_id') and scope.get('scope_manifest_sha256')),
            'per_file_coverage_ledger_present': bool(scope.get('files')),
            'causal_spine_complete': bool(origin and pivot and current),
        },
        'payload': dict(spine),
        'evidence_refs': evidence_refs,
        'recursion_depth': 0,
        'can_trade': False,
    }
