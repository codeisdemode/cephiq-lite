#!/usr/bin/env python
"""
Test using tools_stub to call MCP tools
"""
import os

# Set environment variable for SSE
os.environ["USE_MCP_SSE"] = "1"

# Import tools_stub which handles the imports
from tools_stub import execute_envelope_tool

print("Testing MCP tools through tools_stub...")

# Call create_file tool through MCP
result = execute_envelope_tool("mcp_call", {
    "name": "create_file",
    "arguments": {
        "path": "agent_created_demo.txt",
        "content": "This file was created by the MCP agent!"
    }
})

print("MCP call result:")
print(result)

# Check if file was created
import pathlib
if pathlib.Path("agent_created_demo.txt").exists():
    print("\n✅ SUCCESS: File created by agent!")
    print("File content:")
    print(pathlib.Path("agent_created_demo.txt").read_text())
else:
    print("\n❌ FAILED: File was not created")