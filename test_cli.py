"""cli.py 전용 테스트 — D-070. `ssot` 커맨드의 서브커맨드 5개(classify/
sync/register/init/list)를 실제 함수 호출로 검증한다(subprocess로 매번
새 파이썬 프로세스를 띄우는 대신 `cli.main([...])`을 직접 호출 — 더 빠르고,
router_orchestrator.embed_query_text 같은 무거운 경로를 몽키패치하기도
쉽다).

`classify --full`이 실제로 임베딩 모델을 돈다면 이 테스트 스위트가 콜드
캐시 환경에서 몇 분+네트워크가 걸릴 수 있다(D-070 스모크테스트 중 실측한
문제 그 자체) — 그래서 여기서는 `router_orchestrator.orchestrate`/
`router_classifier.classify_content`를 스파이로 바꿔 "어느 경로로
갔는지"만 확인하고, 그 함수들 자체의 정확성은 test_router_orchestrator.py/
test_router_classifier.py가 이미 검증한다."""
from __future__ import annotations

import json

import pytest

import cli
import router_classifier
import router_orchestrator
import router_registry
import router_sync


def _registry(tmp_path):
    return tmp_path / "ssot-roots.json"


@pytest.fixture(autouse=True)
def isolated_folder_snapshot(tmp_path, monkeypatch):
    """2026-09-04 — `ssot register`(cli._cmd_register)도 이제 router_registry.
    save_folder_snapshot()을 호출한다(D-0XX). 실제 사용자 파일(~/.claude/
    scripts/ssot_folder_snapshots.json)을 절대 안 건드리게 격리."""
    monkeypatch.setattr(router_registry, "FOLDER_SNAPSHOT_PATH", tmp_path / "folder-snapshots.json")


# ---------------------------------------------------------- console encoding

def test_fix_windows_console_encoding_tolerates_stream_without_reconfigure(monkeypatch):
    """D-070 실측 버그: Windows 기본 콘솔(cp949)에서 `ssot --help`가
    UnicodeEncodeError로 죽던 걸 재현·수정했다 — 이 테스트는 reconfigure가
    아예 없는 스트림(io.StringIO 등)이어도 예외 없이 넘어가는지만 확인한다
    (실제 인코딩 전환 자체는 표준 스트림에서만 의미 있어 여기선 검증 대상이
    아님)."""
    import io

    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    cli._fix_windows_console_encoding()  # must not raise


def test_classify_help_does_not_crash_on_encoding(capsys):
    """옛 버그 재현 — 예전엔 이 호출 자체가 UnicodeEncodeError였다."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])
    assert exc_info.value.code == 0


# --------------------------------------------------------------------- classify

def test_classify_default_uses_fast_path_not_orchestrator(tmp_path, monkeypatch, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path), "referenceCondition": "보안 정책"}, registry)

    called_orchestrate = []
    monkeypatch.setattr(router_orchestrator, "orchestrate", lambda *a, **k: called_orchestrate.append(1))

    cli.main(["classify", "보안 정책 문서", "--registry", str(registry)])

    assert called_orchestrate == []  # 무거운 경로가 절대 호출되면 안 됨
    out = capsys.readouterr().out
    assert "a" in out


def test_classify_full_uses_orchestrator(tmp_path, monkeypatch, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path)}, registry)

    called_fast = []
    monkeypatch.setattr(router_classifier, "classify_content", lambda *a, **k: called_fast.append(1) or [])
    monkeypatch.setattr(
        router_orchestrator, "orchestrate",
        lambda text, roots, **k: {"candidates": [], "needsClarification": False, "steps": []},
    )

    cli.main(["classify", "아무 내용", "--full", "--registry", str(registry)])

    assert called_fast == []  # --full이면 1단계 경로를 아예 안 씀


def test_classify_json_output_is_valid_json(tmp_path, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path), "referenceCondition": "보안 정책"}, registry)
    cli.main(["classify", "보안 정책", "--registry", str(registry), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["rootLabel"] == "a"


def test_classify_reads_stdin_when_text_is_dash(tmp_path, monkeypatch, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path), "referenceCondition": "보안 정책"}, registry)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("보안 정책 문서"))
    cli.main(["classify", "-", "--registry", str(registry), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["rootLabel"] == "a"


def test_classify_no_match_reports_empty(tmp_path, capsys):
    registry = _registry(tmp_path)
    cli.main(["classify", "아무 관련 없는 텍스트", "--registry", str(registry)])
    assert "없음" in capsys.readouterr().out


# -------------------------------------------------------------------- register

def test_register_creates_entry(tmp_path, capsys):
    registry = _registry(tmp_path)
    exit_code = cli.main(["register", str(tmp_path), "--label", "a", "--registry", str(registry)])
    assert exit_code == 0
    roots = router_registry.load_roots(registry)
    assert roots[0]["label"] == "a"
    assert "a" in capsys.readouterr().out


def test_register_duplicate_label_fails(tmp_path, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path)}, registry)
    exit_code = cli.main(["register", str(tmp_path), "--label", "a", "--registry", str(registry)])
    assert exit_code == 1


def test_register_stores_condition(tmp_path):
    registry = _registry(tmp_path)
    cli.main(["register", str(tmp_path), "--label", "a", "--condition", "테스트 조건", "--registry", str(registry)])
    roots = router_registry.load_roots(registry)
    assert roots[0]["referenceCondition"] == "테스트 조건"


# ------------------------------------------------------------------------ list

def test_list_empty_registry(tmp_path, capsys):
    registry = _registry(tmp_path)
    cli.main(["list", "--registry", str(registry)])
    assert "없음" in capsys.readouterr().out


def test_list_shows_registered_roots(tmp_path, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path)}, registry)
    cli.main(["list", "--registry", str(registry)])
    assert "a" in capsys.readouterr().out


def test_list_json(tmp_path, capsys):
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "a", "path": str(tmp_path)}, registry)
    cli.main(["list", "--registry", str(registry), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["label"] == "a"


# ------------------------------------------------------------------------ init

def test_init_excludes_already_registered(tmp_path, capsys):
    (tmp_path / "registered_proj").mkdir()
    (tmp_path / "new_proj").mkdir()
    registry = _registry(tmp_path)
    router_registry.add_root({"label": "x", "path": str(tmp_path / "registered_proj")}, registry)

    cli.main(["init", str(tmp_path), "--registry", str(registry)])
    out = capsys.readouterr().out
    assert "new_proj" in out
    assert "registered_proj" not in out


def test_init_excludes_noise_directories(tmp_path, capsys):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "real_proj").mkdir()
    registry = _registry(tmp_path)

    cli.main(["init", str(tmp_path), "--registry", str(registry)])
    out = capsys.readouterr().out
    assert "real_proj" in out
    assert "node_modules" not in out
    assert ".git" not in out


def test_init_json_output(tmp_path, capsys):
    (tmp_path / "proj").mkdir()
    registry = _registry(tmp_path)
    cli.main(["init", str(tmp_path), "--registry", str(registry), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert any("proj" in p for p in payload)


# ------------------------------------------------------------------------ sync

def test_sync_unknown_label_returns_1(tmp_path, capsys):
    registry = _registry(tmp_path)
    exit_code = cli.main(["sync", "nope", "--registry", str(registry)])
    assert exit_code == 1


def test_sync_writes_files_for_new_root(tmp_path):
    registry = _registry(tmp_path)
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    router_registry.add_root({"label": "a", "path": str(root_dir)}, registry)

    exit_code = cli.main(["sync", "a", "--formats", "CLAUDE.md", "--registry", str(registry)])

    assert exit_code == 0
    assert (root_dir / "CLAUDE.md").exists()
    assert router_sync.SYNC_MARKER in (root_dir / "CLAUDE.md").read_text(encoding="utf-8")


def test_sync_needs_confirmation_skipped_when_not_interactive(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    (root_dir / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    router_registry.add_root({"label": "a", "path": str(root_dir)}, registry)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    cli.main(["sync", "a", "--formats", "CLAUDE.md", "--registry", str(registry)])

    assert (root_dir / "CLAUDE.md").read_text(encoding="utf-8") == "손으로 쓴 내용"


def test_sync_yes_flag_confirms_hand_edited_file(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    (root_dir / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    router_registry.add_root({"label": "a", "path": str(root_dir)}, registry)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    cli.main(["sync", "a", "--formats", "CLAUDE.md", "--yes", "--registry", str(registry)])

    assert router_sync.SYNC_MARKER in (root_dir / "CLAUDE.md").read_text(encoding="utf-8")


def test_sync_force_flag_skips_confirmation_prompt_entirely(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    root_dir = tmp_path / "proj"
    root_dir.mkdir()
    (root_dir / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    router_registry.add_root({"label": "a", "path": str(root_dir)}, registry)

    def _explode(*a, **k):
        raise AssertionError("force=True인데 input()이 호출됨")

    monkeypatch.setattr("builtins.input", _explode)
    exit_code = cli.main(["sync", "a", "--formats", "CLAUDE.md", "--force", "--registry", str(registry)])

    assert exit_code == 0
    assert router_sync.SYNC_MARKER in (root_dir / "CLAUDE.md").read_text(encoding="utf-8")
