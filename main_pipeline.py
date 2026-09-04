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

from pathlib import Path

import router_proposals


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
