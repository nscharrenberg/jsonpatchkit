"""Tests for jsonpatchkit.extractor.Extractor.

Uses ScriptedAdapter (tests/fakes.py) so the retry loop is tested
deterministically without any real LLM call. Requires pydantic to run.
"""

import pytest
from pydantic import BaseModel

from jsonpatchkit.exceptions import ExtractionRetriesExhaustedError
from jsonpatchkit.extractor import Extractor
from jsonpatchkit.operations import PatchDocument, PatchValidationErrors
from jsonpatchkit.types import ToolCall
from tests.fakes import ScriptedAdapter


class Person(BaseModel):
    name: str
    age: int


def test_first_time_creation_via_add_operations():
    adapter = ScriptedAdapter(
        [
            [
                ToolCall(
                    name=PatchDocument.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [
                            {"op": "add", "path": "/name", "value": "Alice"},
                            {"op": "add", "path": "/age", "value": 30},
                        ],
                    },
                )
            ]
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person})
    result = extractor.extract([{"role": "user", "content": "Alice is 30"}])
    assert result.documents["Person"] == {"name": "Alice", "age": 30}
    assert result.retries_used == 0


def test_granular_edit_of_existing_document():
    adapter = ScriptedAdapter(
        [
            [
                ToolCall(
                    name=PatchDocument.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [{"op": "replace", "path": "/age", "value": 31}],
                    },
                )
            ]
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person})
    result = extractor.extract(
        [{"role": "user", "content": "She just turned 31"}],
        existing={"Person": {"name": "Alice", "age": 30}},
    )
    assert result.documents["Person"] == {"name": "Alice", "age": 31}


def test_retries_on_validation_error_then_succeeds():
    adapter = ScriptedAdapter(
        [
            # first attempt: invalid type for age
            [
                ToolCall(
                    name=PatchDocument.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [
                            {"op": "add", "path": "/name", "value": "Alice"},
                            {"op": "add", "path": "/age", "value": "thirty"},
                        ],
                    },
                )
            ],
            # correction: fixes the type
            [
                ToolCall(
                    name=PatchValidationErrors.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [{"op": "replace", "path": "/age", "value": 30}],
                    },
                )
            ],
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=2)
    result = extractor.extract([{"role": "user", "content": "Alice is 30"}])
    assert result.documents["Person"] == {"name": "Alice", "age": 30}
    assert result.retries_used == 1


def test_gives_up_after_max_retries():
    bad_call = [
        ToolCall(
            name=PatchDocument.__name__,
            args={"json_doc_id": "Person", "patches": [{"op": "add", "path": "/name", "value": "Alice"}]},
        )
    ]
    # Every attempt is still missing the required "age" field.
    adapter = ScriptedAdapter([bad_call, bad_call, bad_call])
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=1)
    with pytest.raises(ExtractionRetriesExhaustedError):
        extractor.extract([{"role": "user", "content": "Alice"}])


def test_malformed_tool_args_are_retried_not_raised():
    """Regression test: an invalid `op` value inside `patches` must be
    caught by PatchDocument.model_validate and turned into a retryable
    pending error, not raise an unhandled ValidationError."""
    adapter = ScriptedAdapter(
        [
            [
                ToolCall(
                    name=PatchDocument.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [{"op": "frobnicate", "path": "/name", "value": "x"}],
                    },
                )
            ],
            [
                ToolCall(
                    name=PatchValidationErrors.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [
                            {"op": "add", "path": "/name", "value": "Alice"},
                            {"op": "add", "path": "/age", "value": 30},
                        ],
                    },
                )
            ],
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=2)
    result = extractor.extract([{"role": "user", "content": "Alice is 30"}])
    assert result.documents["Person"] == {"name": "Alice", "age": 30}
    assert result.retries_used == 1


def test_no_relevant_tool_call_is_retried_not_silently_treated_as_success():
    """Regression test: if the model calls no PatchDocument /
    PatchValidationErrors tool at all, that must not look identical to
    "zero errors" and be returned as a successful (empty) result."""
    adapter = ScriptedAdapter(
        [
            [ToolCall(name="SomeUnrelatedTool", args={"foo": "bar"})],
            [ToolCall(name="SomeUnrelatedTool", args={"foo": "bar"})],
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=1)
    with pytest.raises(ExtractionRetriesExhaustedError):
        extractor.extract([{"role": "user", "content": "Alice is 30"}])


def test_empty_tool_call_list_is_retried_not_raised_immediately():
    adapter = ScriptedAdapter([[], []])
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=1)
    with pytest.raises(ExtractionRetriesExhaustedError):
        extractor.extract([{"role": "user", "content": "Alice is 30"}])


def test_unknown_json_doc_id_is_reported_as_pending_error_and_retried():
    adapter = ScriptedAdapter(
        [
            [ToolCall(name=PatchDocument.__name__, args={"json_doc_id": "Nope", "patches": []})],
            [
                ToolCall(
                    name=PatchValidationErrors.__name__,
                    args={
                        "json_doc_id": "Person",
                        "patches": [
                            {"op": "add", "path": "/name", "value": "Alice"},
                            {"op": "add", "path": "/age", "value": 30},
                        ],
                    },
                )
            ],
        ]
    )
    extractor = Extractor(adapter, schemas={"Person": Person}, max_retries=2)
    result = extractor.extract([{"role": "user", "content": "Alice is 30"}])
    assert result.documents["Person"] == {"name": "Alice", "age": 30}
