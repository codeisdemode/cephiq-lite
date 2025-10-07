# Orchestrator Architecture Plan

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Core                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Tag Manager │  │ MCP Manager │  │ Envelope Engine     │  │
│  │             │  │             │  │                     │  │
│  │ • Tag Store │  │ • Tool Pool │  │ • Decision Loop     │  │
│  │ • RBAC      │  │ • Discovery │  │ • State Machine     │  │
│  │ • Assembly  │  │ • Filtering │  │ • Validation        │  │
│  │ • Tool Auth │  │ • Execution │  │ • Permission Check  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│ Unified Context │ │ Scoped Tools    │ │ Permission-Aware    │
│ & Capabilities  │ │ Execution       │ │ Reasoning           │
│                 │ │                 │ │                     │
│ • Dynamic       │ • Filtered Tool   │ • Tool Access        │
│   Prompts       │   List            │   Validation         │
│ • Tool Policies │ • Scope Enforcement│ • Policy Compliance  │
│ • RBAC Rules    │ • Policy Checks   │ • Error Handling     │
└─────────────────┘ └─────────────────┘ └─────────────────────┘
```

## Core Components

### 1. Tag Manager
**Purpose**: Unified permission, capability, and workflow layer

**Key Features**:
- **Tag-based RBAC**: Controls both prompt content AND tool access
- **Dynamic Context Assembly**: Builds system prompts from resolved tags
- **Tool Permission Contracts**: Defines which tools are accessible and how
- **Flow-as-Tag Contracts**: Executable workflows defined as tags

**Tag Schema**:
```python
@dataclass
class Tag:
    tag: str           # "flow_checkout", "tool_verify_payment"
    kind: str          # "flow", "tool", "role", "function", "company"
    payload: TagPayload

@dataclass
class TagPayload:
    meta: TagMeta
    config: TagConfig  # RBAC: assigned_users, org_scope, allowed_tools
    content: str       # Prompt content OR workflow definition
```

### 2. MCP Manager
**Purpose**: Tool execution infrastructure

**Key Features**:
- **MCP Tool Discovery**: Connect to MCP servers, list available tools
- **Permission Filtering**: Only show tools allowed by user's tags
- **Scope Enforcement**: Apply tool-specific constraints from tags
- **Parallel Execution**: Multi-tool execution via MCP

### 3. Envelope Engine
**Purpose**: Structured agent reasoning with flow awareness

**Key Features**:
- **Decision Loop**: LLM generates structured envelopes
- **Permission Validation**: Validate tool calls against tag permissions
- **State Machine**: Handle tool, tools, plan, reply, error states
- **Confidence Scoring**: Track decision certainty
- **Flow Execution**: Execute tag-based workflows with step progression
- **Adaptive Planning**: Adjust workflow steps based on execution results
- **Multi-Tool Execution**: Execute multiple tools sequentially in one envelope
- **Batch Results**: Aggregate all tool results before next LLM call

## Backend Service Architecture

### Redis Module (Focused Scope)

**Core Functions**:
- `get_session_state(session_id)` / `set_session_state(session_id, state, ttl)`
- Streaming state for ephemeral tool results
- `pub_event(session_id, payload)` for service coordination
- `get_resolved_tags_cache(cache_key)` / `set_resolved_tags_cache(cache_key, tags, ttl)`
- `get_flow_state(session_id, flow_id)` / `set_flow_state(session_id, flow_id, state, ttl)`

**Key Naming Conventions**:
- `SESSION:{session_id}` - Session state (2h TTL)
- `TAGCACHE:{user_id}:{org_id}:{intent}` - Resolved tags (30m TTL)
- `STREAM:{session_id}:events` - Event stream (1h TTL)
- `STREAM:{session_id}:tool_execution` - Tool state (5m TTL)
- `STREAM:{session_id}:tool_results` - Tool results (10m TTL)
- `FLOW:{session_id}:{flow_id}` - Flow execution state (2h TTL)

**TTL Strategy**:
- Session State: 2 hours (extendable)
- Tag Cache: 30 minutes (refresh on changes)
- Event Stream: 1 hour (recent history)
- Tool Execution: 5 minutes (ephemeral)
- Tool Results: 10 minutes (ephemeral)
- Flow State: 2 hours (extendable)

### API Layer

**Endpoints**:
- `POST /sessions` - Create new agent session
- `GET /sessions/{session_id}` - Get session status
- `GET /events/{session_id}` - SSE stream for progress
- `WebSocket /ws/{session_id}` - Real-time updates
- `POST /sessions/{session_id}/interact` - User input for clarification

**Client Integration**:
- **CLI**: REST API polling
- **Web Widget**: WebSocket for live updates
- **Web UI**: SSE for progress streaming
- **Mobile Apps**: REST API with push notifications

## Key Innovations

### 1. Tags as Unified Permission & Workflow Contracts
- Single source of truth for knowledge, capabilities, AND workflows
- Declarative RBAC through tag configuration
- Dynamic permission updates without code changes
- **Flow-as-Tag**: Executable workflows defined as tags

### 2. Three-Layer Separation
- **MCP**: Tool execution layer (infrastructure)
- **Tags**: Prompt composition AND workflow layer (business logic)
- **Envelope**: Decision protocol layer (agent reasoning)

### 3. Permission-Aware Tool Execution
- Tool discovery filtered by tag permissions
- Runtime scope enforcement
- Policy compliance built-in

### 4. LLM-Driven Flow Execution
- **Dynamic Flow Generation**: LLM creates workflows from user intents
- **Adaptive Execution**: Real-time step adjustment based on results
- **Flow Learning**: Optimize workflows based on performance
- **No Predefined Templates**: Flows generated on-demand
- **Multi-Tool Planning**: LLM plans multiple sequential tool calls
- **Batch Execution**: Execute tool sequences without intermediate LLM calls

### 5. Real-time Coordination
- Redis pub/sub for service communication
- WebSocket/SSE for client updates
- Ephemeral state for tool execution progress

## Implementation Benefits

1. **Separation of Concerns**: Each layer evolves independently
2. **Runtime Flexibility**: Change prompts/tools/workflows without redeployment
3. **Enterprise Ready**: Built-in RBAC, auditing, scalability
4. **Performance**: Parallel tool execution, intelligent caching
5. **Developer Experience**: Clear interfaces, minimal boilerplate
6. **Adaptive Workflows**: LLM-driven flows adapt to specific tasks
7. **No Template Maintenance**: No need to predefine all possible workflows
8. **Continuous Learning**: System improves flows based on execution results

## Next Steps

1. Implement focused Redis module
2. Build Tag Manager with permission AND workflow contracts
3. Integrate MCP Manager with tag-based filtering
4. Create Envelope Engine with permission validation AND flow execution
5. Develop API layer with real-time communication
6. Implement LLM-driven flow generation and execution

This architecture creates a **modular, scalable LLM orchestration system** that combines the best of MCP, tag-based contracts, envelope protocol reasoning, and **LLM-driven adaptive workflows**.