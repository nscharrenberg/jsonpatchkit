import pytest

from jsonpatchkit import pointer
from jsonpatchkit.exceptions import PointerResolutionError, PointerSyntaxError


def test_parse_pointer_empty_means_whole_document():
    assert pointer.parse_pointer("") == []


def test_parse_pointer_splits_and_unescapes():
    assert pointer.parse_pointer("/a/b/0") == ["a", "b", "0"]
    # "~1" -> "/", "~0" -> "~"
    assert pointer.parse_pointer("/a~1b/c~0d") == ["a/b", "c~d"]


def test_parse_pointer_rejects_missing_leading_slash():
    with pytest.raises(PointerSyntaxError):
        pointer.parse_pointer("a/b")


def test_get_root_document():
    doc = {"a": 1}
    assert pointer.get(doc, "") == doc


def test_get_nested_dict_value():
    doc = {"a": {"b": {"c": 42}}}
    assert pointer.get(doc, "/a/b/c") == 42


def test_get_list_index():
    doc = {"items": ["x", "y", "z"]}
    assert pointer.get(doc, "/items/1") == "y"


def test_get_missing_key_raises():
    with pytest.raises(PointerResolutionError):
        pointer.get({"a": 1}, "/b")


def test_get_out_of_range_index_raises():
    with pytest.raises(PointerResolutionError):
        pointer.get({"items": [1, 2]}, "/items/5")


def test_get_dash_for_read_is_rejected():
    with pytest.raises(PointerResolutionError):
        pointer.get({"items": [1, 2]}, "/items/-")


def test_get_leading_zero_index_is_rejected():
    """RFC 6901: array indices must not have a leading zero (e.g. '01')."""
    with pytest.raises(PointerSyntaxError):
        pointer.get({"items": [1, 2, 3]}, "/items/01")


def test_get_bare_zero_index_is_allowed():
    assert pointer.get({"items": [10, 20]}, "/items/0") == 10


def test_set_value_missing_intermediate_object_raises():
    """ "add" must not silently create missing intermediate objects —
    the parent path must already exist, per RFC 6902 semantics."""
    doc = {"a": {}}
    with pytest.raises(PointerResolutionError):
        pointer.set_value(doc, "/a/b/c", "value")


def test_get_descend_into_scalar_raises():
    """Attempting to step into a scalar (not an object or array) as if
    it had children must fail clearly, not silently return garbage."""
    with pytest.raises(PointerResolutionError):
        pointer.get({"a": 1}, "/a/b")


def test_set_value_at_root_pointer_raises():
    with pytest.raises(PointerSyntaxError):
        pointer.set_value({"a": 1}, "", {"replacement": True})


def test_set_value_inside_scalar_parent_raises():
    doc = {"a": 1}
    with pytest.raises(PointerResolutionError):
        pointer.set_value(doc, "/a/b", "value")


def test_replace_value_at_root_pointer_raises():
    with pytest.raises(PointerSyntaxError):
        pointer.replace_value({"a": 1}, "", {"replacement": True})


def test_replace_value_inside_scalar_parent_raises():
    doc = {"a": 1}
    with pytest.raises(PointerResolutionError):
        pointer.replace_value(doc, "/a/b", "value")


def test_remove_value_at_root_pointer_raises():
    with pytest.raises(PointerSyntaxError):
        pointer.remove_value({"a": 1}, "")


def test_remove_value_inside_scalar_parent_raises():
    doc = {"a": 1}
    with pytest.raises(PointerResolutionError):
        pointer.remove_value(doc, "/a/b")


def test_set_value_adds_new_dict_key():
    doc = {"a": 1}
    pointer.set_value(doc, "/b", 2)
    assert doc == {"a": 1, "b": 2}


def test_set_value_overwrites_existing_dict_key():
    doc = {"a": 1}
    pointer.set_value(doc, "/a", 99)
    assert doc == {"a": 99}


def test_set_value_inserts_into_list_at_index():
    doc = {"items": [1, 2, 3]}
    pointer.set_value(doc, "/items/1", "new")
    assert doc == {"items": [1, "new", 2, 3]}


def test_set_value_appends_with_dash():
    doc = {"items": [1, 2]}
    pointer.set_value(doc, "/items/-", 3)
    assert doc == {"items": [1, 2, 3]}


def test_set_value_creates_nested_new_object_field():
    doc = {"person": {"name": "Alice"}}
    pointer.set_value(doc, "/person/age", 30)
    assert doc == {"person": {"name": "Alice", "age": 30}}


def test_replace_value_requires_existing_key():
    with pytest.raises(PointerResolutionError):
        pointer.replace_value({"a": 1}, "/b", 2)


def test_replace_value_overwrites_list_element():
    doc = {"items": [1, 2, 3]}
    pointer.replace_value(doc, "/items/0", "first")
    assert doc == {"items": ["first", 2, 3]}


def test_remove_value_deletes_dict_key():
    doc = {"a": 1, "b": 2}
    removed = pointer.remove_value(doc, "/a")
    assert removed == 1
    assert doc == {"b": 2}


def test_remove_value_deletes_list_element_and_shifts():
    doc = {"items": [1, 2, 3]}
    removed = pointer.remove_value(doc, "/items/1")
    assert removed == 2
    assert doc == {"items": [1, 3]}


def test_remove_missing_key_raises():
    with pytest.raises(PointerResolutionError):
        pointer.remove_value({"a": 1}, "/missing")
