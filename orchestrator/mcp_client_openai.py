from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def _try_openai_client():
    try:
        from openai import OpenAI  # type: ignore
        return ("new", OpenAI)
    except Exception:
        try:
            import openai  # type: ignore
            return ("legacy", openai)
        except Exception:
            return (None, None)


def _call_responses_mcp(server_label: str, server_url: str, prompt_user: str) -> str:
    kind, client_ctor = _try_openai_client()
    if kind is None:
        raise RuntimeError("OpenAI SDK not installed")
    if kind != "new":
        raise RuntimeError("Responses API requires the new OpenAI SDK")
    client = client_ctor()
    resp = client.responses.create(
        model=os.getenv("MCP_MODEL", "o4-mini-deep-research"),
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a research assistant that searches MCP servers to find answers to your questions.",
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": prompt_user}]},
        ],
        tools=[
            {
                "type": "mcp",
                "server_label": server_label,
                "server_url": server_url,
                "allowed_tools": ["search", "fetch"],
                "require_approval": "never",
            }
        ],
        reasoning={"summary": "auto"},
    )
    # Extract assistant output text (JSON-encoded string per MCP tool contract)
    parts: List[str] = []
    for item in getattr(resp, "output", []) or []:  # type: ignore[attr-defined]
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    parts.append(getattr(c, "text", ""))
    return "\n".join(parts).strip()


def search(server_label: str, server_url: str, query: str) -> Dict[str, Any]:
    """
    Calls an MCP server via OpenAI Responses API to perform a search.
    Returns {results: [{id,title,url}, ...]}.
    """
    text = _call_responses_mcp(server_label, server_url, f"SEARCH: {query}")
    # The MCP server returns a content item whose text is a JSON-encoded object with a `results` array.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "results" in obj:
            return {"results": obj["results"]}
    except Exception:
        pass
    return {"error": "unexpected_mcp_search_output", "raw": text[:500]}


def fetch(server_label: str, server_url: str, id: str) -> Dict[str, Any]:
    """
    Calls an MCP server via OpenAI Responses API to fetch a document by id.
    Returns {id,title,text,url,metadata?}.
    """
    text = _call_responses_mcp(server_label, server_url, f"FETCH: {id}")
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and {"id", "title", "text", "url"}.issubset(obj.keys()):
            return obj
    except Exception:
        pass
    return {"error": "unexpected_mcp_fetch_output", "raw": text[:500]}

