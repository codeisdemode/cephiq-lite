# MCP PowerShell Tools Testing Guide

This guide shows how to run and test the local Hybrid MCP server and the orchestrator.

## Prerequisites

- Python 3.10+
- Windows PowerShell available in `PATH`

### 1) Verify environment
```powershell
# Current directory and Python version
Get-Location
python --version
```

### 2) Install dependencies
```powershell
pip install fastmcp mcp jsonschema openai pydantic uvicorn
```

### 3) Set OpenAI API key (required for orchestrator decisions)
```powershell
$env:OPENAI_API_KEY = "your-openai-api-key-here"
```

## Available Tools (Hybrid MCP)

- Safe (read-only): `get_files`, `read_file`, `get_current_date`, `get_current_location`, `get_processes`, `get_services`, `python_eval`
- Write/high‑risk (approval-gated in orchestrator): `execute_powershell`, `create_file`, `create_directory`, `write_block`, `delete_item`, `move_item`, `copy_item`, `change_directory`, `python`

## A) Run MCP Server (SSE)

Start the server in another PowerShell window:
```powershell
python orchestrator/combined_mcp_server.py --transport sse --host 127.0.0.1 --port 8000
```
Expected stderr output:
```
[SSE] Hybrid MCP running on http://127.0.0.1:8000 (SSE at /sse/)
```

Check readiness:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/sse/" -Method GET
```

## B) Quick stdio smoke test (optional)

```powershell
python ..\quick_stdio_test.py
```
This prints discovered tools and a `get_current_location` call result.

## C) Call Tools Directly via Orchestrator Client

Use SSE or stdio transport:
```powershell
# Option 1: SSE transport
$env:USE_MCP_SSE = '1'

# Option 2: stdio transport (launches local stdio server process)
# $env:USE_MCP_STDIO = '1'

python - <<'PY'
from tools_stub import execute_envelope_tool
print(execute_envelope_tool('mcp_call', {'name': 'get_current_date'}))
print(execute_envelope_tool('mcp_call', {'name': 'get_files', 'arguments': {'path': '.'}}))
print(execute_envelope_tool('mcp_call', {'name': 'python_eval', 'arguments': {'expr': '2+2'}}))
PY
```

## D) Run the Orchestrator Loop

Set the transport and goal, then run:
```powershell
$env:USE_MCP_SSE = '1'          # or: $env:USE_MCP_STDIO = '1'
$env:GOAL = 'List files here and summarize.'
$env:MAX_CYCLES = '3'
python orchestrator\runner.py
```
Results are appended to `runs.jsonl` in the repo root.

## Troubleshooting

- "MCP client not available": Set one transport var: `$env:USE_MCP_SSE='1'` or `$env:USE_MCP_STDIO='1'`.
- "OpenAI SDK not installed": `pip install openai`.
- "Server not reachable": Ensure the SSE server is running on port 8000.
- "Invalid envelope": `pip install jsonschema` and ensure `OPENAI_API_KEY` is set.
- **"Stdio transport hangs on Windows":** This is a known issue with Windows IocpProactor. The stdio transport may hang during initialization on Windows. Use SSE transport instead for reliable operation.
- **"Relative import errors":** If you see `ImportError: attempted relative import with no known parent package`, fix the imports in `mcp_client_stdio.py` and `mcp_client_sse.py` by changing `from .debug import get_logger` to `from debug import get_logger`.
- **"SSE client connection issues":** The SSE client may require proper URL formatting. Use `http://127.0.0.1:8000/sse` (without trailing slash) instead of `http://127.0.0.1:8000/sse/`.
- **"Unicode encoding errors":** Avoid using Unicode characters like ✅ in print statements on Windows, as they may cause encoding issues.

## Key Configuration Files

- `orchestrator/mcpServers.json` — MCP server configuration
- `orchestrator/test_config.json` — Testing config (label `local_powershell`)
- `agent_workspace.autonomous.gpt5.json` — Agent workspace
- `envelope.schema.json` — Envelope JSON schema

## Next Steps

- Start with read-only tools, then try write operations.
- Review `debug.log` and `runs.jsonl` for behavior.
- Iterate on goals and MAX_CYCLES to see autonomous decisions.

Monitor costs when using OpenAI-backed decisions.

## PowerShell Integration Verification

To verify that the PowerShell integration is working correctly (independent of MCP transport issues), you can test the PowerShell commands directly:

```python
import subprocess
import json

def test_powershell():
    # Test file creation
    result = subprocess.run(["powershell", "-NoProfile", "-Command", 'New-Item -ItemType File -Path "test.txt" -Force'],
                          capture_output=True, text=True)
    print("File creation:", result.returncode == 0)

    # Test content writing
    result = subprocess.run(["powershell", "-NoProfile", "-Command", 'Set-Content -Path "test.txt" -Value "Hello World"'],
                          capture_output=True, text=True)
    print("Content writing:", result.returncode == 0)

    # Test content reading
    result = subprocess.run(["powershell", "-NoProfile", "-Command", 'Get-Content -Path "test.txt"'],
                          capture_output=True, text=True)
    print("Content reading:", result.returncode == 0)
    print("Content:", result.stdout)

    # Test JSON output (like MCP server)
    result = subprocess.run(["powershell", "-NoProfile", "-Command", 'Get-ChildItem "." | ConvertTo-Json -Depth 1'],
                          capture_output=True, text=True)
    print("JSON output test:", result.returncode == 0)

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            print(f"JSON parsed successfully: {len(data)} items")
        except json.JSONDecodeError:
            print("JSON parse failed - check if corporate profile adds output")

test_powershell()
```

This will verify that the core PowerShell functionality that the MCP server relies on is working properly.

**Important Note:** Use `-NoProfile` flag with PowerShell commands to avoid corporate profile output that can interfere with JSON parsing in the MCP server.

## Current Status

The MCP orchestrator has been successfully set up with the following components working:

### ✅ Working Components:
1. **PowerShell Integration** - File creation, content manipulation, and command execution all work perfectly
2. **MCP Server Core** - The hybrid MCP server with PowerShell/Python tools is functional
3. **SSE Server** - The SSE transport server starts successfully on port 8000/8001
4. **Logging & Configuration** - All logs properly go to stderr, stdout is clean for MCP protocol
5. **Event Loop Policy** - WindowsSelectorEventLoopPolicy is configured to avoid IocpProactor deadlocks

### ⚠️ Known Issues:
1. **Stdio Transport** - The stdio transport hangs due to server not maintaining persistent process
2. **SSE Client Adapter** - The messages endpoint requires proper Content-Type headers that aren't being returned
3. **SSE Message Parsing** - The SSE events contain endpoint URLs rather than direct JSON messages

### 🎯 Recommended Usage:
- Use the **PowerShell integration directly** for file operations and command execution
- The **MCP server core functionality** works when called directly via subprocess
- For MCP protocol usage, consider using a different MCP client implementation or transport

### Direct PowerShell Testing (Working):
```python
import subprocess

# Test file creation
result = subprocess.run(["powershell", "-NoProfile", "-Command", 'New-Item -ItemType File -Path "test.txt" -Force'], capture_output=True, text=True)
print("File creation:", result.returncode == 0)

# Test content writing
result = subprocess.run(["powershell", "-NoProfile", "-Command", 'Set-Content -Path "test.txt" -Value "Hello World"'], capture_output=True, text=True)
print("Content writing:", result.returncode == 0)

# Test content reading
result = subprocess.run(["powershell", "-NoProfile", "-Command", 'Get-Content -Path "test.txt"'], capture_output=True, text=True)
print("Content reading:", result.returncode == 0)
print("Content:", result.stdout)
```

