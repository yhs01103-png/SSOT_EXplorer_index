# Plugin Registry Kit

The "self-registration" pattern, generalized. It was independently
built twice in the source codebase to solve the same problem: a core
module (a Gemini-calling module, in both cases) needs to know about a
growing set of plugins (tools, or per-app system instructions) without
*importing* any of them -- because the core module importing every
plugin either creates an import cycle, or means every new plugin
requires a core-module edit.

The fix both times was to flip the import direction: each plugin module
registers *itself* into a dict the core module owns, at the moment the
plugin module is first imported. The core module never has an `import
tools.web_search` line anywhere in it.

This kit has two pieces, matching the two shapes that pattern actually
took in the source:

- **`registry.Registry`** — the code-driven half. A plugin module calls
  `registry.register(name, handler=..., **metadata)` at import time.
- **`manifest.load_manifests()`** — the data-driven half. Drop a JSON
  file in a directory instead of writing a Python `register()` call;
  each file becomes one registry entry, with every JSON field kept as
  metadata.

## Install

```bash
pip install -e .
```

## Quick start — code-driven

```python
from plugin_registry_kit import Registry

tools = Registry()  # owned by your core module

# In tools/web_search.py, called at import time:
def _handle(args: dict) -> dict:
    ...
tools.register(
    "web_search",
    handler=_handle,
    description="Search the web",
    parameters_json_schema={"type": "object", "properties": {"query": {"type": "string"}}},
)

# Back in your core module -- no import of tools.web_search anywhere:
tool = tools.get("web_search")
if tool is not None:
    result = tool.handler({"query": "..."})
```

## Quick start — data-driven

```python
from pathlib import Path
from plugin_registry_kit import Registry, load_manifests

apps = Registry()
load_manifests(
    Path("app_registry"),           # a directory of {app}.json files
    apps,
    key_field="app_name",           # each file's `app_name` field becomes its registry key
    required_fields=["display_name", "schema_file"],
)
```

matches dropping a file like this straight into that directory:

```json
{"app_name": "workout", "display_name": "Workout Routine", "schema_file": "..."}
```

## What this fixes relative to the source

Neither original registry (`_SYSTEM_INSTRUCTIONS` in the Hub source,
`_TOOLS` in the Jarvis source) detected a second registration under the
same name -- the second one just silently won. `Registry` raises on
that by default (`on_duplicate="error"`); pass `"warn"` or
`"overwrite"` if you want closer-to-original behavior. `manifest.py`
also names the offending file in every error it raises (missing field,
invalid JSON, wrong top-level type) -- a typo in one manifest file
shouldn't turn into a mystery exception three call frames away from
the file that caused it. A duplicate name across two manifest files
names *both* of them (the one that registered first, the one that
collided) -- `Registry.register()` itself only knows the name, not
which file called it, so `load_manifests()` tracks that locally across
its own call and folds it into the error message.

## What's *not* included

No license-key or activation logic. No framework assumptions (this
isn't tied to Gemini, FastAPI, or any specific plugin *kind* -- both
source uses were LLM-tool registries, but nothing here mentions an LLM).
No dependencies at all.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
