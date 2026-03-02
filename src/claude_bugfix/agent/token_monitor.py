"""Token usage monitoring and alerting for agent loop."""

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenAlert:
    """Token usage alert."""
    level: str  # 'info', 'warning', 'critical'
    message: str
    current_tokens: int
    threshold: int
    suggested_action: str


class TokenMonitor:
    """Monitors token usage and triggers alerts/actions."""
    
    def __init__(
        self,
        warning_threshold: int = 48000,
        critical_threshold: int = 60000,
        max_limit: int = 64000,
    ):
        """Initialize token monitor.
        
        Args:
            warning_threshold: Token count to trigger warning
            critical_threshold: Token count to trigger critical alert
            max_limit: Maximum allowed tokens before forced action
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.max_limit = max_limit
        
        self.token_history: List[int] = []
        self.alert_handlers: List[Callable[[TokenAlert], None]] = []
        self.last_alert_level: Optional[str] = None
    
    def add_alert_handler(self, handler: Callable[[TokenAlert], None]) -> None:
        """Add a handler to be called when alerts are triggered."""
        self.alert_handlers.append(handler)
    
    def check_usage(self, current_tokens: int, context: str = "") -> Optional[TokenAlert]:
        """Check current token usage and generate alert if needed.
        
        Args:
            current_tokens: Current estimated token count
            context: Additional context for the alert
            
        Returns:
            TokenAlert if threshold crossed, None otherwise
        """
        self.token_history.append(current_tokens)
        
        # Determine alert level
        level = None
        threshold = 0
        message = ""
        suggested_action = ""
        
        if current_tokens >= self.max_limit:
            level = "critical"
            threshold = self.max_limit
            message = f"Token limit exceeded: {current_tokens:,} >= {self.max_limit:,}"
            suggested_action = "Aggressive compression or context reset required immediately"
        elif current_tokens >= self.critical_threshold:
            level = "critical"
            threshold = self.critical_threshold
            message = f"Critical token usage: {current_tokens:,} / {self.max_limit:,}"
            suggested_action = "Apply aggressive context compression now"
        elif current_tokens >= self.warning_threshold:
            level = "warning"
            threshold = self.warning_threshold
            message = f"High token usage: {current_tokens:,} / {self.max_limit:,}"
            suggested_action = "Consider light to medium context compression"
        
        # Only alert if level changed or is critical
        if level and (level != self.last_alert_level or level == "critical"):
            alert = TokenAlert(
                level=level,
                message=message,
                current_tokens=current_tokens,
                threshold=threshold,
                suggested_action=suggested_action
            )
            
            self._trigger_alert(alert)
            self.last_alert_level = level
            return alert
        
        return None
    
    def _trigger_alert(self, alert: TokenAlert) -> None:
        """Trigger alert through all handlers."""
        log_method = getattr(logger, alert.level)
        log_method(f"[TokenMonitor] {alert.message} - {alert.suggested_action}")
        
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def get_usage_stats(self) -> dict:
        """Get token usage statistics."""
        if not self.token_history:
            return {
                "current": 0,
                "peak": 0,
                "average": 0,
                "growth_rate": 0,
            }
        
        current = self.token_history[-1]
        peak = max(self.token_history)
        average = sum(self.token_history) / len(self.token_history)
        
        # Calculate growth rate (tokens per iteration)
        growth_rate = 0
        if len(self.token_history) >= 3:
            recent = self.token_history[-3:]
            growth_rate = (recent[-1] - recent[0]) / 2
        
        return {
            "current": current,
            "peak": peak,
            "average": average,
            "growth_rate": growth_rate,
            "iterations_monitored": len(self.token_history),
        }
    
    def predict_iteration_limit(self) -> Optional[int]:
        """Predict at which iteration we might hit the limit."""
        if len(self.token_history) < 3:
            return None
        
        stats = self.get_usage_stats()
        growth_rate = stats["growth_rate"]
        current = stats["current"]
        
        if growth_rate <= 0:
            return None
        
        remaining = self.max_limit - current
        iterations_until_limit = remaining / growth_rate
        
        return int(iterations_until_limit)
    
    def reset(self) -> None:
        """Reset monitor state."""
        self.token_history.clear()
        self.last_alert_level = None
    
    def should_compress(self, current_tokens: int, current_iteration: int, 
                       max_iterations: int) -> tuple[bool, str]:
        """Determine if compression should be triggered.
        
        Returns:
            Tuple of (should_compress, reason)
        """
        # Check token thresholds
        if current_tokens >= self.critical_threshold:
            return True, f"Critical token threshold ({self.critical_threshold:,})"
        
        if current_tokens >= self.warning_threshold:
            # Also check if we're in later iterations
            iteration_ratio = current_iteration / max_iterations
            if iteration_ratio > 0.6:
                return True, f"High tokens ({current_tokens:,}) and late iteration ({current_iteration}/{max_iterations})"
        
        # Check iteration-based triggers
        if current_iteration >= max_iterations - 3:
            return True, f"Approaching max iterations ({current_iteration}/{max_iterations})"
        
        return False, ""
