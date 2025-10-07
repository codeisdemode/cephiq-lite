"""
Configuration for Cephiq Lite agents
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for an agent instance"""

    # LLM settings
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.3
    max_tokens_per_call: int = 8000

    # Budget limits
    max_cycles: int = 100
    max_total_tokens: int = 100000
    max_time_seconds: Optional[int] = None

    # Tool execution
    mcp_server_path: Optional[str] = None
    mcp_server_url: Optional[str] = None
    tool_timeout: int = 30  # seconds

    # Behavior
    auto_approve: bool = False  # Auto-approve confirmations
    enable_multi_tool: bool = True  # Enable parallel tool execution
    enable_confidence: bool = True  # Include confidence scores

    # Prompt customization
    custom_system_prompt: Optional[str] = None

    # Debug
    verbose: bool = False
    log_file: Optional[str] = None

    def __post_init__(self):
        """Validate configuration"""
        if not (0 <= self.temperature <= 1):
            raise ValueError("temperature must be between 0 and 1")

        if self.max_cycles < 1:
            raise ValueError("max_cycles must be at least 1")

        if not self.mcp_server_path and not self.mcp_server_url:
            # Default to built-in tools
            self.mcp_server_path = "builtin"
