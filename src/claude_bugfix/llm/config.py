"""LLM configuration management."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class LLMConfig(BaseModel):
    """Configuration for the LLM client."""

    api_key: str = Field(..., description="OpenAI API key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )
    model: str = Field(default="gpt-4", description="Model name to use")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Temperature for generation")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens to generate")
    timeout: int = Field(default=60, gt=0, description="API request timeout in seconds")

    @classmethod
    def from_env(cls, model: Optional[str] = None) -> "LLMConfig":
        """Create configuration from environment variables."""
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4")

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
        )

    class Config:
        """Pydantic config."""

        frozen = True
