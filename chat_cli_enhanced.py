#!/usr/bin/env python3
"""
Enhanced Chat CLI for Cephiq Orchestrator
Cleaner, more intuitive interface inspired by Claudio
"""

import os
import sys
import json
import readline
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import time

try:
    import msvcrt  # Windows key detection
except ImportError:
    msvcrt = None  # Non-Windows systems

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
    def __init__(self, max_turn_cycles: int = None) -> None:
        self.ctx: Dict[str, Any] = {"goal": os.getenv("GOAL", "CLI Chat Session"), "history": [], "mcp_servers": {}, "todo_list": []}
        self.workspace: Dict[str, Any] = {}
        self.schema_path = ENVELOPE_SCHEMA_PATH
        # Allow override via env for quick tuning
        env_cycles = os.getenv("MAX_TURN_CYCLES") or os.getenv("MAX_CYCLES")
        try:
            self.max_turn_cycles = int(env_cycles) if env_cycles else max_turn_cycles
        except Exception:
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

    def _inject_mcp_tools(self) -> None:
        """Inject allowed MCP tools from mcpServers.json into workspace (no keyword filtering)."""
        try:
            import json
            from pathlib import Path

            # Find mcpServers.json
            here = Path(__file__).resolve().parent / "orchestrator"
            mcp_servers_path = here / "mcpServers.json"

            if not mcp_servers_path.exists():
                logger.debug("mcpServers.json not found at %s", mcp_servers_path)
                return

            # Load MCP server config
            with open(mcp_servers_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)

            # Extract all allowed tools
            discovered_tools = []
            for server in mcp_config.get("servers", []):
                allowed_tools = server.get("allowed_tools", [])
                for tool_name in allowed_tools:
                    discovered_tools.append({
                        "name": tool_name,
                        "mode": "mcp",
                        "description": "",
                        "risk": {"level": "unknown"}
                    })

            # Inject into workspace tools
            if "tools" not in self.workspace:
                self.workspace["tools"] = []

            # Add workflow tools to existing tools
            existing_names = {t.get("name") for t in self.workspace["tools"]}
            for tool in discovered_tools:
                if tool["name"] not in existing_names:
                    self.workspace["tools"].append(tool)
                    logger.debug("Injected MCP tool: %s", tool["name"])

        except Exception as e:
            logger.error("Failed to inject workflow tools: %s", e)

    def load_workspace(self) -> None:
        try:
            self.workspace = load_json(WORKSPACE_PATH)
            # Inject MCP tools from server config
            self._inject_mcp_tools()
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
        print("Press ESC during agent execution to cancel and return to CLI")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        print(f"Logging: {log_level} (file: debug.log). Set LOG_LEVEL=DEBUG for verbose logs.")
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
        if not isinstance(env, dict):
            logger.error("render_envelope received non-dict: %s", type(env))
            print(f"\nRender error: envelope is {type(env)}, not dict")
            return

        et = env.get("state") or env.get("type")  # Support both schema formats
        logger.debug("Envelope decided: state=%s", et)

        if et == "message":
            # Handle both envelope formats
            msg = env.get("message", "")
            if not msg and "conversation" in env:
                msg = env["conversation"].get("utterance", "")
            print(f"\nAssistant: {msg}")

        elif et == "plan":
            plan_obj = env.get("plan", {})
            root_task = plan_obj.get("root_task", "")
            steps = plan_obj.get("steps", [])
            print(f"\nPlan ({len(steps)} steps):")
            if root_task:
                print(f"Goal: {root_task}")
            for i, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    step_desc = step.get("description", str(step))
                    step_id = step.get("step_id", i)
                    print(f"  {step_id}. {step_desc}")
                else:
                    print(f"  {i}. {step}")

        elif et == "tool":
            tname = env.get("tool", {}).get("name") if isinstance(env.get("tool"), dict) else env.get("tool")
            args = env.get("tool", {}).get("arguments", {}) if isinstance(env.get("tool"), dict) else env.get("arguments", {})
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
            summary = env.get("finish", {}).get("summary", "Task completed")
            print(f"\n[OK] Task Completed: {summary}")
            if res:
                print(f"Result: {json.dumps(res, ensure_ascii=False, indent=2)}")

    def render_last_observation(self) -> None:
        """Render last observation"""
        obs = self.ctx.get("last_observation")
        logger.debug("Render last_observation present=%s", obs is not None)
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

    def _handle_goal_todo_updates(self, envelope: Dict[str, Any]) -> None:
        """Handle goal and todo updates from envelope meta section"""
        meta = envelope.get("meta", {})

        # Handle goal update
        if "goal_update" in meta:
            goal_update = meta["goal_update"]
            if isinstance(goal_update, dict):
                new_goal = goal_update.get("new_goal")
                reason = goal_update.get("reason", "")
                if new_goal and new_goal != self.ctx.get("goal"):
                    old_goal = self.ctx.get("goal", "")
                    self.ctx["goal"] = new_goal
                    print(f"\n[GOAL] Goal updated: {old_goal} -> {new_goal}")
                    if reason:
                        print(f"   Reason: {reason}")
                    logger.info("Goal updated: %s -> %s", old_goal, new_goal)

        # Handle todo update
        if "todo_update" in meta:
            todo_update = meta["todo_update"]
            if isinstance(todo_update, dict):
                action = todo_update.get("action", "add")
                todo_item = todo_update.get("todo", {})
                reason = todo_update.get("reason", "")

                if action == "add" and todo_item:
                    todo_id = todo_item.get("id") or f"todo_{len(self.ctx.get('todo_list', [])) + 1}"

                    # Check if todo already exists
                    existing_todos = self.ctx.get("todo_list", [])
                    existing_ids = [t.get("id") for t in existing_todos if isinstance(t, dict)]

                    if todo_id not in existing_ids:
                        # Create new todo with enhanced fields
                        new_todo = {
                            "id": todo_id,
                            "content": todo_item.get("content", ""),
                            "status": todo_item.get("status", "pending"),
                            "priority": todo_item.get("priority", "medium"),
                            "related_files": todo_item.get("related_files", []),
                            "notes": todo_item.get("notes", ""),
                            "dependencies": todo_item.get("dependencies", [])
                        }

                        # Add timestamps
                        current_time = datetime.utcnow().isoformat() + "Z"
                        new_todo["created_at"] = todo_item.get("created_at", current_time)
                        new_todo["updated_at"] = todo_item.get("updated_at", current_time)

                        if "todo_list" not in self.ctx:
                            self.ctx["todo_list"] = []
                        self.ctx["todo_list"].append(new_todo)

                        content = new_todo["content"]
                        status = new_todo["status"]
                        priority = new_todo["priority"]

                        print(f"\n📝 Todo added: {content} ({status}, priority: {priority})")
                        if new_todo.get("related_files"):
                            print(f"   Files: {', '.join(new_todo['related_files'])}")
                        if new_todo.get("notes"):
                            print(f"   Notes: {new_todo['notes']}")
                        if reason:
                            print(f"   Reason: {reason}")
                        logger.info("Todo added: %s", content)

                elif action == "complete" and todo_item:
                    todo_id = todo_item.get("id")
                    if todo_id and "todo_list" in self.ctx:
                        for todo in self.ctx["todo_list"]:
                            if isinstance(todo, dict) and todo.get("id") == todo_id:
                                todo["status"] = "completed"
                                # Update timestamp if provided
                                if todo_item.get("updated_at"):
                                    todo["updated_at"] = todo_item["updated_at"]

                                content = todo.get("content", "")
                                print(f"\n✅ Todo completed: {content}")
                                if todo.get("related_files"):
                                    print(f"   Files: {', '.join(todo['related_files'])}")
                                if reason:
                                    print(f"   Reason: {reason}")
                                logger.info("Todo completed: %s", content)
                                break

                elif action == "update" and todo_item:
                    todo_id = todo_item.get("id")
                    if todo_id and "todo_list" in self.ctx:
                        for todo in self.ctx["todo_list"]:
                            if isinstance(todo, dict) and todo.get("id") == todo_id:
                                # Update fields that are provided
                                update_fields = []
                                if "content" in todo_item:
                                    todo["content"] = todo_item["content"]
                                    update_fields.append("content")
                                if "status" in todo_item:
                                    todo["status"] = todo_item["status"]
                                    update_fields.append("status")
                                if "priority" in todo_item:
                                    todo["priority"] = todo_item["priority"]
                                    update_fields.append("priority")
                                if "related_files" in todo_item:
                                    todo["related_files"] = todo_item["related_files"]
                                    update_fields.append("related_files")
                                if "notes" in todo_item:
                                    todo["notes"] = todo_item["notes"]
                                    update_fields.append("notes")
                                if "dependencies" in todo_item:
                                    todo["dependencies"] = todo_item["dependencies"]
                                    update_fields.append("dependencies")

                                # Update timestamp
                                todo["updated_at"] = datetime.utcnow().isoformat() + "Z"

                                print(f"\n📝 Todo updated: {todo.get('content', '')}")
                                print(f"   Updated fields: {', '.join(update_fields)}")
                                if todo.get("related_files"):
                                    print(f"   Files: {', '.join(todo['related_files'])}")
                                if todo.get("notes"):
                                    print(f"   Notes: {todo['notes']}")
                                if reason:
                                    print(f"   Reason: {reason}")
                                logger.info("Todo updated: %s", todo.get("content", ""))
                                break

                elif action == "remove" and todo_item:
                    todo_id = todo_item.get("id")
                    if todo_id and "todo_list" in self.ctx:
                        self.ctx["todo_list"] = [t for t in self.ctx["todo_list"]
                                                if not (isinstance(t, dict) and t.get("id") == todo_id)]
                        print(f"\n🗑️ Todo removed: {todo_id}")
                        if reason:
                            print(f"   Reason: {reason}")
                        logger.info("Todo removed: %s", todo_id)

    def step_once(self) -> bool:
        """Execute one decision step"""
        import time
        t0 = time.perf_counter()
        logger.debug("decide_next start; status=%s; history_len=%d", self.ctx.get("status"), len(self.ctx.get("history") or []))
        ok, env_or_err = decide_next(self.ctx, self.workspace, self.schema_path)
        if not ok:
            errs = env_or_err if isinstance(env_or_err, list) else [str(env_or_err)]
            print(f"\nError: {', '.join(errs)}")
            logger.error("decide_next failed: %s", errs)
            return False

        env = env_or_err  # type: ignore[assignment]

        # Add safety check for envelope format
        if not isinstance(env, dict):
            logger.error("Envelope is not a dict: %s (type: %s)", env, type(env))
            print(f"\nEnvelope format error: expected dict, got {type(env)}")
            return False

        self.ctx["envelope"] = env
        self.render_envelope(env)

        # Cache potential tool for approval
        env_state = env.get("state") or env.get("type")
        self.pending_tool = env if env_state == "tool" else None

        # Handle goal and todo updates before executing cycle
        self._handle_goal_todo_updates(env)

        # Execute one cycle
        t1 = time.perf_counter()
        logger.debug("decide_next duration_ms=%.1f", (t1 - t0) * 1000)

        try:
            self.ctx = run_one_cycle(self.ctx)
            t2 = time.perf_counter()
            logger.debug("run_one_cycle duration_ms=%.1f", (t2 - t1) * 1000)
            self.render_last_observation()
            self.maybe_render_waiting()

            # Use the LLM-controlled continue field instead of automatic logic
            meta = env.get("meta", {})
            should_continue = meta.get("continue", True)  # Default to True for safety

            if not should_continue:
                logger.debug("LLM requested to stop conversation cycle")
                return "stop_cycling"
            else:
                logger.debug("LLM requested to continue conversation cycle")
                return True
        except Exception as cycle_error:
            logger.error("run_one_cycle failed: %s", cycle_error)
            print(f"\nCycle execution error: {cycle_error}")
            return False

    def run_turn(self, user_text: str) -> None:
        """Run a conversation turn"""
        # Reset status for new user input
        if "status" in self.ctx and self.ctx["status"] == "completed":
            self.ctx["status"] = None

        # Put user input where the prompt builder can see it
        self.ctx["last_observation"] = {"type": "user_message", "text": user_text}

        print("\nProcessing... (Press ESC to cancel)")
        cycles = 0
        logger.info("User input: %s", user_text)

        while True:
            # Check for ESC key press before each step
            if self._check_esc_key():
                print("\n[ESC] Agent execution cancelled by user")
                break

            step_result = self.step_once()
            if not step_result or step_result == "stop_cycling":
                break

            status = self.ctx.get("status")
            if status in {"waiting", "completed"}:
                break

            cycles += 1

            # Safety check: prevent infinite loops with a very high limit
            if self.max_turn_cycles and cycles >= self.max_turn_cycles:
                logger.warning("Reached maximum turn cycles (%d), stopping for safety", self.max_turn_cycles)
                break

        logger.debug("turn complete status=%s cycles=%d", self.ctx.get("status"), cycles)

    def show_plan(self) -> None:
        """Show current plan"""
        plan = self.ctx.get("plan")
        if not plan:
            print("No plan in context.")
            return

        if isinstance(plan, dict):
            # New envelope format with nested plan object
            root_task = plan.get("root_task", "")
            steps = plan.get("steps", [])
            print(f"\n📋 Current Plan ({len(steps)} steps):")
            if root_task:
                print(f"Goal: {root_task}")
            for i, step in enumerate(steps, 1):
                if isinstance(step, dict):
                    step_desc = step.get("description", str(step))
                    step_id = step.get("step_id", i)
                    print(f"  {step_id}. {step_desc}")
                else:
                    print(f"  {i}. {step}")
        elif isinstance(plan, list):
            # Legacy format with direct steps array
            print(f"\n📋 Current Plan ({len(plan)} steps):")
            for i, step in enumerate(plan, 1):
                step_str = json.dumps(step, ensure_ascii=False) if not isinstance(step, str) else step
                print(f"  {i}. {step_str}")
        else:
            print(f"\nPlan: {plan}")

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
                print(f"\n[ERROR] Error: {e}")
                logger.error("Error in chat loop: %s", e)

        # Save command history
        self._save_history()

    def _check_esc_key(self) -> bool:
        """Check if ESC key is pressed (Windows only)"""
        if msvcrt:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                # ESC key is 27 in decimal
                if key == b'\x1b':
                    return True

        # For non-Windows systems, we'll use a simpler approach
        # This won't work perfectly but provides basic functionality
        if not msvcrt:
            # Try to use select for Unix-like systems
            try:
                import select
                import sys
                # Check if there's input available on stdin
                if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    char = sys.stdin.read(1)
                    if char == '\x1b':  # ESC character
                        return True
            except (ImportError, Exception):
                # Fallback: can't detect key presses on this system
                pass

        return False


def main() -> None:
    """Main entry point"""
    cli = EnhancedChatCLI()
    cli.run()


if __name__ == "__main__":
    main()
