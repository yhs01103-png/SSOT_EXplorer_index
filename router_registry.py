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
맞음 — 경로가 다르면 서로 다른 키라 상태가 안 섞인다).

2026-08-21(D-071, O-010 해소) — `find_index_files`/`pick_canonical_index_
file`도 같은 이유로 여기 합류. ssot_mcp_server.py가 이 둘 때문에
`from main import ...`를 해서, MCP 서버 하나 띄우는 데도 PySide6가
전부 로드됐다(로직 자체는 순수 파일시스템 스캔, Qt 의존 전혀 없음).
main.py의 로거("ssot_explorer", D-025 — Windows 콘솔 인코딩 문제로 print()
대신 logging 채택)는 그대로 이름으로만 참조한다 — main.py가 먼저
로드됐으면 같은 핸들러를 공유하고(logging.getLogger는 이름으로 캐싱),
헤드리스(CLI/MCP)로만 쓰이면 핸들러가 없어 파이썬 기본 lastResort
핸들러(stderr)로 흘러간다 — 둘 다 안전하다.

2026-08-22(D-073, O-018(b) 해소) — `labeledFolders[]` CRUD(roots[]와 분리된
경량 배열, 서브폴더 라벨 추적용) + 30일 감사 문턱값 계산 + README 자기선언
마커(`<!-- SSOT-LABEL: 이름 -->`) 파싱이 여기 합류. 상세 배경은 설계
결정이력 D-073 참고."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path

import router_proposals

log = logging.getLogger("ssot_explorer")


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


# --------------------------------------------------------- 라벨 폴더(O-018/D-073)
# roots[]와 분리한 경량 배열 — referenceCondition 동기화(CLAUDE.md 4종)/
# actions/dependsOnDocs 같은 무거운 기계장치를 안 짊어진다. "README가
# 있거나 필요한 하위 폴더"를 최소 필드({label, path, parentLabel,
# lastAudited})로만 추적 — 실제 라벨-폴더-README 3자 일치 감사는 스크립트가
# 아니라 Claude Code가 세션 안에서 직접 수행(에이전틱 감사 태스크, P-01과
# 동일한 이유로 이 모듈은 감사를 자동 실행하지 않는다).

LABELED_FOLDER_AUDIT_STALE_DAYS = 30  # check_readme_freshness의 stale_days
# 기본값(D-048)과 동일값 재사용 — "README가 실제 변경 대비 며칠 뒤처졌는지"
# 문턱값을 그대로 "라벨 감사가 며칠 밀렸는지"에도 재사용, 새 숫자를
# 발명하지 않음.

SSOT_LABEL_MARKER_PREFIX = "<!-- SSOT-LABEL:"  # README.md 맨 위 자기선언 마커


def load_labeled_folders(registry_path: Path) -> list[dict]:
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
    folders = data.get("labeledFolders", [])
    for f in folders:
        f.setdefault("parentLabel", None)
        f.setdefault("lastAudited", "")
    return folders


def save_labeled_folders(folders: list[dict], registry_path: Path) -> None:
    """labeledFolders만 갱신 — roots/sharedDocs/relations/$comment는 기존
    파일에서 그대로 보존(save_roots와 동일한 병합 저장 원칙, D-020 유실
    버그 재발 방지). 같은 registry_path에 대해 save_roots와 동일한
    _last_known_hash를 공유하므로(둘 다 파일 하나 전체를 다룸) 충돌 감지도
    동일하게 적용된다."""
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
    payload.setdefault("roots", [])
    payload.setdefault("sharedDocs", [])
    payload.setdefault("relations", [])
    payload["labeledFolders"] = folders

    raw = router_proposals.atomic_write_json(registry_path, payload)
    _last_known_hash[key] = _hash_bytes(raw)


def add_labeled_folder(entry: dict, registry_path: Path) -> None:
    """add_root와 동일한 계약 — 같은 label이 이미 있으면 ValueError."""
    folders = load_labeled_folders(registry_path)
    if any(f["label"] == entry["label"] for f in folders):
        raise ValueError(f"label '{entry['label']}'은(는) 이미 등록돼 있습니다.")
    folders.append(entry)
    save_labeled_folders(folders, registry_path)


def mark_labeled_folder_audited(label: str, registry_path: Path, audited_on: str) -> None:
    """감사(라벨-폴더-README 3자 일치 확인)를 실제로 마친 뒤 lastAudited를
    갱신한다 — 감사 자체는 이 함수가 하지 않는다(호출부, 즉 Claude Code가
    감사를 마쳤다고 판단한 뒤에만 부른다)."""
    folders = load_labeled_folders(registry_path)
    target = next((f for f in folders if f["label"] == label), None)
    if target is None:
        raise ValueError(f"label '{label}'을(를) 찾을 수 없습니다.")
    target["lastAudited"] = audited_on
    save_labeled_folders(folders, registry_path)


def labeled_folder_audit_status(entry: dict, today: date) -> dict:
    """lastAudited 대비 오늘 기준 남은 일수를 계산하는 순수 함수(디스크
    접근 없음 — 테스트가 today를 고정해서 결정적으로 검증 가능). 기존
    _review_age_days(main.py, roots[].lastReviewed용)와 같은 형식 가정
    (YYYY-MM-DD)이지만 별도 함수로 둔 이유: roots는 '초과일수'만 필요하고
    (180일 넘었는지만 보면 됨), 이쪽은 '남은 일수'를 평소에도 항상 보여줘야
    해서(D-073 — 조기 수동 트리거를 유도하는 상시 카운트다운) 반환 형태
    자체가 다르다."""
    label = entry.get("label", "")
    raw = (entry.get("lastAudited") or "").strip()
    if not raw:
        return {"label": label, "status": "never_audited", "daysRemaining": None}
    try:
        last = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return {"label": label, "status": "invalid_last_audited", "daysRemaining": None}
    days_remaining = LABELED_FOLDER_AUDIT_STALE_DAYS - (today - last).days
    status = "due" if days_remaining <= 0 else "ok"
    return {"label": label, "status": status, "daysRemaining": days_remaining}


def read_ssot_label_marker(readme_path: Path) -> str | None:
    """README.md 맨 위 `<!-- SSOT-LABEL: 이름 -->` 자기선언 마커를 읽는다
    (D-073) — 폴더가 이동해도 이 마커로 재탐색(라벨 기준 매칭)이 가능하게
    하는 앵커. 파일 앞부분(마커는 항상 맨 위 근처)만 읽어 큰 README에서도
    가볍게 동작 — 첫 20줄 안에서 못 찾으면 없다고 본다."""
    try:
        with readme_path.open("r", encoding="utf-8-sig") as fh:
            for _ in range(20):
                line = fh.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.startswith(SSOT_LABEL_MARKER_PREFIX) and stripped.endswith("-->"):
                    value = stripped[len(SSOT_LABEL_MARKER_PREFIX):-len("-->")].strip()
                    return value or None
    except OSError:
        return None
    return None


# ------------------------------------------------------------- 인덱스 파일 탐색

INDEX_FILENAMES = {"claude.md", "readme.md"}
CANONICAL_INDEX_NAMES = {"claude.md": "CLAUDE.md", "readme.md": "README.md"}


def pick_canonical_index_file(key: str, paths: list[Path]) -> Path:
    """같은 폴더에 대소문자만 다른 인덱스 파일이 여러 개일 때 어느 걸 쓸지
    결정적으로 고른다 — find_index_files에서 분리한 순수 함수(디스크 접근
    없이 테스트 가능, 실제 케이스-센서티브 파일시스템 없이도 회귀 검증)."""
    canonical = CANONICAL_INDEX_NAMES.get(key)
    chosen = next((p for p in paths if p.name == canonical), None)
    return chosen if chosen is not None else sorted(paths, key=lambda p: p.name)[0]


def find_index_files(folder: Path) -> dict:
    """folder 바로 밑, 그리고 folder\\.claude 밑 양쪽에서 CLAUDE.md/README.md를
    찾는다 — 플랫 컨벤션과 `.claude` 하위 컨벤션 둘 다 지원. 바로 밑 파일이
    있으면 그쪽을 우선한다."""
    found = {}
    if not folder.is_dir():
        return found
    candidates = [folder]
    claude_sub = folder / ".claude"
    if claude_sub.is_dir():
        candidates.append(claude_sub)
    for base in candidates:
        try:
            matches: dict[str, list[Path]] = {}
            for entry in base.iterdir():
                if entry.is_file() and entry.name.lower() in INDEX_FILENAMES:
                    matches.setdefault(entry.name.lower(), []).append(entry)
        except (PermissionError, OSError):
            continue
        for key, paths in matches.items():
            if key in found:
                continue  # 상위 base(폴더 바로 밑)가 이미 채웠으면 유지 — 기존 우선순위
            if len(paths) == 1:
                found[key] = paths[0]
                continue
            chosen = pick_canonical_index_file(key, paths)
            found[key] = chosen
            others = ", ".join(p.name for p in paths if p != chosen)
            log.warning(
                f"{base}에 대소문자만 다른 인덱스 파일 {len(paths)}개 발견 — "
                f"'{chosen.name}' 사용, 무시됨: {others}"
            )
    return found
