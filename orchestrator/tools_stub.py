from __future__ import annotations

import json
from typing import Any, Dict
import os
from pathlib import Path
import json

try:
    # Prefer local logger (avoids relative import issues when launched differently)
    from .debug import get_logger  # type: ignore
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parent))
    from debug import get_logger  # type: ignore

logger = get_logger("tools_stub")

USE_OPENAI_MCP = os.getenv("USE_OPENAI_MCP", "0") == "1"
USE_DIRECT_MCP = os.getenv("USE_DIRECT_MCP", "0") == "1"
USE_MCP_STDIO = os.getenv("USE_MCP_STDIO", "0") == "1"
USE_MCP_SSE = os.getenv("USE_MCP_SSE", "0") == "1"
if USE_OPENAI_MCP:
    try:
        from . import mcp_client_openai  # type: ignore
    except Exception:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.append(str(_Path(__file__).resolve().parent))
        import mcp_client_openai  # type: ignore
elif USE_DIRECT_MCP:
    try:
        from . import mcp_client_direct  # type: ignore
    except Exception:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.append(str(_Path(__file__).resolve().parent))
        import mcp_client_direct  # type: ignore
elif USE_MCP_STDIO:
    try:
        from . import mcp_client_stdio  # type: ignore
    except Exception:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.append(str(_Path(__file__).resolve().parent))
        import mcp_client_stdio  # type: ignore
elif USE_MCP_SSE:
    try:
        from . import mcp_client_sse  # type: ignore
    except Exception:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.append(str(_Path(__file__).resolve().parent))
        import mcp_client_sse  # type: ignore
else:
    raise RuntimeError("No MCP client selected. Set USE_DIRECT_MCP=1, USE_OPENAI_MCP=1, USE_MCP_STDIO=1, or USE_MCP_SSE=1.")

# Log selected transport once at import
try:
    transport = (
        "OPENAI_MCP" if USE_OPENAI_MCP else
        "DIRECT" if USE_DIRECT_MCP else
        "STDIO" if USE_MCP_STDIO else
        "SSE" if USE_MCP_SSE else
        "(none)"
    )
    logger.info("MCP transport selected: %s", transport)
except Exception:
    pass


def mcp_search(query: str, server_label: str | None = None, server_url: str | None = None) -> Dict[str, Any]:
    logger.debug("mcp_search query=%s label=%s url=%s", query, server_label, server_url)
    if USE_OPENAI_MCP:
        if not server_label or not server_url:
            server_label, server_url = _resolve_server()
        if not (server_label and server_url):
            raise RuntimeError("MCP server not configured. Provide server_label/server_url or configure docs/mcpServers.json.")
        logger.debug("mcp_search via OPENAI_MCP label=%s url=%s", server_label, server_url)
        return mcp_client_openai.search(server_label, server_url, query)  # type: ignore[name-defined]
    if USE_DIRECT_MCP:
        if not server_url:
            _, server_url = _resolve_server()
        if not server_url:
            raise RuntimeError("MCP server URL not configured. Provide server_url or configure docs/mcpServers.json.")
        logger.debug("mcp_search via DIRECT url=%s", server_url)
        return mcp_client_direct.search(server_url, query)  # type: ignore[name-defined]
    if USE_MCP_STDIO:
        logger.debug("mcp_search via STDIO")
        # stdio tools are addressed by name, pass query in arguments
        return mcp_client_stdio.call_tool("search", {"query": query})  # type: ignore[name-defined]
    if USE_MCP_SSE:
        logger.debug("mcp_search via SSE url=%s", server_url)
        return mcp_client_sse.call_tool("search", {"query": query}, server_url=server_url)  # type: ignore[name-defined]
    # Should never reach here due to guard above
    raise RuntimeError("MCP client not available.")


def mcp_fetch(id: str, server_label: str | None = None, server_url: str | None = None) -> Dict[str, Any]:
    if USE_OPENAI_MCP:
        if not server_label or not server_url:
            server_label, server_url = _resolve_server()
        if not (server_label and server_url):
            raise RuntimeError("MCP server not configured. Provide server_label/server_url or configure docs/mcpServers.json.")
        return mcp_client_openai.fetch(server_label, server_url, id)  # type: ignore[name-defined]
    if USE_DIRECT_MCP:
        if not server_url:
            _, server_url = _resolve_server()
        if not server_url:
            raise RuntimeError("MCP server URL not configured. Provide server_url or configure docs/mcpServers.json.")
        return mcp_client_direct.fetch(server_url, id)  # type: ignore[name-defined]
    if USE_MCP_STDIO:
        # For stdio servers, expose fetch via tool name
        return mcp_client_stdio.call_tool("fetch", {"id": id})  # type: ignore[name-defined]
    if USE_MCP_SSE:
        return mcp_client_sse.call_tool("fetch", {"id": id}, server_url=server_url)  # type: ignore[name-defined]
    # Should never reach here due to guard above
    raise RuntimeError("MCP client not available.")


def _resolve_server() -> tuple[str | None, str | None]:
    """Load default MCP server label/url from docs/mcpServers.json if present."""
    try:
        root = Path(__file__).resolve().parent.parent  # docs
        here = Path(__file__).resolve().parent        # docs/orchestrator
        # Prefer local orchestrator config, then docs/, then project root
        candidates = [
            here / "mcpServers.json",
            root / "mcpServers.json",
            root.parent / "mcpServers.json",
        ]
        cfg_path = None
        for c in candidates:
            if c.exists():
                cfg_path = c
                break
        if not cfg_path:
            return (None, None)
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
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


def _load_servers_map() -> dict[str, str]:
    """Return {label: url} for all configured servers across common locations."""
    out: dict[str, str] = {}
    try:
        root = Path(__file__).resolve().parent.parent
        here = Path(__file__).resolve().parent
        for cfg_path in [here / "mcpServers.json", root / "mcpServers.json", root.parent / "mcpServers.json"]:
            if not cfg_path.exists():
                continue
            try:
                try:
                    data = json.loads(cfg_path.read_text(encoding="utf-8"))
                except Exception:
                    data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                for s in data.get("servers", []):
                    lbl = s.get("label")
                    url = s.get("url")
                    if lbl and url:
                        out[lbl] = url
            except Exception:
                continue
    except Exception:
        pass
    return out


def execute_envelope_tool(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("execute_envelope_tool tool=%s args=%s", tool, arguments)
    if tool == "mcp_search":
        return mcp_search(**arguments)
    if tool == "mcp_fetch":
        return mcp_fetch(**arguments)

    # Handle direct workflow tools
    if "workflow" in tool:
        if not (USE_MCP_STDIO or USE_MCP_SSE or USE_DIRECT_MCP):
            return {"error": "workflow tools require transport"}

        if USE_DIRECT_MCP:
            # Handle workflow tools directly in DIRECT mode
            return mcp_client_direct.call_tool(tool, arguments)  # type: ignore[name-defined]

    # Generic tool execution: call any available tool by its name
    if tool not in {"mcp_call", "mcp_search", "mcp_fetch"}:
        if USE_MCP_STDIO:
            return mcp_client_stdio.call_tool(tool, arguments)  # type: ignore[name-defined]
        if USE_MCP_SSE:
            # Select a server URL if available
            servers = _load_servers_map()
            server_url = next(iter(servers.values())) if servers else None
            return mcp_client_sse.call_tool(tool, arguments, server_url=server_url)  # type: ignore[name-defined]
        if USE_DIRECT_MCP:
            return mcp_client_direct.call_tool(tool, arguments)  # type: ignore[name-defined]

    if tool == "mcp_call":
        if USE_DIRECT_MCP:
            # In DIRECT mode, unwrap mcp_call and execute the tool directly
            tool_name = arguments.get("tool_name") or arguments.get("name")
            tool_args = arguments.get("arguments") or {}
            if not tool_name:
                return {"error": "Missing 'tool_name' or 'name' for mcp_call"}
            return execute_envelope_tool(tool_name, tool_args)
        elif not (USE_MCP_STDIO or USE_MCP_SSE):
            return {"error": "mcp_call requires USE_MCP_STDIO=1 or USE_MCP_SSE=1"}
        name = arguments.get("name")
        params = arguments.get("arguments") or {}
        if not name:
            return {"error": "Missing 'name' for mcp_call"}
        # High-risk gating
        DANGEROUS = {"execute_powershell", "powershell", "shell", "bash", "python", "python_eval", "delete_item", "write_block", "change_directory"}
        if name in DANGEROUS and not params.get("approved"):
            return {"approval_required": True, "reason": f"High-risk MCP tool '{name}' requires human approval"}
        # Server selection
        server_url = arguments.get("server_url")
        server_label = arguments.get("server_label")
        servers = _load_servers_map()
        if not server_url:
            if server_label:
                server_url = servers.get(server_label)
                if not server_url:
                    return {"error": f"Unknown server_label '{server_label}'"}
            else:
                if len(servers) > 1:
                    return {"error": "Multiple MCP servers configured; provide 'server_label' in arguments"}
                if len(servers) == 1:
                    server_url = next(iter(servers.values()))
        logger.debug("mcp_call name=%s via %s url=%s", name, "STDIO" if USE_MCP_STDIO else "SSE", server_url)
        if USE_MCP_STDIO:
            return mcp_client_stdio.call_tool(name, params)  # type: ignore[name-defined]
        else:
            return mcp_client_sse.call_tool(name, params, server_url=server_url)  # type: ignore[name-defined]
    # Unknown tool: echo back for debugging
    return {"error": f"unknown tool: {tool}", "args": arguments}
