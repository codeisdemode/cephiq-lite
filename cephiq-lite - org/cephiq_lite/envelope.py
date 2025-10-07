"""
Envelope v2.1 - Structured agent decision protocol

Every agent output is a JSON envelope with:
- state: What the agent is doing
- meta: Flow control (continue/stop)
- State-specific fields (tool, tools, conversation, etc.)
"""
import json
from typing import Dict, Any, Tuple, List, Optional


# Envelope v2.1 Schema (simplified for Lite)
ENVELOPE_SCHEMA = {
    "states": ["reply", "tool", "tools", "plan", "error", "clarify", "confirm", "reflect"],
    "stop_reasons": ["user_reply", "task_done", "need_approval", "need_input", "error", "dead_end", "budget_exhausted"],
    "required_fields": ["state", "meta"],
    "meta_required": ["continue"]
}


def validate_envelope(envelope: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate envelope against v2.1 schema

    Returns:
        (valid, errors)
    """
    errors = []

    # Check if dict
    if not isinstance(envelope, dict):
        return False, ["Envelope must be a dict"]

    # Check required fields
    if "state" not in envelope:
        errors.append("Missing required field: state")

    if "meta" not in envelope:
        errors.append("Missing required field: meta")

    if errors:
        return False, errors

    # Validate state
    state = envelope.get("state")
    if state not in ENVELOPE_SCHEMA["states"]:
        errors.append(f"Invalid state: {state}. Must be one of {ENVELOPE_SCHEMA['states']}")

    # Validate meta
    meta = envelope.get("meta", {})
    if not isinstance(meta, dict):
        errors.append("meta must be a dict")
    elif "continue" not in meta:
        errors.append("meta.continue is required")
    elif not isinstance(meta.get("continue"), bool):
        errors.append("meta.continue must be a boolean")

    # Validate stop_reason if continue=false
    if meta.get("continue") is False:
        if "stop_reason" not in meta:
            errors.append("meta.stop_reason required when continue=false")
        elif meta["stop_reason"] not in ENVELOPE_SCHEMA["stop_reasons"]:
            errors.append(f"Invalid stop_reason: {meta['stop_reason']}")

    # State-specific validation
    if state == "tool":
        if "tool" not in envelope:
            errors.append("state=tool requires 'tool' field")
        if "arguments" not in envelope:
            errors.append("state=tool requires 'arguments' field")

    elif state == "tools":
        if "tools" not in envelope:
            errors.append("state=tools requires 'tools' field")
        elif not isinstance(envelope.get("tools"), list):
            errors.append("'tools' must be a list")
        else:
            # Validate each tool in array
            for idx, tool_item in enumerate(envelope["tools"]):
                if not isinstance(tool_item, dict):
                    errors.append(f"tools[{idx}] must be a dict")
                    continue
                if "tool" not in tool_item:
                    errors.append(f"tools[{idx}] missing 'tool' field")
                if "arguments" not in tool_item:
                    errors.append(f"tools[{idx}] missing 'arguments' field")
                if "tool_id" not in tool_item:
                    errors.append(f"tools[{idx}] missing 'tool_id' field")

    elif state == "reply":
        if "conversation" not in envelope:
            errors.append("state=reply requires 'conversation' field")
        elif not isinstance(envelope.get("conversation"), dict):
            errors.append("'conversation' must be a dict")
        elif "utterance" not in envelope.get("conversation", {}):
            errors.append("conversation.utterance is required")

    elif state == "error":
        if "error" not in envelope:
            errors.append("state=error requires 'error' field")

    elif state == "clarify":
        if "clarify" not in envelope:
            errors.append("state=clarify requires 'clarify' field")
        elif "question" not in envelope.get("clarify", {}):
            errors.append("clarify.question is required")

    elif state == "confirm":
        if "confirm" not in envelope:
            errors.append("state=confirm requires 'confirm' field")

    elif state == "plan":
        if "plan" not in envelope:
            errors.append("state=plan requires 'plan' field")

    # Validate confidence if present
    if "meta" in envelope and "confidence" in envelope["meta"]:
        conf = envelope["meta"]["confidence"]
        if conf is not None and (not isinstance(conf, (int, float)) or conf < 0 or conf > 1):
            errors.append("meta.confidence must be between 0 and 1")

    # Validate brief_rationale length if present
    if "brief_rationale" in envelope:
        if len(envelope["brief_rationale"]) > 220:
            errors.append("brief_rationale must be <= 220 characters")

    return len(errors) == 0, errors


def normalize_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize envelope for backward compatibility

    - Add missing fields with defaults
    - Migrate deprecated structures
    """
    out = dict(envelope)

    # Ensure meta.confidence exists
    if "meta" in out and isinstance(out["meta"], dict):
        if "confidence" not in out["meta"]:
            out["meta"]["confidence"] = None

    # Auto-generate tool_ids if missing
    if out.get("state") == "tools" and "tools" in out:
        tools_array = out.get("tools", [])
        if isinstance(tools_array, list):
            for idx, tool_item in enumerate(tools_array):
                if isinstance(tool_item, dict):
                    if "tool_id" not in tool_item or not tool_item["tool_id"]:
                        tool_item["tool_id"] = f"tool_{idx}"

    return out


def parse_llm_response(text: str) -> Tuple[bool, Any]:
    """
    Parse LLM response text into envelope

    Handles:
    - Clean JSON
    - JSON in markdown code blocks
    - Prose + JSON mixed

    Returns:
        (success, envelope_or_error)
    """
    # Strategy 1: Try direct JSON parse
    try:
        envelope = json.loads(text)
        return True, envelope
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code blocks
    if "```json" in text or "```" in text:
        try:
            start = text.find("```json")
            if start == -1:
                start = text.find("```")

            if start != -1:
                start = text.find("\n", start) + 1
                end = text.find("```", start)

                if end != -1:
                    json_text = text[start:end].strip()
                    envelope = json.loads(json_text)
                    return True, envelope
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find JSON by brace counting
    brace_count = 0
    start_idx = -1

    for idx, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start_idx = idx
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    json_text = text[start_idx:idx+1]
                    envelope = json.loads(json_text)
                    return True, envelope
                except json.JSONDecodeError:
                    pass

    return False, "Could not extract valid JSON envelope from response"


def create_error_envelope(error_message: str, error_type: str = "parse_error") -> Dict[str, Any]:
    """Create an error envelope"""
    return {
        "state": "error",
        "brief_rationale": "Failed to parse LLM response",
        "error": {
            "error_type": error_type,
            "error_message": error_message
        },
        "meta": {
            "continue": False,
            "stop_reason": "error"
        }
    }


if __name__ == "__main__":
    # Quick self-test
    test_envelopes = [
        # Valid tool envelope
        {
            "state": "tool",
            "brief_rationale": "Creating file",
            "tool": "create_file",
            "arguments": {"path": "test.txt", "content": "hello"},
            "meta": {"continue": True, "confidence": 0.88}
        },
        # Valid multi-tool envelope
        {
            "state": "tools",
            "brief_rationale": "Creating multiple files",
            "tools": [
                {"tool_id": "f1", "tool": "create_file", "arguments": {"path": "a.txt"}},
                {"tool_id": "f2", "tool": "create_file", "arguments": {"path": "b.txt"}}
            ],
            "meta": {"continue": True}
        },
        # Valid reply envelope
        {
            "state": "reply",
            "brief_rationale": "Task complete",
            "conversation": {"utterance": "Files created successfully"},
            "meta": {"continue": False, "stop_reason": "task_done"}
        },
        # Invalid: missing meta
        {
            "state": "tool",
            "tool": "create_file",
            "arguments": {}
        },
        # Invalid: bad stop_reason
        {
            "state": "reply",
            "conversation": {"utterance": "Done"},
            "meta": {"continue": False, "stop_reason": "invalid_reason"}
        }
    ]

    for idx, envelope in enumerate(test_envelopes):
        valid, errors = validate_envelope(envelope)
        print(f"Test {idx + 1}: {'PASS' if valid else 'FAIL'}")
        if not valid:
            for err in errors:
                print(f"  - {err}")
        print()
