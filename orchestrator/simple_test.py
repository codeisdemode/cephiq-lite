#!/usr/bin/env python
"""
Simple test that runs from orchestrator directory to avoid import issues
"""
import os
import sys

# Set environment variable for SSE
os.environ["USE_MCP_SSE"] = "1"

# Add current directory to path to handle relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Import the modules directly to avoid relative import issues
import debug
import mcp_client_sse

# Now we can use the functions
def test_create_file():
    print("Testing file creation via MCP SSE...")

    try:
        result = mcp_client_sse.call_tool("create_file", {
            "path": "agent_created_demo.txt",
            "content": "This file was created by the MCP agent via SSE!"
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

if __name__ == "__main__":
    test_create_file()