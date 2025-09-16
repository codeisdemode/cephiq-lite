#!/usr/bin/env python
"""
Fix import issues by modifying sys.path and handling relative imports
"""
import os
import sys

# Set environment variable for SSE
os.environ["USE_MCP_SSE"] = "1"

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import debug module first to avoid relative import issues
import debug

# Now we can import mcp_client_sse since debug is available
import mcp_client_sse

# Test the connection
print("Testing MCP SSE connection...")

# List tools to test connection
try:
    tools = mcp_client_sse.list_tools_async()
    print("Tools:", tools)

    # Try to create a file
    result = mcp_client_sse.call_tool("create_file", {
        "path": "agent_created_demo.txt",
        "content": "This file was created by the MCP agent!"
    }, server_url="http://localhost:8000/sse/")

    print("Result:", result)

    # Check if file was created
    import pathlib
    if pathlib.Path("agent_created_demo.txt").exists():
        print("✅ SUCCESS: File created by agent!")
        print("File content:")
        print(pathlib.Path("agent_created_demo.txt").read_text())
    else:
        print("❌ FAILED: File was not created")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()