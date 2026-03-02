"""OpenAI client for LLM interactions."""

import logging
from typing import Any, Dict, List, Optional, Tuple
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall

from claude_bugfix.llm.config import LLMConfig

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for interacting with OpenAI API."""

    def __init__(self, config: LLMConfig):
        """Initialize the OpenAI client."""
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Tuple[Optional[str], Optional[List[ChatCompletionMessageToolCall]]]:
        """
        Send a chat completion request to OpenAI.

        Returns:
            Tuple of (response_content, tool_calls)
            - response_content: The text response from the model (if any)
            - tool_calls: List of tool calls requested by the model (if any)
        """
        try:
            kwargs = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice

            logger.debug(f"Sending chat completion request with {len(messages)} messages")

            response: ChatCompletion = await self.client.chat.completions.create(**kwargs)

            # Track token usage
            if response.usage:
                self.prompt_tokens += response.usage.prompt_tokens
                self.completion_tokens += response.usage.completion_tokens
                self.total_tokens += response.usage.total_tokens
                logger.debug(
                    f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                    f"Completion: {response.usage.completion_tokens}, "
                    f"Total: {response.usage.total_tokens}"
                )

            # Extract response
            choice = response.choices[0]
            message = choice.message

            content = message.content
            tool_calls = message.tool_calls

            if tool_calls:
                logger.debug(f"Model requested {len(tool_calls)} tool call(s)")
            elif content:
                logger.debug("Model returned text response")

            return content, tool_calls

        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
            raise

    def get_token_usage(self) -> Dict[str, int]:
        """Get total token usage statistics."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def reset_token_usage(self) -> None:
        """Reset token usage counters."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
