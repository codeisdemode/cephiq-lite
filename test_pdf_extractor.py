#!/usr/bin/env python3
"""
Test script for PDF extractor MCP tools
"""

import sys
import os

# Add orchestrator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'orchestrator'))

from combined_mcp_server import extract_pdf_text, extract_pdf_metadata

def test_pdf_extraction():
    """Test PDF extraction functionality"""

    # Test with the existing contract PDF
    test_pdf_path = "contracten/doc24883920250627091208.pdf"

    if not os.path.exists(test_pdf_path):
        print(f"PDF file not found: {test_pdf_path}")
        return

    print(f"Testing PDF text extraction on: {test_pdf_path}")
    result = extract_pdf_text(test_pdf_path)

    if "success" in result and result["success"]:
        print(f"✓ Text extraction successful using {result.get('method', 'unknown')}")
        print(f"  Pages extracted: {result.get('pages_extracted', 0)}")
        text_preview = result.get('text', '')[:200] + "..." if len(result.get('text', '')) > 200 else result.get('text', '')
        print(f"  Text preview: {text_preview}")
    else:
        print(f"✗ Text extraction failed: {result.get('error', 'Unknown error')}")

    print("\nTesting PDF metadata extraction...")
    metadata_result = extract_pdf_metadata(test_pdf_path)

    if "success" in metadata_result and metadata_result["success"]:
        print(f"✓ Metadata extraction successful using {metadata_result.get('metadata', {}).get('method', 'unknown')}")
        metadata = metadata_result.get('metadata', {})
        print(f"  Pages: {metadata.get('pages', 'Unknown')}")
        print(f"  Title: {metadata.get('title', 'Unknown')}")
        print(f"  Author: {metadata.get('author', 'Unknown')}")
    else:
        print(f"✗ Metadata extraction failed: {metadata_result.get('error', 'Unknown error')}")

    # Test error handling
    print("\nTesting error handling with non-existent file...")
    error_result = extract_pdf_text("non_existent.pdf")

    if "error" in error_result:
        print(f"✓ Error handling working correctly: {error_result['error']}")
    else:
        print("✗ Error handling test failed")

if __name__ == "__main__":
    test_pdf_extraction()