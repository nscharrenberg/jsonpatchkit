class JsonPatchKitError(Exception):
    """Base class for all errors raised by jsonpatchkit."""
    pass


class SchemaBuildError(JsonPatchKitError):
    """A JSON Schema dict could not be converted into a Pydantic model."""

class PointerSyntaxError(JsonPatchKitError):
    """A JSON Pointer string is malformed (does not conform to RFC 6901)."""


class PointerResolutionError(JsonPatchKitError):
    """A syntactically valid pointer does not resolve within the document."""

