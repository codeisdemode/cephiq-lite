#!/usr/bin/env python
from __future__ import annotations

import os
import sys
import json
from typing import Any, Dict, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except Exception as e:
    print("This CLI requires 'rich'. Install with: pip install rich", file=sys.stderr)
    raise


# Make orchestrator package importable when running from repo root
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
ORCH_DIR = os.path.join(REPO_ROOT, "orchestrator")
if ORCH_DIR not in sys.path:
    sys.path.insert(0, ORCH_DIR)

try:
    # Import orchestrator utilities
    from runner import run_one_cycle, load_json, ENVELOPE_SCHEMA_PATH, WORKSPACE_PATH  # type: ignore
    from decide_next import decide_next  # type: ignore
except Exception:
    # Fallback to package-style import if executed as a module
    from orchestrator.runner import run_one_cycle, load_json, ENVELOPE_SCHEMA_PATH, WORKSPACE_PATH  # type: ignore
    from orchestrator.decide_next import decide_next  # type: ignore


console = Console()


class ChatCLI:
    def __init__(self, max_turn_cycles: int = 3) -> None:
        self.ctx: Dict[str, Any] = {"goal": os.getenv("GOAL", "CLI Chat Session"), "history": [], "mcp_servers": {}}
        self.workspace: Dict[str, Any] = {}
        self.schema_path = ENVELOPE_SCHEMA_PATH
        self.max_turn_cycles = max_turn_cycles
        self.pending_tool: Optional[Dict[str, Any]] = None

    def load_workspace(self) -> None:
        try:
            self.workspace = load_json(WORKSPACE_PATH)
        except Exception as e:
            console.print(Panel(f"Failed to load workspace: {e}\nExpected at: {WORKSPACE_PATH}", title="Workspace Error", style="red"))
            raise SystemExit(1)

    def print_welcome(self) -> None:
        console.print(Panel(
            """
[bold blue]Cephiq Orchestrator Chat[/bold blue]

Type to chat. Commands:
- /help       Show help
- /approve    Approve last high-risk tool
- /deny       Deny last high-risk tool
- /plan       Show current plan (if any)
- /stats      Show session stats
- /exit       Quit
""".strip(), title="Chat UI", expand=False
        ))

        transport = (
            "SSE" if os.getenv("USE_MCP_SSE") == "1" else
            "STDIO" if os.getenv("USE_MCP_STDIO") == "1" else
            "DIRECT" if os.getenv("USE_DIRECT_MCP") == "1" else
            "OPENAI_MCP" if os.getenv("USE_OPENAI_MCP") == "1" else
            "(none)"
        )
        console.print(f"Transport: {transport}    Model: {((self.workspace.get('agent') or {}).get('model') or {}).get('name', 'gpt-5')}")

    def render_envelope(self, env: Dict[str, Any]) -> None:
        et = env.get("type")
        if et == "message":
            msg = env.get("message", "")
            console.print(Panel(msg, title="assistant", style="cyan"))
        elif et == "plan":
            steps = env.get("steps", [])
            table = Table(title="Plan", show_lines=False)
            table.add_column("#", style="cyan", width=4)
            table.add_column("Step", style="green")
            for i, s in enumerate(steps, 1):
                table.add_row(str(i), json.dumps(s, ensure_ascii=False) if not isinstance(s, str) else s)
            console.print(table)
        elif et == "tool":
            tname = env.get("tool")
            args = env.get("arguments", {})
            pretty = json.dumps(args, ensure_ascii=False, indent=2)
            console.print(Panel(pretty, title=f"tool: {tname}", style="magenta"))
        elif et == "ask_human":
            reason = env.get("reason", "")
            console.print(Panel(reason, title="Approval Needed", style="yellow"))
        elif et == "wait":
            ev = env.get("event_type") or f"duration_ms={env.get('duration_ms')}"
            console.print(Panel(f"Waiting for: {ev}", title="Wait", style="yellow"))
        elif et == "finish":
            res = json.dumps(env.get("result"), ensure_ascii=False, indent=2)
            console.print(Panel(res, title="Finished", style="green"))

    def render_last_observation(self) -> None:
        obs = self.ctx.get("last_observation")
        if obs is None:
            return
        # Show a compact summary
        if isinstance(obs, dict) and obs.get("text") and len(obs.get("text")) > 0:
            text = str(obs.get("text"))
            if len(text) > 600:
                text = text[:600] + "..."
            console.print(Panel(text, title="Observation", style="white"))
        else:
            pretty = json.dumps(obs, ensure_ascii=False, indent=2)
            console.print(Panel(pretty, title="Observation", style="white"))

    def maybe_render_waiting(self) -> None:
        if self.ctx.get("status") == "waiting":
            # Look for last approval request in history
            hist = self.ctx.get("history") or []
            if hist:
                last = hist[-1]
                if isinstance(last, dict) and last.get("type") == "approval_request":
                    reason = last.get("reason", "High-risk tool needs approval")
                    console.print(Panel(reason, title="Awaiting Approval (/approve or /deny)", style="yellow"))

    def approve_pending(self, approved: bool) -> None:
        if not self.pending_tool:
            console.print("No pending tool to approve/deny.")
            return
        env = {"type": "tool", "tool": self.pending_tool["tool"], "arguments": dict(self.pending_tool.get("arguments") or {}), "brief_rationale": "User decision."}
        if approved:
            env["arguments"]["approved"] = True
        else:
            # Deny by emitting a message and clearing pending
            self.ctx["envelope"] = {"type": "message", "message": "Action denied by user.", "brief_rationale": "Respect user choice."}
            self.ctx = run_one_cycle(self.ctx)
            self.pending_tool = None
            return
        # Execute the approved tool
        self.ctx["envelope"] = env
        console.print(Panel(json.dumps(env["arguments"], indent=2), title=f"Approved: {env['tool']}", style="green"))
        self.ctx = run_one_cycle(self.ctx)
        self.render_last_observation()
        self.pending_tool = None

    def step_once(self) -> bool:
        ok, env_or_err = decide_next(self.ctx, self.workspace, self.schema_path)
        if not ok:
            errs = env_or_err if isinstance(env_or_err, list) else [str(env_or_err)]
            console.print(Panel("\n".join(errs), title="decide_next error", style="red"))
            return False
        env = env_or_err  # type: ignore[assignment]
        self.ctx["envelope"] = env
        self.render_envelope(env)

        # Cache potential tool for approval if needed
        self.pending_tool = env if env.get("type") == "tool" else None

        # Execute one cycle
        self.ctx = run_one_cycle(self.ctx)
        self.render_last_observation()
        self.maybe_render_waiting()
        return True

    def run_turn(self, user_text: str) -> None:
        # Put user input where the prompt builder can see it (as last_observation)
        self.ctx["last_observation"] = {"type": "user_message", "text": user_text}
        cycles = 0
        while cycles < self.max_turn_cycles:
            if not self.step_once():
                break
            status = self.ctx.get("status")
            if status in {"waiting", "completed"}:
                break
            cycles += 1

    def show_plan(self) -> None:
        plan = self.ctx.get("plan")
        if not plan:
            console.print("No plan in context.")
            return
        table = Table(title="Current Plan")
        table.add_column("#", width=4)
        table.add_column("Step")
        for i, s in enumerate(plan, 1):
            table.add_row(str(i), json.dumps(s, ensure_ascii=False) if not isinstance(s, str) else s)
        console.print(table)

    def show_stats(self) -> None:
        goal = self.ctx.get("goal")
        status = self.ctx.get("status")
        steps = len(self.ctx.get("history") or [])
        console.print(Panel(f"Goal: {goal}\nStatus: {status}\nEvents: {steps}", title="Session Stats"))


def main() -> None:
    cli = ChatCLI()
    cli.load_workspace()
    cli.print_welcome()

    while True:
        try:
            user = Prompt.ask("[bold green]You[/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nExiting.")
            break

        if not user:
            continue
        if user.lower() in {"/exit", "/quit"}:
            break
        if user.lower() == "/help":
            cli.print_welcome()
            continue
        if user.lower() == "/plan":
            cli.show_plan()
            continue
        if user.lower() == "/stats":
            cli.show_stats()
            continue
        if user.lower() == "/approve":
            cli.approve_pending(True)
            continue
        if user.lower() == "/deny":
            cli.approve_pending(False)
            continue

        # Normal chat turn
        console.print(Text("Processing...", style="cyan"))
        cli.run_turn(user)


if __name__ == "__main__":
    main()

