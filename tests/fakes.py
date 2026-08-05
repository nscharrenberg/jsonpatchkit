"""A scripted fake ModelAdapter for tests.

Returns a pre-programmed sequence of tool-call batches, one per call to
`call_with_tools`, so extractor tests can exercise the retry loop
deterministically without a real model.
"""

from typing import Any

from pydantic import BaseModel

from jsonpatchkit.types import ToolCall


class ScriptedAdapter:
    def __init__(self, responses: list[list[ToolCall]]) -> None:
        """Args:
        responses: One list of ToolCalls per expected invocation, in order.
        """
        self._responses = list(responses)
        self.calls_made = 0

    def call_with_tools(
        self,
        messages: list[Any],
        tools: list[type[BaseModel]],
        tool_choice: str,
    ) -> list[ToolCall]:
        if self.calls_made >= len(self._responses):
            raise AssertionError("ScriptedAdapter called more times than scripted.")
        response = self._responses[self.calls_made]
        self.calls_made += 1
        return response

    def wrap_user_message(self, text: str) -> Any:
        # Kept simple and inspectable for assertions in tests.
        return {"role": "user", "content": text}
