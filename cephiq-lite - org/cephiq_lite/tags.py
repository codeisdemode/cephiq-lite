"""
Tag Manager - Unified permission and workflow system

Tags control:
- Prompt content assembly
- Tool access permissions
- Workflow execution
- RBAC and scope enforcement
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum


class TagKind(str, Enum):
    """Types of tags in the system"""
    COMPANY = "company"
    FUNCTION = "function"
    ROLE = "role"
    FLOW = "flow"
    TOOL = "tool"
    GUARDRAIL = "guardrail"


@dataclass
class TagMeta:
    """Metadata for a tag"""
    name: str
    description: str = ""
    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TagConfig:
    """Configuration for tag permissions and scope"""
    assigned_users: List[str] = field(default_factory=list)
    assigned_roles: List[str] = field(default_factory=list)
    org_scope: str = ""
    allowed_tools: List[str] = field(default_factory=list)
    priority: int = 0  # Higher priority overrides lower


@dataclass
class TagPayload:
    """Complete tag payload with metadata and content"""
    meta: TagMeta
    config: TagConfig
    content: str  # Prompt content OR workflow definition


@dataclass
class Tag:
    """A unified tag representing permissions, workflows, and content"""
    tag: str  # "flow_checkout", "tool_verify_payment", "company_acme"
    kind: TagKind
    payload: TagPayload


class TagManager:
    """Manages tags for unified permission and workflow system"""

    def __init__(self):
        self.tags: Dict[str, Tag] = {}
        self._load_default_tags()

    def _load_default_tags(self) -> None:
        """Load default tags for basic functionality"""
        # Default company tag
        company_tag = Tag(
            tag="company_cephiq",
            kind=TagKind.COMPANY,
            payload=TagPayload(
                meta=TagMeta(
                    name="Cephiq",
                    description="Cephiq Lite AI Agent System"
                ),
                config=TagConfig(
                    assigned_users=["*"]
                ),
                content="""
You are Cephiq Lite, a modular AI agent runtime built on Envelope v2.1 protocol.

Core Principles:
- Make structured decisions using envelope protocol
- Execute tools efficiently via MCP
- Follow permission and scope rules
- Be helpful, accurate, and reliable
"""
            )
        )
        self.tags[company_tag.tag] = company_tag

        # Default role tag
        role_tag = Tag(
            tag="role_agent",
            kind=TagKind.ROLE,
            payload=TagPayload(
                meta=TagMeta(
                    name="AI Agent",
                    description="Autonomous AI agent role"
                ),
                config=TagConfig(
                    assigned_roles=["agent"]
                ),
                content="""
You are an autonomous AI agent that can:
- Make decisions using envelope protocol states
- Execute tools to accomplish tasks
- Plan multi-step workflows
- Ask for clarification when needed
- Report progress and results

Always use the envelope protocol for structured decision making.
"""
            )
        )
        self.tags[role_tag.tag] = role_tag

    def add_tag(self, tag: Tag) -> None:
        """Add or update a tag"""
        self.tags[tag.tag] = tag

    def remove_tag(self, tag_name: str) -> bool:
        """Remove a tag by name"""
        if tag_name in self.tags:
            del self.tags[tag_name]
            return True
        return False

    def resolve_tags_for_user(
        self,
        user_id: str,
        user_roles: List[str],
        org_id: str = "",
        intent: str = ""
    ) -> List[Tag]:
        """
        Resolve which tags apply to a user based on permissions

        Args:
            user_id: User identifier
            user_roles: List of user roles
            org_id: Organization identifier
            intent: User intent for flow resolution

        Returns:
            List of applicable tags
        """
        applicable_tags = []

        for tag in self.tags.values():
            config = tag.payload.config

            # Check user assignment
            if config.assigned_users and user_id not in config.assigned_users and "*" not in config.assigned_users:
                continue

            # Check role assignment
            if config.assigned_roles and not any(role in config.assigned_roles for role in user_roles):
                continue

            # Check org scope
            if config.org_scope and config.org_scope != org_id:
                continue

            applicable_tags.append(tag)

        # Sort by priority (higher first)
        applicable_tags.sort(key=lambda t: t.payload.config.priority, reverse=True)

        return applicable_tags

    def build_system_prompt(self, tags: List[Tag]) -> str:
        """
        Build system prompt from resolved tags

        Args:
            tags: List of resolved tags

        Returns:
            Complete system prompt
        """
        sections = {}

        for tag in tags:
            kind = tag.kind.value
            if kind not in sections:
                sections[kind] = []
            sections[kind].append(tag.payload.content)

        # Build prompt with structured sections
        prompt_parts = []

        # Company context
        if TagKind.COMPANY.value in sections:
            prompt_parts.append("=== COMPANY CONTEXT ===")
            prompt_parts.extend(sections[TagKind.COMPANY.value])

        # Function context
        if TagKind.FUNCTION.value in sections:
            prompt_parts.append("\n=== FUNCTION CONTEXT ===")
            prompt_parts.extend(sections[TagKind.FUNCTION.value])

        # Role context
        if TagKind.ROLE.value in sections:
            prompt_parts.append("\n=== ROLE CONTEXT ===")
            prompt_parts.extend(sections[TagKind.ROLE.value])

        # Flow context
        if TagKind.FLOW.value in sections:
            prompt_parts.append("\n=== FLOW CONTEXT ===")
            prompt_parts.extend(sections[TagKind.FLOW.value])

        # Tool context
        if TagKind.TOOL.value in sections:
            prompt_parts.append("\n=== TOOLS AVAILABLE ===")
            prompt_parts.extend(sections[TagKind.TOOL.value])

        # Guardrails
        if TagKind.GUARDRAIL.value in sections:
            prompt_parts.append("\n=== GUARDRAILS ===")
            prompt_parts.extend(sections[TagKind.GUARDRAIL.value])

        return "\n".join(prompt_parts)

    def get_allowed_tools(self, tags: List[Tag]) -> Set[str]:
        """
        Get set of allowed tools from resolved tags

        Args:
            tags: List of resolved tags

        Returns:
            Set of allowed tool names
        """
        allowed_tools = set()

        for tag in tags:
            config = tag.payload.config
            allowed_tools.update(config.allowed_tools)

        return allowed_tools

    def filter_tools_by_permissions(
        self,
        available_tools: List[str],
        allowed_tools: Set[str]
    ) -> List[str]:
        """
        Filter available tools based on permissions

        Args:
            available_tools: List of all available tools
            allowed_tools: Set of allowed tools from tags

        Returns:
            Filtered list of tools
        """
        if not allowed_tools:  # No restrictions
            return available_tools

        return [tool for tool in available_tools if tool in allowed_tools]

    def get_flow_tags(self, intent: str) -> List[Tag]:
        """
        Get flow tags matching an intent

        Args:
            intent: User intent to match against flow tags

        Returns:
            List of matching flow tags
        """
        flow_tags = []

        for tag in self.tags.values():
            if tag.kind == TagKind.FLOW and tag.tag.startswith(f"flow_{intent}"):
                flow_tags.append(tag)

        return flow_tags

    def validate_tool_access(self, tool: str, tags: List[Tag]) -> bool:
        """
        Validate if a tool can be accessed with current tags

        Args:
            tool: Tool name to validate
            tags: Current resolved tags

        Returns:
            True if tool access is allowed
        """
        allowed_tools = self.get_allowed_tools(tags)
        return not allowed_tools or tool in allowed_tools


# Example usage and testing
if __name__ == "__main__":
    # Create tag manager
    tag_manager = TagManager()

    # Add a sample flow tag
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
4. Update inventory
"""
        )
    )
    tag_manager.add_tag(checkout_flow)

    # Test tag resolution
    user_tags = tag_manager.resolve_tags_for_user(
        user_id="user123",
        user_roles=["agent"],
        org_id="acme"
    )

    print(f"Resolved {len(user_tags)} tags for user")

    # Test system prompt building
    system_prompt = tag_manager.build_system_prompt(user_tags)
    print("\nSystem Prompt:")
    print(system_prompt[:500] + "...")

    # Test tool filtering
    available_tools = ["create_file", "read_file", "verify_payment", "create_order"]
    allowed_tools = tag_manager.get_allowed_tools(user_tags)
    filtered_tools = tag_manager.filter_tools_by_permissions(available_tools, allowed_tools)

    print(f"\nAvailable tools: {available_tools}")
    print(f"Allowed tools: {allowed_tools}")
    print(f"Filtered tools: {filtered_tools}")