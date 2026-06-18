import copy
import json
import re
import uuid
from typing import Any, List, Optional, Sequence

import torch
from pydantic import ConfigDict, Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool


class QwenTransformersToolChatModel(BaseChatModel):
    """
    LangChain ChatModel wrapper for Qwen/Qwen2.5-Instruct using native transformers.

    This wrapper:
    1. Passes LangChain tools into tokenizer.apply_chat_template(..., tools=...)
    2. Lets Qwen generate <tool_call>{...}</tool_call>
    3. Parses that output into AIMessage.tool_calls
    4. Allows LangChain create_agent(...) to execute tools
    """

    model: Any = Field(default=None)
    tokenizer: Any = Field(default=None)
    model_id: str = "Qwen/Qwen2.5-3B-Instruct"
    max_new_tokens: int = 512
    temperature: float = 0.0
    tools: Optional[List[dict]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "qwen-transformers-tool-chat"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        LangChain create_agent calls bind_tools().
        We store the tool schemas so apply_chat_template can see them.
        """

        copied = copy.copy(self)

        openai_tools = []
        for tool in tools:
            schema = convert_to_openai_tool(tool)
            openai_tools.append(schema)

        copied.tools = openai_tools
        return copied

    def _convert_messages_to_hf(self, messages: List[BaseMessage]) -> List[dict]:
        hf_messages = []

        for message in messages:
            if isinstance(message, SystemMessage):
                hf_messages.append(
                    {
                        "role": "system",
                        "content": message.content,
                    }
                )

            elif isinstance(message, HumanMessage):
                hf_messages.append(
                    {
                        "role": "user",
                        "content": message.content,
                    }
                )

            elif isinstance(message, AIMessage):
                # If previous assistant message had tool calls, pass them back
                # in the format expected by transformers chat templates.
                if message.tool_calls:
                    hf_tool_calls = []

                    for tool_call in message.tool_calls:
                        hf_tool_calls.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": tool_call["name"],
                                    "arguments": tool_call["args"],
                                },
                            }
                        )

                    hf_messages.append(
                        {
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": hf_tool_calls,
                        }
                    )
                else:
                    hf_messages.append(
                        {
                            "role": "assistant",
                            "content": message.content or "",
                        }
                    )

            elif isinstance(message, ToolMessage):
                # Transformers docs say tool response content should be string.
                hf_messages.append(
                    {
                        "role": "tool",
                        "content": str(message.content),
                    }
                )

            else:
                hf_messages.append(
                    {
                        "role": "user",
                        "content": str(message.content),
                    }
                )

        return hf_messages

    def _parse_tool_calls(self, text: str) -> List[dict]:
        """
        Parse Qwen / Hermes style output:

        <tool_call>
        {"arguments": {"file_path": "..."}, "name": "transcribe_audio_file"}
        </tool_call>
        """

        tool_calls = []

        pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
        matches = re.findall(pattern, text, flags=re.DOTALL)

        for raw_json in matches:
            try:
                parsed = json.loads(raw_json)

                name = parsed.get("name")
                args = parsed.get("arguments", {})

                if name:
                    tool_calls.append(
                        {
                            "name": name,
                            "args": args,
                            "id": f"call_{uuid.uuid4().hex[:24]}",
                            "type": "tool_call",
                        }
                    )

            except json.JSONDecodeError:
                continue

        return tool_calls

    def _clean_content(self, text: str) -> str:
        return re.sub(
            r"<tool_call>\s*.*?\s*</tool_call>",
            "",
            text,
            flags=re.DOTALL,
        ).strip()

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        hf_messages = self._convert_messages_to_hf(messages)

        inputs = self.tokenizer.apply_chat_template(
            hf_messages,
            tools=self.tools,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )

        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        generation_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }

        if self.temperature > 0:
            generation_kwargs["temperature"] = self.temperature

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                **generation_kwargs,
            )

        input_length = inputs["input_ids"].shape[-1]
        generated_tokens = outputs[0][input_length:]

        raw_text = self.tokenizer.decode(
            generated_tokens,
            skip_special_tokens=False,
        )

        tool_calls = self._parse_tool_calls(raw_text)
        clean_content = self._clean_content(raw_text)

        message = AIMessage(
            content=clean_content,
            tool_calls=tool_calls,
        )

        return ChatResult(
            generations=[
                ChatGeneration(message=message)
            ]
        )