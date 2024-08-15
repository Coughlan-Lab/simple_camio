from typing import Dict, Iterable, List, Optional

from openai import OpenAI, OpenAIError
from openai.types import CompletionUsage
from openai.types.chat import (ChatCompletionAssistantMessageParam,
                               ChatCompletionMessage,
                               ChatCompletionMessageParam,
                               ChatCompletionMessageToolCall,
                               ChatCompletionMessageToolCallParam)
from openai.types.chat.chat_completion_message_tool_call_param import \
    Function as FunctionParam

from src.graph import Coords, Graph

from .prompt_formatter import PromptFormatter


class LLM:
    MODEL = "gpt-4o-2024-08-06"  # "gpt-4o-mini-2024-07-18"
    MAX_TOKENS = 2000
    TEMPERATURE = 0.2

    def __init__(
        self,
        graph: Graph,
        context: Dict[str, str],
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = OpenAI()
        self.prompt_formatter = PromptFormatter(graph)

        self.history: List[ChatCompletionMessageParam] = list()
        self.history.append(self.prompt_formatter.get_main_prompt(context))
        self.usage: List[Optional[CompletionUsage]] = list()

        self.running = False

    def is_waiting_for_response(self) -> bool:
        return self.running

    def stop(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str, position: Optional[Coords]) -> Optional[str]:
        new_message = self.prompt_formatter.get_user_message(question, position)
        self.history.append(new_message)
        self.running = True

        output = ""

        try:
            while self.running:
                print("Sending API request...")

                response = self.client.chat.completions.create(
                    model=LLM.MODEL,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=self.history,
                    tools=self.prompt_formatter.get_tool_calls(),
                )
                self.usage.append(response.usage)

                if not self.running:
                    break
                print("Got API response")

                response_message = response.choices[0].message
                if (
                    response_message.content is not None
                    and response_message.content != ""
                ):
                    output += response_message.content + "\n"

                self.history.append(convert_assistant_message(response_message))

                if response_message.tool_calls is None:
                    break

                for tool_call in response_message.tool_calls:
                    self.history.append(
                        self.prompt_formatter.handle_tool_call(tool_call)
                    )

        except OpenAIError as e:
            print(f"An error occurred: {e}")
            self.running = False
            return None

        self.running = False

        return output[:-1]

    def save_chat(self, filename: str) -> None:
        msgs: List[str] = list()
        assistants_cnt = 0

        for msg in self.history:
            if "content" in msg and msg["content"] is not None and msg["content"] != "":
                msgs.append(f"{msg['role']}:\n{msg['content']}")

            if "tool_calls" in msg and msg["tool_calls"] is not None:
                msgs.append(f"{msg['role']}:")
                for tool_call in msg["tool_calls"]:
                    msgs.append(
                        f"Tool call: {tool_call['function']['name']}\n"
                        f"Parameters: {tool_call['function']['arguments']}"
                    )

            if msg["role"] == "assistant":
                usage = self.usage[assistants_cnt]
                if usage is not None:
                    msgs.append(f"Usage: {str(usage.total_tokens)} tokens")
                assistants_cnt += 1

        with open(filename, "w") as f:
            f.write("\n\n".join(msgs))


def convert_assistant_message(msg: ChatCompletionMessage) -> ChatCompletionMessageParam:
    return ChatCompletionAssistantMessageParam(
        role="assistant",
        content=msg.content,
        tool_calls=convert_tool_calls(msg.tool_calls),
    )


def convert_tool_calls(
    tool_calls: Optional[List[ChatCompletionMessageToolCall]],
) -> Optional[Iterable[ChatCompletionMessageToolCallParam]]:
    if tool_calls is None:
        return None

    return [
        ChatCompletionMessageToolCallParam(
            id=tool_call.id,
            function=FunctionParam(
                arguments=tool_call.function.arguments, name=tool_call.function.name
            ),
            type=tool_call.type,
        )
        for tool_call in tool_calls
    ]
