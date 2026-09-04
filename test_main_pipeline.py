"""main_pipeline.py 전용 테스트 — D-100, O-021 Stage 3(파이프라인 레이어).
Qt 없이 순수 함수 호출로 검증한다(router_registry.py류와 동일 원칙) — GUI
다이얼로그(SaveDocumentDialog 등)가 이 함수들을 올바르게 호출하는지는
test_main.py의 기존 통합 테스트가 계속 커버한다."""
from __future__ import annotations

import json

import pytest

import main_pipeline as mp
import router_proposals as rp
import router_registry as rr


@pytest.fixture(autouse=True)
def isolated_router_proposals(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")


@pytest.fixture(autouse=True)
def isolated_folder_snapshot(tmp_path, monkeypatch):
    """add_root_entry()가 router_registry.save_folder_snapshot()도 호출한다
    (D-090, 하위 폴더 README 추적 기준점) — 실제 사용자 파일 절대 안
    건드리게 격리."""
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", tmp_path / "folder-snapshots.json")


def _candidate(root_dir):
    return {"rootLabel": "a", "rootPath": str(root_dir), "score": 0.5, "reason": "테스트"}


# --------------------------------------------------------- save_new_document

def test_save_new_document_writes_file_and_records_approved(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    result = mp.save_new_document(_candidate(root_dir), "메모.md", "내용")
    assert result["status"] == "ok"
    assert (root_dir / "메모.md").read_text(encoding="utf-8") == "내용"
    proposals = rp.load_proposals()
    assert len(proposals) == 1
    assert proposals[0]["decision"] == "approved"


def test_save_new_document_rejects_absolute_path(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    outside = tmp_path / "evil.md"
    result = mp.save_new_document(_candidate(root_dir), str(outside), "내용")
    assert result["status"] == "invalid_filename"
    assert not outside.exists()
    assert rp.load_proposals() == []


def test_save_new_document_rejects_dotdot_traversal(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    outside = tmp_path / "evil.md"
    result = mp.save_new_document(_candidate(root_dir), "../evil.md", "내용")
    assert result["status"] in ("invalid_filename", "outside_root")
    assert not outside.exists()


def test_save_new_document_needs_confirmation_when_target_exists(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    existing = root_dir / "메모.md"
    existing.write_text("기존 내용", encoding="utf-8")

    result = mp.save_new_document(_candidate(root_dir), "메모.md", "새 내용")
    assert result["status"] == "needs_confirmation"
    assert result["targetPath"] == str(existing)
    assert existing.read_text(encoding="utf-8") == "기존 내용"  # 아직 안 덮어씀
    assert rp.load_proposals() == []  # 확인 전이라 기록도 아직 없음


def test_save_new_document_overwrite_true_writes_and_records(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    existing = root_dir / "메모.md"
    existing.write_text("기존 내용", encoding="utf-8")

    result = mp.save_new_document(_candidate(root_dir), "메모.md", "새 내용", overwrite=True)
    assert result["status"] == "ok"
    assert existing.read_text(encoding="utf-8") == "새 내용"
    assert len(rp.load_proposals()) == 1


def test_save_new_document_write_failure_reports_error(tmp_path, monkeypatch):
    root_dir = tmp_path / "root"
    root_dir.mkdir()

    def _boom(self, *a, **k):
        raise OSError("디스크 가득 참(시뮬레이션)")

    monkeypatch.setattr(mp.Path, "write_text", _boom)
    result = mp.save_new_document(_candidate(root_dir), "메모.md", "내용")
    assert result["status"] == "write_failed"
    assert "디스크" in result["error"]
    assert rp.load_proposals() == []  # 쓰기 실패했으니 승인 기록도 안 남음


# ----------------------------------------------------------- record_save_cancelled

def test_record_save_cancelled_records_cancelled_decision(tmp_path):
    root_dir = tmp_path / "root"
    mp.record_save_cancelled(_candidate(root_dir), "미리보기 내용")
    proposals = rp.load_proposals()
    assert len(proposals) == 1
    assert proposals[0]["decision"] == "cancelled"


# --------------------------------------------------------- find_nested_roots

def test_find_nested_roots_detects_covered_subroot(tmp_path):
    parent = tmp_path / "workspace"
    child = parent / "sub"
    child.mkdir(parents=True)
    roots = [{"label": "sub", "path": str(child)}]
    covered = mp.find_nested_roots(parent.resolve(), roots)
    assert [r["label"] for r in covered] == ["sub"]


def test_find_nested_roots_empty_when_no_overlap(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    roots = [{"label": "a", "path": str(a)}]
    assert mp.find_nested_roots(b.resolve(), roots) == []


def test_find_nested_roots_ignores_exact_same_path(tmp_path):
    """등록하려는 폴더 자기 자신은 "하위"가 아니다 — 재등록 시나리오에서
    자기 자신을 삼켰다고 오탐하면 안 된다."""
    folder = tmp_path / "same"
    folder.mkdir()
    roots = [{"label": "same", "path": str(folder)}]
    assert mp.find_nested_roots(folder.resolve(), roots) == []


# --------------------------------------------------------- add_root_entry

def test_add_root_entry_writes_registry_snapshot_and_init_file(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    folder = tmp_path / "newproj"
    folder.mkdir()

    result = mp.add_root_entry(str(folder), "newproj", [], registry_path)
    assert result["status"] == "ok"
    assert result["entry"]["label"] == "newproj"
    assert [r["label"] for r in result["roots"]] == ["newproj"]
    assert [r["label"] for r in rr.load_roots(registry_path)] == ["newproj"]
    assert (folder / "CLAUDE.md").exists()
    assert "initFileError" not in result


def test_add_root_entry_appends_to_existing_roots(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    folder = tmp_path / "newproj"
    folder.mkdir()
    existing = [{"label": "old", "path": "C:\\old", "referenceCondition": ""}]

    result = mp.add_root_entry(str(folder), "newproj", existing, registry_path)
    assert result["status"] == "ok"
    assert {r["label"] for r in result["roots"]} == {"old", "newproj"}
    assert existing == [{"label": "old", "path": "C:\\old", "referenceCondition": ""}]  # 원본 안 건드림


def test_add_root_entry_does_not_overwrite_existing_claude_md(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    folder = tmp_path / "newproj"
    folder.mkdir()
    (folder / "CLAUDE.md").write_text("손편집 내용", encoding="utf-8")

    result = mp.add_root_entry(str(folder), "newproj", [], registry_path)
    assert result["status"] == "ok"
    assert (folder / "CLAUDE.md").read_text(encoding="utf-8") == "손편집 내용"


def test_add_root_entry_conflict_returns_disk_state(tmp_path):
    """test_main.py의 test_save_roots_detects_external_write_conflict와
    동일 기법 — router_registry 모듈 함수를 안 거치고 파일을 직접 바꿔서
    "다른 프로세스가 그 사이 먼저 썼다"를 시뮬레이션한다(모듈 함수를
    거치면 그 자체가 _last_known_hash를 갱신해버려 충돌이 재현이 안 됨)."""
    registry_path = tmp_path / "ssot-roots.json"
    folder = tmp_path / "newproj"
    folder.mkdir()
    rr.save_roots([], registry_path)  # 기준선 — _last_known_hash 확정

    external = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    external["roots"].append({"label": "external", "path": "C:\\external"})
    registry_path.write_text(json.dumps(external), encoding="utf-8")

    result = mp.add_root_entry(str(folder), "newproj", [], registry_path)
    assert result["status"] == "conflict"
    assert [r["label"] for r in result["roots"]] == ["external"]  # 최신 디스크 상태
    assert [r["label"] for r in rr.load_roots(registry_path)] == ["external"]  # newproj는 안 써짐


# --------------------------------------------------------- remove_root_entry

def test_remove_root_entry_removes_and_saves(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    roots = [
        {"label": "a", "path": "C:\\a", "referenceCondition": ""},
        {"label": "b", "path": "C:\\b", "referenceCondition": ""},
    ]
    rr.save_roots(roots, registry_path)

    result = mp.remove_root_entry(0, roots, registry_path)
    assert result["status"] == "ok"
    assert result["removed"]["label"] == "a"
    assert [r["label"] for r in result["roots"]] == ["b"]
    assert [r["label"] for r in rr.load_roots(registry_path)] == ["b"]


def test_remove_root_entry_conflict_returns_disk_state(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    roots = [{"label": "a", "path": "C:\\a", "referenceCondition": ""}]
    rr.save_roots(roots, registry_path)  # 기준선 — _last_known_hash 확정

    # "다른 프로세스"가 그 사이 파일을 직접 바꿨다고 시뮬레이션(모듈 함수를
    # 안 거쳐서 _last_known_hash가 이 변경을 모름).
    external = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    external["roots"].append({"label": "external", "path": "C:\\external"})
    registry_path.write_text(json.dumps(external), encoding="utf-8")

    result = mp.remove_root_entry(0, roots, registry_path)
    assert result["status"] == "conflict"
    assert {r["label"] for r in result["roots"]} == {"a", "external"}


# ------------------------------------------------------- sync_formats/confirm_sync_formats

def test_sync_formats_creates_new_file(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    entry = {"label": "a", "path": str(tmp_path)}
    results = mp.sync_formats(tmp_path, entry, registry_path, ["CLAUDE.md"])
    assert results["CLAUDE.md"] == "ok"
    assert (tmp_path / "CLAUDE.md").exists()


def test_sync_formats_needs_confirmation_for_hand_edited_file(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    entry = {"label": "a", "path": str(tmp_path)}
    results = mp.sync_formats(tmp_path, entry, registry_path, ["CLAUDE.md"])
    assert results["CLAUDE.md"] == "needs-confirmation"
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "손으로 쓴 내용"


def test_confirm_sync_formats_overwrites_confirmed_and_skips_declined(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    (tmp_path / "CLAUDE.md").write_text("손편집 A", encoding="utf-8")
    entry = {"label": "a", "path": str(tmp_path)}
    first = mp.sync_formats(tmp_path, entry, registry_path, ["CLAUDE.md"])
    assert first["CLAUDE.md"] == "needs-confirmation"

    merged = mp.confirm_sync_formats(
        tmp_path, entry, registry_path, first, needs_confirm=["CLAUDE.md"], confirmed=["CLAUDE.md"],
    )
    assert merged["CLAUDE.md"] == "ok"
    assert "손편집 A" not in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


def test_confirm_sync_formats_marks_declined_as_skip(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    (tmp_path / "CLAUDE.md").write_text("손편집 A", encoding="utf-8")
    entry = {"label": "a", "path": str(tmp_path)}
    first = mp.sync_formats(tmp_path, entry, registry_path, ["CLAUDE.md"])

    merged = mp.confirm_sync_formats(
        tmp_path, entry, registry_path, first, needs_confirm=["CLAUDE.md"], confirmed=[],
    )
    assert merged["CLAUDE.md"] == "skip"
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "손편집 A"  # 안 건드림
    assert first["CLAUDE.md"] == "needs-confirmation"  # 원본은 안 변형됨


# --------------------------------------------------------- mark_root_reviewed

def test_mark_root_reviewed_updates_last_reviewed(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.save_roots([{"label": "a", "path": "C:\\a", "referenceCondition": "", "lastReviewed": ""}], registry_path)

    result = mp.mark_root_reviewed("a", registry_path)
    assert result["status"] == "ok"
    assert result["reviewedAt"]
    roots = rr.load_roots(registry_path)
    assert roots[0]["lastReviewed"] == result["reviewedAt"]


def test_mark_root_reviewed_not_found(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.save_roots([], registry_path)
    result = mp.mark_root_reviewed("nope", registry_path)
    assert result["status"] == "not_found"


def test_mark_root_reviewed_conflict(tmp_path, monkeypatch):
    """mark_root_reviewed()는 재시도 없이 load→save 한 번뿐이라(add_pending_
    action류의 D-096 재시도와 다름 — roots[]는 사람이 편집하는 배열이라
    재시도가 안 맞는다는 기존 원칙 그대로), save_roots 자체를 스파이로
    바꿔 충돌 분기를 직접 검증한다."""
    registry_path = tmp_path / "ssot-roots.json"
    rr.save_roots([{"label": "a", "path": "C:\\a", "referenceCondition": "", "lastReviewed": ""}], registry_path)

    def _raise_conflict(roots, path):
        raise rr.RegistryConflictError("simulated conflict")

    monkeypatch.setattr(rr, "save_roots", _raise_conflict)
    result = mp.mark_root_reviewed("a", registry_path)
    assert result["status"] == "conflict"
    assert "error" in result


# --------------------------------------------------------- export_all_roots_to_files

def test_export_all_roots_to_files_writes_new_files(tmp_path):
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    entry = {"label": "proj", "path": str(root_dir)}
    result = mp.export_all_roots_to_files([entry])
    assert result["exported"] == ["proj"]
    assert result["skipped"] == []
    assert result["failed"] == []
    assert (root_dir / "CLAUDE.md").exists()


def test_export_all_roots_to_files_skips_hand_edited_claude_md(tmp_path):
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    (root_dir / "CLAUDE.md").write_text("손편집", encoding="utf-8")
    entry = {"label": "proj", "path": str(root_dir)}
    result = mp.export_all_roots_to_files([entry])
    assert result["skipped"] == ["proj"]
    assert result["exported"] == []
    assert (root_dir / "CLAUDE.md").read_text(encoding="utf-8") == "손편집"


# --------------------------------------------------------- set_developer_mode

def test_set_developer_mode_delegates_to_router_proposals(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    mp.set_developer_mode(False, registry_path)
    assert rp.is_developer_mode(registry_path) is False
    mp.set_developer_mode(True, registry_path)
    assert rp.is_developer_mode(registry_path) is True
