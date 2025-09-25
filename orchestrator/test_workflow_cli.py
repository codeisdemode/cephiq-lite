#!/usr/bin/env python3
"""
Test the workflow system from within orchestrator directory
This avoids import issues
"""

import os
import sys
import json

# Set environment
os.environ['USE_MCP_SSE'] = '1'

def test_workflow_discovery():
    """Test workflow discovery and execution"""

    # Import from local orchestrator directory
    from runner import run_one_cycle, load_json, WORKSPACE_PATH

    print("Testing LLM-Driven Workflow Discovery")
    print("=" * 40)

    # Load workspace
    workspace = load_json(WORKSPACE_PATH)
    print(f"Model: {workspace.get('agent', {}).get('model', {}).get('name')}")
    print(f"Tools: {[t['name'] for t in workspace.get('tools', [])]}")

    # Test context
    context = {
        "goal": "System Information Collection",
        "history": [
            {"user": "Tell me what exact system we are on"}
        ]
    }

    print(f"\nUser Input: Tell me what exact system we are on")
    print("Running LLM decision cycle...")

    try:
        result_context = run_one_cycle(context, workspace)

        print(f"\nResult keys: {list(result_context.keys())}")

        # Check what the LLM decided
        history = result_context.get("history", [])
        if len(history) > 1:
            latest = history[-1]

            if "assistant" in latest:
                print(f"LLM Response: {latest['assistant']}")
            elif "tool_call" in latest:
                tool = latest["tool_call"]
                print(f"LLM Tool Call: {tool.get('name')}")
                if tool.get("name") == "mcp_call":
                    mcp_tool = tool.get("arguments", {}).get("name")
                    print(f"MCP Tool: {mcp_tool}")
                    if mcp_tool in ["list_available_workflows", "start_workflow"]:
                        print("SUCCESS: LLM discovered workflow system!")

        return result_context

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_workflow_discovery()