"""Interactive agent loop with user confirmation."""

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from claude_bugfix.agent.state_manager import ConversationState
from claude_bugfix.llm.client import OpenAIClient
from claude_bugfix.tools.registry import ToolRegistry
from claude_bugfix.tools.base import ToolResult
from claude_bugfix.utils.file_utils import read_file_async

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the agent can take."""
    THINKING = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    FINAL_ANSWER = auto()
    ERROR = auto()


@dataclass
class AgentAction:
    """Represents an action taken by the agent."""
    type: ActionType
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[ToolResult] = None
    iteration: int = 0


# Callback type for interactive mode (can be sync or async)
ActionCallback = Callable[[AgentAction], Any]  # Returns bool or coroutine


class InteractiveAgentLoop:
    """Interactive agent loop that allows user confirmation at each step."""

    def __init__(
        self,
        llm_client: OpenAIClient,
        tool_registry: ToolRegistry,
        system_prompt: str,
        max_iterations: int = 20,
        max_tool_calls_per_iteration: int = 5,
        action_callback: Optional[ActionCallback] = None,
    ):
        """Initialize the interactive agent loop."""
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.max_tool_calls_per_iteration = max_tool_calls_per_iteration
        self.action_callback = action_callback
        self._skip_confirmations = False

    def skip_confirmations(self, skip: bool = True) -> None:
        """Skip all future confirmations (for auto mode)."""
        self._skip_confirmations = skip

    async def _notify_action(self, action: AgentAction) -> bool:
        """Notify callback of an action. Returns whether to proceed."""
        if self._skip_confirmations:
            return True
        if self.action_callback:
            result = self.action_callback(action)
            # Handle both sync and async callbacks
            if asyncio.iscoroutine(result):
                return await result
            return result
        return True

    async def run(self, user_input: str, working_directory: str = ".") -> Dict[str, Any]:
        """
        Run the interactive agent loop.

        Returns:
            Dictionary containing:
            - success: bool
            - result: str (final answer or error message)
            - iterations: int
            - token_usage: dict
            - actions: List[AgentAction] (history of actions)
        """
        # Initialize conversation state
        state = ConversationState(max_iterations=self.max_iterations)
        state.add_system_message(self.system_prompt)
        state.add_user_message(user_input)

        actions_history: List[AgentAction] = []

        logger.info(f"Starting interactive agent loop with input: {user_input[:100]}...")

        # Notify thinking start
        thinking_action = AgentAction(
            type=ActionType.THINKING,
            content="正在分析问题...",
            iteration=state.iteration + 1,
        )
        if not await self._notify_action(thinking_action):
            return {
                "success": False,
                "result": "用户取消了操作",
                "iterations": 0,
                "token_usage": self.llm_client.get_token_usage(),
                "actions": actions_history,
            }

        # Main agent loop
        while not state.is_max_iterations_reached():
            state.increment_iteration()
            current_iteration = state.iteration
            logger.info(f"Iteration {current_iteration}/{self.max_iterations}")

            try:
                # Get LLM response
                content, tool_calls = await self.llm_client.chat_completion(
                    messages=state.get_messages(),
                    tools=self.tool_registry.get_openai_tools(),
                    tool_choice="auto",
                )

                # If no tool calls, we have a final answer
                if not tool_calls:
                    if content:
                        logger.info("Agent provided final answer")
                        final_action = AgentAction(
                            type=ActionType.FINAL_ANSWER,
                            content=content,
                            iteration=current_iteration,
                        )
                        await self._notify_action(final_action)
                        actions_history.append(final_action)

                        return {
                            "success": True,
                            "result": content,
                            "iterations": current_iteration,
                            "token_usage": self.llm_client.get_token_usage(),
                            "actions": actions_history,
                        }
                    else:
                        logger.warning("No content or tool calls in response")
                        continue

                # Add assistant message with tool calls
                state.add_assistant_message(content=content, tool_calls=tool_calls)

                # Limit tool calls per iteration
                if len(tool_calls) > self.max_tool_calls_per_iteration:
                    logger.warning(
                        f"Too many tool calls ({len(tool_calls)}), "
                        f"limiting to {self.max_tool_calls_per_iteration}"
                    )
                    tool_calls = tool_calls[: self.max_tool_calls_per_iteration]

                # Execute tool calls with user confirmation
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args_str = tool_call.function.arguments

                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments: {e}")
                        error_result = ToolResult(
                            success=False,
                            error=f"Error: Invalid tool arguments - {str(e)}"
                        )
                        state.add_tool_result(
                            tool_call.id,
                            tool_name,
                            error_result.to_message(),
                        )
                        continue

                    # Notify about tool call
                    tool_action = AgentAction(
                        type=ActionType.TOOL_CALL,
                        content=f"准备执行工具: {tool_name}",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        iteration=current_iteration,
                    )
                    if not await self._notify_action(tool_action):
                        return {
                            "success": False,
                            "result": "用户取消了工具执行",
                            "iterations": current_iteration,
                            "token_usage": self.llm_client.get_token_usage(),
                            "actions": actions_history,
                        }
                    actions_history.append(tool_action)

                    logger.info(f"Executing tool: {tool_name}")
                    logger.debug(f"Tool arguments: {tool_args}")

                    # Execute the tool
                    result = await self.tool_registry.execute_tool(tool_name, tool_args)

                    # Notify about tool result
                    result_action = AgentAction(
                        type=ActionType.TOOL_RESULT,
                        content="工具执行完成",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_result=result,
                        iteration=current_iteration,
                    )
                    await self._notify_action(result_action)
                    actions_history.append(result_action)

                    # Add tool result to conversation
                    state.add_tool_result(
                        tool_call.id,
                        tool_name,
                        result.to_message(),
                    )

            except Exception as e:
                logger.error(f"Error in agent loop iteration: {str(e)}", exc_info=True)
                error_action = AgentAction(
                    type=ActionType.ERROR,
                    content=f"执行出错: {str(e)}",
                    iteration=current_iteration,
                )
                await self._notify_action(error_action)
                actions_history.append(error_action)

                return {
                    "success": False,
                    "result": f"执行过程中发生错误: {str(e)}",
                    "iterations": current_iteration,
                    "token_usage": self.llm_client.get_token_usage(),
                    "actions": actions_history,
                }

        # Max iterations reached
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        return {
            "success": False,
            "result": f"达到最大迭代次数 ({self.max_iterations})，未能完成分析。",
            "iterations": self.max_iterations,
            "token_usage": self.llm_client.get_token_usage(),
            "actions": actions_history,
        }

    @staticmethod
    async def load_system_prompt(prompt_path: str) -> str:
        """Load system prompt from file."""
        try:
            return await read_file_async(prompt_path)
        except Exception as e:
            logger.error(f"Failed to load system prompt from {prompt_path}: {e}")
            return (
                "You are a code repair agent. Help fix bugs by analyzing code, "
                "identifying root causes, and proposing fixes."
            )
