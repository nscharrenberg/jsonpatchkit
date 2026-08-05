import copy
from typing import Any

from jsonpatchkit import pointer
from jsonpatchkit.exceptions import (
    MalformedOperationError,
    PatchTestFailedError,
    UnknownOperationError,
)

# Operations that only need a "path" (and possibly "value"); "move" and
# "copy" additionally need "from" and are handled specially below.
_SIMPLE_OPS = {"add", "remove", "replace", "test"}
_OPS_REQUIRING_VALUE = {"add", "replace", "test"}
_OPS_REQUIRING_FROM = {"move", "copy"}
_ALL_OPS = _SIMPLE_OPS | _OPS_REQUIRING_FROM


def apply_patch(
    document: Any,
    operations: list[dict[str, Any]],
    in_place: bool = False,
) -> Any:
    """
    Applies a series of patch operations to a document.

    This function takes a document and a list of operations to modify the document according
    to the specified patch rules. The modifications can be done either in-place or on a
    deep copy of the document, depending on the `in_place` parameter.

    Args:
        document: The input document to which patch operations will be applied.
            This can be of any type.
        operations: A list of dictionaries where each dictionary represents a patch operation
            to be applied to the document.
        in_place: A boolean flag indicating whether the operation should modify the input document
            directly (`True`) or create and modify a deep copy (`False`).

    Returns:
        The modified document after the patch operations have been applied. If `in_place` is
        `True`, this will be the input `document`. Otherwise, it will be a separate deep
        copy of the original `document`.
    """
    target = document if in_place else copy.deepcopy(document)

    for operation in operations:
        _apply_single_operation(target, operation)

    return target


def _apply_single_operation(document: Any, operation: dict[str, Any]) -> None:
    """
    Applies a single JSON Patch operation on a document.

    This function processes a single operation from a JSON Patch, applying it to
    the provided document. The operation must follow the JSON Patch standard
    (RFC 6902), and the function supports various operation types, including
    'add', 'replace', 'remove', 'test', 'move', and 'copy'. Validation is performed
    on the operation to ensure all required fields are present. If the operation
    is malformed or unsupported, an appropriate error is raised.

    Args:
        document: The document to apply the JSON Patch operation on. This can be
            any JSON-compatible object, such as a dictionary or list.
        operation: A dictionary representing the JSON Patch operation. The
            dictionary must include an 'op' key specifying the operation type, and
            other required keys depending on the operation type.

    Raises:
        UnknownOperationError: If the operation type ('op') is not recognized or
            is unsupported.
        MalformedOperationError: If the operation is missing required fields for
            the specified operation type.
        PatchTestFailedError: If a 'test' operation fails to validate the expected
            value at the specified path.
    """
    op = operation.get("op")

    if op not in _ALL_OPS:
        raise UnknownOperationError(
            f"Unknown JSON Patch operation {op!r}; expected one of {sorted(_ALL_OPS)}."
        )

    if "path" not in operation or operation["path"] is None:
        raise MalformedOperationError(f"Operation {operation!r} is missing 'path'.")

    path = operation["path"]

    if op in _OPS_REQUIRING_VALUE and "value" not in operation:
        raise MalformedOperationError(
            f"Operation {op!r} at '{path}' is missing required field 'value'."
        )

    if op in _OPS_REQUIRING_FROM and ("from" not in operation or operation["from"] is None):
        raise MalformedOperationError(
            f"Operation {op!r} at '{path}' is missing required field 'from'."
        )

    if op == "add":
        pointer.set_value(document, path, copy.deepcopy(operation["value"]))
    elif op == "replace":
        pointer.replace_value(document, path, copy.deepcopy(operation["value"]))
    elif op == "remove":
        pointer.remove_value(document, path)
    elif op == "test":
        actual = pointer.get(document, path)
        expected = operation["value"]
        if actual != expected:
            raise PatchTestFailedError(
                f"Test failed at '{path}': expected {expected!r}, got {actual!r}."
            )
    elif op == "move":
        source = operation["from"]
        _reject_move_into_own_descendant(source, path)
        value = pointer.remove_value(document, source)
        pointer.set_value(document, path, value)
    elif op == "copy":
        source = operation["from"]
        value = copy.deepcopy(pointer.get(document, source))
        pointer.set_value(document, path, value)


def _reject_move_into_own_descendant(source: str, destination: str) -> None:
    """
    Enforce RFC 6902 §4.4: a location cannot be moved into one of its
    own children (e.g. `from="/a"`, `path="/a/b"` is invalid — it would
    require the location to still exist after it was just removed).

    Args:
        source: The source path of the move operation represented as a JSON
            pointer string.
        destination: The destination path of the move operation represented as
            a JSON pointer string.

    Raises:
        MalformedOperationError: If the source is attempted to be moved into
            itself or one of its own descendants.
    """
    source_tokens = pointer.parse_pointer(source)
    destination_tokens = pointer.parse_pointer(destination)
    is_same_or_descendant = destination_tokens[: len(source_tokens)] == source_tokens

    if source_tokens and is_same_or_descendant:
        raise MalformedOperationError(
            f"Cannot move '{source}' into itself or one of its own children ('{destination}')."
        )
