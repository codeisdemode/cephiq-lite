#!/usr/bin/env python
"""
Hybrid PowerShell + Python MCP Server (FastMCP)

Transports:
- stdio (default): speaks MCP over stdin/stdout. IMPORTANT: Do not print to stdout in this mode.
- sse: runs an HTTP SSE server using FastMCP settings (host/port).

Notes:
- For stdio, avoid printing to stdout before/during the session; use logging or stderr.
- For sse, FastMCP will serve SSE at settings.sse_path (default /sse).
"""

import subprocess
import re
import logging
import base64
import os
import io
import contextlib
import json
from typing import List, Dict, Any, Optional
import sys
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# Ensure stdout is properly configured for stdio transport
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# Configure logging - force all logs to stderr to avoid stdout pollution
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('powershell_python_mcp.log'),
        logging.StreamHandler(sys.stderr)  # Also log to stderr
    ]
)

logger = logging.getLogger("hybrid-mcp")
# Create FastMCP; host/port can be overridden when using SSE via settings
mcp = FastMCP("Hybrid MCP Server")

# --- PowerShell Utilities ---

class CommandOutput(BaseModel):
    command: str
    output: str
    error: Optional[str] = None

def sanitize_path(path: str) -> str:
    return path.strip()

def execute_powershell(command: str) -> CommandOutput:
    logger.info(f"Executing PowerShell: {command}")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
        return CommandOutput(
            command=command,
            output=result.stdout.strip(),
            error=None if result.returncode == 0 else result.stderr.strip()
        )
    except Exception as e:
        return CommandOutput(command=command, output="", error=str(e))

# --- PowerShell Tools ---

@mcp.tool()
def get_files(path: str = ".") -> Dict[str, Any]:
    """
    List files/directories at a given path (PowerShell-based).
    Returns JSON with 'items' array and 'path'.
    """
    safe_path = sanitize_path(path)
    ps_cmd = f'Get-ChildItem "{safe_path}" | ConvertTo-Json -Depth 1'
    result = execute_powershell(ps_cmd)
    if result.error:
        return {"items": [], "path": safe_path, "error": result.error}

    items_list = []
    try:
        raw = json.loads(result.output)
        if not isinstance(raw, list):
            raw = [raw]
        for item in raw:
            item_type = "directory" if "Directory" in item.get("Attributes", "") else "file"
            items_list.append({
                "name": item.get("Name", ""),
                "type": item_type,
                "size": item.get("Length"),
                "last_write_time": item.get("LastWriteTime")
            })
    except Exception as e:
        logger.error(f"Failed to parse file list JSON: {e}")
        return {"items": [], "path": safe_path, "error": str(e)}

    return {"items": items_list, "path": safe_path}

@mcp.tool()
def read_file(path: str) -> Dict[str, Any]:
    """
    Read entire file contents via PowerShell: Get-Content
    """
    cmd_out = execute_powershell(f'Get-Content -Path "{sanitize_path(path)}"')
    return cmd_out.dict()

@mcp.tool()
def create_file(path: str, content: str = "") -> Dict[str, Any]:
    """
    Create a new file (overwrite if exists), optionally write content.
    """
    safe_path = sanitize_path(path)
    result = execute_powershell(f'New-Item -ItemType File -Path "{safe_path}" -Force')
    if content:
        escaped_content = content.replace('"', '`"')
        write_result = execute_powershell(f'Set-Content -Path "{safe_path}" -Value "{escaped_content}"')
        return write_result.dict()
    return result.dict()

@mcp.tool()
def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a new directory, recursively if needed
    """
    cmd_out = execute_powershell(f'New-Item -ItemType Directory -Path "{sanitize_path(path)}" -Force')
    return cmd_out.dict()

@mcp.tool()
def delete_item(path: str, recurse: bool = False, force: bool = False) -> Dict[str, Any]:
    cmd = f'Remove-Item -Path "{sanitize_path(path)}"'
    if recurse:
        cmd += " -Recurse"
    if force:
        cmd += " -Force"
    return execute_powershell(cmd).dict()

@mcp.tool()
def copy_item(source: str, destination: str) -> Dict[str, Any]:
    cmd_out = execute_powershell(f'Copy-Item -Path "{source}" -Destination "{destination}"')
    return cmd_out.dict()

@mcp.tool()
def move_item(source: str, destination: str) -> Dict[str, Any]:
    cmd_out = execute_powershell(f'Move-Item -Path "{source}" -Destination "{destination}"')
    return cmd_out.dict()

@mcp.tool()
def get_processes(name: str = "") -> Dict[str, Any]:
    cmd = f'Get-Process {"-Name " + name if name else ""}'
    return execute_powershell(cmd).dict()

@mcp.tool()
def get_services(name: str = "") -> Dict[str, Any]:
    cmd = f'Get-Service {"-Name " + name if name else ""}'
    return execute_powershell(cmd).dict()

@mcp.tool()
def get_current_date() -> Dict[str, Any]:
    return execute_powershell("Get-Date").dict()

@mcp.tool()
def get_current_location() -> Dict[str, Any]:
    return execute_powershell("Get-Location").dict()

@mcp.tool()
def change_directory(path: str) -> Dict[str, Any]:
    return execute_powershell(f'Set-Location -Path "{sanitize_path(path)}"').dict()

@mcp.tool(name="powershell")
@mcp.tool(name="execute_powershell")
@mcp.tool(name="shell")
@mcp.tool(name="bash")
def execute_passthrough(code: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
    """
    Accept code/command from LLM, pass directly to PowerShell
    """
    cmd = code or command
    if not cmd:
        return {"command": "", "output": "", "error": "Missing 'code' or 'command'"}
    return execute_powershell(cmd).dict()

# Resource: system info
@mcp.resource("system://info")
def get_system_info() -> Dict[str, Any]:
    return {
        "powershell_version": execute_powershell("$PSVersionTable | ConvertTo-Json").output,
        "os_info": execute_powershell("Get-ComputerInfo -Property CsManufacturer,CsModel,OsName,OsVersion | ConvertTo-Json").output,
        "mcp_server": "Hybrid MCP Server v1.0"
    }

# --- Python Tools ---

@mcp.tool()
def python(code: str) -> Dict[str, Any]:
    """
    Execute arbitrary Python code in this server process
    """
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, globals())
        return {"output": output.getvalue()}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def python_eval(expr: str) -> Dict[str, Any]:
    try:
        result = eval(expr, globals())
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# --- Partial File I/O Tools (READ/WRITE BLOCK) ---

@mcp.tool()
def read_block(path: str, start_line: int, num_lines: int) -> Dict[str, Any]:
    """
    Read a partial block of lines from 'path':
    - start_line: 0-based index
    - num_lines: how many lines to read
    Returns { "content": "<text>", "error": ... }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        end_line = start_line + num_lines
        chunk = lines[start_line:end_line]
        return {"content": "".join(chunk), "error": None}
    except Exception as e:
        return {"content": "", "error": str(e)}

@mcp.tool()
def write_block(path: str, start_line: int, text: str) -> Dict[str, Any]:
    """
    Write (or overwrite) lines in 'path' starting at line index 'start_line'.
    'text' can contain newlines. If the file is shorter, we append blank lines as needed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        block_lines = text.splitlines(True)  # keep newlines
        # Extend file if start_line is beyond current length
        if start_line > len(lines):
            lines += ["\n"] * (start_line - len(lines))

        # Overwrite or append lines
        for i, bline in enumerate(block_lines):
            idx = start_line + i
            if idx < len(lines):
                lines[idx] = bline
            else:
                lines.append(bline)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Entry Point ---

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--transport", type=str, choices=["stdio", "sse"], default="stdio")
    args = parser.parse_args()

    # Configure settings for SSE if requested
    if args.transport == "sse":
        # Recreate with host/port settings
        mcp = FastMCP("Hybrid MCP Server", host=args.host, port=args.port)
        print(f"[SSE] Hybrid MCP running on http://{args.host}:{args.port} (SSE at /sse/)", file=sys.stderr)
        mcp.run("sse")
    else:
        # stdio: do not print to stdout
        print("[STDIO] Hybrid MCP running over stdio (no stdout prints)", file=sys.stderr)
        # Add debug logging to track stdio server behavior
        logger.info("Starting stdio MCP server - process should remain running")
        try:
            mcp.run("stdio")
        except Exception as e:
            logger.error(f"Stdio server failed: {e}")
            raise
