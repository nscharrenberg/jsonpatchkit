from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """
    A single tool call as reported by a model adapter.

    This is the adapter boundary: every adapter (LangChain, a raw OpenAI client, a raw Anthropic client, ...)
    must translate its own native tool-call representation into this one shape, so the extractor never needs
    to know which backend produced it.

    :ivar name: The name of the tool being called.
    :type name: str
    :ivar args: A dictionary of arguments passed to the tool during the call.
    :type args: Dict[str, Any]
    :ivar id: An optional identifier for the tool call, useful for tracking or
        distinct identification purposes.
    :type id: Optional[str]
    """
    name: str
    args: dict[str, Any]
    id: str | None = None

@dataclass(frozen=True)
class ExtractionResult:
    """
    Outcome of a single `Extractor.extract(...)` call.

    :ivar documents: Final documents keyed by `json_doc_id` (as plain dicts,
        already validated against their schema).
    :type documents: Dict[str, dict]
    :ivar retries_used: Indicates the number of retries attempted during
        the extraction process.
    :type retries_used: int
    """
    documents: dict[str, dict] = field(default_factory=dict)  # type: ignore[type-arg]
    retries_used: int = 0