"""Core agent loop for orchestrating LLM and tool interactions."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from claude_bugfix.agent.state_manager import ConversationState
from claude_bugfix.agent.context_compressor import ContextCompressor, CompressionConfig
from claude_bugfix.agent.token_monitor import TokenMonitor
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
        enable_compression: bool = True,
        compression_config: Optional[CompressionConfig] = None,
    ):
        """Initialize the agent loop.
        
        Args:
            llm_client: OpenAI client for LLM interactions
            tool_registry: Registry of available tools
            system_prompt: System prompt for the agent
            max_iterations: Maximum number of iterations
            max_tool_calls_per_iteration: Maximum tool calls per iteration
            enable_compression: Whether to enable context compression
            compression_config: Configuration for compression
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.max_tool_calls_per_iteration = max_tool_calls_per_iteration
        self.enable_compression = enable_compression
        
        # Initialize compression components
        self.compression_config = compression_config or CompressionConfig()
        self.compressor: Optional[ContextCompressor] = None
        self.token_monitor: Optional[TokenMonitor] = None
        
        if enable_compression:
            self.compressor = ContextCompressor(self.compression_config)
            self.token_monitor = TokenMonitor(
                warning_threshold=self.compression_config.token_warning_threshold,
                critical_threshold=self.compression_config.token_critical_threshold,
                max_limit=self.compression_config.token_max_limit,
            )

    async def run(self, user_input: str, working_directory: str = ".") -> Dict[str, Any]:
        """
        Run the agent loop with the given user input.

        Returns:
            Dictionary containing:
            - success: bool
            - result: str (final answer or error message)
            - iterations: int
            - token_usage: dict
            - compression_stats: dict (if compression enabled)
        """
        # Initialize conversation state
        state = ConversationState(max_iterations=self.max_iterations)
        state.add_system_message(self.system_prompt)
        state.add_user_message(user_input)
        
        # Setup compression if enabled
        if self.enable_compression and self.compressor and self.token_monitor:
            state.setup_compression(self.compressor, self.token_monitor)
            logger.info("Context compression enabled")

        logger.info(f"Starting agent loop with user input: {user_input[:100]}...")

        # Main agent loop
        while not state.is_max_iterations_reached():
            state.increment_iteration()
            logger.info(f"Iteration {state.iteration}/{self.max_iterations}")

            try:
                # Check if we need to compress before calling LLM
                if self.enable_compression:
                    # This will trigger compression if needed
                    messages = state.get_messages_for_llm()
                    current_tokens = self.compressor.estimator.estimate_messages(messages)
                    
                    # Log token status
                    if state.iteration % 3 == 0 or current_tokens > 30000:
                        logger.info(f"Estimated tokens: ~{current_tokens:,}")
                else:
                    messages = state.get_messages()

                # Get LLM response
                content, tool_calls = await self.llm_client.chat_completion(
                    messages=messages,
                    tools=self.tool_registry.get_openai_tools(),
                    tool_choice="auto",
                )

                # If no tool calls, we have a final answer
                if not tool_calls:
                    if content:
                        logger.info("Agent provided final answer")
                        result = {
                            "success": True,
                            "result": content,
                            "iterations": state.iteration,
                            "token_usage": self.llm_client.get_token_usage(),
                        }
                        
                        if self.enable_compression:
                            result["compression_stats"] = state.get_compression_stats()
                            result["final_token_estimate"] = state.get_token_estimate()
                        
                        return result
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
                error_result = {
                    "success": False,
                    "result": f"Error during execution: {str(e)}",
                    "iterations": state.iteration,
                    "token_usage": self.llm_client.get_token_usage(),
                }
                
                if self.enable_compression:
                    error_result["compression_stats"] = state.get_compression_stats()
                
                return error_result

        # Max iterations reached - try aggressive compression and continue if possible
        if self.enable_compression and state.total_compressions == 0:
            logger.warning(f"Max iterations ({self.max_iterations}) reached, trying aggressive compression...")
            
            compression_result = state.force_compression(level='aggressive')
            
            if compression_result.level != 'none':
                # Give it a few more iterations with compressed context
                extra_iterations = min(5, self.max_iterations // 4)
                state.max_iterations += extra_iterations
                
                logger.info(f"Extended max iterations by {extra_iterations} after compression")
                
                # Continue the loop
                while not state.is_max_iterations_reached():
                    state.increment_iteration()
                    logger.info(f"Extended iteration {state.iteration}/{state.max_iterations}")
                    
                    try:
                        messages = state.get_messages_for_llm()
                        
                        content, tool_calls = await self.llm_client.chat_completion(
                            messages=messages,
                            tools=self.tool_registry.get_openai_tools(),
                            tool_choice="auto",
                        )

                        if not tool_calls and content:
                            logger.info("Agent provided final answer after compression")
                            result = {
                                "success": True,
                                "result": content + "\n\n[Note: Context compression was applied during this run]",
                                "iterations": state.iteration,
                                "token_usage": self.llm_client.get_token_usage(),
                                "compression_stats": state.get_compression_stats(),
                                "final_token_estimate": state.get_token_estimate(),
                            }
                            return result
                        elif tool_calls:
                            state.add_assistant_message(content=content, tool_calls=tool_calls)
                            
                            # Execute tool calls (limited)
                            for tool_call in tool_calls[:self.max_tool_calls_per_iteration]:
                                result = await self.tool_registry.execute_tool(
                                    tool_call.function.name, 
                                    json.loads(tool_call.function.arguments)
                                )
                                state.add_tool_result(
                                    tool_call.id,
                                    tool_call.function.name,
                                    result.to_message(),
                                )
                    
                    except Exception as e:
                        logger.error(f"Error in extended iteration: {e}")
                        break

        # Max iterations truly reached
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        final_result = {
            "success": False,
            "result": f"Maximum iterations ({self.max_iterations}) reached without finding a solution. "
            "The agent may need more iterations or a different approach.",
            "iterations": state.iteration,
            "token_usage": self.llm_client.get_token_usage(),
        }
        
        if self.enable_compression:
            final_result["compression_stats"] = state.get_compression_stats()
            final_result["final_token_estimate"] = state.get_token_estimate()
        
        return final_result
    
    def get_compression_status(self) -> Optional[Dict[str, Any]]:
        """Get current compression configuration status."""
        if not self.enable_compression:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "config": {
                "token_warning_threshold": self.compression_config.token_warning_threshold,
                "token_critical_threshold": self.compression_config.token_critical_threshold,
                "token_max_limit": self.compression_config.token_max_limit,
                "keep_recent_messages": self.compression_config.keep_recent_messages,
            }
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
