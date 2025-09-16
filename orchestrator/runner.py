from __future__ import annotations

import json
from pathlib import Path
import os
from typing import Any, Dict

from jsonschema import Draft202012Validator
from .debug import get_logger

try:
    from .envelope_validator import validate_envelope  # type: ignore
    from .tools_stub import execute_envelope_tool  # type: ignore
    from .decide_next import decide_next  # type: ignore
    from .local_mcp_launcher import LocalMCPServer, url_is_local, url_reachable  # type: ignore
except Exception:
    import sys as _sys
    _sys.path.append(str(Path(__file__).resolve().parent))
    from envelope_validator import validate_envelope  # type: ignore
    from tools_stub import execute_envelope_tool  # type: ignore
    from decide_next import decide_next  # type: ignore
    from local_mcp_launcher import LocalMCPServer, url_is_local, url_reachable  # type: ignore


ROOT = Path(__file__).resolve().parent.parent   # docs
HERE = Path(__file__).resolve().parent          # docs/orchestrator
WORKSPACE_PATH = ROOT / "agent_workspace.autonomous.gpt5.json"
ENVELOPE_SCHEMA_PATH = ROOT / "envelope.schema.json"
MCP_SERVERS_CFG_CANDIDATES = [
    HERE / "mcpServers.json",
    ROOT / "mcpServers.json",
    ROOT.parent / "mcpServers.json",
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if text and text[0] == "\ufeff":
                text = text[1:]
    return json.loads(text)


def _resolve_server() -> tuple[str | None, str | None]:
    try:
        cfg = None
        for c in MCP_SERVERS_CFG_CANDIDATES:
            if c.exists():
                cfg = c
                break
        if not cfg:
            return (None, None)
        data = load_json(cfg)
        servers = data.get("servers", [])
        default_label = data.get("default_label")
        if default_label:
            for s in servers:
                if s.get("label") == default_label:
                    return default_label, s.get("url")
        if servers:
            s0 = servers[0]
            return s0.get("label"), s0.get("url")
    except Exception:
        return (None, None)
    return (None, None)


def run_one_cycle(context: Dict[str, Any]) -> Dict[str, Any]:
    logger = get_logger("runner")
    envelope = context.get("envelope")
    ok, errs = validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)
    if not ok:
        logger.warning("Invalid envelope: %s", errs)
        return {**context, "error": {"kind": "invalid_envelope", "details": errs}}

    etype = envelope["type"]
    if etype == "tool":
        tool = envelope.get("tool")
        args = envelope.get("arguments", {})
        logger.debug("Executing tool: %s args=%s", tool, args)
        obs = execute_envelope_tool(tool, args)
        # Simple approval gating: if tool execution signals approval_required
        if isinstance(obs, dict) and (obs.get("approval_required") or obs.get("error") == "approval_required"):
            logger.info("Tool %s requires approval: %s", tool, obs)
            context.setdefault("history", []).append({"type": "approval_request", "reason": obs.get("reason", "high-risk tool")})
            context["status"] = "waiting"
            return context
        context["last_observation"] = obs
        context.setdefault("history", []).append({"type": "tool_call", "tool": tool, "args": args, "obs": obs})
        return context
    if etype == "message":
        context.setdefault("history", []).append({"type": "message", "role": "assistant", "content": envelope.get("message")})
        return context
    if etype == "plan":
        context["plan"] = envelope.get("steps", [])
        context.setdefault("history", []).append({"type": "message", "role": "system", "content": "Plan recorded."})
        return context
    if etype == "ask_human":
        context.setdefault("history", []).append({"type": "approval_request", "reason": envelope.get("reason"), "fields": envelope.get("fields", [])})
        context["status"] = "waiting"
        return context
    if etype == "wait":
        context.setdefault("history", []).append({"type": "event", "waiting_for": envelope.get("event_type") or f"duration_ms={envelope.get('duration_ms')}"})
        context["status"] = "waiting"
        return context
    if etype == "finish":
        context.setdefault("history", []).append({"type": "transition", "to": "completed"})
        context["status"] = "completed"
        context["result"] = envelope.get("result")
        return context

    return {**context, "error": {"kind": "unknown_envelope_type", "value": etype}}


if __name__ == "__main__":
    logger = get_logger("runner")
    ws = load_json(WORKSPACE_PATH)
    print(f"Loaded workspace: {ws['agent']['name']}")

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for autonomous decisions.")

    # Optionally auto-start local MCP for direct mode
    started_local = False
    use_direct = os.getenv("USE_DIRECT_MCP", "0") == "1"
    start_local = os.getenv("START_LOCAL_MCP", "0") == "1"
    if use_direct and start_local:
        _, server_url = _resolve_server()
        if server_url and url_is_local(server_url) and not url_reachable(server_url):
            # Launch uvicorn on demand
            srv = LocalMCPServer(module=os.getenv("LOCAL_MCP_MODULE", "combined_mcp_server:app"), host="127.0.0.1", port=int(os.getenv("LOCAL_MCP_PORT", "8000")), cwd=ROOT)
            try:
                srv.start(wait_seconds=float(os.getenv("LOCAL_MCP_WAIT", "20")))
                started_local = True
            except Exception as e:
                raise SystemExit(f"Failed to auto-start local MCP: {e}")

    # Log resolved server for visibility
    try:
        lbl, url = _resolve_server()
        if lbl or url:
            print(f"MCP server resolved: label={lbl}, url={url}")
    except Exception:
        pass

    ctx: Dict[str, Any] = {"goal": os.getenv("GOAL", "Demo"), "history": [], "mcp_servers": {}}
    max_cycles = int(os.getenv("MAX_CYCLES", "6"))
    for i in range(max_cycles):
        logger.debug("Cycle %d starting", i + 1)
        ok, out = decide_next(ctx, ws, ENVELOPE_SCHEMA_PATH)
        if not ok:
            logger.error("decide_next failed: %s", out)
            ctx.setdefault("history", []).append({"type": "error", "data": out})
            break
        ctx["envelope"] = out  # type: ignore[assignment]
        logger.debug("Envelope decided: %s", out)
        ctx = run_one_cycle(ctx)
        if ctx.get("status") == "completed":
            logger.info("Run completed")
            break
        if ctx.get("status") == "waiting":
            # For now, end when waiting (no interactive approval path wired here)
            logger.info("Run waiting for approval or event")
            break

    print(json.dumps({k: v for k, v in ctx.items() if k != 'history'}, indent=2))
    print("History events:")
    for h in ctx.get("history", []):
        print(" -", h)

    # Persist run record for observability
    try:
        out_path = ROOT / "runs.jsonl"
        rec = {k: v for k, v in ctx.items() if k in ("goal", "status", "result", "history")}
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # No persistent server lifecycle mgmt here; add stop if we started it and persisted handle


