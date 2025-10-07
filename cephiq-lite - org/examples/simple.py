"""
Simple example - Basic file creation task

Shows minimal usage of Cephiq Lite
"""
import os
import sys

# Make sure we can import from parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cephiq_lite import Agent, AgentConfig


def main():
    """Run simple file creation task"""

    # Check API key
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("Error: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    # Create config
    config = AgentConfig(
        model="claude-sonnet-4-20250514",
        verbose=True,
        max_cycles=10,
        auto_approve=True
    )

    # Create agent
    agent = Agent(config)

    # Run task
    goal = "Create a file called greeting.txt with the content 'Hello from Cephiq Lite!'"

    print("="*60)
    print("CEPHIQ LITE - SIMPLE EXAMPLE")
    print("="*60)
    print(f"Goal: {goal}")
    print("="*60)
    print()

    result = agent.run(goal)

    # Display result
    print("\n" + "="*60)
    print("RESULT")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Cycles: {result['stats']['cycles']}")
    print(f"Duration: {result['stats']['duration_seconds']}s")

    if result['success']:
        final_envelope = result['final_envelope']
        if final_envelope.get('state') == 'reply':
            utterance = final_envelope.get('conversation', {}).get('utterance', '')
            print(f"\nAgent: {utterance}")
    else:
        print(f"\nFailed: {result['final_envelope'].get('error', {})}")


if __name__ == "__main__":
    main()
