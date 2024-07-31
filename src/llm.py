from typing import List, Optional

from openai import OpenAI, OpenAIError
from openai.types.chat import (ChatCompletionAssistantMessageParam,
                               ChatCompletionMessageParam,
                               ChatCompletionUserMessageParam)

from .graph import Edge


class LLM:
    MAX_TOKENS = 1000
    TEMPERATURE = 0.2

    def __init__(
        self, max_tokens: int = MAX_TOKENS, temperature: float = TEMPERATURE
    ) -> None:
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = OpenAI()

        self.history: List[ChatCompletionMessageParam] = list()

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str, position: Optional[Edge]) -> Optional[str]:
        new_message = self.get_user_message(question, position)
        self.history.append(new_message)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-05-13",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=self.history,
            )
        except OpenAIError as e:
            print(f"An error occurred: {e}")
            return None

        response_message = response.choices[0].message
        self.history.append(
            ChatCompletionAssistantMessageParam(
                content=response_message.content, role="assistant"
            )
        )

        return response_message.content

    def get_user_message(
        self, content: str, position: Optional[Edge]
    ) -> ChatCompletionUserMessageParam:
        return ChatCompletionUserMessageParam(content=content, role="user")

    def save_chat(self, filename: str) -> None:
        msgs: List[str] = list()
        for msg in self.history:
            if "content" in msg:
                msgs.append(f"{msg['role']}:\n{msg['content']}")

        with open(filename, "w") as f:
            f.write("\n\n".join(msgs))
