from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Force SelectorEventLoopPolicy on Windows to avoid IocpProactor deadlock
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


DOCS_DIR = Path(__file__).resolve().parent

# Ensure orchestrator package is importable
if str(DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(DOCS_DIR))

# Point stdio client to the combined server script explicitly
server_script = DOCS_DIR / "combined_mcp_server.py"
os.environ["MCP_STDIO_SCRIPT"] = str(server_script)
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# Import mcp_client_stdio directly since we're in the orchestrator directory
import mcp_client_stdio as c


async def main() -> None:
    try:
        tools = await c.list_tools()
        print("TOOLS:", tools, flush=True)
        loc = await c.call_tool_async("get_current_location", {})
        print("LOCATION:", loc, flush=True)
    finally:
        await c._shutdown()


if __name__ == "__main__":
    asyncio.run(main())
