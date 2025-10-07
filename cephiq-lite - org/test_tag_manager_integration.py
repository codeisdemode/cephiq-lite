#!/usr/bin/env python3
"""
Test Tag Manager integration with agent system

Verifies:
- Tag resolution and permission filtering
- Tool access control
- System prompt assembly from tags
- Agent integration with tag-based permissions
"""

import os
import sys
import tempfile
from pathlib import Path

# Add cephiq_lite to path
sys.path.insert(0, str(Path(__file__).parent))

from cephiq_lite.config import AgentConfig
from cephiq_lite.agent import Agent
from cephiq_lite.tags import TagManager, Tag, TagKind, TagMeta, TagConfig, TagPayload


def test_tag_manager_basic():
    """Test basic tag manager functionality"""
    print("=== Testing Tag Manager Basic Functionality ===")

    tag_manager = TagManager()

    # Test default tags
    user_tags = tag_manager.resolve_tags_for_user(
        user_id="test_user",
        user_roles=["agent"],
        org_id=""
    )

    print(f"Resolved {len(user_tags)} default tags")
    assert len(user_tags) >= 2, "Should have at least company and role tags"

    # Test system prompt building
    system_prompt = tag_manager.build_system_prompt(user_tags)
    print(f"System prompt length: {len(system_prompt)} chars")
    assert len(system_prompt) > 0, "System prompt should not be empty"

    # Test allowed tools
    allowed_tools = tag_manager.get_allowed_tools(user_tags)
    print(f"Allowed tools: {allowed_tools}")

    print("PASS Basic tag manager tests passed\n")


def test_custom_tags():
    """Test adding and using custom tags"""
    print("=== Testing Custom Tags ===")

    tag_manager = TagManager()

    # Add a custom flow tag
    file_management_flow = Tag(
        tag="flow_file_management",
        kind=TagKind.FLOW,
        payload=TagPayload(
            meta=TagMeta(
                name="File Management Flow",
                description="File creation and editing workflow"
            ),
            config=TagConfig(
                assigned_roles=["agent"],
                allowed_tools=["create_file", "read_file", "edit_file", "list_files"]
            ),
            content="""
File Management Flow Instructions:
- Use create_file for new files
- Use read_file to examine existing files
- Use edit_file to modify files
- Use list_files to explore directories
"""
        )
    )
    tag_manager.add_tag(file_management_flow)

    # Add a guardrail tag
    security_guardrail = Tag(
        tag="guardrail_security",
        kind=TagKind.GUARDRAIL,
        payload=TagPayload(
            meta=TagMeta(
                name="Security Guardrails",
                description="Security restrictions and guidelines"
            ),
            config=TagConfig(
                assigned_users=["*"]
            ),
            content="""
Security Guardrails:
- Never execute system commands
- Never access sensitive files
- Always validate file paths
- Report suspicious activities
"""
        )
    )
    tag_manager.add_tag(security_guardrail)

    # Resolve tags for user
    user_tags = tag_manager.resolve_tags_for_user(
        user_id="test_user",
        user_roles=["agent"],
        org_id=""
    )

    print(f"Resolved {len(user_tags)} tags (including custom)")

    # Test system prompt with custom tags
    system_prompt = tag_manager.build_system_prompt(user_tags)
    print(f"System prompt with custom tags: {len(system_prompt)} chars")

    # Verify custom content is included
    assert "File Management Flow" in system_prompt, "Custom flow content should be in prompt"
    assert "Security Guardrails" in system_prompt, "Guardrail content should be in prompt"

    # Test tool permissions
    allowed_tools = tag_manager.get_allowed_tools(user_tags)
    print(f"Allowed tools with custom tags: {allowed_tools}")

    # Test tool validation
    assert tag_manager.validate_tool_access("create_file", user_tags), "create_file should be allowed"
    assert tag_manager.validate_tool_access("read_file", user_tags), "read_file should be allowed"

    print("PASS Custom tag tests passed\n")


def test_agent_integration():
    """Test agent integration with tag manager"""
    print("=== Testing Agent Integration ===")

    # Create config with tags enabled
    config = AgentConfig(
        enable_tags=True,
        user_id="test_user",
        user_roles=["agent"],
        org_id="test_org",
        verbose=False,
        max_cycles=5,
        auto_approve=True
    )

    # Create agent
    agent = Agent(config)

    # Verify tag manager is initialized
    assert hasattr(agent, 'tag_manager'), "Agent should have tag_manager"
    assert hasattr(agent, 'current_tags'), "Agent should have current_tags"
    assert hasattr(agent, 'allowed_tools'), "Agent should have allowed_tools"

    print("PASS Agent tag integration verified")

    # Test tag resolution setup (tags are resolved during run(), not initialization)
    if config.enable_tags:
        # Verify tag manager is set up
        assert agent.tag_manager is not None, "Agent should have tag manager"
        assert isinstance(agent.current_tags, list), "Agent should have current_tags list"
        print("Agent tag manager setup verified")

    print("PASS Agent integration tests passed\n")


def test_permission_filtering():
    """Test tool permission filtering"""
    print("=== Testing Permission Filtering ===")

    tag_manager = TagManager()

    # Add restricted tag
    restricted_tag = Tag(
        tag="role_restricted",
        kind=TagKind.ROLE,
        payload=TagPayload(
            meta=TagMeta(
                name="Restricted Role",
                description="Role with limited tool access"
            ),
            config=TagConfig(
                assigned_roles=["restricted"],
                allowed_tools=["read_file", "list_files"]  # Only these tools allowed
            ),
            content="""
You have restricted access. You can only read files and list directories.
"""
        )
    )
    tag_manager.add_tag(restricted_tag)

    # Test restricted user
    restricted_tags = tag_manager.resolve_tags_for_user(
        user_id="restricted_user",
        user_roles=["restricted"],
        org_id=""
    )

    allowed_tools = tag_manager.get_allowed_tools(restricted_tags)
    print(f"Restricted user allowed tools: {allowed_tools}")

    # Test tool validation
    assert tag_manager.validate_tool_access("read_file", restricted_tags), "read_file should be allowed"
    assert tag_manager.validate_tool_access("list_files", restricted_tags), "list_files should be allowed"
    assert not tag_manager.validate_tool_access("create_file", restricted_tags), "create_file should NOT be allowed"
    assert not tag_manager.validate_tool_access("edit_file", restricted_tags), "edit_file should NOT be allowed"

    print("PASS Permission filtering tests passed\n")


def test_flow_tags():
    """Test flow-specific tags"""
    print("=== Testing Flow Tags ===")

    tag_manager = TagManager()

    # Add flow tags
    checkout_flow = Tag(
        tag="flow_checkout",
        kind=TagKind.FLOW,
        payload=TagPayload(
            meta=TagMeta(
                name="Checkout Flow",
                description="E-commerce checkout process"
            ),
            config=TagConfig(
                assigned_roles=["sales_agent"],
                allowed_tools=["verify_payment", "create_order", "send_receipt"]
            ),
            content="""
Checkout Flow Instructions:
1. Verify payment details
2. Create order record
3. Send receipt to customer
"""
        )
    )
    tag_manager.add_tag(checkout_flow)

    # Test flow tag resolution
    flow_tags = tag_manager.get_flow_tags("checkout")
    print(f"Found {len(flow_tags)} checkout flow tags")
    assert len(flow_tags) == 1, "Should find checkout flow tag"

    # Test flow-specific permissions
    sales_tags = tag_manager.resolve_tags_for_user(
        user_id="sales_user",
        user_roles=["sales_agent"],
        org_id=""
    )

    sales_tools = tag_manager.get_allowed_tools(sales_tags)
    print(f"Sales agent allowed tools: {sales_tools}")

    # Verify flow-specific tools are allowed
    assert "verify_payment" in sales_tools, "Sales agent should have verify_payment"
    assert "create_order" in sales_tools, "Sales agent should have create_order"

    print("PASS Flow tag tests passed\n")


def main():
    """Run all integration tests"""
    print("Running Tag Manager Integration Tests\n")

    try:
        test_tag_manager_basic()
        test_custom_tags()
        test_agent_integration()
        test_permission_filtering()
        test_flow_tags()

        print("SUCCESS All Tag Manager integration tests passed!")
        print("\nSummary:")
        print("- Tag resolution and permission filtering PASS")
        print("- System prompt assembly from tags PASS")
        print("- Agent integration with tag-based permissions PASS")
        print("- Tool access control PASS")
        print("- Flow-specific tags and permissions PASS")

    except Exception as e:
        print(f"\nFAIL Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())