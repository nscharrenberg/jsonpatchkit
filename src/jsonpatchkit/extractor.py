import json
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from jsonpatchkit.adapters.base import ModelAdapter
from jsonpatchkit.exceptions import ExtractionRetriesExhaustedError, JsonPatchKitError
from jsonpatchkit.operations import PatchDocument, PatchValidationErrors
from jsonpatchkit.patch import apply_patch
from jsonpatchkit.types import ExtractionResult, ToolCall
from jsonpatchkit.validation import format_errors_for_retry_prompt, validate_against_schema

_PATCH_TOOL_NAMES = {PatchDocument.__name__, PatchValidationErrors.__name__}


@dataclass
class _PendingError:
    doc_id: str
    detail: str


class Extractor:
    """Patch-based extractor: edits existing documents via JSON Patch,
    validating and retrying on schema violations, instead of asking the
    model to regenerate whole documents.
    """

    def __init__(
        self,
        adapter: ModelAdapter,
        schemas: dict[str, type[BaseModel]],
        max_retries: int = 3,
    ) -> None:
        """Args:
        adapter: A `ModelAdapter` (e.g. `LangChainAdapter(chat_model)`).
        schemas: Map of document id -> Pydantic model class each
            document must validate against, e.g.
            ``{"Person": Person}``.
        max_retries: Maximum correction round-trips after an invalid
            or malformed patch, before giving up.

        Raises:
            ValueError: If `schemas` is empty or `max_retries` is negative.
        """
        if not schemas:
            raise ValueError("`schemas` must contain at least one entry.")
        if max_retries < 0:
            raise ValueError(f"`max_retries` must be >= 0, got {max_retries}.")
        self._adapter = adapter
        self._schemas = schemas
        self._max_retries = max_retries

    def extract(
        self,
        messages: list[Any],
        existing: Optional[dict[str, dict[str, Any]]] = None,
    ) -> ExtractionResult:
        """Run one patch-validate-retry cycle.

        Args:
            messages: Conversation messages to send to the model. The
                accepted shape is whatever your `ModelAdapter` accepts;
                jsonpatchkit's own context/error follow-up messages are
                built via `adapter.wrap_user_message(...)`, so the
                extractor itself makes no assumption about message shape.
            existing: Current documents to patch, keyed by the same ids
                used in `schemas`. Any id in `schemas` absent from
                `existing` is treated as starting from an empty `{}`
                document (i.e. the model can populate it from scratch
                via "add" operations — this is how first-time
                extraction and `enable_inserts`-style new-document
                creation both fall out of the same mechanism).

        Returns:
            An `ExtractionResult` with the final validated documents.

        Raises:
            ExtractionRetriesExhaustedError: If a valid patch isn't
                reached within `max_retries` correction attempts, or if
                the model never calls a recognized patch tool at all.
        """
        existing = existing or {}
        doc_state: dict[str, dict[str, Any]] = {
            doc_id: dict(existing.get(doc_id, {})) for doc_id in self._schemas
        }
        working_messages = list(messages) + [
            self._adapter.wrap_user_message(self._context_message_text(doc_state))
        ]

        tools: list[type[BaseModel]] = [PatchDocument]
        tool_choice = PatchDocument.__name__
        retries_used = 0

        while True:
            tool_calls = self._adapter.call_with_tools(
                working_messages, tools=tools, tool_choice=tool_choice
            )

            pending_errors = self._apply_and_validate(tool_calls, doc_state)

            if pending_errors is None:
                return ExtractionResult(documents=doc_state, retries_used=retries_used)

            retries_used += 1
            if retries_used > self._max_retries:
                raise ExtractionRetriesExhaustedError(
                    f"Failed to produce a valid patch after {self._max_retries} "
                    f"retries. Last errors: "
                    f"{[(e.doc_id, e.detail) for e in pending_errors]}"
                )

            working_messages = working_messages + [
                self._adapter.wrap_user_message(self._error_message_text(pending_errors))
            ]
            tools = [PatchValidationErrors]
            tool_choice = PatchValidationErrors.__name__

    def _apply_and_validate(
        self,
        tool_calls: list[ToolCall],
        doc_state: dict[str, dict[str, Any]],
    ) -> Optional[list[_PendingError]]:
        """Validate, patch, and apply each relevant tool call.

        Returns:
            `None` if at least one patch tool call was found and every
            one of them applied and validated successfully (the "clean
            success" case). Otherwise a non-empty list of `_PendingError`
            describing what needs to be corrected on retry — this
            includes the case where the model made zero recognized
            patch-tool calls at all, which must NOT be treated as
            success just because there was nothing to report an error
            about.
        """
        pending_errors: list[_PendingError] = []
        relevant_calls_found = False

        for call in tool_calls:
            if call.name not in _PATCH_TOOL_NAMES:
                continue
            relevant_calls_found = True

            tool_schema = (
                PatchDocument if call.name == PatchDocument.__name__ else PatchValidationErrors
            )  # noqa: E501
            try:
                parsed = tool_schema.model_validate(call.args)
            except ValidationError as exc:
                fallback_id = str(call.args.get("json_doc_id", "<unknown>"))
                pending_errors.append(
                    _PendingError(
                        fallback_id,
                        f"Malformed {call.name} tool call: "
                        f"{format_errors_for_retry_prompt(exc.errors())}",
                    )
                )
                continue

            doc_id = parsed.json_doc_id
            if doc_id not in self._schemas:
                pending_errors.append(_PendingError(doc_id, f"Unknown json_doc_id {doc_id!r}."))
                continue

            patch_ops = [op.model_dump(by_alias=True) for op in parsed.patches]
            base_document = doc_state[doc_id]
            try:
                patched = apply_patch(base_document, patch_ops)
            except JsonPatchKitError as exc:
                pending_errors.append(_PendingError(doc_id, f"Patch could not be applied: {exc}"))
                continue

            outcome = validate_against_schema(patched, self._schemas[doc_id])
            # Always carry the attempt forward as the new baseline, even
            # when it's invalid. The model's next (corrective) patch is
            # written assuming its previous patch was applied — e.g. a
            # "replace /age" correction assumes the "/age" it just added
            # is still there. Reverting to the pre-attempt document here
            # would silently discard that context and make the model's
            # own corrective patch fail to apply for reasons it has no
            # way to anticipate. Success/failure is still tracked purely
            # via `pending_errors`, so this never lets an invalid result
            # leak into a successful `ExtractionResult`.
            doc_state[doc_id] = patched
            if not outcome.is_valid:
                # validate_against_schema always populates `errors` when `is_valid` is False.
                assert outcome.errors is not None
                pending_errors.append(
                    _PendingError(doc_id, format_errors_for_retry_prompt(outcome.errors))
                )

        if not relevant_calls_found:
            pending_errors.append(
                _PendingError(
                    "<none>",
                    "No PatchDocument or PatchValidationErrors tool call was "
                    "made. Call one of these tools to edit the document(s).",
                )
            )

        return pending_errors or None

    @staticmethod
    def _context_message_text(doc_state: dict[str, dict[str, Any]]) -> str:
        summary = "\n".join(f"- {doc_id}: {json.dumps(doc)}" for doc_id, doc in doc_state.items())
        return (
            "Current documents (edit these via PatchDocument; use "
            "JSON Patch operations, do not regenerate them in full):\n"
            f"{summary}"
        )

    @staticmethod
    def _error_message_text(errors: list[_PendingError]) -> str:
        lines = [f"[{e.doc_id}]\n{e.detail}" for e in errors]
        return (
            "Your last response could not be applied. Call "
            "PatchValidationErrors with corrective operations for the "
            "same json_doc_id. Errors:\n" + "\n".join(lines)
        )
