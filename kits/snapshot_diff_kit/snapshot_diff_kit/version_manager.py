"""Versioned snapshot storage: `copytree` a source directory into
`snapshot_root/<name>/v1/`, `v2/`, ... and keep an append-only Markdown
commit log alongside it.

Generalized from the same backup-snapshot watcher as `diff_engine`.
Versioning is plain incrementing-integer folders rather than content
hashing, on the theory that a human occasionally needs to browse
`v1/`, `v2/`, `v3/` directly in a file explorer and reason about order
at a glance -- a hash-named snapshot store is more compact but loses
that."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .diff_engine import should_ignore


def _ignore_fn(ignore_patterns: List[str]):
    def fn(d: str, names: List[str]) -> List[str]:
        return [n for n in names if should_ignore(Path(d) / n, ignore_patterns)]
    return fn


def next_version_label_for_project(snapshot_root: Path, folder_name: str) -> str:
    """Next `vN` label for this project -- `v1` if none exist yet."""
    proj_dir = snapshot_root / folder_name
    if not proj_dir.exists():
        return "v1"
    existing = [
        int(p.name[1:])
        for p in proj_dir.iterdir()
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
    ]
    return f"v{max(existing, default=0) + 1}"


def latest_version_label_for_project(snapshot_root: Path, folder_name: str) -> Optional[str]:
    proj_dir = snapshot_root / folder_name
    if not proj_dir.exists():
        return None
    existing = [
        p for p in proj_dir.iterdir()
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
    ]
    if not existing:
        return None
    return max(existing, key=lambda p: int(p.name[1:])).name


def latest_version_dir_for_project(snapshot_root: Path, folder_name: str) -> Optional[Path]:
    label = latest_version_label_for_project(snapshot_root, folder_name)
    if label is None:
        return None
    return snapshot_root / folder_name / label


def create_snapshot(
    source_root: Path,
    snapshot_root: Path,
    folder_name: str,
    version_label: str,
    ignore_patterns: List[str],
) -> Path:
    """Copy `source_root/folder_name` into
    `snapshot_root/folder_name/version_label`, replacing that version
    directory if it already exists. Drops a `DO_NOT_EDIT.txt` marker
    once per project so a human browsing the snapshot store on disk
    doesn't mistake it for a working copy."""
    src = source_root / folder_name
    dest_dir = snapshot_root / folder_name / version_label

    if not src.is_dir():
        raise FileNotFoundError(f"source project not found: {src}")

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    shutil.copytree(src, dest_dir, ignore=_ignore_fn(ignore_patterns))

    guard = snapshot_root / folder_name / "DO_NOT_EDIT.txt"
    if not guard.exists():
        guard.write_text(
            "This folder is a snapshot store. Do not edit files here directly.\n",
            encoding="utf-8",
        )
    return dest_dir


def append_commit_log(
    snapshot_root: Path,
    committed: List[Dict[str, str]],
    trigger: str = "MANUAL",
) -> None:
    """Append one entry to `snapshot_root/COMMIT_LOG.md`, writing the
    header first if the file doesn't exist yet. `committed` is a list
    of `{"name": ..., "version": ...}` dicts."""
    log_file = snapshot_root / "COMMIT_LOG.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    header = ""
    if not log_file.exists():
        header = "# COMMIT LOG\n\n> One entry per snapshot run.\n\n---\n\n"

    entry = f"### [{ts}] trigger={trigger}\n"
    for item in committed:
        entry += f"- {item['name']} -> {item['version']}\n"
    entry += "\n"

    with open(log_file, "a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)
