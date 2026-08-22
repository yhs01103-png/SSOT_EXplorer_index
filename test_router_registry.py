"""router_registry.py 전용 테스트 — D-069. load_roots/save_roots 자체의
동작(원자적 쓰기/충돌감지/setdefault 필드보정 등)은 main.py가 위임만 하는
얇은 wrapper를 통해 test_main.py의 기존 테스트들이 이미 폭넓게 검증한다
(isolated_registry 픽스처가 m.REGISTRY_PATH를 갈아끼우는 방식) — 여기서는
`add_root`(D-069 신규, register 커맨드 전용)와, GUI 없이 이 모듈만으로
등록이 실제로 되는지만 추가로 검증한다."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import router_registry as rr


def test_add_root_appends_and_persists(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": "C:\\a"}, registry_path)
    roots = rr.load_roots(registry_path)
    assert [r["label"] for r in roots] == ["a"]


def test_add_root_rejects_duplicate_label(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": "C:\\a"}, registry_path)
    try:
        rr.add_root({"label": "a", "path": "C:\\b"}, registry_path)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "a" in str(e)
    # 실패한 시도가 파일을 더럽히지 않았는지
    assert len(rr.load_roots(registry_path)) == 1


def test_load_roots_no_gui_dependency():
    """이 모듈을 임포트해도 PySide6가 전혀 필요 없다는 걸 증명 — sys.modules
    에 PySide6가 없어도(이 테스트 프로세스엔 있을 수 있지만) router_registry
    자체의 import 구문에 PySide6가 안 걸려있는지가 핵심."""
    import ast

    tree = ast.parse(open("router_registry.py", encoding="utf-8").read())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "PySide6" not in imported_names


def test_different_registry_paths_do_not_share_conflict_state(tmp_path):
    """서로 다른 registry_path는 독립적으로 충돌감지 상태를 추적해야 한다
    (D-069 — main.py 시절엔 프로세스에 레지스트리가 하나뿐이라 문제가 안
    됐지만, CLI는 같은 프로세스에서 여러 레지스트리를 다룰 수 있음)."""
    path_a = tmp_path / "a" / "ssot-roots.json"
    path_b = tmp_path / "b" / "ssot-roots.json"
    rr.save_roots([{"label": "x", "path": "C:\\x"}], path_a)
    # path_b는 한 번도 load/save 안 했으니 last_known_hash가 없어야 하고,
    # 첫 저장은 절대 충돌로 취급되면 안 된다.
    rr.save_roots([{"label": "y", "path": "C:\\y"}], path_b)  # 예외 없어야 함


# ---------------------------------------------- D-041(H-003): 대소문자 중복 방지
# (D-071로 main.py에서 이관 — ssot_mcp_server.py가 PySide6 없이 이 순수
# 함수들을 쓸 수 있어야 했음)

def test_pick_canonical_index_file_prefers_canonical_casing():
    upper = Path("C:\\proj\\CLAUDE.md")
    lower = Path("C:\\proj\\claude.md")
    assert rr.pick_canonical_index_file("claude.md", [lower, upper]) == upper
    assert rr.pick_canonical_index_file("claude.md", [upper, lower]) == upper  # 순서 무관


def test_pick_canonical_index_file_falls_back_to_sorted_name_when_no_canonical():
    a = Path("C:\\proj\\Claude.MD")
    b = Path("C:\\proj\\CLAUDE.MD")
    # 어느 쪽도 CANONICAL_INDEX_NAMES("CLAUDE.md")와 정확히 안 맞음 — 사전순 결정
    assert rr.pick_canonical_index_file("claude.md", [b, a]) == sorted([a, b], key=lambda p: p.name)[0]


def test_find_index_files_single_file_normal_case(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    result = rr.find_index_files(tmp_path)
    assert result["claude.md"] == tmp_path / "CLAUDE.md"
    assert "readme.md" not in result


def test_find_index_files_prefers_flat_over_dot_claude_subdir(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("flat", encoding="utf-8")
    dot_claude = tmp_path / ".claude"
    dot_claude.mkdir()
    (dot_claude / "CLAUDE.md").write_text("nested", encoding="utf-8")
    result = rr.find_index_files(tmp_path)
    assert result["claude.md"] == tmp_path / "CLAUDE.md"


def test_find_index_files_deterministic_on_case_duplicate(tmp_path, monkeypatch):
    """이 환경(Windows)은 대소문자 구분 파일시스템이 아니라 CLAUDE.md/claude.md를
    실제로 동시에 만들 수 없다(그게 바로 H-003의 전제) — iterdir/is_file을 이
    테스트 범위에서만 목업해서, 케이스-센서티브 파일시스템에서 실제로 이 상황이
    발생했을 때의 동작을 회귀 검증한다."""
    upper = tmp_path / "CLAUDE.md"
    lower = tmp_path / "claude.md"

    def fake_iterdir(self):
        if self == tmp_path:
            return iter([lower, upper])  # 일부러 lower를 먼저 — 예전 setdefault 방식이면 lower가 이겼음
        return iter([])

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    monkeypatch.setattr(Path, "is_file", lambda self: self in (upper, lower))
    # 이 분기가 실제 사용자 로그 파일(~/.claude/scripts/ssot_explorer.log)에
    # 쓰지 않게 log.warning 자체를 목업(D-025 기존 테스트와 같은 관례).
    monkeypatch.setattr(rr.log, "warning", lambda *a, **k: None)

    result = rr.find_index_files(tmp_path)
    assert result["claude.md"] == upper


def test_find_index_files_missing_folder_returns_empty(tmp_path):
    assert rr.find_index_files(tmp_path / "no-such-folder") == {}


# ------------------------------------------------------- 라벨 폴더(O-018/D-073)

def test_add_labeled_folder_appends_and_persists(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "a", "path": "C:\\a"}, registry_path)
    folders = rr.load_labeled_folders(registry_path)
    assert [f["label"] for f in folders] == ["a"]
    assert folders[0]["parentLabel"] is None  # setdefault로 채워짐
    assert folders[0]["lastAudited"] == ""


def test_add_labeled_folder_rejects_duplicate_label(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "a", "path": "C:\\a"}, registry_path)
    try:
        rr.add_labeled_folder({"label": "a", "path": "C:\\b"}, registry_path)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "a" in str(e)
    assert len(rr.load_labeled_folders(registry_path)) == 1


def test_save_labeled_folders_preserves_roots_and_other_keys(tmp_path):
    """D-020 유실 버그 재발 방지 — labeledFolders만 갱신해도 roots/
    sharedDocs/relations는 그대로 남아야 한다(save_roots가 반대 방향으로
    labeledFolders를 보존하는 것과 대칭)."""
    registry_path = tmp_path / "ssot-roots.json"
    rr.save_roots([{"label": "root-a", "path": "C:\\root-a"}], registry_path)
    rr.add_labeled_folder({"label": "folder-a", "path": "C:\\folder-a"}, registry_path)
    assert [r["label"] for r in rr.load_roots(registry_path)] == ["root-a"]
    assert [f["label"] for f in rr.load_labeled_folders(registry_path)] == ["folder-a"]


def test_save_roots_preserves_labeled_folders(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "folder-a", "path": "C:\\folder-a"}, registry_path)
    rr.save_roots([{"label": "root-a", "path": "C:\\root-a"}], registry_path)
    assert [f["label"] for f in rr.load_labeled_folders(registry_path)] == ["folder-a"]


def test_mark_labeled_folder_audited_updates_date(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "a", "path": "C:\\a"}, registry_path)
    rr.mark_labeled_folder_audited("a", registry_path, "2026-08-22")
    folders = rr.load_labeled_folders(registry_path)
    assert folders[0]["lastAudited"] == "2026-08-22"


def test_mark_labeled_folder_audited_unknown_label_raises(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    try:
        rr.mark_labeled_folder_audited("no-such-label", registry_path, "2026-08-22")
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "no-such-label" in str(e)


def test_labeled_folder_audit_status_never_audited():
    result = rr.labeled_folder_audit_status({"label": "a", "lastAudited": ""}, date(2026, 8, 22))
    assert result == {"label": "a", "status": "never_audited", "daysRemaining": None}


def test_labeled_folder_audit_status_ok_shows_days_remaining():
    entry = {"label": "a", "lastAudited": "2026-08-10"}
    result = rr.labeled_folder_audit_status(entry, date(2026, 8, 15))  # 5일 경과
    assert result == {"label": "a", "status": "ok", "daysRemaining": 25}


def test_labeled_folder_audit_status_due_when_threshold_exceeded():
    entry = {"label": "a", "lastAudited": "2026-07-01"}
    result = rr.labeled_folder_audit_status(entry, date(2026, 8, 22))  # 52일 경과
    assert result["status"] == "due"
    assert result["daysRemaining"] <= 0


def test_labeled_folder_audit_status_invalid_date_format():
    entry = {"label": "a", "lastAudited": "not-a-date"}
    result = rr.labeled_folder_audit_status(entry, date(2026, 8, 22))
    assert result == {"label": "a", "status": "invalid_last_audited", "daysRemaining": None}


def test_read_ssot_label_marker_finds_marker_near_top(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "<!-- SSOT-LABEL: Sand_Box_Coding_Study -->\n\n# Sand_Box_Coding_Study\n",
        encoding="utf-8",
    )
    assert rr.read_ssot_label_marker(readme) == "Sand_Box_Coding_Study"


def test_read_ssot_label_marker_missing_returns_none(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# 그냥 README\n", encoding="utf-8")
    assert rr.read_ssot_label_marker(readme) is None


def test_read_ssot_label_marker_missing_file_returns_none(tmp_path):
    assert rr.read_ssot_label_marker(tmp_path / "no-such-file.md") is None
