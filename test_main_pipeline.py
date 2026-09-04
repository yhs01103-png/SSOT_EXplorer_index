"""main_pipeline.py 전용 테스트 — D-100, O-021 Stage 3(파이프라인 레이어).
Qt 없이 순수 함수 호출로 검증한다(router_registry.py류와 동일 원칙) — GUI
다이얼로그(SaveDocumentDialog 등)가 이 함수들을 올바르게 호출하는지는
test_main.py의 기존 통합 테스트가 계속 커버한다."""
from __future__ import annotations

import pytest

import main_pipeline as mp
import router_proposals as rp


@pytest.fixture(autouse=True)
def isolated_router_proposals(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")


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
