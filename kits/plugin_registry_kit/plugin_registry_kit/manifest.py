"""Declarative counterpart to `registry.Registry` -- generalized from
Hub_APP_Sever/app_registry/*.json, where adding a new app meant dropping
in one JSON file (app_name/display_name/category/tier_required/
rules_file/schema_file/resources) with zero core code changes.

That pattern is the data-driven twin of `registry.py`'s code-driven one:
instead of a Python module calling `registry.register(...)` at import
time, a JSON file sitting in a directory *is* the registration, and
`load_manifests()` is the one piece of code that turns "a file exists"
into "an entry exists in the registry".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from plugin_registry_kit.registry import DuplicateRegistrationError, Registry


class ManifestError(ValueError):
    """A manifest file was malformed, missing a required field, or
    declared a name some other manifest file already claimed -- always
    includes the offending file's path (and, for a duplicate name, the
    other file's path too, when `load_manifests` itself loaded that
    other file) in the message, so a typo or a copy-pasted manifest
    doesn't turn into a mystery `KeyError`/`DuplicateRegistrationError`
    three layers away from where the file was actually loaded."""


def load_manifests(
    directory: Path,
    registry: Registry,
    *,
    key_field: str = "name",
    required_fields: Optional[List[str]] = None,
    pattern: str = "*.json",
) -> List[str]:
    """Load every `pattern`-matching file in `directory` (non-recursive)
    as a JSON object, and `registry.register()` it -- keyed by
    `data[key_field]`. Every other field is kept in the entry's metadata;
    `key_field` itself is not duplicated there (it's already `entry.name`).

    Files are processed in sorted filename order, so registration order
    (and therefore duplicate-detection error messages, if `registry` is
    on_duplicate="error") is reproducible across runs and machines.

    A duplicate name raises `ManifestError` naming *both* the file
    currently being loaded and the file that registered that name first
    (tracked locally across this one `load_manifests` call) -- not just
    "duplicate name", which leaves you grepping the whole directory by
    hand to find the other offender. If the name was already registered
    by something outside this call (a previous `load_manifests` run
    against a different directory, or a code-driven `registry.register()`
    call), the first file is unknown and the message says so explicitly
    instead of guessing.

    Returns the list of names registered.
    """
    required = required_fields or []
    names: List[str] = []
    registered_by: Dict[str, Path] = {}

    for path in sorted(directory.glob(pattern)):
        data = _load_one(path)

        missing = [f for f in (required + [key_field]) if f not in data]
        if missing:
            raise ManifestError(f"{path}: missing required field(s): {', '.join(missing)}")

        name = data[key_field]
        # Strip key_field itself before spreading into register(**metadata) --
        # not just tidiness: register()'s first positional parameter is
        # named `name`, so when key_field=="name" (the default), leaving
        # it in would collide with that positional arg via **data.
        metadata = {k: v for k, v in data.items() if k != key_field}
        try:
            registry.register(name, **metadata)
        except DuplicateRegistrationError as e:
            first_path = registered_by.get(name)
            if first_path is not None:
                raise ManifestError(
                    f"{path}: cannot register '{name}' -- already registered by "
                    f"{first_path}. Rename or remove one of these manifest files."
                ) from e
            raise ManifestError(
                f"{path}: cannot register '{name}' -- already registered, but not "
                f"by any file this load_manifests() call has processed. Check other "
                f"manifest directories or code-driven registrations for the name '{name}'."
            ) from e

        registered_by[name] = path
        names.append(name)

    return names


def _load_one(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(f"{path}: couldn't read file ({e})") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ManifestError(f"{path}: invalid JSON ({e})") from e
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest must be a JSON object, got {type(data).__name__}")
    return data
