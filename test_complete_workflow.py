#!/usr/bin/env python3
"""
Test script to verify complete contract analysis workflow with formatting step
"""

import sys
import os

# Add orchestrator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'orchestrator'))

from combined_mcp_server import workflow_templates

def test_workflow_configuration():
    """Test that the contract analysis workflow includes the new formatting step"""

    print("Testing contract analysis workflow configuration...")

    # Check if workflow template exists
    if 'contract_analysis' not in workflow_templates:
        print("✗ Contract analysis workflow template not found")
        return

    template = workflow_templates['contract_analysis']
    print(f"✓ Contract analysis workflow template loaded: {template['name']}")

    # Check number of steps
    steps = template.get('steps', [])
    print(f"  Total steps: {len(steps)}")

    # Check for the new formatting step
    formatting_step = None
    for step in steps:
        if step.get('action') == 'report_formatting':
            formatting_step = step
            break

    if formatting_step:
        print("✓ Report formatting step found!")
        print(f"  Step ID: {formatting_step.get('id')}")
        print(f"  Action: {formatting_step.get('action')}")
        print(f"  Guidance: {formatting_step.get('guidance', '')[:100]}...")
        print(f"  Next tools: {formatting_step.get('next_tools', [])}")
        print(f"  Completion check: {formatting_step.get('completion_check')}")
    else:
        print("✗ Report formatting step not found in workflow")

    # Verify all required tools are available
    required_tools = ['extract_pdf_text', 'extract_pdf_metadata', 'format_markdown_report']

    print("\nChecking required tools availability...")
    for tool_name in required_tools:
        try:
            import combined_mcp_server
            tool_func = getattr(combined_mcp_server, tool_name, None)
            if tool_func and hasattr(tool_func, '__name__'):
                print(f"✓ {tool_name} tool available")
            else:
                print(f"✗ {tool_name} tool NOT available")
        except Exception as e:
            print(f"✗ {tool_name} tool check failed: {e}")

    # Test workflow step sequence
    print("\nWorkflow step sequence:")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step.get('action', 'Unknown')} - {step.get('completion_check', 'No check')}")

    print("\nWorkflow configuration test completed!")

if __name__ == "__main__":
    test_workflow_configuration()