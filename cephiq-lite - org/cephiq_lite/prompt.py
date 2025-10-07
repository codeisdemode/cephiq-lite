"""
Prompt Builder for Cephiq Lite

Builds system and user prompts for v2.1 envelope protocol
"""
from typing import Dict, Any, List, Optional

# Supported built-in tools for Cephiq Lite (with brief I/O hints)
ALLOWED_TOOLS: List[str] = [
    "create_file  -> {path, size, message}",
    "read_file    -> {path, content, size}",
    "edit_file    -> {path, replacements, message}",
    "delete_file  -> {path, message}",
    "list_files   -> {path, files, count}",
    "create_directory -> {path, message}",
    "directory_tree  -> {path, tree}",
    "get_cwd      -> {cwd}",
]


# Ultimate v2.1 System Prompt (compact version)
SYSTEM_PROMPT_V2_1 = """
═══════════════════════════════════════════════════════════════
CEPHIQ AGENT SYSTEM v2.1
═══════════════════════════════════════════════════════════════

ROLE
────
Autonomous software engineering agent. Plan → Execute → Report.

OUTPUT CONTRACT
───────────────
Every response MUST be exactly one JSON envelope. No prose outside JSON.

ENVELOPE STRUCTURE
──────────────────
{
  "state": <state>,           // REQUIRED
  "brief_rationale": <string>, // REQUIRED: 1 sentence, ≤220 chars
  "meta": {
    "continue": <boolean>,     // REQUIRED: true=keep going, false=stop
    "stop_reason": <enum>,     // REQUIRED if continue=false
    "confidence": <0.0-1.0>    // OPTIONAL: certainty score
  }
}

STATES
──────
reply   → Respond to user
tool    → Execute one tool
tools   → Execute multiple tools (parallel)
plan    → Create execution plan
error   → Report error
clarify → Ask for clarification
confirm → Request approval

STOP REASONS
────────────
user_reply | task_done | need_approval | need_input | error | dead_end | budget_exhausted

TOOL EXECUTION
──────────────
Single tool:
{"state":"tool","brief_rationale":"Reading config","tool":"read_file","arguments":{"path":"config.json"},"meta":{"continue":true}}

Multiple tools (parallel):
{"state":"tools","brief_rationale":"Creating files in parallel","tools":[
  {"tool_id":"f1","tool":"create_file","arguments":{"path":"a.txt","content":"..."}},
  {"tool_id":"f2","tool":"create_file","arguments":{"path":"b.txt","content":"..."}}
],"meta":{"continue":true}}

WHEN TO USE MULTI-TOOL
──────────────────────
✓ Creating multiple independent files
✓ Reading several files for comparison
✗ Creating directory THEN file inside (dependency!)
✗ Reading file THEN editing based on content (dependency!)

TRUST PROTOCOL
──────────────
Trust tool results with clear success indicators:
  ✓ create_file → {success:true, path:"...", size:1234}
  ✓ edit_file → {success:true, replacements:3}

Verify only when ambiguous:
  ✗ create_file → {success:true, size:0} (empty file?)

CONFIDENCE SCORING
──────────────────
Include meta.confidence (0.0-1.0):
- 0.9-1.0: High confidence, trust results
- 0.7-0.9: Normal operation
- 0.5-0.7: Low confidence, consider verification
- <0.5: Very uncertain, use state=clarify

CORE DIRECTIVES
───────────────
- No prose outside JSON
- Always include meta.continue
- Plan before multi-step execution
- On file errors: explore with directory_tree/list_files, don't retry same path
- Trust clear tool feedback, verify only when ambiguous

EXAMPLES
────────
Greeting:
{"state":"reply","brief_rationale":"Greeting user","conversation":{"utterance":"Hello! How can I help?"},"meta":{"continue":false,"stop_reason":"user_reply"}}

Read file:
{"state":"tool","brief_rationale":"Reading configuration","tool":"read_file","arguments":{"path":"config.json"},"meta":{"continue":true,"confidence":0.85}}

Multi-file creation:
{"state":"tools","brief_rationale":"Creating components in parallel","tools":[
  {"tool_id":"header","tool":"create_file","arguments":{"path":"Header.jsx","content":"..."}},
  {"tool_id":"footer","tool":"create_file","arguments":{"path":"Footer.jsx","content":"..."}}
],"meta":{"continue":true,"confidence":0.92}}

Task complete:
{"state":"reply","brief_rationale":"Task finished successfully","conversation":{"utterance":"Created all files successfully"},"meta":{"continue":false,"stop_reason":"task_done","confidence":0.95}}

Dead end:
{"state":"reply","brief_rationale":"Cannot proceed without file","conversation":{"utterance":"I searched the entire project but cannot find config.json. Can you confirm the path?"},"meta":{"continue":false,"stop_reason":"dead_end","confidence":0.88}}

═══════════════════════════════════════════════════════════════
END SYSTEM PROMPT
═══════════════════════════════════════════════════════════════
"""


class PromptBuilder:
    """Build prompts for LLM with context"""

    def __init__(self, custom_system_prompt: Optional[str] = None):
        self.system_prompt = custom_system_prompt or SYSTEM_PROMPT_V2_1
        self.use_tags = False
        self.tag_manager = None

    def set_tag_manager(self, tag_manager):
        """Set tag manager for tag-based prompts"""
        self.tag_manager = tag_manager
        self.use_tags = True

    def build_messages(
        self,
        goal: str,
        history: List[Dict[str, Any]],
        last_observation: Optional[Dict[str, Any]] = None,
        budgets: Optional[Dict[str, int]] = None,
        tags: Optional[List] = None
    ) -> List[Dict[str, str]]:
        """
        Build message list for LLM

        Args:
            goal: User's goal
            history: List of events
            last_observation: Result from last tool execution
            budgets: Remaining budgets {cycles, tokens}
            tags: List of resolved tags for tag-based prompts

        Returns:
            List of {"role": "system/user", "content": "..."}
        """
        messages = []

        # System message
        if self.use_tags and tags and self.tag_manager:
            # Use tag-based system prompt
            system_prompt = self.tag_manager.build_system_prompt(tags)
        else:
            # Use default system prompt
            system_prompt = self.system_prompt

        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # User message with context
        user_content = self._build_user_context(goal, history, last_observation, budgets)

        messages.append({
            "role": "user",
            "content": user_content
        })

        return messages

    def _build_user_context(
        self,
        goal: str,
        history: List[Dict[str, Any]],
        last_observation: Optional[Dict[str, Any]],
        budgets: Optional[Dict[str, int]]
    ) -> str:
        """Build user context message"""

        sections = []

        # Goal
        sections.append(f"GOAL\n----\n{goal}")

        # Budgets
        if budgets:
            budget_lines = []
            if "cycles" in budgets:
                budget_lines.append(f"Cycles: {budgets['cycles']}")
            if "tokens" in budgets:
                budget_lines.append(f"Tokens: {budgets['tokens']}")

            if budget_lines:
                sections.append("BUDGET REMAINING\n----------------\n" + "\n".join(budget_lines))

        # Tools list (help the model pick valid tools)
        try:
            tools_list = "\n".join(f"- {t}" for t in ALLOWED_TOOLS)
            sections.append(
                "AVAILABLE TOOLS\n----------------\n"
                + tools_list
                + "\n\nConstraints:\n- Use only the tools above.\n- Do NOT use unsupported tools like run_command, shell, bash, or run_python.\n"
            )
        except Exception:
            pass

        # Last observation
        if last_observation:
            obs_text = self._format_observation(last_observation)
            sections.append(f"LAST TOOL RESULT\n----------------\n{obs_text}")

        # History (last 15 events)
        if history:
            hist_text = self._format_history(history[-15:])
            sections.append(f"HISTORY (last {min(15, len(history))} events)\n------------------------------------\n{hist_text}")

        # Task instruction
        sections.append("="*60)
        sections.append("YOUR TASK")
        sections.append("="*60)
        sections.append("\nEmit exactly ONE JSON envelope now.")

        return "\n\n".join(sections)

    def _format_observation(self, obs: Dict[str, Any]) -> str:
        """Format tool observation for display"""

        if obs.get("_multi_tool"):
            # Multi-tool result
            lines = [f"Multi-tool execution ({obs.get('count', 0)} tools):"]

            results = obs.get("results", {})
            for tool_id, result in results.items():
                success = "OK" if result.get("success") else "FAIL"
                tool = result.get("tool", "unknown")
                duration = result.get("duration_ms", 0)

                lines.append(f"  [{success}] {tool_id} ({tool}) - {duration}ms")

                # Add key details
                if result.get("success"):
                    if "path" in result.get("result", {}):
                        lines.append(f"      path: {result['result']['path']}")
                    if "size" in result.get("result", {}):
                        lines.append(f"      size: {result['result']['size']} bytes")
                else:
                    if "error" in result:
                        lines.append(f"      error: {result['error']}")

            return "\n".join(lines)
        else:
            # Single tool result
            success = "SUCCESS" if obs.get("success") else "FAILURE"
            tool = obs.get("tool", "unknown")
            duration = obs.get("duration_ms", 0)

            lines = [f"{success}: {tool} ({duration}ms)"]

            result_data = obs.get("result", {})
            if obs.get("success"):
                # Success - show key fields
                if "path" in result_data:
                    lines.append(f"  path: {result_data['path']}")
                if "size" in result_data:
                    lines.append(f"  size: {result_data['size']} bytes")
                if "replacements" in result_data:
                    lines.append(f"  replacements: {result_data['replacements']}")
                if "message" in result_data:
                    lines.append(f"  {result_data['message']}")
                if "cwd" in result_data:
                    lines.append(f"  cwd: {result_data['cwd']}")
                if "files" in result_data and isinstance(result_data.get("files"), list):
                    files = result_data["files"]
                    preview = ", ".join(files[:5]) + (" ..." if len(files) > 5 else "")
                    lines.append(f"  files[{len(files)}]: {preview}")
                if "tree" in result_data:
                    tree = str(result_data.get("tree", ""))
                    tree_lines = tree.splitlines()
                    preview = "\n    ".join(tree_lines[:6]) + ("\n    ..." if len(tree_lines) > 6 else "")
                    lines.append("  tree:\n    " + preview)
                if "content" in result_data:
                    content = str(result_data.get("content", ""))
                    snippet = content[:200] + ("..." if len(content) > 200 else "")
                    lines.append(f"  content: {snippet}")
                # Generic fallback for other scalar fields
                try:
                    for k, v in result_data.items():
                        if k in {"path", "size", "replacements", "message", "cwd", "files", "tree", "content"}:
                            continue
                        if isinstance(v, (str, int, float, bool)):
                            lines.append(f"  {k}: {v}")
                except Exception:
                    pass
            else:
                # Failure - show error
                error = obs.get("error", "Unknown error")
                lines.append(f"  error: {error}")

            return "\n".join(lines)

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Format history events for display"""

        if not history:
            return "(no history)"

        lines = []
        for idx, event in enumerate(history):
            event_type = event.get("type", "unknown")

            if event_type == "decision":
                envelope = event.get("envelope", {})
                state = envelope.get("state", "unknown")
                rationale = envelope.get("brief_rationale", "")[:50]
                lines.append(f"[{idx}] DECIDE: state={state} ({rationale}...)")

            elif event_type == "tool_result":
                result = event.get("result", {})
                success = "OK" if result.get("success") else "FAIL"
                tool = result.get("tool", "unknown")
                lines.append(f"[{idx}] RESULT: {tool} {success}")

            elif event_type == "tools_result":
                results = event.get("results", {})
                count = results.get("count", 0)
                all_ok = results.get("all_success", False)
                status = "ALL OK" if all_ok else "PARTIAL"
                lines.append(f"[{idx}] MULTI-RESULT: {count} tools {status}")

            else:
                lines.append(f"[{idx}] {event_type.upper()}")

        return "\n".join(lines)


if __name__ == "__main__":
    # Self-test
    builder = PromptBuilder()

    # Test message building
    messages = builder.build_messages(
        goal="Create hello.txt with 'Hello World'",
        history=[
            {
                "type": "decision",
                "envelope": {
                    "state": "tool",
                    "brief_rationale": "Creating hello.txt file",
                    "tool": "create_file",
                    "arguments": {"path": "hello.txt", "content": "Hello World"}
                }
            }
        ],
        last_observation={
            "success": True,
            "tool": "create_file",
            "result": {"path": "hello.txt", "size": 11},
            "duration_ms": 45.2
        },
        budgets={"cycles": 47, "tokens": 95000}
    )

    print("Messages built:")
    print(f"  System message: {len(messages[0]['content'])} chars")
    print(f"  User message: {len(messages[1]['content'])} chars")
    print("\nUser context:")
    # Handle unicode encoding for Windows console
    try:
        print(messages[1]["content"])
    except UnicodeEncodeError:
        print(messages[1]["content"].encode('utf-8', errors='replace').decode('utf-8'))
