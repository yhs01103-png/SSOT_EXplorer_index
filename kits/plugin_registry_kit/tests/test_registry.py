import pytest

from plugin_registry_kit.registry import (
    DuplicateRegistrationError,
    Registry,
)


def test_register_and_get():
    r = Registry()
    r.register("web_search", handler=lambda args: {"success": True}, description="searches the web")
    entry = r.get("web_search")
    assert entry is not None
    assert entry.name == "web_search"
    assert entry["description"] == "searches the web"
    assert entry.handler({}) == {"success": True}


def test_get_missing_returns_none():
    r = Registry()
    assert r.get("nope") is None


def test_contains_and_len_and_names():
    r = Registry()
    r.register("a")
    r.register("b")
    assert "a" in r
    assert "c" not in r
    assert len(r) == 2
    assert set(r.names()) == {"a", "b"}


def test_duplicate_registration_raises_by_default():
    r = Registry()
    r.register("a", handler=None)
    with pytest.raises(DuplicateRegistrationError):
        r.register("a", handler=None)


def test_duplicate_registration_warns_and_keeps_newest():
    r = Registry(on_duplicate="warn")
    r.register("a", note="first")
    with pytest.warns(UserWarning):
        r.register("a", note="second")
    assert r.get("a")["note"] == "second"


def test_duplicate_registration_overwrite_is_silent():
    import warnings

    r = Registry(on_duplicate="overwrite")
    r.register("a", note="first")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here fails the test
        r.register("a", note="second")
    assert r.get("a")["note"] == "second"


def test_validator_can_reject_registration():
    def require_handler_or_client_flag(name, handler, metadata):
        if handler is None and not metadata.get("client_required"):
            raise ValueError(f"tool '{name}': handler-less tools must set client_required=True")

    r = Registry(validator=require_handler_or_client_flag)
    r.register("device_tool", handler=None, client_required=True)  # ok
    with pytest.raises(ValueError, match="client_required"):
        r.register("broken_tool", handler=None)


def test_metadata_getitem_raises_keyerror_for_unknown_field():
    r = Registry()
    r.register("a", description="x")
    with pytest.raises(KeyError):
        r.get("a")["nonexistent_field"]


def test_metadata_get_has_default():
    r = Registry()
    r.register("a", description="x")
    assert r.get("a").get("nonexistent_field", "fallback") == "fallback"


def test_clear_empties_the_registry():
    r = Registry()
    r.register("a")
    r.clear()
    assert len(r) == 0
    assert r.get("a") is None
