from typing import Any, Union

from jsonpatchkit.exceptions import PointerResolutionError, PointerSyntaxError

JsonValue = Union[dict[str, Any], list[Any], str, int, float, bool, None]

# Sentinel used to represent the "append to end of array" token ("-")
# defined by RFC 6901 / RFC 6902.
END_OF_ARRAY = "-"


def parse_pointer(pointer: str) -> list[str]:
    """
    Parses a given JSON Pointer string into a list of unescaped reference tokens.

    This function takes a string formatted as a JSON Pointer, as defined by
    RFC 6901, and splits it into its individual reference tokens. It also
    applies unescaping rules specified in the RFC, converting escape sequences
    such as "~1" to "/" and "~0" to "~".

    The JSON Pointer must either be an empty string or start with a forward
    slash ("/"); otherwise, a `PointerSyntaxError` is raised.

    Args:
        pointer (str): The JSON Pointer string to be parsed. Must be either empty
            or start with a forward slash ("/"), following RFC 6901 syntax.

    Returns:
        List[str]: A list of unescaped reference tokens obtained by splitting and
            unescaping the JSON Pointer.

    Raises:
        PointerSyntaxError: If the JSON Pointer string is invalid, such as not
            being empty or failing to start with a forward slash ("/").
    """
    if pointer == "":
        return []

    if not pointer.startswith("/"):
        raise PointerSyntaxError(
            f"Invalid JSON Pointer {pointer!r}: must be empty or start with '/'."
        )

    # RFC 6901 escaping: "~1" -> "/", "~0" -> "~". Order matters: unescape
    # "~1" before "~0" would be wrong the other way round, so we replace
    # "~1" first then "~0", per the spec's own guidance.
    raw_tokens = pointer.split("/")[1:]
    return [token.replace("~1", "/").replace("~0", "~") for token in raw_tokens]


def _resolve_container(document: JsonValue, tokens: list[str]) -> Any:
    """
    Resolves a container in a JSON-like document by traversing its structure using a list of tokens.

    This function navigates through a hierarchical JSON-like structure using the provided list of
    tokens to find the desired nested container. The traversal follows the sequence of tokens
    except for the last one. A helper function `_step` is used to perform each step of the
    traversal.

    Args:
        document: The root of the JSON-like structure to traverse.
        tokens: A list of strings representing the path to traverse in the document.
            Each token corresponds to a key or index in the JSON structure.

    Returns:
        Any: The resolved container in the document reached after traversing the path.
    """
    current = document

    for depth, token in enumerate(tokens[:-1]):
        current = _step(current, token, pointer_trace=tokens[: depth + 1])

    return current


def _step(current: Any, token: str, pointer_trace: list[str]) -> Any:
    """
    Move one level into `current` using a single reference token.

    Processes a step in JSON Pointer traversal, resolving the next element in a JSON structure
    (object or array) based on the current element and the provided token.

    Args:
        current: The current element being traversed in the JSON structure. This
            can be a dictionary (JSON object) or a list (JSON array).
        token: The token indicating the next step in the pointer. Represents
            either a key for an object or an index for an array.
        pointer_trace: The sequence of previously resolved tokens in the JSON
            Pointer path, used for error reporting.

    Returns:
        The resolved element, which can be either the value corresponding to the key
        in a dictionary, or the value at the index in a list.

    Raises:
        PointerResolutionError: If the token is not found in the current dictionary,
            the index is invalid in the current list, or the current element is not
            a dictionary or a list.
    """
    if isinstance(current, dict):
        if token not in current:
            raise PointerResolutionError(
                f"Key {token!r} not found at '/{'/'.join(pointer_trace)}'."
            )

        return current[token]

    if isinstance(current, list):
        index = _list_index(token, list_len=len(current), for_write=False)
        return current[index]

    raise PointerResolutionError(
        f"Cannot descend into {type(current).__name__} at "
        f"'/{'/'.join(pointer_trace)}'; expected object or array."
    )


def _list_index(token: str, list_len: int, for_write: bool) -> int:
    """
    Convert a pointer token into a validated list index.

    Resolves a string token into a list index, based on the provided list length
    and intended usage (read or write). The token can represent an integer index
    or the end-of-array marker. Performs validation of the token and its relation
    to the list bounds.

    Args:
        token (str): A string representing the array index. It can be an integer
            string or, in special cases, the end-of-array marker ('-').
        list_len (int): The current length of the list.
        for_write (bool): A flag indicating whether the index is intended for
            write operations (True) or read/removal operations (False).

    Returns:
        int: The resolved integer index corresponding to the input token.

    Raises:
        PointerResolutionError: If the token is the end-of-array marker ('-') and
            for_write is False, or if the resolved index is out of list bounds.
        PointerSyntaxError: If the token is improperly formatted (not a
            non-negative integer or the end-of-array marker, or contains leading
            zeros).
    """
    if token == END_OF_ARRAY:
        if not for_write:
            raise PointerResolutionError(
                "'-' (end-of-array marker) is only valid as an insertion "
                "target, not for reads or removals."
            )

        return list_len

    if not token.isdigit() or (len(token) > 1 and token[0] == "0"):
        raise PointerSyntaxError(
            f"Array index must be '0' or a non-negative integer with no "
            f"leading zero, or '-'; got {token!r}."
        )

    index = int(token)
    upper_bound = list_len if for_write else list_len - 1

    if index > upper_bound or index < 0:
        raise PointerResolutionError(f"Array index {index} out of bounds for length {list_len}.")

    return index


def get(document: JsonValue, pointer: str) -> Any:
    """
    Retrieves a value from a JSON document based on a given pointer.

    This function allows accessing nested elements within a JSON-compliant
    data structure using a pointer syntax. The pointer is parsed into
    individual tokens to navigate through the structure. The function resolves
    the path to the parent container of the desired value, then retrieves and
    returns it.

    Args:
        document (JsonValue): The JSON document from which the value is to be
            retrieved. It should support JSON-like hierarchies (e.g., dict, list).
        pointer (str): The JSON pointer or path indicating the location of the
            desired value within the document.

    Returns:
        Any: The value extracted from the given document at the location specified
        by the pointer. The return type is dependent on the type of the value at
        the pointer location.
    """
    tokens = parse_pointer(pointer)

    if not tokens:
        return document

    parent = _resolve_container(document, tokens)
    return _step(parent, tokens[-1], pointer_trace=tokens)


def set_value(document: JsonValue, pointer: str, value: Any) -> None:
    """
    Set (or insert) `value` at `pointer`, mutating `document` in place.

    The function allows modifying or inserting a value into a JSON compatible data
    structure (e.g., dict or list) based on the given pointer. The pointer follows
    the JSON Pointer syntax for navigating hierarchical structures.

    Args:
        document: The JSON-like data structure (dict, list, or similar) where the
            value is to be set.
        pointer: A JSON Pointer (string) indicating the location within the
            document to set the value. The pointer must meet the JSON Pointer
            syntax rules.
        value: The value to set at the specified location in the document.

    Raises:
        PointerSyntaxError: If the pointer is empty or points to the root of the
            document, which is disallowed.
        PointerResolutionError: If the pointer cannot resolve to a valid
            container (dict or list) where the value should be set.
    """
    tokens = parse_pointer(pointer)

    if not tokens:
        raise PointerSyntaxError("Cannot set the root document itself via a pointer.")

    parent = _resolve_container(document, tokens)
    last = tokens[-1]

    if isinstance(parent, dict):
        parent[last] = value
    elif isinstance(parent, list):
        index = _list_index(last, list_len=len(parent), for_write=True)
        parent.insert(index, value)
    else:
        raise PointerResolutionError(
            f"Cannot set a value inside {type(parent).__name__} at '/{'/'.join(tokens[:-1])}'."
        )


def replace_value(document: JsonValue, pointer: str, value: Any) -> None:
    """
    Replaces a value in a JSON-like document at the location specified by a
    JSON Pointer.

    This function modifies the given document in place by replacing the value
    located at the provided JSON Pointer. The pointer must point to an existing
    element; otherwise, an error will be raised.

    Args:
        document (JsonValue): The JSON-like document to be modified. This can
            be a nested dictionary or list structure.
        pointer (str): The JSON Pointer string indicating the location of the
            value to replace. The pointer must be valid and reference an existing
            key or index in the document.
        value (Any): The new value to replace the old value at the location
            specified by the pointer.

    Raises:
        PointerSyntaxError: If the pointer is invalid or attempts to replace the
            root document itself.
        PointerResolutionError: If the pointer does not resolve to an existing
            key or index in the document, or if the parent container at the
            specified location is not a dictionary or list.
    """
    tokens = parse_pointer(pointer)

    if not tokens:
        raise PointerSyntaxError("Cannot replace the root document itself via a pointer.")

    parent = _resolve_container(document, tokens)
    last = tokens[-1]

    if isinstance(parent, dict):
        if last not in parent:
            raise PointerResolutionError(
                f"Cannot replace missing key {last!r} at '/{'/'.join(tokens[:-1])}'."
            )
        parent[last] = value
    elif isinstance(parent, list):
        index = _list_index(last, list_len=len(parent), for_write=False)
        parent[index] = value
    else:
        raise PointerResolutionError(
            f"Cannot replace a value inside {type(parent).__name__} at '/{'/'.join(tokens[:-1])}'."
        )


def remove_value(document: JsonValue, pointer: str) -> Any:
    """
    Remove the value associated with the specified JSON Pointer from a JSON-like
    document. This function resolves the pointer, navigates to the specified
    value, and removes it from the parent container. It supports both dictionary
    and list-based structured data.

    Args:
        document (JsonValue): The JSON-like document (dictionary or list) from
            which the value is to be removed.
        pointer (str): A JSON Pointer string that specifies the path to the
            value to be removed.

    Returns:
        Any: The value that was removed from the document.

    Raises:
        PointerSyntaxError: If the pointer attempts to remove the root document
            or is malformed.
        PointerResolutionError: If the pointer cannot resolve to a valid
            location within the document, or if the target location is not
            a removable value (e.g., unsupported container type or missing key
            or index).
    """
    tokens = parse_pointer(pointer)

    if not tokens:
        raise PointerSyntaxError("Cannot remove the root document itself via a pointer.")

    parent = _resolve_container(document, tokens)
    last = tokens[-1]

    if isinstance(parent, dict):
        if last not in parent:
            raise PointerResolutionError(
                f"Cannot remove missing key {last!r} at '/{'/'.join(tokens[:-1])}'."
            )
        return parent.pop(last)
    if isinstance(parent, list):
        index = _list_index(last, list_len=len(parent), for_write=False)
        return parent.pop(index)
    raise PointerResolutionError(
        f"Cannot remove a value inside {type(parent).__name__} at '/{'/'.join(tokens[:-1])}'."
    )
