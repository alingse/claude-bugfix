"""Logging configuration for the application."""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "claude_bugfix",
    level: int = logging.INFO,
    verbose: bool = False,
) -> logging.Logger:
    """Set up and configure a logger."""
    logger = logging.getLogger(name)

    # Set level
    if verbose:
        level = logging.DEBUG
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(f"claude_bugfix.{name}")
    return logging.getLogger("claude_bugfix")
