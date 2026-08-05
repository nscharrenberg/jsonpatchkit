from typing import Any

from pydantic import BaseModel

from jsonpatchkit.types import ToolCall


class LangChainAdapter:
    """`ModelAdapter` implementation backed by a LangChain chat model."""

    def __init__(self, model: Any) -> None:
        """
        Initializes the LangChainAdapter class.

        This class depends on the `langchain-core` library. If the library is not
        installed, an ImportError will be raised during initialization.

        Args:
            model: An already-configured `BaseChatModel`
                (e.g. `ChatAnthropic(model="claude-sonnet-5")`).

        Raises:
            ImportError: If the `langchain-core` library is not installed.
        """
        try:
            from langchain_core.language_models import BaseChatModel  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "LangChainAdapter requires langchain-core. "
                "Install it with: pip install 'jsonpatchkit[langchain]'"
            ) from exc
        self._model = model

    def call_with_tools(
        self,
        messages: list[Any],
        tools: list[type[BaseModel]],
        tool_choice: str,
    ) -> list[ToolCall]:
        """
        Processes messages by invoking specific tools, selected based on the tool choice,
        and returns a list of tool calls derived from the response.

        Args:
            messages: A list of messages to be processed.
            tools: A list of tool models to be bound and invoked.
            tool_choice: A string specifying the choice of tool to bind and use.

        Returns:
            List[ToolCall]: A list of ToolCall objects representing the results of tool
            invocations, including tool names, arguments, and optional IDs.
        """
        bound = self._model.bind_tools(tools, tool_choice=tool_choice)
        response = bound.invoke(messages)
        raw_tool_calls = getattr(response, "tool_calls", None) or []
        return [
            ToolCall(name=tc["name"], args=tc["args"], id=tc.get("id"))
            for tc in raw_tool_calls
        ]

    def wrap_user_message(self, text: str) -> Any:
        """
        Wraps a user's message into a HumanMessage object with the specified content.

        This function takes a string input from a user and creates a HumanMessage
        instance containing the provided text.

        Args:
            text: The message content from the user to be wrapped.

        Returns:
            A HumanMessage instance containing the provided text.
        """
        from langchain_core.messages import HumanMessage

        return HumanMessage(content=text)