from __future__ import annotations

import json
import logging
from urllib import request
from urllib.parse import urljoin
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
        return json.loads(body)


def _normalize_base(server_url: str) -> str:
    # Accept SSE endpoint like http://host:8000/sse/ and strip to base
    s = server_url.rstrip("/")
    if s.endswith("/sse"):
        s = s[:-4]
    return s + "/"


def search(server_url: str, query: str) -> Dict[str, Any]:
    base = _normalize_base(server_url)
    obj = _post_json(urljoin(base, "tools/search"), {"query": query})
    items = obj.get("content") or []
    for item in items:
        if item.get("type") == "text":
            try:
                payload = json.loads(item.get("text") or "{}")
                if isinstance(payload, dict) and "results" in payload:
                    return {"results": payload["results"]}
            except Exception:
                pass
    return {"error": "unexpected_mcp_search_output", "raw": obj}


def fetch(server_url: str, id: str) -> Dict[str, Any]:
    base = _normalize_base(server_url)
    obj = _post_json(urljoin(base, "tools/fetch"), {"id": id})
    items = obj.get("content") or []
    for item in items:
        if item.get("type") == "text":
            try:
                payload = json.loads(item.get("text") or "{}")
                if isinstance(payload, dict) and {"id", "title", "text", "url"}.issubset(payload.keys()):
                    return payload
            except Exception:
                pass
    return {"error": "unexpected_mcp_fetch_output", "raw": obj}


def call_tool(name: str, arguments: Dict[str, Any], server_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Call a tool via DIRECT HTTP to the MCP server"""
    try:
        import combined_mcp_server

        # Handle workflow tools specially - they use the generic start_workflow function
        if "workflow" in name and name.startswith("start_") and name.endswith("_workflow"):
            # Extract template_id from tool name: start_system_info_workflow -> system_info
            template_id = name[6:-9]  # Remove "start_" prefix and "_workflow" suffix
            result = combined_mcp_server.start_workflow(template_id)
            return {"text": str(result), "is_error": False}
        else:
            # Map tool names to actual function names
            tool_function_map = {
                "powershell": "execute_passthrough",
                "execute_powershell": "execute_passthrough",
                "shell": "execute_passthrough",
                "bash": "execute_passthrough",
                "python": "execute_python",
                "python_eval": "execute_python_eval",
                # Add more mappings as needed
            }

            # Map parameter names for specific tools
            parameter_mappings = {
                "write_block": {
                    "content": "text",      # LLM sends 'content', function expects 'text'
                    "filename": "path"       # LLM sends 'filename', function expects 'path'
                },
            }

            # Get the actual function name
            func_name = tool_function_map.get(name, name)

            # Apply parameter mappings if needed
            mapped_arguments = arguments.copy()
            if name in parameter_mappings:
                for llm_param, func_param in parameter_mappings[name].items():
                    if llm_param in mapped_arguments:
                        mapped_arguments[func_param] = mapped_arguments.pop(llm_param)

            # Try to call the function
            if hasattr(combined_mcp_server, func_name):
                func = getattr(combined_mcp_server, func_name)

                # Log the call for debugging
                import inspect
                sig = inspect.signature(func)

                # Filter out parameters that don't exist in the function signature
                valid_params = list(sig.parameters.keys())
                invalid_params = [param for param in mapped_arguments.keys() if param not in valid_params]

                # Remove invalid parameters with warning
                if invalid_params:
                    logger.warning(f"Tool '{name}' received invalid parameters: {invalid_params}. Removing them.")
                    for invalid_param in invalid_params:
                        mapped_arguments.pop(invalid_param, None)

                required_params = [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]

                # Check if all required parameters are provided
                missing_params = [p.name for p in required_params if p.name not in mapped_arguments]
                if missing_params:
                    error_msg = f"Tool '{name}' missing required parameters: {missing_params}. "
                    error_msg += f"Provided parameters: {list(mapped_arguments.keys())}. "
                    error_msg += f"Expected parameters: {list(sig.parameters.keys())}. "
                    error_msg += f"Please retry with all required parameters."
                    return {"error": error_msg, "is_error": True}

                result = func(**mapped_arguments)
                return {"text": str(result), "is_error": False}
            else:
                return {"error": f"Tool '{name}' (function '{func_name}') not found", "is_error": True}

    except Exception as e:
        return {"error": f"DIRECT call_tool failed: {e}", "is_error": True}

