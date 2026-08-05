import pytest

from jsonpatchkit.exceptions import (
    MalformedOperationError,
    PatchTestFailedError,
    PointerResolutionError,
    UnknownOperationError,
)
from jsonpatchkit.patch import apply_patch


def test_add_new_scalar_property():
    doc = {"name": "Alice"}
    result = apply_patch(doc, [{"op": "add", "path": "/age", "value": 30}])
    assert result == {"name": "Alice", "age": 30}


def test_add_does_not_mutate_original_by_default():
    doc = {"name": "Alice"}
    apply_patch(doc, [{"op": "add", "path": "/age", "value": 30}])
    assert doc == {"name": "Alice"}  # original untouched


def test_in_place_true_mutates_original():
    doc = {"name": "Alice"}
    result = apply_patch(doc, [{"op": "add", "path": "/age", "value": 30}], in_place=True)
    assert doc == {"name": "Alice", "age": 30}
    assert result is doc


def test_add_new_object_value():
    doc = {"person": {}}
    result = apply_patch(
        doc,
        [{"op": "add", "path": "/person/address", "value": {"city": "Maastricht"}}],
    )
    assert result == {"person": {"address": {"city": "Maastricht"}}}


def test_add_append_to_array_with_dash():
    doc = {"tags": ["hiking"]}
    result = apply_patch(doc, [{"op": "add", "path": "/tags/-", "value": "painting"}])
    assert result == {"tags": ["hiking", "painting"]}


def test_add_insert_into_array_at_index():
    doc = {"tags": ["a", "c"]}
    result = apply_patch(doc, [{"op": "add", "path": "/tags/1", "value": "b"}])
    assert result == {"tags": ["a", "b", "c"]}


def test_replace_scalar_property():
    doc = {"age": 30}
    result = apply_patch(doc, [{"op": "replace", "path": "/age", "value": 31}])
    assert result == {"age": 31}


def test_replace_missing_key_raises():
    with pytest.raises(PointerResolutionError):
        apply_patch({"age": 30}, [{"op": "replace", "path": "/height", "value": 180}])


def test_remove_property():
    doc = {"name": "Alice", "nickname": "Al"}
    result = apply_patch(doc, [{"op": "remove", "path": "/nickname"}])
    assert result == {"name": "Alice"}


def test_remove_array_element():
    doc = {"tags": ["a", "b", "c"]}
    result = apply_patch(doc, [{"op": "remove", "path": "/tags/1"}])
    assert result == {"tags": ["a", "c"]}


def test_move_operation():
    doc = {"old_name": "value", "other": 1}
    result = apply_patch(doc, [{"op": "move", "from": "/old_name", "path": "/new_name"}])
    assert result == {"other": 1, "new_name": "value"}


def test_copy_operation():
    doc = {"a": {"x": 1}}
    result = apply_patch(doc, [{"op": "copy", "from": "/a", "path": "/b"}])
    assert result == {"a": {"x": 1}, "b": {"x": 1}}
    # ensure it's a deep copy, not the same nested object
    result["a"]["x"] = 999
    assert result["b"]["x"] == 1


def test_test_operation_passes_silently():
    doc = {"status": "active"}
    result = apply_patch(doc, [{"op": "test", "path": "/status", "value": "active"}])
    assert result == {"status": "active"}


def test_test_operation_failure_raises():
    with pytest.raises(PatchTestFailedError):
        apply_patch({"status": "active"}, [{"op": "test", "path": "/status", "value": "inactive"}])


def test_unknown_operation_raises():
    with pytest.raises(UnknownOperationError):
        apply_patch({"a": 1}, [{"op": "frobnicate", "path": "/a", "value": 2}])


def test_multiple_operations_applied_in_sequence():
    doc = {"name": "Alice", "age": 30, "tags": ["hiking"]}
    ops = [
        {"op": "replace", "path": "/age", "value": 31},
        {"op": "add", "path": "/tags/-", "value": "painting"},
        {"op": "remove", "path": "/name"},
        {"op": "add", "path": "/city", "value": "Maastricht"},
    ]
    result = apply_patch(doc, ops)
    assert result == {"age": 31, "tags": ["hiking", "painting"], "city": "Maastricht"}


def test_add_missing_value_raises_malformed_not_key_error():
    """Regression test: a missing 'value' must surface as a typed,
    catchable jsonpatchkit error — not a bare KeyError — since the
    extractor's retry loop only catches JsonPatchKitError subclasses."""
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "add", "path": "/b"}])


def test_replace_missing_value_raises_malformed():
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "replace", "path": "/a"}])


def test_test_op_missing_value_raises_malformed():
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "test", "path": "/a"}])


def test_move_missing_from_raises_malformed():
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "move", "path": "/b"}])


def test_copy_missing_from_raises_malformed():
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "copy", "path": "/b"}])


def test_operation_missing_path_raises_malformed():
    with pytest.raises(MalformedOperationError):
        apply_patch({"a": 1}, [{"op": "add", "value": 1}])


def test_move_into_own_descendant_rejected():
    doc = {"a": {"b": 1}}
    with pytest.raises(MalformedOperationError):
        apply_patch(doc, [{"op": "move", "from": "/a", "path": "/a/b"}])


def test_move_into_self_rejected():
    doc = {"a": 1}
    with pytest.raises(MalformedOperationError):
        apply_patch(doc, [{"op": "move", "from": "/a", "path": "/a"}])


def test_copy_from_empty_string_root_pointer_is_not_treated_as_missing():
    """ "" is a syntactically valid JSON Pointer (the whole document) —
    it must not be confused with a missing/omitted 'from' field."""
    doc = {"a": 1}
    result = apply_patch(doc, [{"op": "copy", "from": "", "path": "/backup"}])
    assert result == {"a": 1, "backup": {"a": 1}}


def test_move_to_unrelated_path_still_works():
    doc = {"a": {"x": 1}, "sibling": {}}
    result = apply_patch(doc, [{"op": "move", "from": "/a", "path": "/sibling/a"}])
    assert result == {"sibling": {"a": {"x": 1}}}


def test_nested_edit_deep_in_structure():
    doc = {"a": {"b": {"c": [1, 2, {"d": "old"}]}}}
    result = apply_patch(doc, [{"op": "replace", "path": "/a/b/c/2/d", "value": "new"}])
    assert result == {"a": {"b": {"c": [1, 2, {"d": "new"}]}}}
