import pytest
from pydantic import ValidationError

from jsonpatchkit.operations import JsonPatchOperation, PatchDocument


def test_json_patch_operation_accepts_valid_op():
    op = JsonPatchOperation(op="add", path="/tags/-", value="painting")
    assert op.op == "add"
    assert op.value == "painting"


def test_json_patch_operation_rejects_unknown_op():
    with pytest.raises(ValidationError):
        JsonPatchOperation(op="frobnicate", path="/a")


def test_json_patch_operation_from_alias_for_move():
    op = JsonPatchOperation.model_validate({"op": "move", "path": "/b", "from": "/a"})
    assert op.from_ == "/a"


def test_patch_document_bundles_multiple_operations():
    doc = PatchDocument(
        json_doc_id="Person",
        patches=[
            {"op": "replace", "path": "/age", "value": 31},
            {"op": "add", "path": "/tags/-", "value": "painting"},
        ],
    )
    assert doc.json_doc_id == "Person"
    assert len(doc.patches) == 2
    assert doc.patches[0].op == "replace"
