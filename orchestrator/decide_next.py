from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple
from pathlib import Path
try:
    from .debug import get_logger  # type: ignore
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parent))
    from debug import get_logger  # type: ignore

try:
    from .envelope_validator import validate_envelope  # type: ignore
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parent))
    from envelope_validator import validate_envelope  # type: ignore


DEFAULT_MODEL = os.getenv("DECIDE_MODEL", "gpt-5")
logger = get_logger("decide_next")


def _clean_and_parse_json(text: str) -> Tuple[bool, Dict[str, Any] | str]:
    """
    Attempt to clean and parse JSON from model responses with multiple fallback strategies.
    Returns (success: bool, result: Dict | error_message: str)
    """
    if not text or not text.strip():
        return False, "Empty response text"

    original_text = text.strip()
    logger.debug("Attempting to parse JSON from %d chars", len(original_text))

    # Strategy 1: Try parsing as-is
    try:
        obj = json.loads(original_text)
        if isinstance(obj, dict):
            logger.debug("JSON parsed successfully on first attempt")
            return True, obj
    except json.JSONDecodeError as e:
        logger.debug("Direct JSON parse failed: %s", e)

    # Strategy 2: Extract JSON from markdown code blocks
    code_block_patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'`([^`]+)`'
    ]

    for pattern in code_block_patterns:
        matches = re.findall(pattern, original_text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                obj = json.loads(match.strip())
                if isinstance(obj, dict):
                    logger.debug("JSON extracted from code block successfully")
                    return True, obj
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find JSON object boundaries more carefully
    # Look for outermost curly braces
    brace_count = 0
    start_pos = -1
    end_pos = -1

    for i, char in enumerate(original_text):
        if char == '{':
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                end_pos = i
                break

    if start_pos != -1 and end_pos != -1:
        json_candidate = original_text[start_pos:end_pos + 1]
        try:
            obj = json.loads(json_candidate)
            if isinstance(obj, dict):
                logger.debug("JSON extracted via brace counting successfully")
                return True, obj
        except json.JSONDecodeError as e:
            logger.debug("Brace-extracted JSON parse failed: %s", e)

    # Strategy 4: Clean common formatting issues
    cleaned_text = original_text

    # Remove leading/trailing prose
    lines = cleaned_text.split('\n')
    start_line = 0
    end_line = len(lines)

    for i, line in enumerate(lines):
        if line.strip().startswith('{'):
            start_line = i
            break

    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().endswith('}'):
            end_line = i + 1
            break

    if start_line < end_line:
        cleaned_text = '\n'.join(lines[start_line:end_line])
        try:
            obj = json.loads(cleaned_text)
            if isinstance(obj, dict):
                logger.debug("JSON parsed after line cleaning")
                return True, obj
        except json.JSONDecodeError as e:
            logger.debug("Line-cleaned JSON parse failed: %s", e)

    # Strategy 5: Fix common JSON syntax issues
    repair_patterns = [
        # Fix trailing commas
        (r',(\s*[}\]])', r'\1'),
        # Fix missing quotes on keys
        (r'(\w+):', r'"\1":'),
        # Fix single quotes to double quotes
        (r"'([^']*)'", r'"\1"'),
        # Remove comments
        (r'//.*?\n', '\n'),
        (r'/\*.*?\*/', ''),
    ]

    repaired_text = cleaned_text
    for pattern, replacement in repair_patterns:
        repaired_text = re.sub(pattern, replacement, repaired_text)

    try:
        obj = json.loads(repaired_text)
        if isinstance(obj, dict):
            logger.debug("JSON parsed after syntax repair")
            return True, obj
    except json.JSONDecodeError as e:
        logger.debug("Repaired JSON parse failed: %s", e)

    # Strategy 6: Last resort - try to construct minimal valid envelope
    logger.warning("All JSON parsing strategies failed, creating error envelope")

    # Try to extract at least the state if possible
    state_match = re.search(r'"state"\s*:\s*"([^"]+)"', original_text)
    extracted_state = state_match.group(1) if state_match else "error"

    error_envelope = {
        "envelope_id": "parse_error",
        "timestamp": "2024-01-01T00:00:00Z",
        "state": "error",
        "brief_rationale": "Failed to parse JSON response",
        "error": {
            "error_type": "json_parse_error",
            "error_message": f"Could not parse model response as valid JSON. Original text: {original_text[:500]}...",
            "suggested_repair": "retry"
        }
    }

    return True, error_envelope


def _auto_repair_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to auto-repair common envelope schema violations.
    Returns a repaired envelope that should pass validation.
    """
    logger.debug("Attempting to auto-repair envelope")
    repaired = envelope.copy()

    # Ensure required fields exist
    if "state" not in repaired:
        repaired["state"] = "error"
        logger.debug("Added missing 'state' field")

    if "brief_rationale" not in repaired:
        repaired["brief_rationale"] = "Auto-generated rationale"
        logger.debug("Added missing 'brief_rationale' field")

    # Add envelope_id if missing
    if "envelope_id" not in repaired:
        import uuid
        repaired["envelope_id"] = str(uuid.uuid4())[:8]
        logger.debug("Added missing 'envelope_id' field")

    # Add timestamp if missing
    if "timestamp" not in repaired:
        from datetime import datetime
        repaired["timestamp"] = datetime.utcnow().isoformat() + "Z"
        logger.debug("Added missing 'timestamp' field")

    # Validate and fix state-specific requirements
    state = repaired.get("state")

    if state == "tool":
        if "tool" not in repaired:
            # Don't set a default tool name - this should be validated as an error
            # Instead, set state to error to indicate the envelope is invalid
            repaired["state"] = "error"
            repaired["error"] = {
                "error_type": "missing_tool_name",
                "error_message": "Tool state requires a valid tool name"
            }
            logger.debug("Changed state to error due to missing tool name")
        if "arguments" not in repaired:
            repaired["arguments"] = {}
            logger.debug("Added missing 'arguments' field for tool state")

    elif state == "message":
        if "conversation" not in repaired:
            repaired["conversation"] = {"utterance": "Auto-generated message"}
            logger.debug("Added missing 'conversation' field for message state")
        elif "utterance" not in repaired["conversation"]:
            repaired["conversation"]["utterance"] = "Auto-generated message"
            logger.debug("Added missing 'utterance' field in conversation")

    # Ensure meta object exists if goal_update, todo_update, or continue are present
    if "meta" in repaired:
        if "goal_update" in repaired["meta"] and not isinstance(repaired["meta"]["goal_update"], dict):
            repaired["meta"]["goal_update"] = {"new_goal": "", "reason": ""}
            logger.debug("Fixed invalid goal_update structure")
        if "todo_update" in repaired["meta"] and not isinstance(repaired["meta"]["todo_update"], dict):
            repaired["meta"]["todo_update"] = {
                "action": "add",
                "todo": {"id": "", "content": "", "status": "pending"},
                "reason": ""
            }
            logger.debug("Fixed invalid todo_update structure")
        if "continue" in repaired["meta"] and not isinstance(repaired["meta"]["continue"], bool):
            # Default to true for safety (continue conversation)
            repaired["meta"]["continue"] = True
            logger.debug("Fixed invalid continue field")

    elif state == "plan":
        if "plan" not in repaired:
            repaired["plan"] = {
                "root_task": "Auto-generated plan",
                "steps": []
            }
            logger.debug("Added missing 'plan' field for plan state")
        else:
            if "root_task" not in repaired["plan"]:
                repaired["plan"]["root_task"] = "Auto-generated task"
                logger.debug("Added missing 'root_task' in plan")
            if "steps" not in repaired["plan"]:
                repaired["plan"]["steps"] = []
                logger.debug("Added missing 'steps' in plan")

    elif state == "ask_human":
        if "reason" not in repaired:
            repaired["reason"] = "Auto-generated reason"
            logger.debug("Added missing 'reason' field for ask_human state")

    elif state == "wait":
        if "wait" not in repaired:
            repaired["wait"] = {"event_type": "timeout"}
            logger.debug("Added missing 'wait' field for wait state")
        elif "event_type" not in repaired["wait"]:
            repaired["wait"]["event_type"] = "timeout"
            logger.debug("Added missing 'event_type' in wait")

    elif state == "finish":
        if "finish" not in repaired:
            repaired["finish"] = {"summary": "Auto-generated summary"}
            logger.debug("Added missing 'finish' field for finish state")
        elif "summary" not in repaired["finish"]:
            repaired["finish"]["summary"] = "Auto-generated summary"
            logger.debug("Added missing 'summary' in finish")

    elif state == "handoff":
        if "handoff" not in repaired:
            repaired["handoff"] = {
                "to_agent": "unknown",
                "message": "Auto-generated handoff"
            }
            logger.debug("Added missing 'handoff' field for handoff state")
        else:
            if "to_agent" not in repaired["handoff"]:
                repaired["handoff"]["to_agent"] = "unknown"
                logger.debug("Added missing 'to_agent' in handoff")
            if "message" not in repaired["handoff"]:
                repaired["handoff"]["message"] = "Auto-generated handoff"
                logger.debug("Added missing 'message' in handoff")

    elif state == "reflect":
        if "reflect" not in repaired:
            repaired["reflect"] = {"analysis": "Auto-generated analysis"}
            logger.debug("Added missing 'reflect' field for reflect state")
        elif "analysis" not in repaired["reflect"]:
            repaired["reflect"]["analysis"] = "Auto-generated analysis"
            logger.debug("Added missing 'analysis' in reflect")

    elif state == "error":
        if "error" not in repaired:
            repaired["error"] = {
                "error_type": "unknown",
                "error_message": "Auto-generated error"
            }
            logger.debug("Added missing 'error' field for error state")
        else:
            if "error_type" not in repaired["error"]:
                repaired["error"]["error_type"] = "unknown"
                logger.debug("Added missing 'error_type' in error")
            if "error_message" not in repaired["error"]:
                repaired["error"]["error_message"] = "Auto-generated error"
                logger.debug("Added missing 'error_message' in error")

    # Validate state is in allowed enum
    valid_states = ["message", "tool", "plan", "finish", "ask_human", "wait", "handoff", "reflect", "error"]
    if repaired["state"] not in valid_states:
        logger.debug(f"Invalid state '{repaired['state']}', changing to 'error'")
        repaired["state"] = "error"
        if "error" not in repaired:
            repaired["error"] = {
                "error_type": "invalid_state",
                "error_message": f"Original state '{envelope.get('state')}' was invalid"
            }

    logger.debug("Auto-repair completed")
    return repaired


def _try_import_openai():
    try:
        # New SDK
        from openai import OpenAI  # type: ignore
        return ("new", OpenAI)
    except Exception:
        pass
    try:
        # Legacy SDK
        import openai  # type: ignore
        return ("legacy", openai)
    except Exception:
        return (None, None)


def _try_import_anthropic():
    try:
        from anthropic import Anthropic  # type: ignore
        return ("anthropic", Anthropic)
    except Exception:
        return (None, None)


def _summarize_tools(ws_tools: List[Dict[str, Any]]) -> str:
    lines: List[str] = []

    # Tool signature definitions for common tools
    tool_signatures = {
        "read_block": "read_block(path: str, start_line: int, num_lines: int)",
        "write_block": "write_block(path: str, start_line: int, text: str)",
        "read_file": "read_file(path: str)",
        "write_file": "write_file(path: str, content: str)",
        "list_files": "list_files(path: str)",
        "execute_powershell": "execute_powershell(script: str)",
        "execute_python": "execute_python(code: str)",
        "execute_python_eval": "execute_python_eval(expression: str)",
        "search": "search(query: str)",
        "fetch": "fetch(id: str)"
    }

    for t in ws_tools:
        name = t.get("name")
        mode = t.get("mode")
        desc = (t.get("description") or "").strip()
        risk = (t.get("risk") or {}).get("level", "unknown")

        # Add signature if available
        signature = tool_signatures.get(name)
        if signature:
            lines.append(f"- {signature} (mode={mode}, risk={risk}) - {desc}")
        else:
            lines.append(f"- {name} (mode={mode}, risk={risk}) - {desc}")

    return "\n".join(lines)


def _format_conversation_history(history: List[Any]) -> str:
    """Format conversation history in a readable tail -f style"""
    if not history:
        return "No conversation history yet."

    lines = []
    lines.append("Conversation History (most recent first):")
    lines.append("-" * 40)

    # Show last 40 events (adjustable)
    recent_history = history[-40:] if len(history) > 40 else history

    for i, event in enumerate(recent_history, 1):
        if isinstance(event, dict):
            event_type = event.get("type", "unknown")

            if event_type == "user_message":
                text = event.get("text", "")
                lines.append(f"[{i}] USER: {text}")
            elif event_type == "tool_call":
                tool_name = event.get("tool", "unknown")
                lines.append(f"[{i}] TOOL: {tool_name}")
            elif event_type == "tool_result":
                result = event.get("result", {})
                success = result.get("success", False)
                lines.append(f"[{i}] RESULT: {'SUCCESS' if success else 'ERROR'}")
            elif event_type == "message":
                text = event.get("text", event.get("utterance", ""))
                lines.append(f"[{i}] ASSISTANT: {text[:100]}{'...' if len(text) > 100 else ''}")
            elif event_type == "approval_request":
                reason = event.get("reason", "High-risk tool")
                lines.append(f"[{i}] APPROVAL: {reason}")
            else:
                lines.append(f"[{i}] {event_type.upper()}: {str(event)[:100]}...")
        else:
            lines.append(f"[{i}] UNKNOWN: {str(event)[:100]}...")

    if len(history) > 10:
        lines.append(f"... and {len(history) - 10} more events")

    return "\n".join(lines)


def _build_messages(context: Dict[str, Any], tools_summary: str, budgets: Dict[str, Any]) -> List[Dict[str, str]]:
    goal = context.get("goal", "")
    last_obs = context.get("last_observation")
    plan = context.get("plan")
    todo_list = context.get("todo_list", [])
    history = context.get("history", [])

    system = (
        "You are an autonomous agent. ALWAYS output exactly one JSON envelope, no prose.\n"
        "Schema:\n"
        "{\n"
        "  envelope_id: string,\n"
        "  timestamp: ISO-8601 string,\n"
        "  state: one of [message, tool, plan, finish, ask_human, wait, handoff, reflect, error],\n"
        "  brief_rationale: string,\n"
        "  conversation?: {utterance, dialogue_act, target},\n"
        "  tool?: string,\n"
        "  arguments?: object,\n"
        "  server_label?: string,\n"
        "  plan?: {root_task, steps, execution_mode, confidence, revision},\n"
        "  wait?: {event_type, timeout},\n"
        "  finish?: {summary, artifacts},\n"
        "  handoff?: {to_agent, message, context},\n"
        "  reflect?: {analysis, next_action},\n"
        "  error?: {error_type, error_message, suggested_repair},\n"
        "  meta?: {budget:{...}, risk:{level,reason}, goal_update?:{...}, todo_update?:{...}, continue?: boolean}\n"
        "}\n"
        "Rules:\n"
        "- Respond with ONLY this JSON object.\n"
        "- For conversation, use state=message + conversation. dialogue_act can be 'inform','ack','clarify','question'.\n"
        "- For plan: embed steps inline.\n"
        "- For wait: event_type must be explicit.\n"
        "- If something fails, emit state=error with details.\n"
        "- Respect budgets and safety. If uncertain, prefer asking for clarification.\n"
        "- Never include chain-of-thought or prose outside the JSON envelope.\n"
        "\n"
        "Conversation Flow Control:\n"
        "- Use meta.continue: true/false to control whether the conversation should continue after this envelope\n"
        "- Set meta.continue: true ONLY when you need to perform multiple automated steps without user input\n"
        "- Set meta.continue: false when you're waiting for user response or the conversation is complete\n"
        "- For simple conversation responses (questions, suggestions, information), ALWAYS set meta.continue: false\n"
        "- For multi-step automated tasks (file operations, data processing), set meta.continue: true\n"
        "- When you ask the user a question or present options, ALWAYS set meta.continue: false to wait for their response\n"
        "- If you're unsure, default to meta.continue: false to avoid conversation loops\n"
        "\n"
        "Goal Management:\n"
        "- You can update the current goal using meta.goal_update: {new_goal: string, reason: string}\n"
        "- You can manage a todo list using meta.todo_update: {action: 'add'|'remove'|'complete'|'update', todo: {id: string, content: string, status: 'pending'|'in_progress'|'completed', priority: 'low'|'medium'|'high', related_files: [string], notes: string, dependencies: [string], created_at: string, updated_at: string}, reason: string}\n"
        "- Use goal updates when the user's request changes the overall objective\n"
        "- Use todo updates to track multi-step tasks and maintain progress\n"
        "- Enhanced todo fields:\n"
        "  - priority: Set task importance (low/medium/high)\n"
        "  - related_files: Track which files are relevant to this task\n"
        "  - notes: Add contextual information, debugging insights, or important details\n"
        "  - dependencies: Track task relationships and prerequisites\n"
        "  - created_at/updated_at: Track task timeline (ISO format)\n"
    )
    servers_info = ""
    try:
        servers = context.get("mcp_servers") or {}
        if isinstance(servers, dict) and servers:
            labels = ", ".join(sorted(servers.keys()))
            servers_info = f"Available MCP servers (labels): {labels}. If more than one, include server_label in mcp_call.\n"
    except Exception:
        pass
    tools = f"Available tools:\n{tools_summary}\n{servers_info}"
    b = f"Budgets remaining: tokens={budgets.get('tokens_remaining','?')}, tool_cost_usd={budgets.get('tool_cost_remaining_usd','?')}, steps={budgets.get('steps_remaining','?')}"
    # Build scratchpad from active todos
    scratchpad = ""
    if todo_list:
        active_todos = [t for t in todo_list if t.get("status") in ["pending", "in_progress"]]
        if active_todos:
            scratchpad = "Active Context (Scratchpad):\n"
            for i, todo in enumerate(active_todos, 1):
                scratchpad += f"{i}. {todo.get('content', '')} ({todo.get('status', 'pending')})\n"
                if todo.get('priority'):
                    scratchpad += f"   Priority: {todo['priority']}\n"
                if todo.get('related_files'):
                    scratchpad += f"   Files: {', '.join(todo['related_files'])}\n"
                if todo.get('notes'):
                    scratchpad += f"   Notes: {todo['notes']}\n"
                if todo.get('dependencies'):
                    scratchpad += f"   Depends on: {', '.join(todo['dependencies'])}\n"
                scratchpad += "\n"

    user = (
        f"Goal:\n{goal}\n\n"
        f"{_format_conversation_history(history)}\n\n"
        f"{scratchpad}"
        f"Current plan:\n{json.dumps(plan, ensure_ascii=False) if plan else 'None'}\n\n"
        f"Todo list ({len(todo_list)} items):\n"
        f"{json.dumps(todo_list, ensure_ascii=False) if todo_list else 'None'}\n\n"
        f"Last observation:\n{json.dumps(last_obs, ensure_ascii=False) if last_obs is not None else 'None'}\n\n"
        f"{tools}\n"
        f"Budgets:\n{b}\n\n"
        "Output the next envelope in this state machine.\n"
        "If you want to speak naturally, use state=message with conversation. If you need tools, use state=tool. "
        "If you need to pause, use state=wait. If you're done, first send a final summary message using state=message, then use state=finish. "
        "If you want to hand off, use state=handoff. "
        "If you want to critique or self-correct, use state=reflect. "
        "If an error occurs, use state=error.\n\n"
        "Goal Management Instructions:\n"
        "- If the user's request changes the overall objective, update the goal using meta.goal_update\n"
        "- If you're starting a multi-step task, add todos to track progress\n"
        "- Update todo status as you complete tasks\n"
        "- Prioritize the user's current request over the static goal\n"
        "- When the user provides a new request that differs from the current goal, update the goal to reflect their actual intent\n"
        "- Avoid getting stuck on generic goals like 'CLI Chat Session' - update to specific user requests\n"
        "\nEnhanced Todo System Instructions:\n"
        "- Use the scratchpad section above for important context like file references, notes, and dependencies\n"
        "- When adding todos, include relevant files, priority, and any important notes\n"
        "- Update todo notes to capture debugging insights or important context\n"
        "- Use priority levels (low/medium/high) to indicate task importance\n"
        "- Track file dependencies to remember which files are relevant to which tasks\n"
        "\nConversation Flow Control Instructions:\n"
        "- Use meta.continue: true/false to control whether the conversation should continue\n"
        "- **ALWAYS set meta.continue: false when:**\n"
        "  - You ask the user a question (like 'Which option do you prefer?')\n"
        "  - You present options for the user to choose from\n"
        "  - You provide information and wait for user response\n"
        "  - The conversation is a simple back-and-forth exchange\n"
        "- **ONLY set meta.continue: true when:**\n"
        "  - You need to perform automated multi-step operations without user input\n"
        "  - You're executing a sequence of tools to complete a task\n"
        "  - The user explicitly asked for automated processing\n"
        "- **Examples:**\n"
        "  - User: 'What can you do?' → Response with options → meta.continue: false (wait for choice)\n"
        "  - User: 'Create a file for me' → Execute tools → meta.continue: true (automated steps)\n"
        "  - User: 'Suggest a demo' → Present suggestions → meta.continue: false (wait for selection)\n"
        "\nCompletion Instructions:\n"
        "- When you complete a task, always send a final summary message using state=message first\n"
        "- Include a completion summary, key results, and any important follow-up information\n"
        "- After sending the final message, use state=finish to complete the task\n"
        "- This ensures the user receives clear feedback about what was accomplished\n"
        "\nTool Selection Instructions:\n"
        "- ALWAYS select a specific, valid tool name from the Available tools list above\n"
        "- NEVER use 'unknown' as a tool name - this will cause an error\n"
        "- If you need to perform an action but don't see an appropriate tool, use state=message to ask for clarification\n"
        "\nTool Parameter Instructions:\n"
        "- ALWAYS check the tool signature above to ensure you provide ALL required parameters\n"
        "- Common parameter mistakes to avoid:\n"
        "  - read_block: requires path, start_line, AND num_lines (not just path and start_line)\n"
        "  - write_block: requires path, start_line, AND text (not just path and content)\n"
        "  - read_file: requires only path\n"
        "  - write_file: requires path AND content\n"
        "- If you're unsure about parameters, check the tool signature in the Available tools section\n"
        "- Never assume parameters - always verify against the signature\n"
        "\nTool Error Handling Instructions:\n"
        "- If a tool call fails with a parameter error, read the error message carefully\n"
        "- The error will show which parameters are missing and which were provided\n"
        "- It will also show the function signature with expected parameter names\n"
        "- Retry the tool call with the correct parameter names and values\n"
        "- Example: If error says 'missing required parameters: [num_lines]', add num_lines parameter\n"
        "- Use state=tool to retry the tool call with corrected parameters\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_openai_json(messages: List[Dict[str, str]], model: str) -> Tuple[bool, Dict[str, Any] | str]:
    kind, client_ctor = _try_import_openai()
    if kind is None:
        logger.error("OpenAI SDK not installed")
        return False, "OpenAI SDK not installed. Install 'openai' package to enable live decisions."

    try:
        if kind == "new":
            client = client_ctor()
            # Prefer Responses API if available (omit temperature if unsupported)
            try:
                logger.debug("Calling Responses API model=%s (json_object)", model)
                resp = client.responses.create(
                    model=model,
                    input=[{"role": m["role"], "content": [{"type": "text", "text": m["content"]}]} for m in messages],
                    response_format={"type": "json_object"},
                )
                # Extract text
                text_parts = []
                for item in getattr(resp, "output", []) or []:  # type: ignore[attr-defined]
                    if getattr(item, "type", None) == "message":
                        for part in getattr(item, "content", []) or []:
                            if getattr(part, "type", None) == "output_text":
                                text_parts.append(getattr(part, "text", ""))
                text = "\n".join(text_parts).strip()
                try:
                    # Best-effort debug dump (truncated)
                    raw = getattr(resp, "model_dump_json", None)
                    raw_json = raw() if callable(raw) else str(resp)
                    logger.debug("OpenAI Responses raw (trunc 2000): %s", raw_json[:2000])
                except Exception:
                    pass
            except Exception as _e1:
                # Fallback to chat.completions style (if present)
                try:
                    logger.debug("Falling back to chat.completions model=%s", model)
                    resp = client.chat.completions.create(  # type: ignore[attr-defined]
                        model=model,
                        messages=messages,
                    )
                    text = resp.choices[0].message.content  # type: ignore[index]
                    try:
                        # Minimal debug of raw response
                        from json import dumps as _dumps
                        logger.debug("OpenAI Chat raw (trunc 2000): %s", _dumps(resp.dict() if hasattr(resp, 'dict') else resp.__dict__, ensure_ascii=False)[:2000])
                    except Exception:
                        logger.debug("OpenAI Chat raw (repr trunc 2000): %s", repr(resp)[:2000])
                except Exception as _e2:
                    # Last resort: legacy API below
                    logger.error("OpenAI new SDK calls failed: %s | %s", _e1, _e2)
                    raise
        else:
            openai = client_ctor
            try:
                logger.debug("Legacy ChatCompletion model=%s", model)
                resp = openai.ChatCompletion.create(
                    model=model,
                    messages=messages,
                )
                text = resp["choices"][0]["message"]["content"]
                try:
                    from json import dumps as _dumps
                    logger.debug("OpenAI Legacy Chat raw (trunc 2000): %s", _dumps(resp, ensure_ascii=False)[:2000])
                except Exception:
                    pass
            except Exception as e:
                # If the model rejects temperature/response_format, retry without them
                logger.error("Legacy ChatCompletion failed: %s", e)
                raise

        logger.debug("OpenAI returned %d chars", len(text) if text else -1)
        if text:
            logger.debug("OpenAI text (trunc 1000): %s", text[:1000])

        # Use robust JSON parsing
        success, result = _clean_and_parse_json(text)
        if success:
            return True, result
        else:
            return False, f"Failed to parse OpenAI JSON response: {result}"
    except Exception as e:
        logger.error("OpenAI call failed: %s", e)
        return False, f"OpenAI call failed: {e}"


def _call_anthropic_json(messages: List[Dict[str, str]], model: str) -> Tuple[bool, Dict[str, Any] | str]:
    kind, client_ctor = _try_import_anthropic()
    if kind is None:
        logger.error("Anthropic SDK not installed")
        return False, "Anthropic SDK not installed. Install 'anthropic' package to enable Claude decisions."

    try:
        client = client_ctor()

        # Convert messages to Anthropic format
        system_message = ""
        conversation_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                conversation_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Call Anthropic API
        logger.debug("Calling Anthropic API model=%s", model)

        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system_message,
            messages=conversation_messages,
        )

        # Extract and parse JSON response
        text = response.content[0].text
        logger.debug("Anthropic returned %d chars", len(text) if text else -1)

        if text:
            logger.debug("Anthropic text (trunc 1000): %s", text[:1000])

            # Check for truncated response (unterminated strings/brackets)
            if text.count('{') != text.count('}') or text.count('[') != text.count(']'):
                logger.warning("Response appears truncated - bracket mismatch detected")
                return False, "Response appears truncated (bracket mismatch)"

            # Check for unterminated strings
            if text.count('"') % 2 != 0:
                logger.warning("Response appears truncated - unterminated string detected")
                return False, "Response appears truncated (unterminated string)"

            # Use robust JSON parsing
            success, result = _clean_and_parse_json(text)
            if success:
                return True, result
            else:
                return False, f"Failed to parse Anthropic JSON response: {result}"

        return False, "Empty response from Anthropic"

    except Exception as e:
        logger.error("Anthropic call failed: %s", e)
        return False, f"Anthropic call failed: {e}"


def _decide_next_attempt(context: Dict[str, Any], workspace: Dict[str, Any], envelope_schema_path: Path, max_repairs: int = 2) -> Tuple[bool, Dict[str, Any] | List[str]]:
    """Single attempt at generating a valid envelope."""
    tools_summary = _summarize_tools(workspace.get("tools", []))
    spend = ((workspace.get("policies") or {}).get("autonomy") or {}).get("spend_limits", {})
    budgets = {
        "tokens_remaining": spend.get("max_tokens"),
        "tool_cost_remaining_usd": spend.get("max_tool_cost_usd"),
        "steps_remaining": context.get("steps_remaining"),
    }

    messages = _build_messages(context, tools_summary, budgets)
    try:
        logger.debug("Prompt sizes: system=%d, user=%d", len(messages[0]['content']), len(messages[1]['content']))
    except Exception:
        pass
    model = ((workspace.get("agent") or {}).get("model") or {}).get("name", DEFAULT_MODEL)

    # Determine which API to use based on model name
    if model.startswith("claude"):
        ok, result = _call_anthropic_json(messages, model)
    else:
        ok, result = _call_openai_json(messages, model)

    if not ok:
        return False, [str(result)]

    envelope = result  # type: ignore[assignment]
    valid, errs = validate_envelope(envelope, envelope_schema_path)
    repairs = 0

    # First try auto-repair if validation fails
    if not valid and isinstance(envelope, dict):
        logger.debug("Initial validation failed, attempting auto-repair")
        auto_repaired = _auto_repair_envelope(envelope)
        auto_valid, auto_errs = validate_envelope(auto_repaired, envelope_schema_path)
        if auto_valid:
            logger.debug("Auto-repair successful")
            return True, auto_repaired
        else:
            logger.debug("Auto-repair failed, %d errors remain", len(auto_errs))
            envelope = auto_repaired  # Use the auto-repaired version for LLM repair
            errs = auto_errs

    # If auto-repair didn't work, try LLM-based repair
    while not valid and repairs < max_repairs:
        # Ask the model to repair: append errors to the prompt
        err_text = "\n".join(f"- {e}" for e in errs)
        repair_msgs = messages + [
            {
                "role": "system",
                "content": (
                    "The previous JSON was invalid against the schema due to:\n" + err_text +
                    "\nRe-emit a corrected JSON envelope only. Follow the schema exactly."
                ),
            }
        ]
        logger.debug("LLM repair attempt %d with %d errors", repairs + 1, len(errs))

        # Use the same provider logic as main call
        if model.startswith("claude"):
            ok, result = _call_anthropic_json(repair_msgs, model)
        else:
            ok, result = _call_openai_json(repair_msgs, model)

        if not ok:
            logger.error("LLM repair call failed: %s", result)
            # Fall back to auto-repair if LLM repair fails
            if isinstance(envelope, dict):
                fallback_repaired = _auto_repair_envelope(envelope)
                fallback_valid, fallback_errs = validate_envelope(fallback_repaired, envelope_schema_path)
                if fallback_valid:
                    logger.debug("Fallback auto-repair successful")
                    return True, fallback_repaired
            return False, [str(result)]

        envelope = result  # type: ignore[assignment]

        # Try auto-repair on the LLM response too
        if isinstance(envelope, dict):
            pre_repair_valid, pre_repair_errs = validate_envelope(envelope, envelope_schema_path)
            if not pre_repair_valid:
                envelope = _auto_repair_envelope(envelope)

        valid, errs = validate_envelope(envelope, envelope_schema_path)
        repairs += 1

    if not valid:
        # Last resort: force a valid error envelope
        logger.warning("All repair attempts failed, creating fallback error envelope")
        fallback_envelope = {
            "envelope_id": "fallback_error",
            "timestamp": "2024-01-01T00:00:00Z",
            "state": "error",
            "brief_rationale": "Multiple repair attempts failed",
            "error": {
                "error_type": "validation_failure",
                "error_message": f"Could not create valid envelope after {repairs} repair attempts. Errors: {errs[:3]}",
                "suggested_repair": "retry"
            }
        }
        return True, fallback_envelope

    return True, envelope


def decide_next(context: Dict[str, Any], workspace: Dict[str, Any], envelope_schema_path: Path, max_repairs: int = 2, max_retries: int = 3) -> Tuple[bool, Dict[str, Any] | List[str]]:
    """
    Generate a valid envelope with exponential backoff retry logic.

    Args:
        context: Current context state
        workspace: Workspace configuration
        envelope_schema_path: Path to envelope schema for validation
        max_repairs: Maximum number of LLM repair attempts per try
        max_retries: Maximum number of complete retry attempts

    Returns:
        (success: bool, result: Dict | error_messages: List[str])
    """
    import time
    import random

    base_delay = 0.5  # Start with 500ms delay
    max_delay = 8.0   # Cap at 8 seconds

    last_errors = []

    for attempt in range(max_retries + 1):  # +1 to include initial attempt
        if attempt > 0:
            # Calculate exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
            total_delay = delay + jitter

            logger.debug(f"Retry attempt {attempt}/{max_retries} after {total_delay:.2f}s delay")
            time.sleep(total_delay)

        try:
            success, result = _decide_next_attempt(context, workspace, envelope_schema_path, max_repairs)

            if success:
                if attempt > 0:
                    logger.info(f"Successfully generated envelope on attempt {attempt + 1}/{max_retries + 1}")
                return True, result
            else:
                last_errors = result if isinstance(result, list) else [str(result)]
                logger.warning(f"Attempt {attempt + 1} failed: {last_errors}")

                # Don't retry if it's a fundamental configuration issue
                if any("SDK not installed" in str(err) for err in last_errors):
                    logger.error("Fundamental configuration issue, not retrying")
                    break

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} raised exception: {e}")
            last_errors = [f"Exception during attempt {attempt + 1}: {e}"]

            # Don't retry for certain critical errors
            if "import" in str(e).lower() or "module" in str(e).lower():
                logger.error("Import/module error, not retrying")
                break

    # All retries failed - return the best error we have
    logger.error(f"All {max_retries + 1} attempts failed")

    # Create a final fallback error envelope if possible
    try:
        fallback_envelope = {
            "envelope_id": "retry_exhausted",
            "timestamp": "2024-01-01T00:00:00Z",
            "state": "error",
            "brief_rationale": f"All {max_retries + 1} generation attempts failed",
            "error": {
                "error_type": "generation_failure",
                "error_message": f"Exhausted all retry attempts. Last errors: {last_errors[:2]}",
                "suggested_repair": "check_configuration"
            }
        }

        # Validate this fallback envelope
        try:
            from envelope_validator import validate_envelope  # type: ignore
            valid, _ = validate_envelope(fallback_envelope, envelope_schema_path)
            if valid:
                logger.debug("Returning validated fallback envelope")
                return True, fallback_envelope
        except Exception:
            pass

        # If validation fails, return the envelope anyway
        logger.debug("Returning unvalidated fallback envelope")
        return True, fallback_envelope

    except Exception as e:
        logger.error(f"Failed to create fallback envelope: {e}")
        return False, last_errors or [f"Complete failure after {max_retries + 1} attempts"]
