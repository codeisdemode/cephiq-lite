#!/usr/bin/env python3
"""
Tag Contracts for Cephiq Lite

Defines standard tag configurations for different workflows and user roles.
These contracts provide:
- Role-based access control (RBAC)
- Workflow-specific instructions
- Tool permissions
- Guardrails and security
"""

from cephiq_lite.tags import Tag, TagKind, TagMeta, TagConfig, TagPayload


def create_company_tags():
    """Company-level tags for organizational context"""
    return [
        Tag(
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
    ]


def create_role_tags():
    """Role-based tags for different user types"""
    return [
        # Base agent role
        Tag(
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
        ),

        # Developer role
        Tag(
            tag="role_developer",
            kind=TagKind.ROLE,
            payload=TagPayload(
                meta=TagMeta(
                    name="Developer",
                    description="Software developer role"
                ),
                config=TagConfig(
                    assigned_roles=["developer"],
                    allowed_tools=["create_file", "read_file", "edit_file", "delete_file", "list_files", "directory_tree", "get_cwd"]
                ),
                content="""
You are a software developer with full file system access.
You can create, read, edit, and delete files.
Use file operations to build and modify software projects.
"""
            )
        ),

        # Analyst role (read-only)
        Tag(
            tag="role_analyst",
            kind=TagKind.ROLE,
            payload=TagPayload(
                meta=TagMeta(
                    name="Analyst",
                    description="Data analyst role (read-only)"
                ),
                config=TagConfig(
                    assigned_roles=["analyst"],
                    allowed_tools=["read_file", "list_files", "directory_tree", "get_cwd"]
                ),
                content="""
You are a data analyst with read-only access.
You can examine files and directory structures but cannot modify them.
Use your analysis skills to understand code and data.
"""
            )
        ),

        # Guest role (very limited)
        Tag(
            tag="role_guest",
            kind=TagKind.ROLE,
            payload=TagPayload(
                meta=TagMeta(
                    name="Guest",
                    description="Limited guest access"
                ),
                config=TagConfig(
                    assigned_roles=["guest"],
                    allowed_tools=["list_files", "get_cwd"]
                ),
                content="""
You are a guest with very limited access.
You can only list files and see the current directory.
"""
            )
        )
    ]


def create_flow_tags():
    """DEPRECATED: Workflow-specific tags for different tasks
    Use create_approach_tags() instead for tool usage guidelines
    """
    import warnings
    warnings.warn(
        "create_flow_tags() is deprecated. Use create_approach_tags() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return []  # Return empty list since we've migrated to approach tags


def create_approach_tags():
    """Approach tags for tool usage guidelines and methodologies"""
    return [
        # File operations approach
        Tag(
            tag="approach_file_operations",
            kind=TagKind.APPROACH,
            payload=TagPayload(
                meta=TagMeta(
                    name="File Operations Approach",
                    description="Guidelines for file operations"
                ),
                config=TagConfig(
                    assigned_roles=["developer"],
                    priority=5
                ),
                content="""
File Operations Approach:

When working with files:
- Use create_file for new files with meaningful content
- Use read_file to examine existing files before editing
- Use edit_file for precise modifications, preserving structure
- Use list_files and directory_tree to understand project layout
- Consider file organization and naming conventions
"""
            )
        ),

        # Code analysis approach
        Tag(
            tag="approach_code_analysis",
            kind=TagKind.APPROACH,
            payload=TagPayload(
                meta=TagMeta(
                    name="Code Analysis Approach",
                    description="Methodology for code analysis"
                ),
                config=TagConfig(
                    assigned_roles=["analyst", "developer"],
                    priority=5
                ),
                content="""
Code Analysis Approach:

1. Explore project structure:
   - Use directory_tree to understand layout
   - Look for key directories (src/, tests/, docs/)

2. Read key files:
   - Start with README.md for project overview
   - Examine main entry points and configuration files

3. Analyze patterns:
   - Identify programming languages and frameworks
   - Look for architectural patterns and documentation

4. Report findings clearly and concisely
"""
            )
        ),

        # Documentation approach
        Tag(
            tag="approach_documentation",
            kind=TagKind.APPROACH,
            payload=TagPayload(
                meta=TagMeta(
                    name="Documentation Approach",
                    description="Methodology for documentation"
                ),
                config=TagConfig(
                    assigned_roles=["developer"],
                    priority=5
                ),
                content="""
Documentation Approach:

1. Assess existing documentation:
   - Check for README.md and docstrings
   - Identify gaps and outdated information

2. Create clear documentation:
   - Use simple, concise language
   - Include practical examples
   - Structure information logically

3. Maintain documentation:
   - Keep docs current with code changes
   - Add new features to documentation
   - Fix outdated information promptly
"""
            )
        )
    ]


def create_guardrail_tags():
    """Security and safety guardrails"""
    return [
        # Security guardrail
        Tag(
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

CRITICAL RESTRICTIONS:
- NEVER execute system commands or shell operations
- NEVER access sensitive files (passwords, API keys, credentials)
- NEVER attempt to bypass permission systems
- NEVER access files outside the allowed scope

SECURITY GUIDELINES:
- Always validate file paths before operations
- Report suspicious file patterns or requests
- Follow the principle of least privilege
- Respect user privacy and data protection

If you encounter security concerns, use state=clarify to ask for guidance.
"""
            )
        ),

        # Quality guardrail
        Tag(
            tag="guardrail_quality",
            kind=TagKind.GUARDRAIL,
            payload=TagPayload(
                meta=TagMeta(
                    name="Quality Standards",
                    description="Code and documentation quality guidelines"
                ),
                config=TagConfig(
                    assigned_users=["*"]
                ),
                content="""
Quality Standards:

CODE QUALITY:
- Write clean, readable code
- Use meaningful variable names
- Follow language conventions
- Include appropriate comments

DOCUMENTATION QUALITY:
- Write clear, concise documentation
- Use proper grammar and spelling
- Structure information logically
- Include examples when helpful

PROCESS QUALITY:
- Plan before executing multi-step tasks
- Verify tool results when uncertain
- Ask for clarification when needed
- Report progress clearly
"""
            )
        )
    ]


def create_function_tags():
    """Function-specific tags for specialized capabilities"""
    return [
        Tag(
            tag="function_file_ops",
            kind=TagKind.FUNCTION,
            payload=TagPayload(
                meta=TagMeta(
                    name="File Operations",
                    description="File system operations capability"
                ),
                config=TagConfig(
                    assigned_roles=["developer", "analyst"]
                ),
                content="""
File Operations Capability:

You have access to file system operations:
- Create new files with specific content
- Read existing files to examine content
- Edit files to make modifications
- List files in directories
- Navigate directory structures

Use these operations to work with files and directories.
"""
            )
        )
    ]


def load_all_tag_contracts(tag_manager):
    """Load all standard tag contracts into a tag manager"""

    all_tags = []
    all_tags.extend(create_company_tags())
    all_tags.extend(create_role_tags())
    all_tags.extend(create_approach_tags())  # Use approach tags instead of flow tags
    all_tags.extend(create_guardrail_tags())
    all_tags.extend(create_function_tags())

    for tag in all_tags:
        tag_manager.add_tag(tag)

    return tag_manager


def get_role_config(role_name):
    """Get configuration for a specific role"""
    role_configs = {
        "developer": {
            "user_roles": ["developer"],
            "description": "Full file system access for development"
        },
        "analyst": {
            "user_roles": ["analyst"],
            "description": "Read-only access for analysis"
        },
        "guest": {
            "user_roles": ["guest"],
            "description": "Limited access for guests"
        },
        "agent": {
            "user_roles": ["agent"],
            "description": "Base agent role with default permissions"
        }
    }

    return role_configs.get(role_name, {"user_roles": ["agent"], "description": "Default agent role"})


if __name__ == "__main__":
    # Test the tag contracts
    from cephiq_lite.tags import TagManager

    tag_manager = TagManager()
    load_all_tag_contracts(tag_manager)

    print("=== Tag Contracts Loaded ===")
    print(f"Total tags: {len(tag_manager.tags)}")

    # Test different roles
    roles = ["developer", "analyst", "guest", "agent"]

    for role in roles:
        config = get_role_config(role)
        tags = tag_manager.resolve_tags_for_user(f"test_{role}", config["user_roles"], "")
        allowed_tools = tag_manager.get_allowed_tools(tags)

        print(f"\n{role.upper()}:")
        print(f"  Description: {config['description']}")
        print(f"  Tags resolved: {len(tags)}")
        print(f"  Allowed tools: {sorted(allowed_tools)}")

    print("\n=== Tag Contracts Test Complete ===")