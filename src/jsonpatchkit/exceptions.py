class JsonPatchKitError(Exception):
    """Base class for all errors raised by jsonpatchkit."""
    pass


class SchemaBuildError(JsonPatchKitError):
    """A JSON Schema dict could not be converted into a Pydantic model."""

class PointerSyntaxError(JsonPatchKitError):
    """A JSON Pointer string is malformed (does not conform to RFC 6901)."""


class PointerResolutionError(JsonPatchKitError):
    """A syntactically valid pointer does not resolve within the document."""

class MalformedOperationError(JsonPatchKitError):
    """A patch operation is missing a field required for its `op`.

    e.g. an "add" without "value", or a "move" without "from". Kept
    distinct from `UnknownOperationError` so callers can tell "the verb
    itself is invalid" apart from "the verb is fine but the arguments
    are incomplete" — both are equally retryable by an LLM caller, but
    they warrant different corrective guidance in a retry prompt.
    """

class PatchTestFailedError(JsonPatchKitError):
    """A `test` operation's expected value did not match the document."""

class UnknownOperationError(JsonPatchKitError):
    """A patch operation's `op` field is not one of the RFC 6902 verbs."""
