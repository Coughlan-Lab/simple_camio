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

from src.graph import Graph
from src.modules_repository import Module
from src.position import PositionInfo

from .prompt_formatter import PromptFormatter


class LLM(Module):
    MODEL = "gpt-4o-2024-08-06"  # "gpt-4o-mini-2024-07-18"
    MAX_TOKENS = 2000
    DEFAULT_TEMPERATURE = 0.0

    def __init__(
        self,
        prompt_file: str,
        context: Dict[str, str],
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        super().__init__()

        self.temperature = temperature

        self.client = OpenAI()
        self.prompt_formatter = PromptFormatter(prompt_file, self.__graph)

        self.context = context
        self.history: List[ChatCompletionMessageParam] = list()
        self.history.append(self.prompt_formatter.get_main_prompt(self.context))
        self.usage: List[Optional[CompletionUsage]] = list()

        self.running = False

    @property
    def __graph(self) -> Graph:
        return self._repository[Graph]

    def is_waiting_for_response(self) -> bool:
        return self.running

    def stop(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.running = False
        self.history.clear()
        self.history.append(self.prompt_formatter.get_main_prompt(self.context))

    def ask(self, question: str, position: Optional[PositionInfo]) -> Optional[str]:
        new_message = self.prompt_formatter.get_user_message(question, position)
        self.history.append(new_message)
        self.running = True

        output = ""

        try:
            while self.running:
                print("Sending API request...")

                response = self.client.chat.completions.create(
                    model=LLM.MODEL,
                    max_tokens=LLM.MAX_TOKENS,
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
                    and len(response_message.content) > 0
                ):
                    output += response_message.content + "\n"

                self.history.append(convert_assistant_message(response_message))

                if (
                    response_message.tool_calls is not None
                    and len(response_message.tool_calls) > 0
                ):
                    for tool_call in response_message.tool_calls:
                        self.history.append(
                            self.prompt_formatter.handle_tool_call(tool_call)
                        )
                    self.history.append(self.prompt_formatter.get_instructions_prompt())

                else:
                    break

        except OpenAIError as e:
            print(f"An error occurred: {e}")
            return None

        finally:
            self.running = False

        return output[:-1]

    def save_chat(self, filename: str) -> None:
        msgs: List[str] = list()
        assistants_cnt = 0

        for msg in self.history:
            if "content" in msg and msg["content"] is not None and msg["content"] != "":
                msgs.append(f"{msg['role']}:\n{msg['content']}")

            if "tool_calls" in msg and msg.get("tool_calls", None) is not None:
                msgs.append(f"{msg['role']}:")
                for tool_call in msg.get("tool_calls", list()):
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
