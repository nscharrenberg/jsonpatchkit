from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from jsonpatchkit.types import ToolCall


@runtime_checkable
class ModelAdapter(Protocol):
    def call_with_tools(
        self,
        messages: list[Any],
        tools: list[type[BaseModel]],
        tool_choice: str,
    ) -> list[ToolCall]:
        """
        Processes a list of messages and maps them into tool calls using the
        specified tools and tool choice.

        Args:
            messages: A list of messages to be processed.
            tools: A list of tool models that messages will be mapped to.
            tool_choice: A string specifying the strategy or method for how
                tools are selected or used in processing.

        Returns:
            A list of ToolCall instances that represent the processed results
            corresponding to the messages and selected tools.
        """
        ...

    def wrap_user_message(self, text: str) -> Any:
        """
        "Wrap plain text into whatever message shape this adapter's
        backend expects for `call_with_tools`.

        The extractor uses this for its own injected context/error
        follow-up messages, so it never has to assume a specific
        provider's message format (e.g. OpenAI-style role/content
        dicts vs. LangChain `BaseMessage` instances vs. something
        else entirely).

        Args:
            text (str): The input string message provided by the user.

        Returns:
            Any: The result of the processing or transformation applied to the
            input message.
        """
        ...