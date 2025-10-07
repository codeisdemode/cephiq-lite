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
    """Workflow-specific tags for different tasks"""
    return [
        # File management flow
        Tag(
            tag="flow_file_management",
            kind=TagKind.FLOW,
            payload=TagPayload(
                meta=TagMeta(
                    name="File Management",
                    description="File creation and editing workflow"
                ),
                config=TagConfig(
                    assigned_roles=["developer"],
                    priority=5
                ),
                content="""
File Management Flow:

1. When creating files:
   - Use create_file with meaningful content
   - Include proper file extensions
   - Consider file organization

2. When reading files:
   - Use read_file to examine content
   - Look for patterns and structure

3. When editing files:
   - Use edit_file for precise modifications
   - Make minimal changes when possible
   - Preserve existing structure

4. When exploring:
   - Use list_files and directory_tree to understand project structure
"""
            )
        ),

        # Code analysis flow
        Tag(
            tag="flow_code_analysis",
            kind=TagKind.FLOW,
            payload=TagPayload(
                meta=TagMeta(
                    name="Code Analysis",
                    description="Code review and analysis workflow"
                ),
                config=TagConfig(
                    assigned_roles=["analyst", "developer"],
                    priority=5
                ),
                content="""
Code Analysis Flow:

1. Explore project structure:
   - Use directory_tree to understand layout
   - Look for key directories (src/, tests/, docs/)

2. Read key files:
   - Start with README.md for project overview
   - Examine main entry points
   - Look for configuration files

3. Analyze code patterns:
   - Identify programming languages used
   - Look for architectural patterns
   - Check for documentation quality

4. Report findings:
   - Summarize project structure
   - Identify potential issues
   - Suggest improvements
"""
            )
        ),

        # Documentation flow
        Tag(
            tag="flow_documentation",
            kind=TagKind.FLOW,
            payload=TagPayload(
                meta=TagMeta(
                    name="Documentation",
                    description="Documentation creation and maintenance"
                ),
                config=TagConfig(
                    assigned_roles=["developer"],
                    priority=5
                ),
                content="""
Documentation Flow:

1. Assess existing documentation:
   - Check for README.md
   - Look for docstrings in code
   - Identify documentation gaps

2. Create documentation:
   - Use clear, concise language
   - Include examples when helpful
   - Structure information logically

3. Update documentation:
   - Keep documentation current with code
   - Add new features to docs
   - Fix outdated information

4. Documentation best practices:
   - Use markdown for formatting
   - Include code examples
   - Add table of contents for long docs
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
    all_tags.extend(create_flow_tags())
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