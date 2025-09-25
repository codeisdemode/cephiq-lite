#!/usr/bin/env python3
"""
Test script for markdown report formatting tool
"""

import sys
import os

# Add orchestrator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'orchestrator'))

from combined_mcp_server import format_markdown_report

def test_report_formatting():
    """Test markdown report formatting functionality"""

    # Test with the existing contract analysis report
    test_report_path = "contracten/contract_analysis_report.md"

    if not os.path.exists(test_report_path):
        print(f"Report file not found: {test_report_path}")
        return

    print(f"Testing markdown report formatting on: {test_report_path}")

    # Test the formatting tool
    result = format_markdown_report(test_report_path, "enhanced readability and visual hierarchy")

    if "success" in result and result["success"]:
        print(f"✓ Report formatting successful!")
        print(f"  Improvements made: {', '.join(result.get('improvements', []))}")
        print(f"  Backup created: {result.get('backup_created', 'No backup')}")
        print(f"  Original length: {result.get('original_length', 0)} characters")
        print(f"  Formatted length: {result.get('formatted_length', 0)} characters")
        print(f"  Summary: {result.get('improvement_summary', 'No summary')}")

        # Show a preview of the formatted content
        with open(test_report_path, 'r', encoding='utf-8') as f:
            formatted_content = f.read()

        print(f"\nFormatted report preview (first 500 chars):")
        print(formatted_content[:500] + "...")

    else:
        print(f"✗ Report formatting failed: {result.get('error', 'Unknown error')}")

    # Test error handling
    print("\nTesting error handling with non-existent file...")
    error_result = format_markdown_report("non_existent_report.md")

    if "error" in error_result:
        print(f"✓ Error handling working correctly: {error_result['error']}")
    else:
        print("✗ Error handling test failed")

if __name__ == "__main__":
    test_report_formatting()