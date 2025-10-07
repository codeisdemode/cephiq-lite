"""
Interactive Chat CLI for Cephiq Lite

Provides a simple REPL to talk to the agent across multiple turns.

Usage:
  python -m cephiq_lite.chat_cli
"""
from __future__ import annotations

import argparse
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .agent import Agent
from .config import AgentConfig


def print_banner(model: str, auto: bool) -> None:
    print("=" * 60)
    print("CEPHIQ LITE - CHAT CLI")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Auto-approve: {'ON' if auto else 'OFF'}")
    print("Commands: /auto on|off, /quit")
    print("=" * 60)


def build_config(args: argparse.Namespace, custom_prompt: Optional[str]) -> AgentConfig:
    return AgentConfig(
        model=args.model,
        temperature=args.temperature,
        max_tokens_per_call=args.max_tokens,
        max_cycles=args.cycles,
        max_total_tokens=args.total_tokens,
        max_time_seconds=args.timeout,
        mcp_server_path=args.mcp_server,
        tool_timeout=args.tool_timeout,
        enable_multi_tool=not args.no_multi_tool,
        enable_confidence=not args.no_confidence,
        auto_approve=not args.no_auto_approve,
        verbose=args.verbose,
        log_file=args.log_file,
        custom_system_prompt=custom_prompt,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cephiq Lite - Interactive Chat CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cephiq_lite.chat_cli
  python -m cephiq_lite.chat_cli --model claude-sonnet-4-20250514 --verbose
        """
    )

    # LLM settings
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514", help="LLM model name")
    parser.add_argument("--temperature", type=float, default=0.3, help="Temperature (0-1)")
    parser.add_argument("--max-tokens", type=int, default=8000, help="Max tokens per call")

    # Budget
    parser.add_argument("--cycles", type=int, default=50, help="Max cycles per message")
    parser.add_argument("--total-tokens", type=int, default=100000, help="Max total tokens")
    parser.add_argument("--timeout", type=int, help="Max execution time in seconds")

    # Tools
    parser.add_argument("--mcp-server", type=str, help="Path to MCP server executable (builtins if omitted)")
    parser.add_argument("--tool-timeout", type=int, default=30, help="Tool execution timeout (s)")
    parser.add_argument("--no-multi-tool", action="store_true", help="Disable parallel multi-tool execution")

    # Behavior
    parser.add_argument("--no-confidence", action="store_true", help="Disable confidence scoring")
    parser.add_argument("--no-auto-approve", action="store_true", help="Disable auto-approve (default ON)")

    # Display / debug
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--log-file", type=str, help="Log file path")

    # System prompt override
    parser.add_argument("--system-prompt", type=str, help="Path to custom system prompt file")

    args = parser.parse_args()

    # Read custom prompt if provided
    custom_prompt = None
    if args.system_prompt:
        try:
            custom_prompt = Path(args.system_prompt).read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading system prompt file: {e}", file=sys.stderr)
            sys.exit(1)

    # Build config and agent
    try:
        config = build_config(args, custom_prompt)
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    agent = Agent(config)

    print_banner(config.model, config.auto_approve)

    # Simple REPL
    while True:
        try:
            user = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user:
            continue
        if user.lower() in {"/q", "/quit", "quit", "exit", "/exit"}:
            print("Goodbye.")
            break
        if user.lower().startswith("/auto"):
            parts = user.split()
            if len(parts) >= 2 and parts[1].lower() in {"on", "off"}:
                on = parts[1].lower() == "on"
                agent.config.auto_approve = on
                print(f"Auto-approve set to: {'ON' if on else 'OFF'}")
            else:
                print("Usage: /auto on|off")
            continue

        # Append user message to history for context (best-effort)
        agent.history.append({
            "type": "user_message",
            "timestamp": time.time(),
            "text": user
        })

        # Run one turn with the user's input as the goal/topic
        try:
            result = agent.run(user)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            continue

        final = result.get("final_envelope", {})
        state = final.get("state")

        if state == "reply":
            utterance = (final.get("conversation") or {}).get("utterance", "")
            print(f"Agent> {utterance}")
        elif state == "confirm":
            info = final.get("confirm", {})
            action = info.get("action", "Proceed with action")
            print(f"Agent needs confirmation: {action}")
            print("Tip: toggle /auto on to auto-approve and re-ask.")
        elif state == "clarify":
            info = final.get("clarify", {})
            q = info.get("question", "Need clarification")
            print(f"Agent needs clarification: {q}")
        elif state == "error":
            err = final.get("error", {})
            print(f"Agent error: {err.get('error_message', 'Unknown error')}")
        else:
            # Generic fallback
            print(f"Agent finished in state: {state}")


if __name__ == "__main__":
    main()

