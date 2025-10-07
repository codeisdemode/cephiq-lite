#!/usr/bin/env python3
"""
Interactive Chat Test with Tag Contracts

Demonstrates the chat CLI with different user roles and tag-based permissions.
"""

import os
import sys
from pathlib import Path

# Add cephiq_lite to path
sys.path.insert(0, str(Path(__file__).parent))

from cephiq_lite.config import AgentConfig
from cephiq_lite.agent import Agent
from tag_contracts import load_all_tag_contracts


def chat_with_role(role_name, user_roles):
    """Interactive chat session with specific role"""
    print(f"\n{'='*60}")
    print(f"CHAT SESSION: {role_name.upper()}")
    print(f"{'='*60}")
    print(f"Role: {role_name}")
    print(f"Permissions: {user_roles}")
    print("Type '/quit' to exit or '/role' to switch roles")
    print("="*60)

    # Create config with tags enabled
    config = AgentConfig(
        enable_tags=True,
        user_id=f"chat_{role_name}",
        user_roles=user_roles,
        org_id="test_org",
        verbose=False,  # Set to True for detailed output
        max_cycles=20,
        auto_approve=True,
        max_total_tokens=100000
    )

    # Create agent and load tag contracts
    agent = Agent(config)
    load_all_tag_contracts(agent.tag_manager)

    # Interactive chat loop
    while True:
        try:
            user_input = input(f"\n[{role_name}] You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"/q", "/quit", "quit", "exit", "/exit"}:
            print("Ending chat session...")
            break

        if user_input.lower() == "/role":
            print("Switching roles...")
            return True  # Signal to switch roles

        # Run agent with user input
        try:
            result = agent.run(user_input)
            final_envelope = result.get("final_envelope", {})
            state = final_envelope.get("state")

            if state == "reply":
                utterance = final_envelope.get("conversation", {}).get("utterance", "")
                print(f"[{role_name}] Agent> {utterance}")
            elif state == "error":
                error = final_envelope.get("error", {})
                print(f"[{role_name}] Error> {error.get('error_message', 'Unknown error')}")
            elif state == "clarify":
                clarify = final_envelope.get("clarify", {})
                print(f"[{role_name}] Clarify> {clarify.get('question', 'Need clarification')}")
            else:
                print(f"[{role_name}] Agent finished in state: {state}")

        except Exception as e:
            print(f"[{role_name}] Error: {e}")

    return False


def main():
    """Main chat interface with role selection"""
    print("Cephiq Lite - Interactive Chat with Tag Contracts")
    print("="*60)

    # Available roles
    roles = {
        "1": {"name": "developer", "user_roles": ["developer"], "description": "Full file system access"},
        "2": {"name": "analyst", "user_roles": ["analyst"], "description": "Read-only access"},
        "3": {"name": "guest", "user_roles": ["guest"], "description": "Limited access"},
        "4": {"name": "agent", "user_roles": ["agent"], "description": "Base agent role"}
    }

    while True:
        print("\nSelect a role to chat as:")
        for key, role in roles.items():
            print(f"  {key}. {role['name']} - {role['description']}")
        print("  q. Quit")

        choice = input("\nEnter choice: ").strip().lower()

        if choice in {"q", "quit", "exit"}:
            print("Goodbye!")
            break

        if choice in roles:
            role_config = roles[choice]
            switch_role = chat_with_role(role_config["name"], role_config["user_roles"])

            if not switch_role:
                break  # User quit entirely
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    # Check if we have API key
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set!")
        print("Please set it before running the chat:")
        print("  export ANTHROPIC_API_KEY=your_key_here")
        print("  OR")
        print("  set ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    main()