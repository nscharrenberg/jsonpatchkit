import keyword
import re
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, create_model

from jsonpatchkit.exceptions import SchemaBuildError

_PRIMITIVE_TYPES: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "null": type(None),
}

_NON_IDENTIFIER_CHARS = re.compile(r"\W")

def _to_valid_identifier(name: str, taken: dict[str, int]) -> str:
    """
    Map an arbitrary JSON Schema property name to a valid, unique Python identifier
    suitable as a `create_model` keyword argument.

    This function ensures that the given name is transformed into a valid Python identifier by:
    1. Replacing invalid characters with underscores.
    2. Ensuring the identifier does not start with a digit.
    3. Appending an underscore for identifiers that are reserved keywords in Python.
    4. Making the identifier unique by appending a numeric suffix if necessary.

    Args:
        name (str): The input string to be transformed into a valid identifier.
        taken (dict[str, int]): A dictionary that tracks previously generated identifiers
        and their counts.

    Returns:
        str: A valid and unique Python identifier based on the input name.
    """
    candidate = _NON_IDENTIFIER_CHARS.sub("_", name)

    if not candidate or candidate[0].isdigit():
        candidate = f"field_{candidate}"

    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_"

    count = taken.get(candidate, 0)
    unique = candidate if count == 0 else f"{candidate}_{count}"
    taken[candidate] = count + 1

    return unique

def build_model_from_schema(
        json_schema: dict[str, Any],
        model_name: str | None = None
) -> type[BaseModel]:
    """
    Builds a Pydantic model dynamically based on a provided JSON schema.

    This function takes a JSON schema and generates a Pydantic model from it.
    The generated model can be used for validating and accessing data structures
    that conform to the JSON schema. If no model name is provided, the function
    will use the "title" field in the JSON schema (if present), or default to
    "DynamicModel".

    Args:
        json_schema (dict[str, Any]): The schema definition in JSON format used to
            construct the Pydantic model.
        model_name (Optional[str]): An optional string specifying the name of the
            generated model. Defaults to None, in which case the "title" field in
            the JSON schema or "DynamicModel" is used.

    Returns:
        Type[BaseModel]: A dynamically constructed Pydantic model class that
            represents the provided JSON schema.
    """
    defs = _collect_defs(json_schema)
    name = model_name or json_schema.get("title") or "DynamicModel"
    return _build_object_model(json_schema, name, defs)

def _collect_defs(root_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Gather reusable sub-schemas from "$defs" / "definitions".

    This function aggregates schema definitions from the "definitions" and "$defs"
    keys in the provided root schema dictionary into a single dictionary.

    Args:
        root_schema (dict[str, Any]): The root schema dictionary potentially containing
            schema definitions under the keys "definitions" and "$defs".

    Returns:
        dict[str, Any]: A dictionary containing the combined schema definitions
            from the "definitions" and "$defs" keys.
    """
    return {
        **root_schema.get("definitions", {}),
        **root_schema.get("$defs", {}),
    }

def _build_object_model(
    schema: dict[str, Any],
    name: str,
    defs: dict[str, Any],
) -> type[BaseModel]:
    """
    Builds a Pydantic object model from a given JSON schema.

    This function generates a Pydantic model using the provided JSON schema. The
    schema must represent a top-level object type. The model includes fields
    defined in the schema's `properties` section, and it handles validation,
    aliases, required fields, and type resolution. The function also ensures valid
    Python identifiers are used as field names.

    Args:
        schema (dict[str, Any]): JSON schema representing the object. The schema
            must have a `type` field with the value `"object"`. If the schema does
            not meet these criteria, an error is raised.
        name (str): Name of the model to be created. This will be assigned to the
            generated Pydantic model.
        defs (dict[str, Any]): Mapping of schema definitions for resolving
            references within the schema.

    Returns:
        Type[BaseModel]: A dynamically created Pydantic model based on the given
            schema.

    Raises:
        SchemaBuildError: If the schema does not have a type of "object", if it
            lacks properties, or if an error occurs while resolving field types or
            names.
    """
    if schema.get("type", "object") != "object":
        raise SchemaBuildError(
            f"build_model_from_schema expects a top-level object schema, "
            f"got type={schema.get('type')!r}."
        )

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    taken_identifiers: dict[str, int] = {}
    for field_name, field_schema in properties.items():
        annotation = _resolve_type(field_schema, defs, context=f"{name}.{field_name}")
        is_required = field_name in required
        python_name = _to_valid_identifier(field_name, taken_identifiers)

        if python_name == field_name:
            # Fast path: no alias machinery needed for the common case
            # of an already-valid identifier.
            if is_required:
                field_definitions[python_name] = (annotation, ...)
            else:
                field_definitions[python_name] = (Optional[annotation], None)
        else:
            default = ... if is_required else None
            declared_type = annotation if is_required else Optional[annotation]
            field_definitions[python_name] = (
                declared_type,
                Field(default=default, alias=field_name),
            )

    if not field_definitions:
        raise SchemaBuildError(f"Schema {name!r} has no properties to build fields from.")

    return create_model(
        name,
        __config__=ConfigDict(populate_by_name=True),
        **field_definitions,
    )

def _resolve_type(field_schema: dict[str, Any], defs: dict[str, Any], context: str) -> Any:
    """
    Resolves and returns the corresponding Python type or model representation of a given
    JSON schema definition. This function is used to process schemas to determine their
    type, manage references, handle enums, and resolve complex constructs like objects and
    arrays.

    Args:
        field_schema (dict[str, Any]): The JSON schema field definition to process.
        defs (dict[str, Any]): A dictionary containing schema definitions, used to resolve
            references within the schema.
        context (str): The context or path of the schema being resolved, used in error
            messages.

    Returns:
        Any: A Python type or model representation of the resolved schema.

    Raises:
        SchemaBuildError: If the schema contains unresolved references, invalid entries for
            enum, missing items in array types, unsupported types, or unspecified fields
            required for processing correctly.
    """
    if "$ref" in field_schema:
        ref_name = field_schema["$ref"].split("/")[-1]

        if ref_name not in defs:
            raise SchemaBuildError(f"Unresolved $ref {field_schema['$ref']!r} in {context}.")

        return _build_object_model(defs[ref_name], ref_name, defs)

    if "enum" in field_schema:
        enum_values = field_schema["enum"]

        if not enum_values:
            raise SchemaBuildError(f"'enum' at {context} must not be empty.")

        from typing import Literal

        return Literal[tuple(enum_values)]  # type: ignore[valid-type]

    schema_type = field_schema.get("type")

    if schema_type == "object":
        nested_name = field_schema.get("title", f"{context}_Object")

        return _build_object_model(field_schema, nested_name, defs)

    if schema_type == "array":
        items_schema = field_schema.get("items")

        if items_schema is None:
            raise SchemaBuildError(f"Array field in {context} is missing 'items'.")

        item_type = _resolve_type(items_schema, defs, context=f"{context}[]")

        return list[item_type]

    if schema_type in _PRIMITIVE_TYPES:
        return _PRIMITIVE_TYPES[schema_type]

    if isinstance(schema_type, list):
        # e.g. {"type": ["string", "null"]}
        options = [_PRIMITIVE_TYPES[t] for t in schema_type if t in _PRIMITIVE_TYPES]

        if not options:
            raise SchemaBuildError(f"No supported types in {schema_type!r} at {context}.")

        return Union[tuple(options)]

    raise SchemaBuildError(
        f"Unsupported or missing 'type' in schema at {context}: {field_schema!r}."
    )