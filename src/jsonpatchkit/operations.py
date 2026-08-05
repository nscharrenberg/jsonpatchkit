from typing import Any, Literal

from pydantic import BaseModel, Field

PatchOpName = Literal["add", "remove", "replace", "move", "copy", "test"]


class JsonPatchOperation(BaseModel):
    """
    Represents a single JSON Patch operation as per RFC 6902.

    This class models an individual operation in a JSON Patch request. JSON Patch
    is a lightweight format for expressing a sequence of operations to apply to a
    JSON document. Supported operations include adding, removing, replacing,
    copying, and moving values, which transform the target JSON document. Each
    operation is defined by specific attributes such as the operation type,
    the target location, and, where applicable, the value to be used or the source
    location.

    Attributes:
        op (PatchOpName): The patch operation to perform (e.g., add, remove,
            replace, move, copy, test).
        path (str): JSON Pointer (RFC 6901) to the target location in the
            JSON document. Examples include '/tags/-' to append to an array, or
            '/address/city' for modifying a nested field.
        value (Optional[Any]): The value to add or replace with. Not applicable for
            the 'remove' operation.
        from_ (Optional[str]): Source JSON Pointer used only with the 'move' and
            'copy' operations. This specifies the source location of the data
            to be moved or copied.
    """

    op: PatchOpName = Field(description="The patch operation to perform.")
    path: str = Field(
        description=(
            "JSON Pointer (RFC 6901) to the target location, e.g. "
            "'/tags/-' to append to an array, '/address/city' for a "
            "nested field."
        )
    )
    value: Any | None = Field(
        default=None,
        description="The value to add/replace with. Not used for 'remove'.",
    )
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Source JSON Pointer. Required for 'move' and 'copy'.",
    )

    model_config = {"populate_by_name": True}


class PatchDocument(BaseModel):
    """
    Tool the model calls to edit an existing document.

    This class encapsulates the information required to apply a set of JSON Patch
    operations to an existing document. It includes the target document identifier,
    a justification for the changes, and the list of patch operations.

    Attributes:
        json_doc_id (str): Identifier of the existing document being patched.
        reasoning (Optional[str]): Brief note on what is being changed and why
            (optional).
        patches (List[JsonPatchOperation]): The JSON Patch operations to apply.
    """

    json_doc_id: str = Field(description="Identifier of the existing document being patched.")
    reasoning: str | None = Field(
        default=None,
        description="Brief note on what is being changed and why (optional).",
    )
    patches: list[JsonPatchOperation] = Field(
        default_factory=list,
        description="The JSON Patch operations to apply.",
    )


class PatchValidationErrors(BaseModel):
    """
    Tool the model calls to correct a document that failed validation.

    This class is used to capture details of validation errors that occur while
    applying corrective JSON Patch operations to a specific JSON document. It
    encapsulates the ID of the document being corrected and provides a list of the
    corresponding JSON Patch operations involved.

    Attributes:
        json_doc_id (str): Identifier of the document being corrected.
        patches (List[JsonPatchOperation]): Additional/corrective JSON Patch
            operations.
    """

    json_doc_id: str = Field(description="Identifier of the document being corrected.")
    patches: list[JsonPatchOperation] = Field(
        default_factory=list,
        description="Additional/corrective JSON Patch operations.",
    )
