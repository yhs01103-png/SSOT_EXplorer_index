import json

import pytest

from plugin_registry_kit.manifest import ManifestError, load_manifests
from plugin_registry_kit.registry import DuplicateRegistrationError, Registry


def _write(path, name, **fields):
    (path / f"{name}.json").write_text(json.dumps({"name": name, **fields}), encoding="utf-8")


def test_loads_every_json_file_in_directory(tmp_path):
    _write(tmp_path, "workout", display_name="Workout Routine", category="free")
    _write(tmp_path, "diet", display_name="Diet Log", category="free")

    r = Registry()
    names = load_manifests(tmp_path, r)

    assert set(names) == {"workout", "diet"}
    assert r.get("workout")["display_name"] == "Workout Routine"
    assert r.get("diet")["category"] == "free"


def test_registration_order_is_sorted_by_filename(tmp_path):
    _write(tmp_path, "zzz_app")
    _write(tmp_path, "aaa_app")

    r = Registry()
    names = load_manifests(tmp_path, r)
    assert names == ["aaa_app", "zzz_app"]


def test_custom_key_field(tmp_path):
    (tmp_path / "one.json").write_text(json.dumps({"app_name": "workout", "tier": "beta"}), encoding="utf-8")

    r = Registry()
    names = load_manifests(tmp_path, r, key_field="app_name")
    assert names == ["workout"]
    assert r.get("workout")["tier"] == "beta"


def test_missing_required_field_raises_with_filename_in_message(tmp_path):
    (tmp_path / "broken.json").write_text(json.dumps({"name": "broken"}), encoding="utf-8")

    r = Registry()
    with pytest.raises(ManifestError, match="broken.json.*schema_file"):
        load_manifests(tmp_path, r, required_fields=["schema_file"])


def test_invalid_json_raises_with_filename(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")

    r = Registry()
    with pytest.raises(ManifestError, match="bad.json"):
        load_manifests(tmp_path, r)


def test_non_object_json_rejected(tmp_path):
    (tmp_path / "array.json").write_text("[1, 2, 3]", encoding="utf-8")

    r = Registry()
    with pytest.raises(ManifestError, match="must be a JSON object"):
        load_manifests(tmp_path, r)


def test_duplicate_key_across_two_manifest_files_raises_naming_both_files(tmp_path):
    _write(tmp_path, "workout", note="first")
    (tmp_path / "workout_dupe.json").write_text(json.dumps({"name": "workout", "note": "second"}), encoding="utf-8")

    r = Registry()  # default on_duplicate="error"
    with pytest.raises(ManifestError) as exc_info:
        load_manifests(tmp_path, r)

    message = str(exc_info.value)
    assert "workout.json" in message  # first file, that registered successfully
    assert "workout_dupe.json" in message  # second file, that collided
    assert isinstance(exc_info.value.__cause__, DuplicateRegistrationError)


def test_duplicate_key_registered_outside_this_call_names_only_current_file(tmp_path):
    _write(tmp_path, "workout", note="from a manifest")

    r = Registry()
    r.register("workout", note="registered in code, not from any manifest file")

    with pytest.raises(ManifestError) as exc_info:
        load_manifests(tmp_path, r)

    message = str(exc_info.value)
    assert "workout.json" in message
    assert "not by any file this load_manifests() call has processed" in message


def test_pattern_filters_which_files_are_loaded(tmp_path):
    _write(tmp_path, "included")
    (tmp_path / "excluded.yaml").write_text("name: excluded", encoding="utf-8")

    r = Registry()
    names = load_manifests(tmp_path, r, pattern="*.json")
    assert names == ["included"]
