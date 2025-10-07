"""
Cephiq Lite - Minimal AI Agent Runtime

A focused, learning-friendly implementation of the Envelope v2.1 protocol.
~1,500 lines. Zero bloat. Maximum clarity.
"""

from .agent import Agent
from .config import AgentConfig
from .envelope import validate_envelope, normalize_envelope, parse_llm_response

__version__ = "0.1.0"
__all__ = ["Agent", "AgentConfig", "validate_envelope", "normalize_envelope", "parse_llm_response"]
