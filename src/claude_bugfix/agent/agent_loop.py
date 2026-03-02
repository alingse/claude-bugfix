"""Core agent loop for orchestrating LLM and tool interactions."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from claude_bugfix.agent.state_manager import ConversationState
from claude_bugfix.llm.client import OpenAIClient
from claude_bugfix.tools.registry import ToolRegistry
from claude_bugfix.utils.file_utils import read_file_async

logger = logging.getLogger(__name__)


class AgentLoop:
    """Main agent loop that orchestrates LLM and tool interactions."""

    def __init__(
        self,
        llm_client: OpenAIClient,
        tool_registry: ToolRegistry,
        system_prompt: str,
        max_iterations: int = 20,
        max_tool_calls_per_iteration: int = 5,
    ):
        """Initialize the agent loop."""
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.max_tool_calls_per_iteration = max_tool_calls_per_iteration

    async def run(self, user_input: str, working_directory: str = ".") -> Dict[str, Any]:
        """
        Run the agent loop with the given user input.

        Returns:
            Dictionary containing:
            - success: bool
            - result: str (final answer or error message)
            - iterations: int
            - token_usage: dict
        """
        # Initialize conversation state
        state = ConversationState(max_iterations=self.max_iterations)
        state.add_system_message(self.system_prompt)
        state.add_user_message(user_input)

        logger.info(f"Starting agent loop with user input: {user_input[:100]}...")

        # Main agent loop
        while not state.is_max_iterations_reached():
            state.increment_iteration()
            logger.info(f"Iteration {state.iteration}/{self.max_iterations}")

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
                        return {
                            "success": True,
                            "result": content,
                            "iterations": state.iteration,
                            "token_usage": self.llm_client.get_token_usage(),
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

                # Execute tool calls
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args_str = tool_call.function.arguments

                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments: {e}")
                        state.add_tool_result(
                            tool_call.id,
                            tool_name,
                            f"Error: Invalid tool arguments - {str(e)}",
                        )
                        continue

                    logger.info(f"Executing tool: {tool_name}")
                    logger.debug(f"Tool arguments: {tool_args}")

                    # Execute the tool
                    result = await self.tool_registry.execute_tool(tool_name, tool_args)

                    # Add tool result to conversation
                    state.add_tool_result(
                        tool_call.id,
                        tool_name,
                        result.to_message(),
                    )

            except Exception as e:
                logger.error(f"Error in agent loop iteration: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "result": f"Error during execution: {str(e)}",
                    "iterations": state.iteration,
                    "token_usage": self.llm_client.get_token_usage(),
                }

        # Max iterations reached
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        return {
            "success": False,
            "result": f"Maximum iterations ({self.max_iterations}) reached without finding a solution. "
            "The agent may need more iterations or a different approach.",
            "iterations": state.iteration,
            "token_usage": self.llm_client.get_token_usage(),
        }

    @staticmethod
    async def load_system_prompt(prompt_path: str) -> str:
        """Load system prompt from file."""
        try:
            return await read_file_async(prompt_path)
        except Exception as e:
            logger.error(f"Failed to load system prompt from {prompt_path}: {e}")
            # Return a basic fallback prompt
            return (
                "You are a code repair agent. Help fix bugs by analyzing code, "
                "identifying root causes, and proposing fixes."
            )
