from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """
    A single tool call as reported by a model adapter.

    This is the adapter boundary: every adapter (LangChain, a raw OpenAI client, a raw Anthropic
    client, ...) must translate its own native tool-call representation into this one shape,
    so the extractor never needs to know which backend produced it.

    Attributes:
        name (str): The name of the tool being called.
        args (dict[str, Any]): The arguments provided to the tool.
        id (str | None): An optional identifier for the tool call.
    """
    name: str
    args: dict[str, Any]
    id: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """
    Outcome of a single `Extractor.extract(...)` call.

    Attributes:
        documents (dict[str, dict[str, Any]]): Final documents keyed by `json_doc_id` (as plain
        dicts, already validated against their schema).
        retries_used (int): The number of retries performed during the extraction
            process to handle errors or failures.
    """
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    retries_used: int = 0
