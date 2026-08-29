"""Generic self-registration registry -- the "inversion of control" pattern
independently proven twice in the source codebase:

  Hub_APP_Sever/core/gemini_caller.py::register_system_instruction()
    apps/{app}/contracts/stack.py calls this at import time; the core
    Gemini-calling module never imports `apps.*` itself.

  Lazzy_App_OS_Server/core/gemini_caller.py::register_tool()
    tools/*.py calls this at import time; the core module never imports
    `tools.*`. (Comment in that file literally says it copied the shape
    of the Hub version.)

Both call sites share one shape: a module owns a piece of behavior/data,
and registers itself into a dict some other, generic module owns --
instead of that generic module importing every plugin by name (which
either creates an import cycle, or forces the generic module to know
about every plugin that will ever exist). `Registry` here is that shape,
pulled out once instead of hand-rolled a third time.

One real gap closed relative to both sources: neither original dict
(`_SYSTEM_INSTRUCTIONS`, `_TOOLS`) detected a second registration under
the same name -- it just silently overwrote the first. That's a live
footgun the moment two plugin modules pick the same name by accident.
`Registry` defaults to raising on that; see `on_duplicate` if you want
the original silent-overwrite behavior back.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

OnDuplicate = Literal["error", "warn", "overwrite"]


class DuplicateRegistrationError(ValueError):
    """Raised when `on_duplicate="error"` (the default) and a name is
    registered twice."""


@dataclass
class RegisteredEntry:
    """One registered plugin. `handler` is the common case (a tool's
    implementation, in the Jarvis source; absent entirely in the Hub
    source, which only ever registered a string) -- everything else
    domain-specific goes in `metadata` rather than being named fields
    here, so this one class covers both source shapes without a
    subclass per use case."""
    name: str
    handler: Optional[Callable[..., Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        """`entry["description"]` as a shortcut for `entry.metadata["description"]`
        -- matches how the source call sites read registered tools' fields."""
        return self.metadata[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)


class Registry:
    """A named, in-process store of self-registered plugins.

    `on_duplicate` controls what happens when the same name is
    registered twice:
      - "error" (default): raises `DuplicateRegistrationError` immediately
        -- catches the "two plugin modules picked the same name" bug at
        import time instead of at "whichever one happened to import last
        silently wins" time.
      - "warn": `warnings.warn()`, keeps the newest registration (matches
        the source apps' actual historical behavior, minus the silence).
      - "overwrite": exactly the source apps' original behavior -- no
        error, no warning, last registration silently wins.

    `validator`, if given, is called as `validator(name, handler,
    metadata)` on every `register()` call, before it's stored -- raise
    from it to reject a bad registration. This generalizes the one piece
    of domain logic the Jarvis source had inline ("no handler requires
    client_required=True"): that rule doesn't belong in a generic
    registry, but *having a hook for a rule like it* does.
    """

    def __init__(
        self,
        *,
        on_duplicate: OnDuplicate = "error",
        validator: Optional[Callable[[str, Optional[Callable[..., Any]], Dict[str, Any]], None]] = None,
    ) -> None:
        self._entries: Dict[str, RegisteredEntry] = {}
        self._on_duplicate = on_duplicate
        self._validator = validator

    def register(
        self,
        name: str,
        *,
        handler: Optional[Callable[..., Any]] = None,
        **metadata: Any,
    ) -> None:
        if self._validator is not None:
            self._validator(name, handler, metadata)

        if name in self._entries:
            if self._on_duplicate == "error":
                raise DuplicateRegistrationError(
                    f"'{name}' is already registered -- two plugin modules picked "
                    f"the same name. Pass on_duplicate='warn' or 'overwrite' to "
                    f"this Registry if that's intentional."
                )
            if self._on_duplicate == "warn":
                warnings.warn(f"'{name}' re-registered, overwriting the previous entry", stacklevel=2)
            # "overwrite": fall through silently, matching the source apps.

        self._entries[name] = RegisteredEntry(name=name, handler=handler, metadata=metadata)

    def get(self, name: str) -> Optional[RegisteredEntry]:
        return self._entries.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def names(self) -> List[str]:
        return list(self._entries.keys())

    def all(self) -> List[RegisteredEntry]:
        return list(self._entries.values())

    def clear(self) -> None:
        """Mainly for tests -- a real app registers its plugins once at
        import time and never needs this."""
        self._entries.clear()
