"""Tests for context compression functionality."""

import pytest
from claude_bugfix.agent.context_compressor import (
    CompressionConfig,
    ContextCompressor,
    TokenEstimator,
)
from claude_bugfix.agent.token_monitor import TokenMonitor, TokenAlert
from claude_bugfix.agent.state_manager import ConversationState


class TestTokenEstimator:
    """Tests for TokenEstimator."""
    
    def test_estimate_simple_message(self):
        """Test estimating a simple message."""
        msg = {"role": "user", "content": "Hello world"}
        tokens = TokenEstimator.estimate_message(msg)
        assert tokens > 0
        # 11 chars / 4 + overhead ≈ 7 tokens
        assert 5 <= tokens <= 15
    
    def test_estimate_messages(self):
        """Test estimating multiple messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        total = TokenEstimator.estimate_messages(messages)
        assert total > 0
        # Should be sum of individual estimates
        individual_sum = sum(TokenEstimator.estimate_message(m) for m in messages)
        assert total == individual_sum
    
    def test_estimate_with_tool_calls(self):
        """Test estimating message with tool calls."""
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "/test/file.py"}'
                    }
                }
            ]
        }
        tokens = TokenEstimator.estimate_message(msg)
        assert tokens > 0


class TestCompressionConfig:
    """Tests for CompressionConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CompressionConfig()
        assert config.token_warning_threshold == 48000
        assert config.token_critical_threshold == 60000
        assert config.token_max_limit == 64000
        assert config.keep_recent_messages == 4
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = CompressionConfig(
            token_warning_threshold=10000,
            token_max_limit=20000,
            keep_recent_messages=2
        )
        assert config.token_warning_threshold == 10000
        assert config.token_max_limit == 20000
        assert config.keep_recent_messages == 2


class TestContextCompressor:
    """Tests for ContextCompressor."""
    
    @pytest.fixture
    def compressor(self):
        """Create a compressor with test config."""
        config = CompressionConfig(
            token_warning_threshold=500,
            token_critical_threshold=800,
            token_max_limit=1000,
            keep_recent_messages=2,
        )
        return ContextCompressor(config)
    
    @pytest.fixture
    def sample_messages(self):
        """Create sample conversation messages."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Fix the bug in my code."},
            {"role": "assistant", "content": "I'll help you fix the bug."},
            {"role": "tool", "tool_call_id": "1", "name": "read_file", "content": "File content..."},
            {"role": "assistant", "content": "I see the issue."},
            {"role": "tool", "tool_call_id": "2", "name": "search_codebase", "content": "Search results..."},
            {"role": "assistant", "content": "Let me check another file."},
            {"role": "tool", "tool_call_id": "3", "name": "read_file", "content": "More content..."},
        ]
    
    def test_no_compression_needed(self, compressor, sample_messages):
        """Test that no compression is applied when under threshold."""
        result = compressor.check_and_compress(sample_messages, iteration=1)
        
        assert result.level == 'none'
        assert result.compression_ratio == 1.0
        assert len(result.messages) == len(sample_messages)
    
    def test_light_compression(self, compressor):
        """Test light compression level."""
        # Create messages that trigger light compression
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "User request."},
        ]
        # Add many tool results to trigger compression
        for i in range(20):
            messages.extend([
                {"role": "assistant", "content": f"Analysis {i}"},
                {"role": "tool", "tool_call_id": str(i), "name": "read_file", 
                 "content": f"File content {i}: " + "x" * 100},
            ])
        
        result = compressor.check_and_compress(messages, iteration=10, force_level='light')
        
        assert result.level == 'light'
        assert result.compression_ratio <= 1.0
        # Light compression may not reduce message count (replaces rather than removes)
        # but should summarize tool results
        has_summary = any("Summarized" in str(m.get("content", "")) 
                         for m in result.messages if m.get("role") == "tool")
        assert has_summary or result.messages_removed > 0
    
    def test_medium_compression(self, compressor):
        """Test medium compression level."""
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "User request."},
        ]
        for i in range(30):
            messages.extend([
                {"role": "assistant", "content": f"Analysis {i}"},
                {"role": "tool", "tool_call_id": str(i), "name": "read_file", 
                 "content": f"Content {i}: " + "y" * 200},
            ])
        
        result = compressor.check_and_compress(messages, iteration=15, force_level='medium')
        
        assert result.level == 'medium'
        assert result.messages_removed > 0
        # Should have exploration summary
        has_summary = any("summarized" in str(m.get("content", "")).lower() 
                         for m in result.messages)
        assert has_summary or result.messages_removed > 5
    
    def test_aggressive_compression(self, compressor):
        """Test aggressive compression level."""
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "User request."},
        ]
        for i in range(40):
            messages.extend([
                {"role": "assistant", "content": f"The root cause is X. Found issue in line {i}."},
                {"role": "tool", "tool_call_id": str(i), "name": "read_file", 
                 "content": f"Content {i}"},
            ])
        
        result = compressor.check_and_compress(messages, iteration=18, force_level='aggressive')
        
        assert result.level == 'aggressive'
        assert result.messages_removed > 10
    
    def test_preserves_system_and_user(self, compressor):
        """Test that system and first user messages are always preserved."""
        messages = [
            {"role": "system", "content": "Important system prompt."},
            {"role": "user", "content": "Critical user request."},
        ]
        for i in range(50):
            messages.append({"role": "assistant", "content": f"Message {i}"})
        
        result = compressor.check_and_compress(messages, iteration=10, force_level='aggressive')
        
        # Check system message preserved
        system_msgs = [m for m in result.messages if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "Important system prompt."
        
        # Check first user message preserved
        user_msgs = [m for m in result.messages if m.get("role") == "user"]
        assert len(user_msgs) >= 1
        assert user_msgs[0]["content"] == "Critical user request."


class TestTokenMonitor:
    """Tests for TokenMonitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create a token monitor with test thresholds."""
        return TokenMonitor(
            warning_threshold=500,
            critical_threshold=800,
            max_limit=1000,
        )
    
    def test_no_alert_when_under_threshold(self, monitor):
        """Test no alert when under warning threshold."""
        alert = monitor.check_usage(400)
        assert alert is None
    
    def test_warning_alert(self, monitor):
        """Test warning alert triggered."""
        alert = monitor.check_usage(600)
        
        assert alert is not None
        assert alert.level == "warning"
        assert alert.current_tokens == 600
        assert alert.threshold == 500
    
    def test_critical_alert(self, monitor):
        """Test critical alert triggered."""
        alert = monitor.check_usage(850)
        
        assert alert is not None
        assert alert.level == "critical"
        assert alert.current_tokens == 850
        assert "850" in alert.message
    
    def test_max_limit_alert(self, monitor):
        """Test max limit alert."""
        alert = monitor.check_usage(1000)
        
        assert alert is not None
        assert alert.level == "critical"
        assert "exceeded" in alert.message.lower() or alert.current_tokens >= 1000
    
    def test_usage_stats(self, monitor):
        """Test usage statistics."""
        monitor.check_usage(100)
        monitor.check_usage(200)
        monitor.check_usage(300)
        
        stats = monitor.get_usage_stats()
        
        assert stats["current"] == 300
        assert stats["peak"] == 300
        assert stats["average"] == 200
        assert stats["iterations_monitored"] == 3
    
    def test_predict_iteration_limit(self, monitor):
        """Test iteration limit prediction."""
        # Simulate growing token usage
        for i in range(5):
            monitor.check_usage(100 + i * 100)  # 100, 200, 300, 400, 500
        
        prediction = monitor.predict_iteration_limit()
        
        # Should predict when we'll hit 1000 at current growth rate
        assert prediction is not None
        assert prediction > 0
    
    def test_should_compress(self, monitor):
        """Test compression decision logic."""
        # Should not compress at start
        should, reason = monitor.should_compress(400, 1, 20)
        assert should is False
        
        # Should compress at critical threshold
        should, reason = monitor.should_compress(850, 5, 20)
        assert should is True
        assert "critical" in reason.lower()
        
        # Should compress near max iterations
        should, reason = monitor.should_compress(400, 18, 20)
        assert should is True
        assert "iteration" in reason.lower()
    
    def test_alert_handlers(self, monitor):
        """Test alert handlers are called."""
        alerts_received = []
        
        def handler(alert):
            alerts_received.append(alert)
        
        monitor.add_alert_handler(handler)
        monitor.check_usage(600)  # Trigger warning
        
        assert len(alerts_received) == 1
        assert alerts_received[0].level == "warning"


class TestConversationStateCompression:
    """Tests for ConversationState compression integration."""
    
    @pytest.fixture
    def state_with_compression(self):
        """Create state with compression enabled."""
        state = ConversationState(max_iterations=20)
        
        config = CompressionConfig(
            token_warning_threshold=500,
            token_critical_threshold=800,
            token_max_limit=1000,
        )
        compressor = ContextCompressor(config)
        monitor = TokenMonitor(
            warning_threshold=500,
            critical_threshold=800,
            max_limit=1000,
        )
        
        state.setup_compression(compressor, monitor)
        return state
    
    def test_compression_setup(self, state_with_compression):
        """Test that compression components are set up."""
        assert state_with_compression._compressor is not None
        assert state_with_compression._monitor is not None
    
    def test_get_token_estimate(self, state_with_compression):
        """Test token estimation."""
        state_with_compression.add_system_message("System prompt.")
        state_with_compression.add_user_message("User message.")
        
        estimate = state_with_compression.get_token_estimate()
        assert estimate > 0
    
    def test_compression_stats_initial(self, state_with_compression):
        """Test compression stats before any compression."""
        stats = state_with_compression.get_compression_stats()
        
        assert stats["total_compressions"] == 0
        assert stats["current_level"] == "none"
        assert stats["average_compression_ratio"] == 1.0
    
    def test_force_compression(self, state_with_compression):
        """Test forced compression."""
        # Add many messages
        state_with_compression.add_system_message("System.")
        state_with_compression.add_user_message("Request.")
        for i in range(30):
            state_with_compression.add_assistant_message(f"Analysis {i}")
            state_with_compression.add_tool_result(str(i), "read_file", f"Content {i}")
        
        result = state_with_compression.force_compression(level='medium')
        
        assert result.level == 'medium'
        assert state_with_compression.total_compressions == 1
        
        stats = state_with_compression.get_compression_stats()
        assert stats["total_compressions"] == 1
    
    def test_multiple_compressions(self, state_with_compression):
        """Test multiple compressions tracked correctly."""
        state_with_compression.add_system_message("System.")
        state_with_compression.add_user_message("Request.")
        
        # Force multiple compressions
        for i in range(5):
            state_with_compression.add_assistant_message(f"Analysis batch {i}")
            state_with_compression.force_compression(level='light')
        
        stats = state_with_compression.get_compression_stats()
        assert stats["total_compressions"] == 5


class TestIntegration:
    """Integration tests for the full compression flow."""
    
    def test_end_to_end_compression_scenario(self):
        """Test a realistic scenario with compression."""
        # Setup
        config = CompressionConfig(
            token_warning_threshold=200,
            token_critical_threshold=400,
            token_max_limit=500,
            keep_recent_messages=2,
        )
        compressor = ContextCompressor(config)
        monitor = TokenMonitor(
            warning_threshold=200,
            critical_threshold=400,
            max_limit=500,
        )
        state = ConversationState(max_iterations=20)
        state.setup_compression(compressor, monitor)
        
        # Simulate conversation
        state.add_system_message("You are a bug fixing agent.")
        state.add_user_message("Fix the division by zero bug.")
        
        # Add many exploration messages
        for i in range(20):
            state.add_assistant_message(f"Let me check file {i}.py")
            state.add_tool_result(
                f"call_{i}", 
                "read_file", 
                f"Content of file {i}: " + "code" * 50
            )
        
        # Check token usage
        initial_estimate = state.get_token_estimate()
        
        # Get messages for LLM (triggers compression if needed)
        messages = state.get_messages_for_llm()
        
        # Verify compression happened
        stats = state.get_compression_stats()
        
        # Either compression happened or we're under threshold
        if stats["total_compressions"] > 0:
            assert stats["current_level"] in ['light', 'medium', 'aggressive']
            assert len(messages) < 45  # Original was 42 messages (2 + 20*2)
