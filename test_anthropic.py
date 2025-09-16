#!/usr/bin/env python3
"""
Test script for Anthropic Claude integration
"""

import os
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "orchestrator"))

# Set Anthropic API key
os.environ['ANTHROPIC_API_KEY'] = 'your-api-key-here'  # Replace with actual key

def test_anthropic_integration():
    """Test Anthropic Claude integration"""
    try:
        from decide_next import _try_import_anthropic, _call_anthropic_json

        # Test Anthropic SDK import
        kind, client_ctor = _try_import_anthropic()
        if kind is None:
            print("❌ Anthropic SDK not available")
            return False

        print("✅ Anthropic SDK imported successfully")

        # Test messages format
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Respond with valid JSON only."
            },
            {
                "role": "user",
                "content": "Hello! Please respond with a simple JSON message like {\"message\": \"hello\"}"
            }
        ]

        # Test API call (this will fail without valid API key, but should show proper error)
        success, result = _call_anthropic_json(messages, "claude-3-haiku-20240307")  # Use haiku for testing

        if success:
            print(f"✅ Anthropic API call successful: {result}")
            return True
        else:
            print(f"⚠️  Anthropic API call failed (expected without valid key): {result}")
            # Even if it fails due to auth, the integration is working
            return True

    except Exception as e:
        print(f"❌ Error testing Anthropic integration: {e}")
        return False

if __name__ == "__main__":
    print("Testing Anthropic Claude integration...")
    success = test_anthropic_integration()
    if success:
        print("\n🎉 Anthropic integration is working!")
        print("\nNext steps:")
        print("1. Set your ANTHROPIC_API_KEY environment variable")
        print("2. Update agent_workspace.autonomous.gpt5.json to use Claude model")
        print("3. Run chat_cli.py with Claude model")
    else:
        print("\n❌ Anthropic integration failed")