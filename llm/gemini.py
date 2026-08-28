import os
from typing import Any
from google import genai
from google.genai import types

from llm.base import BaseLLM, ChatMessage, LLMResponse, ToolCall


class GeminiLLM(BaseLLM):
    def __init__(self, model: str = "gemini-3.6-flash", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

    def _convert_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str | None, list[types.Content]]:
        system_instruction: str | None = None
        contents: list[types.Content] = []

        for msg in messages:
            if msg.role == "system":
                # Gemini accepts system_instruction in GenerateContentConfig
                if msg.content:
                    system_instruction = (
                        f"{system_instruction}\n{msg.content}"
                        if system_instruction
                        else msg.content
                    )
            elif msg.role == "user":
                parts: list[types.Part] = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                contents.append(types.Content(role="user", parts=parts))
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        part_kwargs: dict[str, Any] = {
                            "function_call": types.FunctionCall(
                                name=tc.name,
                                args=tc.arguments,
                                id=tc.id,
                            )
                        }
                        if tc.thought_signature is not None:
                            part_kwargs["thought_signature"] = tc.thought_signature
                        parts.append(types.Part(**part_kwargs))
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                tool_part = types.Part.from_function_response(
                    name=msg.name or "tool",
                    response={"result": msg.content},
                )
                contents.append(types.Content(role="user", parts=[tool_part]))

        return system_instruction, contents

    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        system_instruction, contents = self._convert_messages(messages)

        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if tools:
            config_kwargs["tools"] = [
                types.Tool(function_declarations=tools)
            ]

        config = (
            types.GenerateContentConfig(**config_kwargs)
            if config_kwargs
            else None
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        # Parse response
        content_text = ""
        tool_calls: list[ToolCall] = []

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        content_text += part.text
                    if part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(
                            ToolCall(
                                name=fc.name,
                                arguments=args,
                                id=getattr(fc, "id", None),
                                thought_signature=part.thought_signature,
                            )
                        )

        return LLMResponse(
            content=content_text if content_text else None,
            tool_calls=tool_calls,
        )
