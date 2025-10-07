# Flows Analysis & LLM-Driven Workflow Integration

## Overview

The flows directory contains **predefined workflow templates** that represent common agent tasks. These workflows combine:

1. **JSON Templates** - Declarative workflow definitions
2. **Python Workflows** - Programmatic workflow execution
3. **Intent Resolution** - Mapping user intents to workflows

## Flow Types & Patterns

### 1. JSON Template Workflows

**Structure**:
```json
{
  "id": "workflow_id",
  "name": "Workflow Name",
  "description": "Description",
  "steps": [
    {
      "id": 1,
      "action": "action_name",
      "guidance": "LLM guidance for this step",
      "next_tools": ["tool1", "tool2"],
      "completion_check": "validation_criteria"
    }
  ]
}
```

**Examples Found**:
- `smart_file_creation` - File creation with auto-validation
- `file_search_analysis` - File search and content analysis
- `git_status_review` - Git repository analysis
- `web_research_flow` - Multi-source web research
- `contract_analysis` - Dutch construction contract compliance

### 2. Python Programmatic Workflows

**Example**: `contract_analysis_workflow.py`
- **Multi-phase execution** (6 phases)
- **State management** with context persistence
- **Error handling** and retry logic
- **Progress tracking** and logging

**Phases in Contract Analysis**:
1. Request Planning - Define analysis strategy
2. Text Extraction - OCR and text processing
3. Analysis Execution - Compliance checking
4. Results Processing - Confidence scoring
5. Report Generation - Markdown report creation
6. Quality Assessment - Review and improvements

### 3. Development Workflows

**Example**: `development_workflows.json`
- **Project structure creation** with standard directories
- **Smart file creation** with auto-verification
- **Code refactoring** with validation
- **Project analysis** with reporting

## How Flows Work in the System

### 1. Intent Resolution
```python
# workflow_resolver.py
class WorkflowResolver:
    def resolve_intent_to_template(self, intent_name: str) -> Optional[str]:
        # Maps intents like "contract_analysis_v1" to template IDs
        return self.template_mapping.get(intent_name)

    def create_workflow_envelope(self, template_id: str, intent_name: str, confidence: float):
        # Creates tool envelope to start workflow via MCP
        return {
            "tool_calls": [{
                "name": "mcp_call",
                "arguments": {
                    "name": "start_workflow",
                    "arguments": {"template_id": template_id}
                }
            }]
        }
```

### 2. Workflow Execution Flow
```
User Intent → Intent Recognition → Workflow Resolver → MCP Workflow Start → Multi-step Execution
```

## Key Features of Current Flow System

### 1. **Declarative Workflow Definitions**
- JSON-based templates for easy modification
- Tool guidance and completion criteria
- Parameterized steps with placeholders

### 2. **Multi-phase Execution**
- Sequential phase execution with state persistence
- Error recovery and retry mechanisms
- Progress tracking and logging

### 3. **Tool Integration**
- Predefined tool sequences for common tasks
- Tool validation and error handling
- Parallel tool execution where possible

### 4. **Quality Assurance**
- Completion checks for each step
- Confidence scoring for results
- Quality assessment phases

## Integration with Our Architecture

### How to Add LLM-Driven Flows to Our System

#### 1. **Tag-Based Flow Resolution**
```python
class EnhancedTagManager:
    def resolve_workflow_tags(self, user_context: UserContext, intent: str) -> List[Tag]:
        # Resolve flows based on user role + intent
        # Example: sales_manager + "contract_analysis" → contract_analysis flow
        flow_tags = self.get_flow_tags(intent)
        return self.filter_tags_by_permissions(flow_tags, user_context)
```

#### 2. **Flow-Aware Envelope Engine**
```python
class FlowAwareEnvelopeEngine:
    def make_flow_decision(self, context: Context, current_flow: Flow) -> Envelope:
        # Use flow guidance to inform LLM decisions
        # Flow provides step guidance, next tools, completion criteria
        prompt = self.build_flow_prompt(context, current_flow)
        return self.llm.decide(prompt)
```

#### 3. **Redis Flow State Management**
```python
class FlowStateManager:
    def set_flow_state(self, session_id: str, flow_id: str, state: FlowState):
        key = f"FLOW:{session_id}:{flow_id}"
        self.redis.setex(key, 3600, json.dumps(state))

    def get_current_step(self, session_id: str, flow_id: str) -> Optional[FlowStep]:
        state = self.get_flow_state(session_id, flow_id)
        return state.get("current_step") if state else None
```

## Proposed LLM-Driven Flow System

### 1. **Dynamic Flow Generation**
Instead of predefined JSON templates, use LLM to:
- **Analyze user intent** and generate appropriate workflow
- **Select tools** based on available capabilities and permissions
- **Create step-by-step guidance** tailored to the specific task

### 2. **Adaptive Flow Execution**
- **Real-time step adjustment** based on execution results
- **Tool fallback strategies** when preferred tools fail
- **Confidence-based progression** to next steps

### 3. **Flow Learning & Optimization**
- **Track successful flow patterns** for similar intents
- **Optimize tool sequences** based on performance metrics
- **Learn from user feedback** to improve flow quality

### 4. **Integration with Tag System**
```python
# Flow tags become executable workflows
flow_contract_analysis = Tag(
    tag="flow_contract_analysis",
    kind="flow",
    payload=TagPayload(
        meta=TagMeta(name="Contract Analysis", description="Dutch compliance check"),
        config=TagConfig(
            allowed_tools=["extract_pdf_text", "analyze_text", "create_file"],
            assigned_roles=["legal_analyst", "compliance_officer"]
        ),
        content="""
Workflow: Contract Analysis
Steps:
1. Extract text from PDF using OCR if needed
2. Analyze for Dutch construction compliance requirements
3. Generate compliance report with risk assessment
4. Quality check and confidence scoring
"""
    )
)
```

## Implementation Strategy

### Phase 1: Basic Flow Integration
1. **Extend Tag Manager** to handle flow tags
2. **Create Flow Executor** that interprets flow content
3. **Enhance Envelope Engine** to use flow guidance

### Phase 2: Dynamic Flow Generation
1. **Add Flow Generator** that creates flows from intents
2. **Implement Flow Optimizer** that learns from execution
3. **Create Flow Library** for reusable patterns

### Phase 3: Advanced Features
1. **Multi-flow Coordination** for complex tasks
2. **Flow Versioning** and A/B testing
3. **Flow Marketplace** for sharing successful workflows

## Benefits of LLM-Driven Flows

1. **Adaptability**: Flows generated on-demand for specific tasks
2. **Learning**: System improves flows based on execution results
3. **Flexibility**: No need to predefine all possible workflows
4. **Personalization**: Flows tailored to user roles and contexts
5. **Evolution**: Flows can be optimized and improved over time

This approach combines the structure of predefined workflows with the flexibility of LLM-driven task execution, creating a powerful system that can handle both common patterns and novel scenarios effectively.