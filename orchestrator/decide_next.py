from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
from .debug import get_logger

try:
    from .envelope_validator import validate_envelope  # type: ignore
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parent))
    from envelope_validator import validate_envelope  # type: ignore


DEFAULT_MODEL = os.getenv("DECIDE_MODEL", "gpt-5")
logger = get_logger("decide_next")


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


def _summarize_tools(ws_tools: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for t in ws_tools:
        name = t.get("name")
        mode = t.get("mode")
        desc = (t.get("description") or "").strip()
        risk = (t.get("risk") or {}).get("level", "unknown")
        lines.append(f"- {name} (mode={mode}, risk={risk}) - {desc}")
    return "\n".join(lines)


def _build_messages(context: Dict[str, Any], tools_summary: str, budgets: Dict[str, Any]) -> List[Dict[str, str]]:
    goal = context.get("goal", "")
    last_obs = context.get("last_observation")
    plan = context.get("plan")
    system = (
        "You are an autonomous agent. Output must be ONE JSON object only (no prose).\n"
        "It must conform to the envelope schema with fields: type in [tool,message,finish,plan,ask_human,wait],"
        " brief_rationale, and per-type required fields. Never include chain-of-thought.\n"
        "Use tools to gather facts. For user input: first emit a message (the question), then a wait envelope with event_type 'user_message'.\n"
        "Respect budgets and safety. If uncertain, prefer asking for clarification.\n\n"
        "Tool call envelope examples (exact shapes):\n"
        "- Call a tool: {\"type\":\"tool\",\"tool\":\"mcp_call\",\"arguments\":{\"name\":\"get_current_location\"},\"brief_rationale\":\"...\"}\n"
        "- Perform a search: {\"type\":\"tool\",\"tool\":\"mcp_search\",\"arguments\":{\"query\":\"cats\"},\"brief_rationale\":\"...\"}\n"
        "- Finish: {\"type\":\"finish\",\"result\":{\"summary\":\"...\"},\"brief_rationale\":\"...\"}\n"
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
    user = (
        f"Goal:\n{goal}\n\n"
        f"Current plan (optional):\n{json.dumps(plan, ensure_ascii=False) if plan else 'None'}\n\n"
        f"Last observation (optional):\n{json.dumps(last_obs, ensure_ascii=False) if last_obs is not None else 'None'}\n\n"
        f"{tools}\n{b}\n\n"
        "Respond with a single JSON envelope."
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
        obj = json.loads(text)
        return True, obj
    except Exception as e:
        logger.error("OpenAI call failed: %s", e)
        return False, f"OpenAI call failed: {e}"


def decide_next(context: Dict[str, Any], workspace: Dict[str, Any], envelope_schema_path: Path, max_repairs: int = 2) -> Tuple[bool, Dict[str, Any] | List[str]]:
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

    ok, result = _call_openai_json(messages, model)
    if not ok:
        return False, [str(result)]

    envelope = result  # type: ignore[assignment]
    valid, errs = validate_envelope(envelope, envelope_schema_path)
    repairs = 0
    while not valid and repairs < max_repairs:
        # Ask the model to repair: append errors to the prompt
        err_text = "\n".join(f"- {e}" for e in errs)
        repair_msgs = messages + [
            {
                "role": "system",
                "content": (
                    "The previous JSON was invalid against the schema due to:\n" + err_text +
                    "\nRe-emit a corrected JSON envelope only."
                ),
            }
        ]
        logger.debug("Repair attempt %d with %d errors", repairs + 1, len(errs))
        ok, result = _call_openai_json(repair_msgs, model)
        if not ok:
            return False, [str(result)]
        envelope = result  # type: ignore[assignment]
        valid, errs = validate_envelope(envelope, envelope_schema_path)
        repairs += 1

    if not valid:
        return False, errs
    return True, envelope
