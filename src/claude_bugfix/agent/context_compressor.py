"""Context compression for managing long agent conversations.

This module provides strategies for compressing conversation context when
token usage grows too large or iterations exceed limits.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """Configuration for context compression."""
    
    # Token thresholds
    token_warning_threshold: int = 48000  # 48K - start light compression
    token_critical_threshold: int = 60000  # 60K - aggressive compression
    token_max_limit: int = 64000  # 64K - hard limit
    
    # Iteration thresholds  
    iteration_warning_threshold: int = 12
    iteration_critical_threshold: int = 17
    
    # Compression settings
    keep_recent_messages: int = 4  # Always keep last N messages full
    summarize_batch_size: int = 6  # Group this many messages for summary
    
    # Message priorities (higher = more important to keep)
    priority_system: int = 100
    priority_user_original: int = 90
    priority_tool_error: int = 80
    priority_file_write: int = 75
    priority_key_finding: int = 70
    priority_assistant_analysis: int = 50
    priority_tool_result: int = 30
    priority_file_read: int = 20
    priority_list_search: int = 10


@dataclass
class CompressionResult:
    """Result of a compression operation."""
    messages: List[Dict[str, Any]]
    original_token_estimate: int
    compressed_token_estimate: int
    compression_ratio: float
    messages_removed: int
    messages_summarized: int
    level: str  # 'none', 'light', 'medium', 'aggressive'
    summary: str


class TokenEstimator:
    """Simple token estimator for messages."""
    
    # Rough estimate: 1 token ≈ 4 characters for English text
    CHARS_PER_TOKEN = 4
    
    @classmethod
    def estimate_message(cls, message: Dict[str, Any]) -> int:
        """Estimate tokens for a single message."""
        content = message.get("content", "") or ""
        # Count tool calls if present
        tool_calls = message.get("tool_calls", [])
        tool_estimate = 0
        for tc in tool_calls:
            if isinstance(tc, dict):
                tool_estimate += len(tc.get("function", {}).get("arguments", "")) // cls.CHARS_PER_TOKEN
                tool_estimate += len(tc.get("function", {}).get("name", "")) // cls.CHARS_PER_TOKEN
            else:
                tool_estimate += 50  # Rough estimate for object-based tool calls
        
        return len(content) // cls.CHARS_PER_TOKEN + tool_estimate + 4  # +4 for message overhead
    
    @classmethod
    def estimate_messages(cls, messages: List[Dict[str, Any]]) -> int:
        """Estimate total tokens for message list."""
        return sum(cls.estimate_message(m) for m in messages)


class ContextCompressor:
    """Compresses conversation context to manage token usage."""
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        """Initialize compressor with configuration."""
        self.config = config or CompressionConfig()
        self.estimator = TokenEstimator()
    
    def check_and_compress(
        self, 
        messages: List[Dict[str, Any]], 
        current_iteration: int,
        force_level: Optional[str] = None
    ) -> CompressionResult:
        """
        Check token usage and compress if necessary.
        
        Args:
            messages: Current message list
            current_iteration: Current iteration count
            force_level: Force specific compression level ('light', 'medium', 'aggressive')
            
        Returns:
            CompressionResult with compressed messages and metadata
        """
        original_tokens = self.estimator.estimate_messages(messages)
        
        # Determine compression level
        level = self._determine_compression_level(
            original_tokens, current_iteration, force_level
        )
        
        if level == 'none':
            return CompressionResult(
                messages=messages.copy(),
                original_token_estimate=original_tokens,
                compressed_token_estimate=original_tokens,
                compression_ratio=1.0,
                messages_removed=0,
                messages_summarized=0,
                level='none',
                summary="No compression needed"
            )
        
        logger.info(f"Applying {level} compression to context "
                   f"({original_tokens} est. tokens, iter {current_iteration})")
        
        # Apply compression based on level
        if level == 'light':
            compressed = self._light_compression(messages)
        elif level == 'medium':
            compressed = self._medium_compression(messages)
        else:  # aggressive
            compressed = self._aggressive_compression(messages)
        
        compressed_tokens = self.estimator.estimate_messages(compressed)
        
        result = CompressionResult(
            messages=compressed,
            original_token_estimate=original_tokens,
            compressed_token_estimate=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            messages_removed=len(messages) - len(compressed),
            messages_summarized=self._count_summarized(messages, compressed),
            level=level,
            summary=f"Applied {level} compression: {len(messages)} -> {len(compressed)} messages, "
                   f"~{original_tokens} -> ~{compressed_tokens} tokens"
        )
        
        logger.info(f"Compression complete: {result.summary}")
        return result
    
    def _determine_compression_level(
        self, 
        tokens: int, 
        iteration: int,
        force_level: Optional[str]
    ) -> str:
        """Determine appropriate compression level."""
        if force_level:
            return force_level
            
        # Check critical thresholds first
        if tokens >= self.config.token_critical_threshold or iteration >= self.config.iteration_critical_threshold:
            return 'aggressive'
        elif tokens >= self.config.token_warning_threshold or iteration >= self.config.iteration_warning_threshold:
            return 'medium'
        elif tokens >= self.config.token_warning_threshold * 0.7:
            return 'light'
        
        return 'none'
    
    def _light_compression(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Light compression: Summarize oldest tool results while keeping structure."""
        if len(messages) <= self.config.keep_recent_messages + 2:
            return messages.copy()
        
        # Always keep system and first user message
        preserved = []
        to_compress = []
        
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            # Always preserve system and first user message
            if role == "system" or (role == "user" and i == 1):
                preserved.append((i, msg))
            # Keep recent messages
            elif i >= len(messages) - self.config.keep_recent_messages:
                preserved.append((i, msg))
            else:
                to_compress.append((i, msg))
        
        # Compress tool results in the middle section
        compressed_middle = self._summarize_tool_results(to_compress)
        
        # Merge preserved and compressed
        all_messages = preserved + compressed_middle
        all_messages.sort(key=lambda x: x[0])  # Sort by original index
        
        return [msg for _, msg in all_messages]
    
    def _medium_compression(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Medium compression: Create exploration summary."""
        if len(messages) <= self.config.keep_recent_messages + 2:
            return self._light_compression(messages)
        
        # Identify sections
        system_msg = None
        user_request = None
        recent_messages = []
        middle_section = []
        
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            if role == "system":
                system_msg = msg
            elif role == "user" and user_request is None:
                user_request = msg
            elif i >= len(messages) - self.config.keep_recent_messages:
                recent_messages.append(msg)
            else:
                middle_section.append(msg)
        
        # Generate exploration summary from middle section
        exploration_summary = self._generate_exploration_summary(middle_section)
        
        # Build compressed context
        result = []
        if system_msg:
            result.append(system_msg)
        if user_request:
            result.append(user_request)
        
        # Add compression notice and summary
        result.append({
            "role": "assistant",
            "content": f"[Context Compression Applied]\n\n"
                      f"Due to conversation length, earlier exploration has been summarized:\n\n"
                      f"{exploration_summary}\n\n"
                      f"I will continue from the current state shown in the recent messages below."
        })
        
        result.extend(recent_messages)
        return result
    
    def _aggressive_compression(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggressive compression: Keep only essential state."""
        system_msg = None
        user_request = None
        recent_messages = []
        
        # Extract key findings and modified files from full history
        key_findings = self._extract_key_findings(messages)
        modified_files = self._extract_modified_files(messages)
        
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            if role == "system":
                system_msg = msg
            elif role == "user" and user_request is None:
                user_request = msg
            elif i >= len(messages) - max(2, self.config.keep_recent_messages // 2):
                recent_messages.append(msg)
        
        result = []
        if system_msg:
            result.append(system_msg)
        if user_request:
            result.append(user_request)
        
        # Build minimal state representation
        state_content = "[AGGRESSIVE CONTEXT COMPRESSION]\n\n"
        state_content += f"Token limit approached. Preserving essential state:\n\n"
        
        if modified_files:
            state_content += f"**Files Modified:**\n" + "\n".join(f"- {f}" for f in modified_files) + "\n\n"
        
        if key_findings:
            state_content += f"**Key Findings:**\n" + "\n".join(f"- {f}" for f in key_findings[:5]) + "\n\n"
        
        state_content += "Continuing with recent context..."
        
        result.append({
            "role": "assistant", 
            "content": state_content
        })
        result.extend(recent_messages)
        
        return result
    
    def _summarize_tool_results(
        self, 
        messages: List[Tuple[int, Dict[str, Any]]]
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """Summarize consecutive tool result messages."""
        if not messages:
            return []
        
        result = []
        current_batch = []
        batch_indices = []
        
        for idx, msg in messages:
            role = msg.get("role", "")
            
            if role == "tool":
                current_batch.append(msg)
                batch_indices.append(idx)
            else:
                # Flush current batch if exists
                if current_batch:
                    summary_idx = batch_indices[len(batch_indices) // 2]
                    summary_msg = self._create_tool_summary(current_batch)
                    result.append((summary_idx, summary_msg))
                    current_batch = []
                    batch_indices = []
                result.append((idx, msg))
        
        # Flush remaining batch
        if current_batch:
            summary_idx = batch_indices[len(batch_indices) // 2]
            summary_msg = self._create_tool_summary(current_batch)
            result.append((summary_idx, summary_msg))
        
        return result
    
    def _create_tool_summary(self, tool_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a summary of multiple tool result messages."""
        tool_names = set()
        total_chars = 0
        
        for msg in tool_messages:
            name = msg.get("name", "unknown")
            tool_names.add(name)
            content = msg.get("content", "") or ""
            total_chars += len(content)
        
        summary_content = (
            f"[Summarized {len(tool_messages)} tool results] "
            f"Tools used: {', '.join(sorted(tool_names))}. "
            f"Total output: ~{total_chars // self.estimator.CHARS_PER_TOKEN} tokens. "
            f"(Details available if needed)"
        )
        
        return {
            "role": "tool",
            "tool_call_id": tool_messages[-1].get("tool_call_id", "summary"),
            "name": "batch_summary",
            "content": summary_content
        }
    
    def _generate_exploration_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a summary of exploration activities."""
        files_read = set()
        files_written = set()
        searches_performed = []
        errors_encountered = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            name = msg.get("name", "")
            
            if role == "tool":
                if name == "read_file":
                    # Try to extract filename from result or tool call
                    if "Reading file:" in content:
                        files_read.add(content.split("Reading file:")[1].strip().split("\n")[0])
                elif name == "write_file":
                    if "Writing file:" in content:
                        files_written.add(content.split("Writing file:")[1].strip().split("\n")[0])
                elif name == "search_codebase":
                    if len(searches_performed) < 3:  # Limit to avoid too long summary
                        searches_performed.append("search query")
                elif "error" in content.lower() or "Error" in content:
                    if len(errors_encountered) < 3:
                        errors_encountered.append(content[:100])
        
        summary_parts = []
        if files_read:
            summary_parts.append(f"📄 Explored {len(files_read)} files")
        if files_written:
            summary_parts.append(f"✏️ Modified: {', '.join(files_written)}")
        if searches_performed:
            summary_parts.append(f"🔍 Performed {len(searches_performed)} searches")
        if errors_encountered:
            summary_parts.append(f"⚠️ Encountered {len(errors_encountered)} errors/warnings")
        
        return "\n".join(f"• {part}" for part in summary_parts) if summary_parts else "Exploration in progress..."
    
    def _extract_key_findings(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract key findings from message history."""
        findings = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            
            if role == "assistant" and content:
                # Look for analysis patterns
                if any(kw in content.lower() for kw in ["root cause", "identified", "found", "issue is", "problem is"]):
                    # Extract first sentence
                    first_sentence = content.split('.')[0][:150]
                    if len(first_sentence) > 30:  # Only substantial findings
                        findings.append(first_sentence)
        
        return findings[-5:]  # Return last 5 findings
    
    def _extract_modified_files(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract list of files that were modified."""
        modified = set()
        
        for msg in messages:
            name = msg.get("name", "")
            content = msg.get("content", "") or ""
            
            if name in ["write_file", "replace_in_file"]:
                if "path" in content:
                    try:
                        result = json.loads(content)
                        if isinstance(result, dict) and "path" in result:
                            modified.add(result["path"])
                    except:
                        pass
                # Try to extract from text
                if "Successfully" in content and "path" in content.lower():
                    lines = content.split("\n")
                    for line in lines:
                        if "/" in line or "." in line[:50]:
                            modified.add(line.strip()[:100])
        
        return sorted(list(modified))[:10]  # Limit to 10 files
    
    def _count_summarized(
        self, 
        original: List[Dict[str, Any]], 
        compressed: List[Dict[str, Any]]
    ) -> int:
        """Count how many messages were summarized/removed."""
        return max(0, len(original) - len(compressed))
    
    def get_compression_suggestion(self, current_tokens: int, max_tokens: int) -> str:
        """Get a human-readable suggestion for compression."""
        ratio = current_tokens / max_tokens
        
        if ratio < 0.6:
            return "Context healthy"
        elif ratio < 0.75:
            return "Consider light compression soon"
        elif ratio < 0.9:
            return "Compression recommended"
        else:
            return "Urgent: Compress or reset context"
