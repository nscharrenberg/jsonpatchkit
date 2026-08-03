"""
Validate a (patched) document against its target Pydantic schema.

Uses `BaseModel.model_validate` and `ValidationError.errors()` from Pydantic
(https://docs.pydantic.dev/latest/concepts/models/#validating-data,
https://docs.pydantic.dev/latest/errors/errors/#error-messages)
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True)
class ValidationOutcome:
    """
    Represents the outcome of a validation process.

    This class encapsulates information on whether a given entity passed validation,
    along with any validated data and associated validation errors. Designed to be
    immutable and thread-safe due to its usage of the `@dataclass` decorator with
    the `frozen=True` parameter. Commonly used in scenarios requiring structured
    feedback from validation functions.

    Attributes:
        is_valid (bool): Indicates whether the validation was successful.
        validated (Any): The validated data that corresponds to a successful
            validation outcome, or None if validation failed.
        errors (Optional[list[dict]]): A list of error details providing insights into
            the reasons for validation failure, or None if validation succeeded.
    """

    is_valid: bool
    validated: Any = None
    errors: list[dict] | None = None  # type: ignore[type-arg]


def validate_against_schema(data: dict, schema: type[BaseModel]) -> ValidationOutcome:  # type: ignore[type-arg]
    """
    Validates input data against a specified pydantic schema.

    This function takes a dictionary of data and a schema class that extends the
    BaseModel class. It validates the input data against the provided schema. If
    the data conforms to the schema, the function returns a successful validation
    outcome. Otherwise, it provides a list of validation errors.

    Args:
        data (dict): The input data to validate.
        schema (Type[BaseModel]): The schema class used to validate the input data.
            It must be a subclass of BaseModel.

    Returns:
        ValidationOutcome: An object that represents the result of the validation.
        It contains a flag indicating whether the data is valid and the validated
        data or a list of errors, depending on the validation outcome.
    """
    try:
        instance = schema.model_validate(data)
    except ValidationError as exc:
        return ValidationOutcome(is_valid=False, errors=exc.errors())  # type: ignore[arg-type]

    return ValidationOutcome(is_valid=True, validated=instance)


def format_errors_for_retry_prompt(errors: list[dict]) -> str:  # type: ignore[type-arg]
    """
    Render validation errors as a compact string for a retry prompt.

    The function takes a list of error dictionaries, each containing details about an error,
    such as its location, message, and type, and converts them into a human-readable string.
    Each error is displayed on a new line with its location, message, and type formatted in a
    consistent style.

    Args:
        errors (list[dict]): A list of dictionaries representing errors. Each dictionary should
         contain at least the keys 'loc' (a location represented as a tuple of path segments),
         'msg' (a message describing the error), and 'type' (a string identifying the error type).

    Returns:
        str: A single string combining all errors into a formatted, human-readable list,
            separated by
        newline characters.
    """
    lines = []

    for error in errors:
        path = ".".join(str(part) for part in error.get("loc", ()))
        lines.append(f"- at '{path}': {error.get('msg')} (type={error.get('type')})")

    return "\n".join(lines)
