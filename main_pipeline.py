"""SSOT_Explorer — 파이프라인 레이어(2026-09-04, D-100, O-021 Stage 3).

레이어 분리 방침(Plug_In_Global\\.claude\\레이어_분리_방침.md) 대비 main.py
분석(O-021)에서 지적된 4개 갭 중 "UX가 파이프라인 없이 로직/DB를 직접 호출"을
해소한다. 지금까지 main.py의 다이얼로그/툴바 핸들러(UX)가 router_registry/
router_proposals/router_sync와 파일 I/O를 직접 불렀다 — 이 모듈이 그 사이에
들어가는 파이프라인 계층이다.

**설계 원칙**(방침의 파이프라인 정의 "재조립만, 직접 처리 안 함/재조립 후
상태 미보유"를 그대로 따름):
- 이 모듈은 Qt를 import하지 않는다 — QMessageBox/QDialog 등 UX 확인 절차는
  전부 main.py에 남는다. 손편집 파일 덮어쓰기처럼 사람 확인이 필요한 경우는
  `router_sync.sync_root()`가 이미 쓰는 패턴(결과 dict의 status가
  "needs_confirmation"이면 UX가 확인 후 같은 함수를 `overwrite=True`로
  재호출)을 그대로 재사용한다 — 새 계약을 만들지 않는다.
- 함수는 상태를 갖지 않는다 — 매번 필요한 값을 인자로 받고 결과 dict를
  반환할 뿐, self.candidates 같은 다이얼로그 상태를 참조하지 않는다.
- 반환값은 이 프로젝트 전역 관례대로 plain dict(status 필드 + 관련 값) —
  router_sync.sync_root()/router_registry의 여러 함수와 동일한 스타일,
  새 클래스 계층을 도입하지 않는다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import router_proposals
import router_registry
import router_sync


def save_new_document(
    candidate: dict, filename: str, content: str, overwrite: bool = False,
) -> dict:
    """`SaveDocumentDialog.save_to_selected()`의 판단/쓰기 로직(D-029, 경로
    traversal 방어는 D-043 code-review 발견 반영). 파일이 이미 있는데
    `overwrite=False`면 쓰지 않고 `{"status": "needs_confirmation",
    "targetPath": ...}`만 반환 — UX가 확인받은 뒤 `overwrite=True`로
    재호출한다.

    반환 status: "invalid_filename"(절대경로/'..') / "outside_root"(경로
    traversal) / "needs_confirmation" / "write_failed"(OSError, "error"
    포함) / "ok"(성공, "targetPath" 포함 — 이때만 router_proposals.
    record_decision이 "approved"로 기록됨)."""
    name_path = Path(filename)
    root_path = Path(candidate["rootPath"])
    if name_path.is_absolute() or ".." in name_path.parts:
        return {"status": "invalid_filename"}
    target = root_path / name_path
    try:
        target.resolve().relative_to(root_path.resolve())
    except ValueError:
        return {"status": "outside_root"}
    if target.exists() and not overwrite:
        return {"status": "needs_confirmation", "targetPath": str(target)}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        return {"status": "write_failed", "error": str(e)}
    router_proposals.record_decision(candidate, content, "approved")
    return {"status": "ok", "targetPath": str(target)}


def record_save_cancelled(candidate: dict, content_preview: str) -> None:
    """`SaveDocumentDialog.cancel_and_close()`의 기록 로직 — 후보를 봤는데
    저장 안 하고 취소하면 1순위 후보 기준으로 "취소" 기록(제안 정밀도 데이터
    누적)."""
    router_proposals.record_decision(candidate, content_preview, "cancelled")


def find_nested_roots(new_root: Path, roots: list[dict]) -> list[dict]:
    """`add_root()`가 실제로 등록하기 전에 먼저 계산 — 2026-09-03 실측
    사고(SSOT_Coding_File을 flutter_App/Local_APP보다 먼저 등록해서 하위
    세션이 더 넓은 루트로 잘못 매치됨) 재발 방지. `new_root`가 이미
    등록된 어떤 루트를 하위에 품고 있으면(=그 루트를 "삼키면") 그 목록을
    반환 — UX는 이 목록이 비어있지 않으면 경고 다이얼로그를 보여준다.
    `new_root`는 호출부가 이미 `.resolve()`한 상태로 넘겨야 한다."""
    covered = []
    for r in roots:
        try:
            existing_path = Path(r["path"]).resolve()
        except (OSError, ValueError):
            continue
        if existing_path == new_root:
            continue
        try:
            existing_path.relative_to(new_root)
        except ValueError:
            continue
        covered.append(r)
    return covered


def add_root_entry(folder: str, label: str, roots: list[dict], registry_path: Path) -> dict:
    """`add_root()`의 등록 시퀀스 — save_roots + 하위 폴더 README 추적
    기준점 스냅샷 + init CLAUDE.md 생성. `roots`는 아직 새 entry가 안 붙은
    현재 목록(이 함수가 append/저장을 전담 — 호출부는 실패 시 되돌릴
    필요가 없다).

    반환 status: "conflict"(RegistryConflictError, "error"+최신 디스크
    상태 "roots" 포함) / "ok"(성공, "entry"+갱신된 "roots" 포함). "ok"여도
    init CLAUDE.md 쓰기만 실패했으면 "initFileError"가 추가로 붙는다 —
    등록 자체는 이미 끝났으므로 conflict로 취급하지 않는다(원본 add_root()
    와 동일한 관용 — QMessageBox.warning만 별도로 보여주고 등록은 유지)."""
    entry = {"label": label.strip(), "path": folder, "referenceCondition": ""}
    new_roots = [*roots, entry]
    try:
        router_registry.save_roots(new_roots, registry_path)
    except router_registry.RegistryConflictError as e:
        return {"status": "conflict", "error": str(e), "roots": router_registry.load_roots(registry_path)}

    # 2026-09-04 — 하위 폴더 README 추적(D-090)의 기준점. 등록 시점의 "누가
    # README를 갖고 있었는지" 스냅샷이 없으면 워치독이 나중에 "사라졌다"를
    # 판단할 기준이 없다 — 실패해도 등록 자체는 이미 끝났으니 조용히
    # 넘어간다(다음 워치독 스캔이 빈 스냅샷 기준으로 다시 시작할 뿐).
    try:
        snapshot = router_registry.scan_subfolder_readmes(Path(folder))
        router_registry.save_folder_snapshot(entry["label"], snapshot)
    except OSError:
        pass

    result = {"status": "ok", "entry": entry, "roots": new_roots}
    # 새 루트는 기존 내용이 없으니 안전하게 init CLAUDE.md를 바로 생성
    claude_path = router_sync.resolve_claude_md_target(Path(folder))
    if not claude_path.exists():
        try:
            claude_path.write_text(
                router_sync.generate_init_claude_md(entry, registry_path), encoding="utf-8",
            )
        except OSError as e:
            result["initFileError"] = str(e)
    return result


def remove_root_entry(idx: int, roots: list[dict], registry_path: Path) -> dict:
    """`_remove_root_at()`의 save_roots 시퀀스 — 툴바 버튼과 Delete 단축키
    양쪽이 공유. 반환 status: "conflict"(RegistryConflictError, "error"+
    최신 디스크 상태 "roots" 포함) / "ok"(성공, "removed"+갱신된 "roots"
    포함)."""
    new_roots = list(roots)
    removed = new_roots.pop(idx)
    try:
        router_registry.save_roots(new_roots, registry_path)
    except router_registry.RegistryConflictError as e:
        return {"status": "conflict", "error": str(e), "roots": router_registry.load_roots(registry_path)}
    return {"status": "ok", "removed": removed, "roots": new_roots}


def sync_formats(root_path: Path, entry: dict, registry_path: Path, formats: list[str]) -> dict:
    """`SyncFormatsDialog._sync()`의 1차 시도 — `router_sync.sync_root()`를
    그대로 호출한다(D-068, 실제 판단/생성 로직은 router_sync 소유 — 여기는
    그 경계를 파이프라인 이름으로 재노출). 결과 dict의 status가
    "needs-confirmation"인 포맷은 UX가 사람 확인을 거쳐
    `confirm_sync_formats()`로 재호출해야 한다."""
    return router_sync.sync_root(root_path, entry, registry_path, formats=formats)


def confirm_sync_formats(
    root_path: Path, entry: dict, registry_path: Path,
    first_results: dict, needs_confirm: list[str], confirmed: list[str],
) -> dict:
    """`SyncFormatsDialog._sync()`의 2차 처리 — 사용자가 확인한(`confirmed`)
    포맷만 force=True로 재시도하고, 확인은 물어봤지만 거부한(needs_confirm
    이지만 confirmed엔 없는) 포맷은 "skip"으로 표시한다(취소와 동일
    취급). `first_results`는 변형하지 않고 새 dict를 반환한다."""
    merged = dict(first_results)
    if confirmed:
        second = router_sync.sync_root(root_path, entry, registry_path, formats=confirmed, force=True)
        merged.update(second)
    for fmt in needs_confirm:
        if fmt not in confirmed:
            merged[fmt] = "skip"
    return merged


def mark_root_reviewed(label: str, registry_path: Path) -> dict:
    """`SyncFormatsDialog.mark_reviewed()`의 저장 로직 — 레지스트리를 새로
    읽어(다이얼로그가 들고 있는 entry는 스냅샷이라 최신이 아닐 수 있음)
    오늘 날짜로 lastReviewed를 갱신하고 저장한다.

    반환 status: "not_found"(레지스트리에서 label을 못 찾음) /
    "conflict"(RegistryConflictError, "error" 포함) / "ok"(성공,
    "reviewedAt" 포함)."""
    today = datetime.now().strftime("%Y-%m-%d")
    roots = router_registry.load_roots(registry_path)
    target = next((r for r in roots if r["label"] == label), None)
    if target is None:
        return {"status": "not_found"}
    target["lastReviewed"] = today
    try:
        router_registry.save_roots(roots, registry_path)
    except router_registry.RegistryConflictError as e:
        return {"status": "conflict", "error": str(e)}
    return {"status": "ok", "reviewedAt": today}


def export_all_roots_to_files(roots: list[dict]) -> dict:
    """`export_all_roots()`의 순회+쓰기 로직 — 레지스트리 전체를 완전판
    CLAUDE.md/README.md로 내보낸다(앱/레지스트리 없이도 동작하는 스냅샷).
    동기화 마커 없는(=손편집) 파일은 건너뛰고 절대 안 건드린다.

    반환: {"exported": [...], "skipped": [...], "failed": [...]} (전부
    label 목록)."""
    exported: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for entry in roots:
        root_path = Path(entry["path"])
        claude_path = router_sync.resolve_claude_md_target(root_path)
        if claude_path.exists():
            existing = claude_path.read_text(encoding="utf-8", errors="replace")
            if router_sync.SYNC_MARKER not in existing:
                skipped.append(entry["label"])
                continue
        try:
            claude_path.write_text(router_sync.generate_full_export_claude_md(entry), encoding="utf-8")
            exported.append(entry["label"])
        except OSError:
            failed.append(entry["label"])
            continue

        if (entry.get("readmeReferenceCondition") or "").strip():
            readme_path = root_path / "README.md"
            if readme_path.exists():
                existing_readme = readme_path.read_text(encoding="utf-8", errors="replace")
                if router_sync.SYNC_MARKER not in existing_readme:
                    continue  # README는 손편집 보호, CLAUDE.md만 내보내고 건너뜀
            try:
                readme_path.write_text(router_sync.generate_full_export_readme_md(entry), encoding="utf-8")
            except OSError:
                pass
    return {"exported": exported, "skipped": skipped, "failed": failed}


def set_developer_mode(enabled: bool, registry_path: Path) -> None:
    """`on_developer_mode_toggled()`의 저장 호출 — router_proposals.
    set_developer_mode()에 그대로 위임하는 얇은 재노출이다. 로직 자체는
    이미 router_proposals 소유(레지스트리 필드 하나만 갱신, 낙관적 동시성
    제어 생략은 D-057 참고) — 여기서는 UX가 그 모듈을 직접 안 부르고
    파이프라인 경계를 하나만 거치게 하는 목적."""
    router_proposals.set_developer_mode(enabled, registry_path)
