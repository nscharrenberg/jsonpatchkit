# jsonpatchkit

[![CI](https://github.com/nscharrenberg/jsonpatchkit/actions/workflows/ci.yml/badge.svg)](https://github.com/nscharrenberg/jsonpatchkit/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/nscharrenberg/jsonpatchkit/graph/badge.svg)](https://codecov.io/gh/nscharrenberg/jsonpatchkit)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

Granular, schema-safe JSON editing for LLM tool calling.

Instead of asking a model to regenerate an entire JSON document to change
one field, `jsonpatchkit` lets it emit a small [JSON Patch (RFC
6902)](https://www.rfc-editor.org/rfc/rfc6902) against the existing
document. The patch is validated against your Pydantic schema, and if it
doesn't validate, the model retries with the specific error. The model
never has to re-derive a whole object from scratch, and the result can
never violate your schema.

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

## How it works

| Module | Responsibility |
|---|---|
| `pointer.py` | RFC 6901 JSON Pointer resolution — pure stdlib, zero deps |
| `patch.py` | RFC 6902 JSON Patch application, built on `pointer.py` |
| `schema.py` | JSON Schema dict → Pydantic model, via `pydantic.create_model` |
| `validation.py` | Validate a document against a schema, format errors for retry prompts |
| `operations.py` | The `PatchDocument` / `PatchValidationErrors` tool schemas the model calls |
| `extractor.py` | The retry loop tying the above together |
| `adapters/base.py` | `ModelAdapter` protocol — the only thing `extractor.py` depends on |
| `adapters/langchain_adapter.py` | Optional, lazily-imported LangChain implementation of that protocol |

The core (`pointer.py` through `extractor.py`) has one runtime
dependency: `pydantic`. `LangChainAdapter` is opt-in and only imports
`langchain-core` when you instantiate it — a new adapter for a raw
OpenAI or Anthropic client is an addition to the core, not a rewrite
of it.

Supported today: patch-based updates to an existing document, first-time
extraction, multiple documents/schemas in a single call, a
validation-error retry loop, nested objects and arrays (including array
append via `/tags/-`), and schemas passed as Pydantic models or raw JSON
Schema dicts.

## Roadmap

- Raw OpenAI / Anthropic SDK adapters, using the same `ModelAdapter` protocol
- Async `aextract()`
- Streaming of patch ops as they're generated
- A local eval harness

## Contributing

Clone the repo and set up an editable install with the `dev` dependency
group (pytest, ruff, mypy, pytest-cov, plus langchain-core for the
adapter tests). This project uses [PEP 735 dependency
groups](https://peps.python.org/pep-0735/), not a
`project.optional-dependencies` extra, so it needs `pip>=25.1` for the
`--group` flag rather than `pip install -e ".[dev]"`:

```bash
git clone https://github.com/nscharrenberg/jsonpatchkit.git
cd jsonpatchkit
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip        # need >=25.1 for --group support
pip install -e . --group dev
```

### Tests

```bash
pytest                           # whole suite
pytest tests/test_pointer.py     # a single module
pytest -k "test_move"            # tests matching a name pattern
pytest --cov=jsonpatchkit --cov-branch --cov-report=term-missing   # with coverage
```

### Lint, format, type-check

```bash
ruff check .                     # lint
ruff check . --fix               # lint, auto-fixing what's safe
ruff format .                    # format
mypy                              # strict mode, configured in pyproject.toml
```

### Before opening a PR

1. `pytest` passes.
2. `ruff check .` and `mypy` are clean, or new findings are justified in
   the PR description (e.g. a necessary `type: ignore`).
3. New behavior has a test. Bug fixes should include a regression test
   that fails on the old code and passes on the fix.

## Releasing

Versioning is derived from git tags via `hatch-vcs`
(`[tool.hatch.version]` in `pyproject.toml`) — there's no version string
to bump by hand. `src/jsonpatchkit/_version.py` is generated at
build/install time and is gitignored.

```bash
git tag v0.2.0
git push origin v0.2.0
gh release create v0.2.0 --generate-notes
```

Publishing the GitHub Release triggers `.github/workflows/release.yml`,
which builds the package with the version baked in from the tag and
publishes it to PyPI via [trusted publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC — no API token or repo secret required). A manual
`workflow_dispatch` run of the same workflow publishes to TestPyPI
instead, for dry-running a release.

CI (`.github/workflows/ci.yml`) runs ruff, ruff format --check, and mypy
in one job; pytest across Python 3.10–3.13 on Ubuntu, Windows, and macOS
in another (uploading a coverage report to Codecov from the Ubuntu/3.12
run); and a build-verification job (`python -m build` + `twine check`)
on every push and pull request. Dependabot keeps GitHub Actions versions
and dependency floors current.

## License

[MIT](LICENSE)
