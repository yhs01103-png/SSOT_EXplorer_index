"""SSOT_Explorer — 레지스트리(ssot-roots.json) 로드/저장(2026-08-21, D-069).

`main.py`가 갖고 있던 `load_roots`/`save_roots`/`RegistryConflictError`를
뽑아냈다 — router_sync.py(D-068)와 같은 이유: 순수 로직(JSON I/O, 원자적
쓰기+낙관적 동시성 제어, 해시 비교)인데 물리적으로 PySide6를 임포트하는
main.py 안에 있어서, GUI 없이 "루트 하나 등록하기" 같은 걸 할 방법이
없었다. `ssot register`/`ssot init` CLI가 이 모듈만 임포트하면 되고,
PySide6는 전혀 필요 없다.

main.py의 원래 `_LAST_KNOWN_HASH`는 모듈 전역 변수 하나였다(그 프로세스가
평생 레지스트리 하나만 쓰는 GUI라 충분했음) — 여기서는 `registry_path`별로
추적하는 dict로 일반화했다(CLI가 같은 프로세스 안에서 여러 레지스트리를
다룰 가능성, 또는 테스트가 매번 다른 tmp_path를 쓰는 것 둘 다 자연스럽게
맞음 — 경로가 다르면 서로 다른 키라 상태가 안 섞인다)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import router_proposals


class RegistryConflictError(Exception):
    """save_roots()가 쓰기 직전 재확인한 디스크 해시가, 마지막으로 읽은
    시점의 해시와 다를 때. OneDrive로 여러 기기에 동기화되는 레지스트리라
    이 프로세스가 모르는 사이 다른 기기/세션이 먼저 저장했을 수 있다는 뜻
    — 조용히 덮어쓰지 않고 여기서 멈춘다."""


_last_known_hash: dict[str, str] = {}


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _current_hash(registry_path: Path) -> str:
    if not registry_path.exists():
        return ""
    try:
        return _hash_bytes(registry_path.read_bytes())
    except OSError:
        return ""


def load_roots(registry_path: Path) -> list[dict]:
    key = str(registry_path)
    if not registry_path.exists():
        _last_known_hash[key] = ""
        return []
    try:
        raw = registry_path.read_bytes()
    except OSError:
        return []
    _last_known_hash[key] = _hash_bytes(raw)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    roots = data.get("roots", [])
    for r in roots:
        r.setdefault("referenceCondition", "")
        r.setdefault("readmeReferenceCondition", "")
        r.setdefault("webArtifactUrl", "")
        r.setdefault("owner", "")
        r.setdefault("lastReviewed", "")
        r.setdefault("scope", "")
        r.setdefault("dependsOnDocs", [])
        r.setdefault("primarySource", "local")
        r.setdefault("actions", [])
    return roots


def save_roots(roots: list[dict], registry_path: Path) -> None:
    """roots만 갱신 — sharedDocs/$comment 등 다른 최상위 키는 기존 파일에서
    그대로 보존한다(병합 저장). 원자적 쓰기(router_proposals.
    atomic_write_json에 위임)+낙관적 동시성 제어(같은 registry_path에 대해
    이 프로세스가 마지막으로 확인한 해시와 지금 디스크 해시가 다르면
    RegistryConflictError)."""
    key = str(registry_path)
    current = _current_hash(registry_path)
    last = _last_known_hash.get(key, "")
    if last and current != last:
        raise RegistryConflictError(
            "레지스트리가 마지막으로 읽은 이후 다른 곳에서 바뀌었습니다. "
            "덮어쓰지 않고 중단합니다 — 새로고침 후 다시 시도하세요."
        )

    payload: dict = {}
    if registry_path.exists():
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.setdefault(
        "$comment",
        "SSOT 인덱싱 루트 레지스트리 — 단일 소스. main.py(SSOT Explorer), "
        "ssot_index_drift_check.py, ssot_index_reminder.py가 전부 이 파일을 "
        "읽는다. referenceCondition은 각 루트 CLAUDE.md(init)로 동기화되는 "
        "실제 규칙 텍스트, dependsOnDocs는 sharedDocs 의존관계(영향범위 전파) "
        "— 전부 Claude Code가 대화 중 직접 채운다.",
    )
    payload.setdefault("sharedDocs", [])
    payload.setdefault("relations", [])
    payload["roots"] = roots

    raw = router_proposals.atomic_write_json(registry_path, payload)
    _last_known_hash[key] = _hash_bytes(raw)


def add_root(entry: dict, registry_path: Path) -> None:
    """`register` 커맨드가 쓰는 편의 함수 — 같은 label이 이미 있으면
    ValueError(덮어쓰기는 update_root로 명시적으로 하게, 실수로 중복
    등록되는 걸 막음)."""
    roots = load_roots(registry_path)
    if any(r["label"] == entry["label"] for r in roots):
        raise ValueError(f"label '{entry['label']}'은(는) 이미 등록돼 있습니다.")
    roots.append(entry)
    save_roots(roots, registry_path)
