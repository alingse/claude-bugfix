"""Conversation state management for the agent."""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ConversationState(BaseModel):
    """Manages the conversation state between the agent and LLM."""

    messages: List[Dict[str, Any]] = []
    iteration: int = 0
    max_iterations: int = 20

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to the conversation history."""
        message = {"role": role, "content": content}
        message.update(kwargs)
        self.messages.append(message)

    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self.add_message("system", content)

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add_message("user", content)

    def add_assistant_message(self, content: Optional[str] = None, tool_calls: Optional[List] = None) -> None:
        """Add an assistant message with optional tool calls."""
        message = {"role": "assistant"}

        if content:
            message["content"] = content

        if tool_calls:
            # Convert tool calls to dict format
            message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ]

        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> None:
        """Add a tool result message."""
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": result,
            }
        )

    def increment_iteration(self) -> None:
        """Increment the iteration counter."""
        self.iteration += 1

    def is_max_iterations_reached(self) -> bool:
        """Check if maximum iterations have been reached."""
        return self.iteration >= self.max_iterations

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all messages in the conversation."""
        return self.messages

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "messages": self.messages,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }

    def to_json(self) -> str:
        """Convert state to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Create state from dictionary."""
        return cls(**data)

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
