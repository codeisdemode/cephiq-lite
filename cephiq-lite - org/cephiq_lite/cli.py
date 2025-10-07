"""
CLI - Command-line interface for Cephiq Lite

Provides simple command-line interaction with the agent
"""
import argparse
import sys
import json
from pathlib import Path
from typing import Optional
from .agent import Agent
from .config import AgentConfig


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Cephiq Lite - Minimal autonomous agent runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cephiq_lite "Create hello.txt with Hello World"
  python -m cephiq_lite "List all Python files" --model claude-opus-4-20250514
  python -m cephiq_lite "Refactor main.py" --cycles 50 --verbose
  python -m cephiq_lite --goal-file task.txt --output result.json
        """
    )

    # Goal input
    goal_group = parser.add_mutually_exclusive_group(required=True)
    goal_group.add_argument(
        "goal",
        nargs="?",
        help="Goal/task description (inline)"
    )
    goal_group.add_argument(
        "--goal-file",
        type=str,
        help="Read goal from file"
    )

    # LLM settings
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="LLM model name (default: claude-sonnet-4-20250514)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="Temperature (0-1, default: 0.3)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Max tokens per LLM call (default: 8000)"
    )

    # Budget settings
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="Max decision cycles (default: 100)"
    )
    parser.add_argument(
        "--total-tokens",
        type=int,
        default=100000,
        help="Max total tokens (default: 100000)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Max execution time in seconds"
    )

    # Tool settings
    parser.add_argument(
        "--mcp-server",
        type=str,
        help="Path to MCP server executable (uses built-in tools if not specified)"
    )
    parser.add_argument(
        "--tool-timeout",
        type=int,
        default=30,
        help="Tool execution timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--no-multi-tool",
        action="store_true",
        help="Disable parallel multi-tool execution"
    )

    # Behavior settings
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve confirmations"
    )
    parser.add_argument(
        "--no-confidence",
        action="store_true",
        help="Disable confidence scoring"
    )

    # Output settings
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (show agent decisions)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Save result to JSON file"
    )
    parser.add_argument(
        "--history",
        type=str,
        help="Save full history to JSON file"
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (final result only)"
    )

    # Debug settings
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug mode (verbose + log file)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path"
    )

    # System prompt
    parser.add_argument(
        "--system-prompt",
        type=str,
        help="Path to custom system prompt file"
    )

    args = parser.parse_args()

    # Read goal
    if args.goal:
        goal = args.goal
    elif args.goal_file:
        try:
            goal = Path(args.goal_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Error reading goal file: {e}", file=sys.stderr)
            sys.exit(1)

    # Read custom system prompt if provided
    custom_prompt = None
    if args.system_prompt:
        try:
            custom_prompt = Path(args.system_prompt).read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading system prompt file: {e}", file=sys.stderr)
            sys.exit(1)

    # Build config
    try:
        config = AgentConfig(
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
            auto_approve=args.auto_approve,
            verbose=args.verbose or args.debug,
            log_file=args.log_file,
            custom_system_prompt=custom_prompt
        )
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print header (unless quiet mode)
    if not args.quiet:
        print("="*60)
        print("CEPHIQ LITE")
        print("="*60)
        print(f"Goal: {goal[:100]}{'...' if len(goal) > 100 else ''}")
        print(f"Model: {config.model}")
        print(f"Max cycles: {config.max_cycles}")
        print("="*60)
        print()

    # Run agent
    try:
        agent = Agent(config)
        result = agent.run(goal)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nAgent error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Display result
    if not args.quiet:
        print("\n" + "="*60)
        print("RESULT")
        print("="*60)

    success = result["success"]
    final_envelope = result["final_envelope"]
    stats = result["stats"]

    if not args.quiet:
        print(f"Success: {success}")
        print(f"State: {final_envelope.get('state')}")
        print(f"Cycles: {stats['cycles']}")
        print(f"Duration: {stats['duration_seconds']}s")

    # Show final message
    state = final_envelope.get("state")

    if state == "reply":
        utterance = final_envelope.get("conversation", {}).get("utterance", "")
        if not args.quiet:
            print(f"\nAgent: {utterance}")
        else:
            print(utterance)

    elif state == "error":
        error_data = final_envelope.get("error", {})
        error_msg = error_data.get("error_message", "Unknown error")
        print(f"\nError: {error_msg}", file=sys.stderr)

    elif state == "clarify":
        clarify_data = final_envelope.get("clarify", {})
        question = clarify_data.get("question", "Need input")
        print(f"\nAgent needs clarification: {question}")

    elif state == "confirm":
        confirm_data = final_envelope.get("confirm", {})
        action = confirm_data.get("action", "Action pending")
        print(f"\nAgent needs confirmation: {action}")

    # Save output if requested
    if args.output:
        try:
            output_data = {
                "success": success,
                "final_envelope": final_envelope,
                "stats": stats
            }
            Path(args.output).write_text(
                json.dumps(output_data, indent=2),
                encoding="utf-8"
            )
            if not args.quiet:
                print(f"\nResult saved to: {args.output}")
        except Exception as e:
            print(f"Error saving output: {e}", file=sys.stderr)

    # Save history if requested
    if args.history:
        try:
            history_data = {
                "goal": goal,
                "config": {
                    "model": config.model,
                    "max_cycles": config.max_cycles
                },
                "history": result["history"],
                "stats": stats
            }
            Path(args.history).write_text(
                json.dumps(history_data, indent=2),
                encoding="utf-8"
            )
            if not args.quiet:
                print(f"History saved to: {args.history}")
        except Exception as e:
            print(f"Error saving history: {e}", file=sys.stderr)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
