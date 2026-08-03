from pydantic import BaseModel

from jsonpatchkit.validation import format_errors_for_retry_prompt, validate_against_schema  # type: ignore[import-untyped]


class _Person(BaseModel):
    name: str
    age: int

def test_valid_data_returns_success_outcome() -> None:
    """Given valid data, the validation function should return a success outcome."""
    outcome = validate_against_schema({"name": "Alice", "age": 30}, _Person)
    assert outcome.is_valid
    assert outcome.validated.name == "Alice"
    assert outcome.errors is None


def test_invalid_data_returns_structured_errors() -> None:
    """Given invalid data, the validation function should return structured errors."""
    outcome = validate_against_schema({"name": "Alice", "age": "not-a-number"}, _Person)
    assert not outcome.is_valid
    assert outcome.validated is None
    assert len(outcome.errors) == 1
    assert outcome.errors[0]["loc"] == ("age",)


def test_missing_required_field_reported() -> None:
    """Given missing required fields, the validation function should report them."""
    outcome = validate_against_schema({"age": 30}, _Person)
    assert not outcome.is_valid
    assert any(err["loc"] == ("name",) for err in outcome.errors)


def test_format_errors_for_retry_prompt_is_human_readable() -> None:
    """Given validation errors, the format_errors_for_retry_prompt function should return a human-readable string."""
    outcome = validate_against_schema({"age": "x"}, _Person)
    text = format_errors_for_retry_prompt(outcome.errors)
    assert "name" in text
    assert "age" in text