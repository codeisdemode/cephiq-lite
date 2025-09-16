from __future__ import annotations

import json
from urllib import request
from urllib.parse import urljoin
from typing import Any, Dict


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

