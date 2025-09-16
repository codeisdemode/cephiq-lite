#!/usr/bin/env python
"""
Simple test to call MCP tool from orchestrator directory
"""
import os
import asyncio

# Set environment variable for SSE
os.environ["USE_MCP_SSE"] = "1"

# Import the SSE client
from mcp_client_sse import call_tool

print("Testing MCP SSE client from orchestrator directory...")

# Call create_file tool through MCP
result = call_tool("create_file", {
    "path": "agent_created_demo.txt",
    "content": "This file was created by the MCP agent!"
}, server_url="http://localhost:8000/sse/")

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