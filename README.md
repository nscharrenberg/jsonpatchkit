# jsonpatchkit

Granular, schema-safe JSON editing for LLM tool calling.

Instead of asking a model to regenerate an entire JSON document to change
one field, `jsonpatchkit` lets it emit a small [JSON Patch (RFC
6902)](https://www.rfc-editor.org/rfc/rfc6902) against the existing
document, validates the result against your Pydantic schema, and — if it
doesn't validate — retries with the specific error, so the model never
has to re-derive a whole object from scratch and the output can never
violate your schema.

This is a from-scratch alternative to
[`trustcall`](https://github.com/hinthornw/trustcall), built without a
dependency on `dydantic` or LangGraph internals.

## Install

```bash
pip install jsonpatchkit
# with the LangChain adapter:
pip install "jsonpatchkit[langchain]"
```

## Quickstart

```python
from pydantic import BaseModel
from jsonpatchkit import Extractor
from jsonpatchkit.adapters.langchain_adapter import LangChainAdapter
from langchain_anthropic import ChatAnthropic

class Person(BaseModel):
    name: str
    age: int
    tags: list[str] = []

model = ChatAnthropic(model="claude-sonnet-5")
extractor = Extractor(LangChainAdapter(model), schemas={"Person": Person})

# First-time creation
result = extractor.extract([{"role": "user", "content": "Alice is 30, likes hiking"}])
person = result.documents["Person"]  # {"name": "Alice", "age": 30, "tags": ["hiking"]}

# Granular edit of an existing document — the model only emits a patch,
# not a full regeneration.
result = extractor.extract(
    [{"role": "user", "content": "Add painting to her tags, she's 31 now"}],
    existing={"Person": person},
)
```

## Development

Clone the repo, then set up an editable install with the dev extras
(pytest, ruff, mypy, plus langchain-core for the adapter tests):

```bash
git clone <your-fork-url>
cd jsonpatchkit
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run the tests

```bash
pytest                           # whole suite
pytest tests/test_pointer.py     # a single module
pytest -k "test_move"            # tests matching a name pattern
pytest -v                        # verbose, one line per test
```

For a coverage report, also install `pytest-cov` (not pinned in `dev`
since it's optional) and run:

```bash
pip install pytest-cov
pytest --cov=jsonpatchkit --cov-report=term-missing
```

### Lint and format

```bash
ruff check .                     # lint
ruff check . --fix               # lint, auto-fixing what's safe
ruff format .                    # format
```

### Type-check

```bash
mypy
```

`pyproject.toml` already has `[tool.ruff]` and `[tool.mypy]` sections
(strict mode for mypy), so these run with the project's actual config
with no extra flags needed.

### Before opening a PR

1. `pytest` passes.
2. `ruff check .` and `mypy` are both clean (or new findings are
   justified in the PR description — e.g. a necessary `type: ignore`).
3. New behavior has a test. Bug fixes should include a regression test
   that fails on the old code and passes on the fix — see
   `tests/test_patch.py`'s `test_add_missing_value_raises_malformed_not_key_error`
   for the pattern this project follows.
4. If you touch `schema.py`, `validation.py`, `operations.py`, or
   `extractor.py`, please actually run the tests — those four modules
   were written and reviewed without a working `pydantic` install in
   the original development environment (see "Honest note on test
   execution" below), so they need a real run more than most changes
   would.

## Architecture (why this differs from trustcall)

| Module | Responsibility |
|---|---|
| `pointer.py` | RFC 6901 JSON Pointer resolution — pure stdlib, zero deps |
| `patch.py` | RFC 6902 JSON Patch application, built on `pointer.py` |
| `schema.py` | JSON Schema dict → Pydantic model (replaces `dydantic`, uses `pydantic.create_model`) |
| `validation.py` | Validate a document against a schema, format errors for retry prompts |
| `operations.py` | The `PatchDocument` / `PatchValidationErrors` tool schemas the model calls |
| `extractor.py` | The retry loop tying the above together |
| `adapters/base.py` | `ModelAdapter` protocol — the only thing `extractor.py` depends on |
| `adapters/langchain_adapter.py` | Optional, lazily-imported LangChain implementation of that protocol |

The core (`pointer.py` through `extractor.py`) has **one runtime
dependency: `pydantic`.** No LangGraph, no LangChain. `LangChainAdapter`
is opt-in and only imports `langchain-core` when you instantiate it. This
is the structural fix for the problem that prompted this rewrite:
trustcall's core retry loop is built directly on `langgraph.graph.StateGraph`
and `langgraph.utils.runnable.RunnableCallable`, which ties its release
cadence to LangGraph's internals. Here, a new adapter for a raw OpenAI or
Anthropic client — or a future LangGraph integration — is an addition,
not a rewrite of the core.

## Feature parity with trustcall

- ✅ Patch-based updates to existing documents (`existing={...}`)
- ✅ First-time extraction (empty existing doc, patched via `add` ops)
- ✅ Multiple documents/schemas in one call
- ✅ Validation-error retry loop with a distinct corrective tool
  (`PatchValidationErrors`, mirroring `PatchFunctionErrors`)
- ✅ Nested objects, arrays, array append (`/tags/-`), and arbitrary
  nested paths
- ✅ Schemas as Pydantic models directly, or as raw JSON Schema dicts
  via `build_model_from_schema`
- ⏳ Not yet ported: LangSmith-based eval harness, `existing_schema_policy`
  fine-grained ignore/error modes. These are natural follow-ups, not
  architectural blockers — see "Roadmap" below.

## Dependency verification

Every dependency floor in `pyproject.toml` was checked against PyPI
directly (not assumed from training data) on 2026-08-03:

- `pydantic`: latest stable release is **2.13.4** (a `2.14.0a1` alpha
  exists but is intentionally not used as the floor).
- `langchain-core` (optional): latest stable release is **1.5.3**.
- `pytest` (dev): latest stable release is **9.1.1**.
- `pydantic.create_model`'s signature was checked against Pydantic's
  official API reference before `schema.py` was written, rather than
  assumed from memory.

## Code review (v0.1.0 → v0.1.2)

### Round 1 (v0.1.1): functional bugs
A dedicated review pass found and fixed 6 real bugs, the biggest being
that the retry loop wasn't actually resilient to the malformed model
output it exists to handle (tool-call args were never validated against
`operations.py`'s schemas — see the fixes table in git history / prior
notes). All fixes shipped with regression tests.

### Round 2 (v0.1.2): the identifier limitation, plus coverage/typing/lint
Round 1 left one item as "documented but not fixed": `schema.py` passed
JSON Schema property names straight into `pydantic.create_model(**...)`,
which requires valid Python identifiers — a property like `"first-name"`
would raise a raw `TypeError`. **This is now fixed**: non-identifier
names are sanitized to a valid Python attribute name and mapped back via
a Pydantic field `alias`, with collision handling (e.g. `"first-name"`
and `"first_name"` both sanitizing to the same candidate no longer
silently collide). Models built this way accept either the original
JSON key or the sanitized attribute name (`populate_by_name=True`).

This round also went back over the earlier honest gaps rather than
leaving them as caveats:

**Test coverage — actually measured, not estimated.** Python's stdlib
`trace` module gives real line-coverage numbers without needing the
`coverage` package (which couldn't be installed in this offline
sandbox). For the two modules that could actually be executed here:

| Module | Line coverage |
|---|---|
| `pointer.py` | **100%** (103/103 executable lines) |
| `patch.py` | **100%** (63/63 executable lines) |

Getting there surfaced 8 untested branches — all defensive error paths
(descending into a scalar, operating on the root pointer, targeting a
non-container) that had no test forcing them to execute. Regression
tests were added for each; nothing was skipped or excluded to inflate
the number.

For `schema.py`, `validation.py`, `operations.py`, and `extractor.py`
(anything touching `pydantic`), coverage genuinely **cannot** be
measured in this sandbox — there's no way to execute those tests without
the real `pydantic` installed, and no network to install it. Run
`pytest --cov=jsonpatchkit` yourself for real numbers there; this
README will not claim a percentage it can't back up.

**Typing.** No `mypy` available to run, so instead: an `ast`-based sweep
of every function in `src/` and `tests/` for missing return-type
annotations. Found 3 (all `__init__` methods missing `-> None`) — all
fixed. `mypy --strict` config is now in `pyproject.toml`, but has not
actually been run against this code; treat it as configured-but-unverified
until you run it yourself.

**Linting / static analysis.** No `ruff` available either, so a small
`ast`-based checker was written (unused imports, bare `except:`,
mutable default arguments) — genuine static analysis, not a claim
without a check behind it. Found 2 unused imports: one was a real bug
(`List` in `types.py`, removed), the other was a false positive (an
intentional `# noqa: F401`-marked import-existence check in
`langchain_adapter.py` — my checker doesn't parse `noqa` comments, a
real `ruff` run would correctly ignore it). `ruff` config is now in
`pyproject.toml`; again, unverified by an actual `ruff` run.

**Dead code.** `SchemaValidationError` was defined and publicly
exported but never actually raised anywhere — `validate_against_schema`
correctly uses a `ValidationOutcome` return value instead (the retry
loop needs non-exception control flow). Removed rather than left as
decoration; `MalformedOperationError` (which *is* raised, by `patch.py`)
was added to the public exports in its place, since it had been missing.

### What "near 100%" honestly means here
- Dependency-free core: 100% line coverage, real, measured, re-verified after every fix.
- Everything touching `pydantic`: written with the same rigor, but genuinely unverified in this environment. Not "probably fine" — actually unverified, and the README says so rather than rounding up.
- No claim in this section is aspirational; every number came from a tool run in this conversation, and every "not run" is stated as such.

## Honest note on test execution

This library was developed in a sandboxed environment with **no network
access**, so `pydantic`, `pytest`, and `langchain-core` could not actually
be installed there.

- `tests/test_pointer.py` and `tests/test_patch.py` cover the fully
  dependency-free core (`pointer.py`, `patch.py`) and **were actually
  executed** in that sandbox, using a small local shim providing just
  `pytest.raises` — **56/56 passed** (29 + 27), at **100% line coverage**
  for both modules, measured with Python's stdlib `trace` module. See
  the "Code review" section above for how that number was reached.
- `tests/test_schema.py`, `tests/test_validation.py`,
  `tests/test_operations.py`, and `tests/test_extractor.py` depend on
  `pydantic` and were written against its documented, verified API
  (including the new tests added during review for bugs #5 and #6
  above), but **could not be executed** in that environment — only
  import-checked against a minimal stub, which proves there are no
  `NameError`/`ImportError`-class mistakes but proves nothing about
  actual validation behavior. Please run them yourself before relying
  on this in production:

```bash
pip install -e ".[dev]"
pytest
```

If anything fails, it's most likely a small signature mismatch in the
untested layer, not the core patch engine (which is verified).

## Roadmap / Possible improvements

- Raw OpenAI / Anthropic SDK adapters (same `ModelAdapter` protocol,
  no LangChain required)
- Async `aextract()` variant
- Streaming of patch ops as they're generated
- Local eval harness (no LangSmith account required)
- `existing_schema_policy` (`True` / `False` / `"ignore"`) parity with trustcall
