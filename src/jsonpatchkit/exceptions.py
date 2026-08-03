class JsonPatchKitError(Exception):
    """Base class for all errors raised by jsonpatchkit."""
    pass


class SchemaBuildError(JsonPatchKitError):
    """A JSON Schema dict could not be converted into a Pydantic model."""
