from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from debug import get_logger


logger = get_logger("mcp_client_stdio")

_SESSION: Optional[ClientSession] = None
_CTX = None  # holds the async context manager object


async def _ensure_session(server_script: Optional[str] = None) -> ClientSession:
    global _SESSION, _CTX
    if _SESSION is not None:
        return _SESSION

    # Determine server command
    # Prefer module path env (LOCAL_MCP_MODULE) like "orchestrator.combined_mcp_server:app"
    # but FastMCP stdio servers are typically launched as scripts.
    script = server_script or os.getenv("MCP_STDIO_SCRIPT")
    if not script:
        # default to orchestrator/combined_mcp_server.py under docs
        here = Path(__file__).resolve().parent
        candidate = here / "combined_mcp_server.py"
        script = str(candidate)

    if not Path(script).exists():
        logger.error("MCP stdio server script not found: %s", script)
        raise RuntimeError(f"MCP stdio server script not found: {script}")

    params = StdioServerParameters(
        command=sys.executable,
        args=[script],
        env=os.environ.copy(),
        cwd=str(Path(script).resolve().parent),
    )

    logger.debug("Starting stdio MCP server: cmd=%s args=%s cwd=%s", params.command, params.args, params.cwd)
    _CTX = stdio_client(params)
    cm = _CTX.__aenter__()
    # stdio_client yields read/write streams; ClientSession consumes them
    read_stream, write_stream = await cm  # type: ignore[misc]
    _SESSION = ClientSession(read_stream, write_stream)
    logger.debug("Initializing MCP ClientSession (stdio)")
    await _SESSION.initialize()
    logger.info("MCP stdio session established with %s", script)
    return _SESSION


async def _shutdown() -> None:
    global _SESSION, _CTX
    if _SESSION is not None:
        # Closing is handled by exiting the stdio_client context
        _SESSION = None
    if _CTX is not None:
        await _CTX.__aexit__(None, None, None)  # type: ignore[misc]
        _CTX = None


async def list_tools() -> Dict[str, Any]:
    logger.debug("list_tools (stdio)")
    sess = await _ensure_session()
    res = await sess.list_tools()
    return {"tools": [t.name for t in res.tools]}


async def call_tool_async(name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    logger.debug("call_tool stdio name=%s args=%s", name, arguments)
    sess = await _ensure_session()
    res = await sess.call_tool(name=name, arguments=arguments or {})
    # Convert CallToolResult to dict
    out: Dict[str, Any] = {"is_error": bool(res.isError)}
    # structuredContent if provided
    if res.structuredContent is not None:
        out["structured"] = res.structuredContent
    # Flatten content blocks (text only if present)
    texts = []
    for block in res.content:
        # ContentBlock may have 'type' and 'text'
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    if texts:
        out["text"] = "\n".join(texts)
    return out


def call_tool(name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Synchronous wrapper to call a tool over stdio MCP."""
    return asyncio.run(call_tool_async(name, arguments))
