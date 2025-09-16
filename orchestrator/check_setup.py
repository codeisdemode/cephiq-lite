import sys
import importlib
import json
from pathlib import Path

print("?? MCP Orchestrator Setup Checker")
print("=" * 50)

# Check Python version
print(f"?? Python version: {sys.version}")

# Check current directory
print(f"?? Current directory: {Path.cwd()}")

# Check dependencies
print("\n?? Checking dependencies...")
deps = {
    "jsonschema": "JSON schema validation",
    "openai": "OpenAI API client", 
    "pydantic": "Data validation",
}

missing = []
for dep, desc in deps.items():
    try:
        importlib.import_module(dep)
        print(f"  ? {dep}: OK ({desc})")
    except ImportError:
        print(f"  ? {dep}: MISSING ({desc})")
        missing.append(dep)

# FastMCP check (might not be available)
try:
    importlib.import_module("fastmcp")
    print(f"  ? fastmcp: OK (MCP server framework)")
except ImportError:
    print(f"  ??  fastmcp: MISSING (MCP server framework)")
    missing.append("fastmcp")

try:
    importlib.import_module("mcp")
    print(f"  ? mcp: OK (MCP protocol)")
except ImportError:
    print(f"  ??  mcp: MISSING (MCP protocol)")
    missing.append("mcp")

if missing:
    print(f"\n?? Install missing dependencies:")
    print(f"pip install {' '.join(missing)}")

# Check configuration files
print("\n?? Checking configuration files...")
config_files = [
    "mcpServers.json",
    "../agent_workspace.autonomous.gpt5.json", 
    "../envelope.schema.json"
]

for config in config_files:
    path = Path(config)
    if path.exists():
        print(f"  ? {config}: Found")
        try:
            with open(path) as f:
                data = json.load(f)
            print(f"     ?? {len(str(data))} characters")
        except Exception as e:
            print(f"     ??  Parse error: {e}")
    else:
        print(f"  ? {config}: Not found")

# Check environment requirements
print("\n?? Environment requirements:")
import os
if os.getenv("OPENAI_API_KEY"):
    print("  ? OPENAI_API_KEY: Set")
else:
    print("  ??  OPENAI_API_KEY: Not set (required for AI decisions)")

# Check MCP transport mode
mcp_modes = ["USE_MCP_SSE", "USE_MCP_STDIO", "USE_DIRECT_MCP", "USE_OPENAI_MCP"]
set_modes = [mode for mode in mcp_modes if os.getenv(mode) == "1"]

if set_modes:
    print(f"  ? MCP Transport: {', '.join(set_modes)}")
else:
    print("  ??  MCP Transport: None set (will need one of: USE_MCP_SSE=1, USE_MCP_STDIO=1, etc.)")

# Test basic imports
print("\n?? Testing basic functionality...")
try:
    from envelope_validator import validate_envelope
    print("  ? envelope_validator: Import OK")
except Exception as e:
    print(f"  ? envelope_validator: {e}")

try:
    from tools_stub import execute_envelope_tool
    print("  ? tools_stub: Import OK")
except Exception as e:
    print(f"  ? tools_stub: {e}")

try:
    from decide_next import decide_next
    print("  ? decide_next: Import OK")
except Exception as e:
    print(f"  ? decide_next: {e}")

print("\n? Setup check complete!")
print("\nNext steps:")
print("1. Install any missing dependencies")
print("2. Set OPENAI_API_KEY environment variable")
print("3. Choose MCP transport mode (USE_MCP_SSE=1 recommended)")
print("4. Start MCP server: python combined_mcp_server.py --transport=sse --port=8000")
print("5. Test individual tools or run full orchestrator")

