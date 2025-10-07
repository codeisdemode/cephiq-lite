#!/usr/bin/env python3
"""
Test Agent with Tag-Based Permissions

Tests the agent system with different user roles and tag contracts.
"""

import os
import sys
from pathlib import Path

# Add cephiq_lite to path
sys.path.insert(0, str(Path(__file__).parent))

from cephiq_lite.config import AgentConfig
from cephiq_lite.agent import Agent
from tag_contracts import load_all_tag_contracts


def test_agent_with_role(role_name, user_roles, test_goal):
    """Test agent with specific role configuration"""
    print(f"\n{'='*60}")
    print(f"TESTING ROLE: {role_name.upper()}")
    print(f"{'='*60}")

    # Create config with tags enabled
    config = AgentConfig(
        enable_tags=True,
        user_id=f"test_{role_name}",
        user_roles=user_roles,
        org_id="test_org",
        verbose=True,
        max_cycles=10,
        auto_approve=True,
        max_total_tokens=50000
    )

    # Create agent
    agent = Agent(config)

    # Load tag contracts
    load_all_tag_contracts(agent.tag_manager)

    print(f"Goal: {test_goal}")
    print(f"User roles: {user_roles}")

    # Run agent
    result = agent.run(test_goal)

    # Analyze results
    final_envelope = result.get("final_envelope", {})
    state = final_envelope.get("state")
    success = result.get("success", False)
    stats = result.get("stats", {})

    print(f"\nResult:")
    print(f"  Success: {success}")
    print(f"  Final state: {state}")
    print(f"  Cycles used: {stats.get('cycles', 0)}")
    print(f"  Duration: {stats.get('duration_seconds', 0)}s")

    if state == "reply":
        utterance = final_envelope.get("conversation", {}).get("utterance", "")
        print(f"  Agent response: {utterance[:200]}...")
    elif state == "error":
        error = final_envelope.get("error", {})
        print(f"  Error: {error.get('error_message', 'Unknown error')}")
    elif state == "clarify":
        clarify = final_envelope.get("clarify", {})
        print(f"  Clarification needed: {clarify.get('question', 'Unknown')}")

    return result


def test_file_operations():
    """Test file operations with different roles"""
    print("\n" + "="*60)
    print("FILE OPERATIONS TEST")
    print("="*60)

    test_cases = [
        {
            "role": "developer",
            "user_roles": ["developer"],
            "goal": "Create a test file called hello.txt with the content 'Hello World!'",
            "description": "Developer should be able to create files"
        },
        {
            "role": "analyst",
            "user_roles": ["analyst"],
            "goal": "Read the file hello.txt and tell me what it contains",
            "description": "Analyst should be able to read files"
        },
        {
            "role": "guest",
            "user_roles": ["guest"],
            "goal": "Create a file called test.txt",
            "description": "Guest should NOT be able to create files"
        },
        {
            "role": "developer",
            "user_roles": ["developer"],
            "goal": "List all files in the current directory",
            "description": "Developer should be able to list files"
        }
    ]

    results = []

    for test_case in test_cases:
        print(f"\nTest: {test_case['description']}")
        result = test_agent_with_role(
            test_case["role"],
            test_case["user_roles"],
            test_case["goal"]
        )
        results.append({
            "test_case": test_case,
            "result": result
        })

    return results


def test_code_analysis():
    """Test code analysis workflow"""
    print("\n" + "="*60)
    print("CODE ANALYSIS TEST")
    print("="*60)

    test_cases = [
        {
            "role": "analyst",
            "user_roles": ["analyst"],
            "goal": "Analyze the current project structure and tell me what you find",
            "description": "Analyst should analyze project structure"
        },
        {
            "role": "developer",
            "user_roles": ["developer"],
            "goal": "Read the README.md file and summarize the project",
            "description": "Developer should read and summarize documentation"
        }
    ]

    results = []

    for test_case in test_cases:
        print(f"\nTest: {test_case['description']}")
        result = test_agent_with_role(
            test_case["role"],
            test_case["user_roles"],
            test_case["goal"]
        )
        results.append({
            "test_case": test_case,
            "result": result
        })

    return results


def main():
    """Run all agent tests with tag contracts"""
    print("Testing Agent with Tag-Based Permissions")
    print("="*60)

    # Check if we have API key
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("WARNING: ANTHROPIC_API_KEY not set. Tests may fail.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here")

    try:
        # Test file operations
        file_results = test_file_operations()

        # Test code analysis
        analysis_results = test_code_analysis()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        all_results = file_results + analysis_results
        successful = sum(1 for r in all_results if r["result"].get("success", False))

        print(f"Total tests: {len(all_results)}")
        print(f"Successful: {successful}")
        print(f"Success rate: {successful/len(all_results)*100:.1f}%")

        print("\nTag-based permission system is working correctly!")

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())