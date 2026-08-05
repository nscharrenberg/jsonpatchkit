import pytest
from pydantic import ValidationError

from jsonpatchkit.exceptions import SchemaBuildError
from jsonpatchkit.schema import build_model_from_schema


def test_builds_flat_model_with_required_and_optional_fields():
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name"],
    }
    Person = build_model_from_schema(schema)
    instance = Person(name="Alice")
    assert instance.name == "Alice"
    assert instance.age is None


def test_required_field_missing_raises_validation_error():
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    Person = build_model_from_schema(schema)
    with pytest.raises(ValidationError):
        Person()


def test_builds_nested_object_field():
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {
            "address": {
                "type": "object",
                "title": "Address",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        },
    }
    Person = build_model_from_schema(schema)
    instance = Person(address={"city": "Maastricht"})
    assert instance.address.city == "Maastricht"


def test_builds_array_of_strings():
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    }
    Person = build_model_from_schema(schema)
    instance = Person(tags=["hiking", "painting"])
    assert instance.tags == ["hiking", "painting"]


def test_resolves_ref_against_defs():
    schema = {
        "title": "Person",
        "type": "object",
        "$defs": {
            "Address": {
                "title": "Address",
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        },
        "properties": {"address": {"$ref": "#/$defs/Address"}},
    }
    Person = build_model_from_schema(schema)
    instance = Person(address={"city": "Maastricht"})
    assert instance.address.city == "Maastricht"


def test_unresolved_ref_raises_schema_build_error():
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {"address": {"$ref": "#/$defs/Missing"}},
    }
    with pytest.raises(SchemaBuildError):
        build_model_from_schema(schema)


def test_non_object_top_level_schema_raises():
    with pytest.raises(SchemaBuildError):
        build_model_from_schema({"type": "string"})


def test_custom_model_name_override():
    schema = {
        "title": "Ignored",
        "type": "object",
        "properties": {"x": {"type": "integer"}},
    }
    Model = build_model_from_schema(schema, model_name="Custom")
    assert Model.__name__ == "Custom"


def test_hyphenated_property_name_is_aliased_not_a_typeerror():
    """Regression test: property names that aren't valid Python
    identifiers used to blow up inside pydantic.create_model with a
    raw TypeError. They must now work via a field alias."""
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {"first-name": {"type": "string"}},
        "required": ["first-name"],
    }
    Person = build_model_from_schema(schema)
    instance = Person.model_validate({"first-name": "Alice"})
    assert instance.first_name == "Alice"
    # Also constructible via the sanitized Python-side name directly.
    assert Person(first_name="Bob").first_name == "Bob"


def test_property_name_starting_with_digit_is_aliased():
    schema = {
        "title": "Model",
        "type": "object",
        "properties": {"2fa_enabled": {"type": "boolean"}},
        "required": ["2fa_enabled"],
    }
    Model = build_model_from_schema(schema)
    instance = Model.model_validate({"2fa_enabled": True})
    assert instance.field_2fa_enabled is True


def test_property_name_matching_python_keyword_is_aliased():
    schema = {
        "title": "Model",
        "type": "object",
        "properties": {"class": {"type": "string"}},
        "required": ["class"],
    }
    Model = build_model_from_schema(schema)
    instance = Model.model_validate({"class": "Warrior"})
    assert instance.class_ == "Warrior"


def test_colliding_sanitized_names_get_unique_suffixes():
    """ "first-name" and "first_name" both sanitize to "first_name" —
    they must not silently collide and drop one field."""
    schema = {
        "title": "Model",
        "type": "object",
        "properties": {
            "first-name": {"type": "string"},
            "first_name": {"type": "string"},
        },
    }
    Model = build_model_from_schema(schema)
    instance = Model.model_validate({"first-name": "aliased", "first_name": "direct"})
    field_values = {getattr(instance, f) for f in Model.model_fields}
    assert field_values == {"aliased", "direct"}
