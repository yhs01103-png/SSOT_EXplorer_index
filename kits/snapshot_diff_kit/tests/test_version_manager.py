from pathlib import Path

from snapshot_diff_kit import (
    append_commit_log,
    create_snapshot,
    latest_version_dir_for_project,
    latest_version_label_for_project,
    next_version_label_for_project,
)


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_next_version_label_starts_at_v1(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    assert next_version_label_for_project(snapshot_root, "proj") == "v1"


def test_next_version_label_increments_past_existing(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    (snapshot_root / "proj" / "v1").mkdir(parents=True)
    (snapshot_root / "proj" / "v2").mkdir(parents=True)

    assert next_version_label_for_project(snapshot_root, "proj") == "v3"


def test_latest_version_label_and_dir_none_when_no_versions(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    assert latest_version_label_for_project(snapshot_root, "proj") is None
    assert latest_version_dir_for_project(snapshot_root, "proj") is None


def test_create_snapshot_copies_source_and_writes_guard_marker(tmp_path):
    source_root = tmp_path / "source"
    snapshot_root = tmp_path / "snapshots"
    _write(source_root, "proj/a.txt", "hello")

    dest = create_snapshot(source_root, snapshot_root, "proj", "v1", ignore_patterns=[])

    assert dest == snapshot_root / "proj" / "v1"
    assert (dest / "a.txt").read_text(encoding="utf-8") == "hello"
    assert (snapshot_root / "proj" / "DO_NOT_EDIT.txt").exists()


def test_create_snapshot_replaces_existing_version_dir(tmp_path):
    source_root = tmp_path / "source"
    snapshot_root = tmp_path / "snapshots"
    _write(source_root, "proj/a.txt", "first")
    create_snapshot(source_root, snapshot_root, "proj", "v1", ignore_patterns=[])

    _write(source_root, "proj/a.txt", "second")
    _write(source_root, "proj/stale.txt", "should not survive replacement")
    (snapshot_root / "proj" / "v1" / "stale.txt").write_text("old snapshot only", encoding="utf-8")
    dest = create_snapshot(source_root, snapshot_root, "proj", "v1", ignore_patterns=[])

    assert (dest / "a.txt").read_text(encoding="utf-8") == "second"


def test_create_snapshot_raises_when_source_missing(tmp_path):
    source_root = tmp_path / "source"
    snapshot_root = tmp_path / "snapshots"
    source_root.mkdir()

    try:
        create_snapshot(source_root, snapshot_root, "missing_proj", "v1", ignore_patterns=[])
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_append_commit_log_writes_header_once(tmp_path):
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()

    append_commit_log(snapshot_root, [{"name": "proj", "version": "v1"}], trigger="MANUAL")
    append_commit_log(snapshot_root, [{"name": "proj", "version": "v2"}], trigger="AUTO")

    text = (snapshot_root / "COMMIT_LOG.md").read_text(encoding="utf-8")
    assert text.count("# COMMIT LOG") == 1
    assert "proj -> v1" in text
    assert "proj -> v2" in text
