# Snapshot Diff Kit

Versioned directory snapshots (`v1/`, `v2/`, `v3/`, ...) plus a diff
engine that treats a *physically deleted* file (present before, gone
now) as a distinct case from a *content-modified* file (present in
both, bytes differ) -- rather than collapsing both into one generic
"changed" bucket the way most naive recursive diffs do. Generalized
from a local backup-snapshot watcher's core comparison and versioning
step.

## What this is

Two small pieces:

- **`diff_engine`** — `compare_dirs(left, right, ignore_patterns)`
  returns `(physical_deleted, added, content_modified)`: three sorted
  lists of relative paths. `left` is the newer/current side, `right`
  the older/reference side. Comparison is full-content
  (`filecmp.cmp(..., shallow=False)`), not mtime/size heuristics.
  `should_ignore`/`collect_files` are exposed separately for callers
  that want the file-collection step without a full diff.
- **`version_manager`** — `create_snapshot(source_root, snapshot_root,
  folder_name, version_label, ignore_patterns)` copies a directory
  into `snapshot_root/folder_name/version_label/`, replacing that
  version if it exists. `next_version_label_for_project` /
  `latest_version_label_for_project` /
  `latest_version_dir_for_project` manage the `v1`, `v2`, ...
  numbering. `append_commit_log` keeps a plain Markdown log of what
  got snapshotted and when.

## What this is not

Not a file watcher — nothing here polls, listens for filesystem
events, or runs on a schedule. Call `compare_dirs`/`create_snapshot`
whenever your own trigger (a cron job, a button, a CI step) decides
it's time.

Not a backup-restore tool. A physically-deleted file is reported, not
restored — deciding what to do about a deletion (warn, abort, auto-
restore from the last snapshot) is caller policy that the source
watcher had bolted on as an app-specific escalation system (streak-
based severity tiers, a separate mirror-integrity subsystem); none of
that opinionated policy layer is in this kit, only the comparison and
storage primitives it was built on.

Not project-discovery — the source watcher scanned a root directory
for subfolders containing a `project.meta.json` marker file to decide
what to snapshot. That convention is specific to that app's own
workspace layout, so it's left out; pass `folder_name` explicitly for
whatever your own project-discovery logic finds.

## Install

```bash
pip install -e .
```

## Quick start

```python
from pathlib import Path
from snapshot_diff_kit import (
    compare_dirs, create_snapshot,
    latest_version_dir_for_project, latest_version_label_for_project,
    next_version_label_for_project, append_commit_log,
)

source_root = Path("./projects")
snapshot_root = Path("./snapshots")
ignore = [".git", "__pycache__", "*.pyc"]
folder_name = "my_project"

latest_dir = latest_version_dir_for_project(snapshot_root, folder_name)
if latest_dir is None:
    create_snapshot(source_root, snapshot_root, folder_name, "v1", ignore)
else:
    deleted, added, modified = compare_dirs(
        source_root / folder_name, latest_dir, ignore,
    )
    if deleted or added or modified:
        label = next_version_label_for_project(snapshot_root, folder_name)
        create_snapshot(source_root, snapshot_root, folder_name, label, ignore)
        append_commit_log(snapshot_root, [{"name": folder_name, "version": label}])
```

## What's *not* included

No scheduling/watch loop, no restore/rollback action, no severity or
escalation policy for repeated deletions, no project-discovery
convention. No license-key or activation logic.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
