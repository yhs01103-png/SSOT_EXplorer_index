"""Directory-tree diff that distinguishes *physical* deletion (a file
disappeared) from a *content* change (a file at the same path now
differs), instead of collapsing both into one "changed" bucket the way
most naive recursive diffs do.

Generalized from a local backup-snapshot watcher's core comparison
step. The distinction matters because the two cases usually deserve
different handling: a content change is normal churn worth a new
snapshot, while a physical deletion is often worth flagging for review
before anything acts on it (the source app used this to gate an
auto-restore step -- not included here, since *what to do* about a
detected deletion is caller policy, not a diffing concern)."""

from __future__ import annotations

import filecmp
from pathlib import Path
from typing import List, Optional, Set, Tuple


def should_ignore(path: Path, ignore_patterns: List[str]) -> bool:
    """True if `path` matches any pattern: `*.ext` suffix, a literal
    substring of the name, an exact directory-name match, or an exact
    match against any path component (so a pattern like ".git" ignores
    the whole subtree, not just a top-level ".git" entry)."""
    name = path.name
    for pat in ignore_patterns:
        if pat.startswith("*.") and name.endswith(pat[1:]):
            return True
        if pat in name:
            return True
        if path.is_dir() and pat == name:
            return True
    for part in path.parts:
        if part in ignore_patterns:
            return True
    return False


def collect_files(root: Path, ignore_patterns: List[str], prefix: Optional[Path] = None) -> Set[Path]:
    """All files under `root`, as paths relative to `prefix` (default
    `root`), skipping anything `should_ignore` flags."""
    prefix = prefix or root
    out: Set[Path] = set()
    for p in root.rglob("*"):
        if p.is_file() and not should_ignore(p, ignore_patterns):
            try:
                out.add(p.relative_to(prefix))
            except ValueError:
                pass
    return out


def compare_dirs(
    left: Path,
    right: Path,
    ignore_patterns: List[str],
    ignore_for_right: Optional[List[str]] = None,
) -> Tuple[List[Path], List[Path], List[Path]]:
    """Compare two directory trees. `left` is treated as the newer/current
    side, `right` as the older/reference side.

    Returns `(physical_deleted, added, content_modified)`, sorted lists
    of paths relative to each root:
      - physical_deleted = in `right` only  -> present before, gone now
      - added            = in `left` only   -> new since `right`
      - content_modified = in both, bytes differ (full comparison via
        `filecmp.cmp(..., shallow=False)`, not just mtime/size)

    `ignore_for_right`: extra patterns applied only when collecting
    `right`'s files -- useful when `right` is itself a snapshot
    directory that contains generated metadata (e.g. a "readme"
    subfolder written by a previous run) that shouldn't count as a
    tracked file.
    """
    left_files = collect_files(left, ignore_patterns, left)
    right_ignore = list(ignore_patterns)
    if ignore_for_right:
        right_ignore = right_ignore + list(ignore_for_right)
    right_files = collect_files(right, right_ignore, right)

    physical_deleted = sorted(right_files - left_files)
    added = sorted(left_files - right_files)
    common = left_files & right_files

    content_modified = []
    for rel in sorted(common):
        lf, rf = left / rel, right / rel
        if lf.is_file() and rf.is_file() and not filecmp.cmp(lf, rf, shallow=False):
            content_modified.append(rel)

    return physical_deleted, added, content_modified
