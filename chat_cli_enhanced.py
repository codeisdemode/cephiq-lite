#!/usr/bin/env python3
"""
Enhanced Chat CLI for Cephiq Orchestrator
Cleaner, more intuitive interface inspired by Claudio
"""

import os
import sys
import json
import readline
from pathlib import Path
from typing import Any, Dict, Optional

# Make orchestrator package importable when running from repo root
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
ORCH_DIR = os.path.join(REPO_ROOT, "orchestrator")
if ORCH_DIR not in sys.path:
    sys.path.insert(0, ORCH_DIR)

try:
    # Import orchestrator utilities
    from runner import run_one_cycle, load_json, ENVELOPE_SCHEMA_PATH, WORKSPACE_PATH  # type: ignore
    from decide_next import decide_next  # type: ignore
    from debug import get_logger  # type: ignore
except Exception:
    # Fallback to package-style import if executed as a module
    from orchestrator.runner import run_one_cycle, load_json, ENVELOPE_SCHEMA_PATH, WORKSPACE_PATH  # type: ignore
    from orchestrator.decide_next import decide_next  # type: ignore
    from orchestrator.debug import get_logger  # type: ignore

logger = get_logger("chat_cli")

class EnhancedChatCLI:
    def __init__(self, max_turn_cycles: int = 3) -> None:
        self.ctx: Dict[str, Any] = {"goal": os.getenv("GOAL", "CLI Chat Session"), "history": [], "mcp_servers": {}}
        self.workspace: Dict[str, Any] = {}
        self.schema_path = ENVELOPE_SCHEMA_PATH
        self.max_turn_cycles = max_turn_cycles
        self.pending_tool: Optional[Dict[str, Any]] = None

        # Command history
        self.history_file = Path("logs/cli_history.txt")
        self.history_file.parent.mkdir(exist_ok=True)
        self._load_history()

    def _load_history(self):
        """Load command history"""
        try:
            readline.read_history_file(str(self.history_file))
        except FileNotFoundError:
            pass

    def _save_history(self):
        """Save command history"""
        try:
            readline.write_history_file(str(self.history_file))
        except:
            pass

    def load_workspace(self) -> None:
        try:
            self.workspace = load_json(WORKSPACE_PATH)
        except Exception as e:
            print(f"Failed to load workspace: {e}\nExpected at: {WORKSPACE_PATH}")
            raise SystemExit(1)

    def print_welcome(self) -> None:
        """Print welcome banner"""
        print("=" * 60)
        print("Cephiq Orchestrator - Enhanced Chat Interface")
        print("=" * 60)

        # Show model and transport info
        model_name = ((self.workspace.get('agent') or {}).get('model') or {}).get('name', 'gpt-5')
        transport = (
            "SSE" if os.getenv("USE_MCP_SSE") == "1" else
            "STDIO" if os.getenv("USE_MCP_STDIO") == "1" else
            "DIRECT" if os.getenv("USE_DIRECT_MCP") == "1" else
            "OPENAI_MCP" if os.getenv("USE_OPENAI_MCP") == "1" else
            "(none)"
        )

        print(f"Model: {model_name}")
        print(f"Transport: {transport}")
        print("-" * 60)
        print("Type 'help' for commands or just start chatting!")
        print("Type 'quit' to exit")
        print("=" * 60)

    def _show_help(self):
        """Show help information"""
        print("""
Available commands:
  help     - Show this help message
  status   - Show current session status
  clear    - Clear conversation history
  plan     - Show current plan (if any)
  approve  - Approve last high-risk tool
  deny     - Deny last high-risk tool
  quit     - Exit the chat

Just type your message to start a conversation with the agent.
""")

    def _show_status(self):
        """Show current session status"""
        goal = self.ctx.get("goal", "No goal set")
        status = self.ctx.get("status", "ready")
        history_count = len(self.ctx.get("history", []))

        print(f"\nSession Status:")
        print(f"Goal: {goal}")
        print(f"Status: {status}")
        print(f"History events: {history_count}")

        # Show pending tool if any
        if self.pending_tool:
            tool_name = self.pending_tool.get("tool", "unknown")
            print(f"Pending approval: {tool_name}")

    def render_envelope(self, env: Dict[str, Any]) -> None:
        """Render envelope in a cleaner format"""
        et = env.get("type")

        if et == "message":
            msg = env.get("message", "")
            print(f"\nAssistant: {msg}")

        elif et == "plan":
            steps = env.get("steps", [])
            print(f"\nPlan ({len(steps)} steps):")
            for i, step in enumerate(steps, 1):
                step_str = json.dumps(step, ensure_ascii=False) if not isinstance(step, str) else step
                print(f"  {i}. {step_str}")

        elif et == "tool":
            tname = env.get("tool")
            args = env.get("arguments", {})
            print(f"\nTool: {tname}")
            if args:
                args_str = json.dumps(args, ensure_ascii=False, indent=2)
                print(f"Arguments:\n{args_str}")

        elif et == "ask_human":
            reason = env.get("reason", "")
            print(f"\nApproval Needed: {reason}")

        elif et == "wait":
            ev = env.get("event_type") or f"duration_ms={env.get('duration_ms')}"
            print(f"\nWaiting for: {ev}")

        elif et == "finish":
            res = env.get("result", {})
            print(f"\nFinished: {json.dumps(res, ensure_ascii=False, indent=2)}")

    def render_last_observation(self) -> None:
        """Render last observation"""
        obs = self.ctx.get("last_observation")
        if obs is None:
            return

        if isinstance(obs, dict) and obs.get("text"):
            text = str(obs.get("text"))
            if len(text) > 400:
                text = text[:400] + "..."
            print(f"\nObservation: {text}")
        else:
            obs_str = json.dumps(obs, ensure_ascii=False, indent=2)
            if len(obs_str) > 400:
                obs_str = obs_str[:400] + "..."
            print(f"\nObservation:\n{obs_str}")

    def maybe_render_waiting(self) -> None:
        """Show waiting status if needed"""
        if self.ctx.get("status") == "waiting":
            hist = self.ctx.get("history") or []
            if hist:
                last = hist[-1]
                if isinstance(last, dict) and last.get("type") == "approval_request":
                    reason = last.get("reason", "High-risk tool needs approval")
                    print(f"\nAwaiting Approval: {reason}")
                    print("Use 'approve' or 'deny' to respond")

    def approve_pending(self, approved: bool) -> None:
        """Handle tool approval"""
        if not self.pending_tool:
            print("No pending tool to approve/deny.")
            return

        tool_name = self.pending_tool["tool"]

        if approved:
            env = {
                "type": "tool",
                "tool": tool_name,
                "arguments": dict(self.pending_tool.get("arguments") or {}),
                "brief_rationale": "User approved."
            }
            env["arguments"]["approved"] = True
            self.ctx["envelope"] = env
            print(f"Approved: {tool_name}")
            self.ctx = run_one_cycle(self.ctx)
            self.render_last_observation()
        else:
            # Deny by emitting a message
            self.ctx["envelope"] = {
                "type": "message",
                "message": f"Action '{tool_name}' denied by user.",
                "brief_rationale": "Respect user choice."
            }
            self.ctx = run_one_cycle(self.ctx)
            print(f"Denied: {tool_name}")

        self.pending_tool = None

    def step_once(self) -> bool:
        """Execute one decision step"""
        ok, env_or_err = decide_next(self.ctx, self.workspace, self.schema_path)
        if not ok:
            errs = env_or_err if isinstance(env_or_err, list) else [str(env_or_err)]
            print(f"\nError: {', '.join(errs)}")
            return False

        env = env_or_err  # type: ignore[assignment]
        self.ctx["envelope"] = env
        self.render_envelope(env)

        # Cache potential tool for approval
        self.pending_tool = env if env.get("type") == "tool" else None

        # Execute one cycle
        self.ctx = run_one_cycle(self.ctx)
        self.render_last_observation()
        self.maybe_render_waiting()
        return True

    def run_turn(self, user_text: str) -> None:
        """Run a conversation turn"""
        # Put user input where the prompt builder can see it
        self.ctx["last_observation"] = {"type": "user_message", "text": user_text}

        print("\nProcessing...")
        cycles = 0

        while cycles < self.max_turn_cycles:
            if not self.step_once():
                break

            status = self.ctx.get("status")
            if status in {"waiting", "completed"}:
                break

            cycles += 1

    def show_plan(self) -> None:
        """Show current plan"""
        plan = self.ctx.get("plan")
        if not plan:
            print("No plan in context.")
            return

        print(f"\n📋 Current Plan ({len(plan)} steps):")
        for i, step in enumerate(plan, 1):
            step_str = json.dumps(step, ensure_ascii=False) if not isinstance(step, str) else step
            print(f"  {i}. {step_str}")

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.ctx["history"] = []
        print("Conversation history cleared.")

    def run(self) -> None:
        """Main run loop"""
        self.load_workspace()
        self.print_welcome()

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break

                elif user_input.lower() == 'help':
                    self._show_help()
                    continue

                elif user_input.lower() == 'status':
                    self._show_status()
                    continue

                elif user_input.lower() == 'clear':
                    self.clear_history()
                    continue

                elif user_input.lower() == 'plan':
                    self.show_plan()
                    continue

                elif user_input.lower() == 'approve':
                    self.approve_pending(True)
                    continue

                elif user_input.lower() == 'deny':
                    self.approve_pending(False)
                    continue

                # Normal chat message
                self.run_turn(user_input)

            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error("Error in chat loop: %s", e)

        # Save command history
        self._save_history()


def main() -> None:
    """Main entry point"""
    cli = EnhancedChatCLI()
    cli.run()


if __name__ == "__main__":
    main()