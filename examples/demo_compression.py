"""
Demo script to show context compression functionality.

This script simulates a long conversation to demonstrate how
the context compression system works.
"""

import asyncio
from claude_bugfix.agent.state_manager import ConversationState
from claude_bugfix.agent.context_compressor import ContextCompressor, CompressionConfig
from claude_bugfix.agent.token_monitor import TokenMonitor


def print_separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_messages(messages, max_chars=200):
    """Print messages with truncation."""
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "") or ""
        name = msg.get("name", "")
        
        if len(content) > max_chars:
            content = content[:max_chars] + "... [truncated]"
        
        prefix = f"[{role}]"
        if name:
            prefix += f" {name}"
        
        print(f"  {i}: {prefix}")
        if content:
            print(f"     {content[:100]}")
    print()


async def demo_no_compression():
    """Demo: Normal conversation without compression."""
    print_separator("Demo 1: Normal Conversation (No Compression)")
    
    config = CompressionConfig(
        token_warning_threshold=50000,
        token_critical_threshold=60000,
    )
    compressor = ContextCompressor(config)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Fix the bug in calculator.py"},
        {"role": "assistant", "content": "I'll help you fix the bug."},
        {"role": "tool", "tool_call_id": "1", "name": "read_file", 
         "content": "def divide(a, b):\n    return a / b"},
        {"role": "assistant", "content": "I see the issue."},
    ]
    
    result = compressor.check_and_compress(messages, iteration=3)
    
    print(f"Original messages: {len(messages)}")
    print(f"Compressed messages: {len(result.messages)}")
    print(f"Compression level: {result.level}")
    print(f"Compression ratio: {result.compression_ratio}")


async def demo_light_compression():
    """Demo: Light compression with many tool results."""
    print_separator("Demo 2: Light Compression (Tool Result Summarization)")
    
    config = CompressionConfig(
        token_warning_threshold=2000,
        token_critical_threshold=3000,
        keep_recent_messages=3,
    )
    compressor = ContextCompressor(config)
    
    messages = [
        {"role": "system", "content": "You are a bug fixing agent."},
        {"role": "user", "content": "Find the memory leak in the server."},
    ]
    
    # Add many exploration messages
    for i in range(15):
        messages.extend([
            {"role": "assistant", "content": f"Let me check file_{i}.py"},
            {"role": "tool", "tool_call_id": str(i), "name": "read_file",
             "content": f"# File {i}\n" + "code\n" * 20 + "# End of file"},
        ])
    
    print(f"Before compression:")
    print(f"  Total messages: {len(messages)}")
    print(f"  Estimated tokens: {compressor.estimator.estimate_messages(messages)}")
    
    result = compressor.check_and_compress(messages, iteration=10, force_level='light')
    
    print(f"\nAfter light compression:")
    print(f"  Total messages: {len(result.messages)}")
    print(f"  Estimated tokens: {result.compressed_token_estimate}")
    print(f"  Compression level: {result.level}")
    print(f"  Messages summarized: {result.messages_summarized}")
    print(f"\nLast 5 messages:")
    print_messages(result.messages[-5:])


async def demo_medium_compression():
    """Demo: Medium compression with exploration summary."""
    print_separator("Demo 3: Medium Compression (Exploration Summary)")
    
    config = CompressionConfig(
        token_warning_threshold=1500,
        token_critical_threshold=2500,
        keep_recent_messages=4,
    )
    compressor = ContextCompressor(config)
    
    messages = [
        {"role": "system", "content": "You are a bug fixing agent."},
        {"role": "user", "content": "Fix the authentication bug."},
    ]
    
    # Add exploration messages with some analysis
    for i in range(20):
        if i == 5:
            messages.append({"role": "assistant", 
                           "content": "I found the root cause! The token validation is missing."})
        elif i == 10:
            messages.append({"role": "assistant",
                           "content": "The problem is in the validate_token function."})
        else:
            messages.extend([
                {"role": "assistant", "content": f"Checking auth module part {i}"},
                {"role": "tool", "tool_call_id": str(i), "name": "read_file" if i % 2 == 0 else "search_codebase",
                 "content": f"Results for operation {i}: " + "data " * 30},
            ])
    
    print(f"Before compression: {len(messages)} messages")
    
    result = compressor.check_and_compress(messages, iteration=15, force_level='medium')
    
    print(f"After medium compression: {len(result.messages)} messages")
    print(f"Compression ratio: {result.compression_ratio:.2f}")
    print(f"\nMessage structure after compression:")
    print_messages(result.messages)


async def demo_aggressive_compression():
    """Demo: Aggressive compression keeping only essentials."""
    print_separator("Demo 4: Aggressive Compression (Essential State Only)")
    
    config = CompressionConfig(
        token_warning_threshold=1000,
        token_critical_threshold=1500,
    )
    compressor = ContextCompressor(config)
    
    messages = [
        {"role": "system", "content": "You are a bug fixing agent."},
        {"role": "user", "content": "Fix the performance issue in the database layer."},
    ]
    
    # Simulate long exploration
    for i in range(30):
        if i == 8:
            messages.append({"role": "assistant",
                           "content": "Root cause identified: Missing index on user_id column."})
        elif i == 15:
            messages.append({"role": "assistant",
                           "content": "The query is doing a full table scan."})
        else:
            messages.extend([
                {"role": "assistant", "content": f"Analysis step {i}: Checking queries"},
                {"role": "tool", "tool_call_id": str(i), "name": "read_file",
                 "content": f"Query analysis {i}: " + "SELECT * FROM " * 10},
            ])
    
    # Add a write operation
    messages.extend([
        {"role": "assistant", "content": "I'll add the missing index."},
        {"role": "tool", "tool_call_id": "write_1", "name": "write_file",
         "content": "Successfully wrote migration file: add_user_id_index.sql"},
    ])
    
    print(f"Before aggressive compression: {len(messages)} messages")
    
    result = compressor.check_and_compress(messages, iteration=18, force_level='aggressive')
    
    print(f"After aggressive compression: {len(result.messages)} messages")
    print(f"Messages removed: {result.messages_removed}")
    print(f"\nAll remaining messages:")
    print_messages(result.messages)


async def demo_token_monitor():
    """Demo: Token monitor alerting."""
    print_separator("Demo 5: Token Monitor Alerts")
    
    monitor = TokenMonitor(
        warning_threshold=100,
        critical_threshold=200,
        max_limit=250,
    )
    
    alerts_triggered = []
    
    def alert_handler(alert):
        alerts_triggered.append(alert)
        print(f"  🔔 [{alert.level.upper()}] {alert.message}")
        print(f"      Suggested action: {alert.suggested_action}")
    
    monitor.add_alert_handler(alert_handler)
    
    # Simulate growing token usage
    token_counts = [50, 80, 110, 150, 180, 220, 260]
    
    print("Simulating token growth:")
    for tokens in token_counts:
        print(f"\n  Current tokens: {tokens}")
        alert = monitor.check_usage(tokens)
        if not alert:
            print("  ✓ No alert")
    
    print(f"\nTotal alerts triggered: {len(alerts_triggered)}")
    
    stats = monitor.get_usage_stats()
    print(f"\nUsage stats:")
    print(f"  Peak: {stats['peak']} tokens")
    print(f"  Average: {stats['average']:.1f} tokens")
    print(f"  Growth rate: {stats['growth_rate']:.1f} tokens/iteration")


async def demo_conversation_state():
    """Demo: Full conversation state with compression."""
    print_separator("Demo 6: ConversationState with Compression")
    
    state = ConversationState(max_iterations=20)
    
    # Setup compression
    config = CompressionConfig(
        token_warning_threshold=800,
        token_critical_threshold=1200,
    )
    compressor = ContextCompressor(config)
    monitor = TokenMonitor(
        warning_threshold=800,
        critical_threshold=1200,
    )
    state.setup_compression(compressor, monitor)
    
    # Build conversation
    state.add_system_message("You are a code repair agent.")
    state.add_user_message("Fix the null pointer exception.")
    
    print(f"Initial state: {state.get_token_estimate()} est. tokens")
    
    # Simulate long exploration
    for i in range(25):
        state.add_assistant_message(f"Exploring codebase part {i}...")
        state.add_tool_result(
            f"call_{i}",
            "read_file",
            f"File content {i}: " + "class Example: pass\n" * 10
        )
    
    print(f"Before compression: {state.get_token_estimate()} est. tokens")
    print(f"Total messages: {len(state.get_messages())}")
    
    # Force compression
    result = state.force_compression(level='medium')
    
    print(f"\nAfter forced compression:")
    print(f"  Level: {result.level}")
    print(f"  Estimated tokens: {result.compressed_token_estimate}")
    print(f"  Messages removed: {result.messages_removed}")
    
    stats = state.get_compression_stats()
    print(f"\nCompression stats:")
    print(f"  Total compressions: {stats['total_compressions']}")
    print(f"  Average ratio: {stats['average_compression_ratio']}")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  Context Compression Demo")
    print("  Showing how agent loop handles long conversations")
    print("=" * 60)
    
    await demo_no_compression()
    await demo_light_compression()
    await demo_medium_compression()
    await demo_aggressive_compression()
    await demo_token_monitor()
    await demo_conversation_state()
    
    print_separator("All Demos Complete")
    print("""
Summary:
--------
1. No compression: Small conversations stay unchanged
2. Light compression: Summarizes tool results, keeps structure
3. Medium compression: Creates exploration summary with key stats
4. Aggressive compression: Keeps only system, user, key findings, and recent context
5. Token monitor: Alerts at different thresholds with suggestions
6. ConversationState: Full integration with automatic compression

For complex bugs that require many iterations, context compression
allows the agent to continue working instead of hitting limits.
""")


if __name__ == "__main__":
    asyncio.run(main())
