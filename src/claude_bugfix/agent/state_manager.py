"""Conversation state management for the agent."""

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from claude_bugfix.agent.context_compressor import (
    CompressionResult,
    ContextCompressor,
    CompressionConfig,
)
from claude_bugfix.agent.token_monitor import TokenMonitor

logger = logging.getLogger(__name__)


class ConversationState(BaseModel):
    """Manages the conversation state between the agent and LLM."""

    messages: List[Dict[str, Any]] = []
    iteration: int = 0
    max_iterations: int = 20
    
    # Compression tracking
    compression_history: List[CompressionResult] = Field(default_factory=list)
    total_compressions: int = 0
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def __init__(self, max_iterations: int = 20, **data):
        """Initialize conversation state."""
        super().__init__(max_iterations=max_iterations, **data)
        self._compressor: Optional[ContextCompressor] = None
        self._monitor: Optional[TokenMonitor] = None
    
    def setup_compression(
        self,
        compressor: Optional[ContextCompressor] = None,
        monitor: Optional[TokenMonitor] = None,
    ) -> None:
        """Setup compression and monitoring."""
        self._compressor = compressor
        self._monitor = monitor
    
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
    
    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """Get messages for LLM, applying compression if needed."""
        if self._compressor and self._monitor:
            return self._apply_compression_if_needed()
        return self.messages
    
    def _apply_compression_if_needed(self) -> List[Dict[str, Any]]:
        """Check and apply compression if thresholds are met."""
        if not self._compressor or not self._monitor:
            return self.messages
        
        # Estimate current tokens
        current_tokens = self._compressor.estimator.estimate_messages(self.messages)
        
        # Check if compression is needed
        should_compress, reason = self._monitor.should_compress(
            current_tokens, self.iteration, self.max_iterations
        )
        
        if should_compress:
            logger.info(f"Triggering compression: {reason}")
            
            result = self._compressor.check_and_compress(
                self.messages, self.iteration
            )
            
            if result.level != 'none':
                self.compression_history.append(result)
                self.total_compressions += 1
                
                # Update messages with compressed version
                self.messages = result.messages
                
                logger.info(f"Compression applied: {result.summary}")
        
        return self.messages

    def force_compression(self, level: Optional[str] = None) -> CompressionResult:
        """Force compression at specified level.
        
        Args:
            level: Force specific compression level ('light', 'medium', 'aggressive')
            
        Returns:
            CompressionResult
        """
        if not self._compressor:
            return CompressionResult(
                messages=self.messages.copy(),
                original_token_estimate=0,
                compressed_token_estimate=0,
                compression_ratio=1.0,
                messages_removed=0,
                messages_summarized=0,
                level='none',
                summary="Compressor not configured"
            )
        
        result = self._compressor.check_and_compress(
            self.messages, self.iteration, force_level=level
        )
        
        if result.level != 'none':
            self.compression_history.append(result)
            self.total_compressions += 1
            self.messages = result.messages
        
        return result
    
    def get_token_estimate(self) -> int:
        """Get estimated token count for current messages."""
        if self._compressor:
            return self._compressor.estimator.estimate_messages(self.messages)
        return 0
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        if not self.compression_history:
            return {
                "total_compressions": 0,
                "current_level": "none",
                "total_messages_removed": 0,
                "average_compression_ratio": 1.0,
            }
        
        total_removed = sum(r.messages_removed for r in self.compression_history)
        avg_ratio = sum(r.compression_ratio for r in self.compression_history) / len(self.compression_history)
        
        return {
            "total_compressions": self.total_compressions,
            "current_level": self.compression_history[-1].level if self.compression_history else "none",
            "total_messages_removed": total_removed,
            "average_compression_ratio": round(avg_ratio, 2),
            "compression_history": [
                {
                    "level": r.level,
                    "original_tokens": r.original_token_estimate,
                    "compressed_tokens": r.compressed_token_estimate,
                    "ratio": round(r.compression_ratio, 2),
                }
                for r in self.compression_history
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "messages": self.messages,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "compression_stats": self.get_compression_stats(),
        }

    def to_json(self) -> str:
        """Convert state to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Create state from dictionary."""
        return cls(**data)
