from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from mcp.client.sse import aconnect_sse
from mcp.client.session import ClientSession
try:
    from .debug import get_logger  # type: ignore
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.append(str(_Path(__file__).resolve().parent))
    from debug import get_logger  # type: ignore


logger = get_logger("mcp_client_sse")

_SESSIONS: dict[str, ClientSession] = {}
_ACMS: dict[str, any] = {}


def _load_mcp_url() -> Optional[str]:
    """Resolve SSE URL from env or mcpServers.json.

    Order:
    1) Env var MCP_SSE_URL
    2) mcpServers.json (default_label or first server)
    """
    url = os.getenv("MCP_SSE_URL")
    if url:
        return url
    # Try common config locations
    try:
        root = Path(__file__).resolve().parent.parent
        here = Path(__file__).resolve().parent
        for cfg in [here / "mcpServers.json", root / "mcpServers.json", root.parent / "mcpServers.json"]:
            if not cfg.exists():
                continue
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
            except Exception:
                data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            servers = data.get("servers", [])
            default_label = data.get("default_label")
            if default_label:
                for s in servers:
                    if s.get("label") == default_label:
                        return s.get("url")
            if servers:
                return servers[0].get("url")
    except Exception:
        return None
    return None


async def _ensure_session(server_url: Optional[str] = None) -> ClientSession:
    url = server_url or _load_mcp_url()
    if not url:
        raise RuntimeError("MCP_SSE_URL not configured and no mcpServers.json found")
    if url in _SESSIONS:
        return _SESSIONS[url]

    # simple retry with backoff
    delays = [0.2, 0.5, 1.0, 2.0]
    last_err = None
    for d in delays:
        try:
            logger.debug("Connecting SSE to %s", url)
            import httpx
            from httpx_sse import aconnect_sse
            from mcp.types import JSONRPCMessage
            from mcp.shared.message import SessionMessage
            import anyio

            client = httpx.AsyncClient()

            # Create proper duplex streams for ClientSession
            server_to_client_stream, client_from_server_stream = anyio.create_memory_object_stream(100)
            client_to_server_stream, server_from_client_stream = anyio.create_memory_object_stream(100)

            # We'll obtain the messages endpoint from the SAME SSE connection we keep open
            messages_url: Optional[str] = None
            messages_ready = asyncio.Event()

            # Long-lived event processing task (single persistent SSE connection)
            async def process_events():
                """Continuously read SSE events and forward to client"""
                event_client = httpx.AsyncClient(timeout=60.0)  # Longer timeout for event stream
                try:
                    async with aconnect_sse(event_client, "GET", url) as event_source:
                        logger.info("SSE event processing started: %s", url)
                        async for event in event_source.aiter_sse():
                            # Log at INFO so it's visible without DEBUG
                            preview = (event.data[:200] + "...") if (event.data and len(event.data) > 200) else event.data
                            logger.info("SSE event: %s", event.event)
                            logger.debug("SSE event data: %s", preview)
                            # The first event should provide the messages endpoint for this session
                            if event.event == 'endpoint' and event.data:
                                nonlocal messages_url
                                messages_url = event.data.strip()
                                logger.info("Messages endpoint: %s", messages_url)
                                messages_ready.set()
                                continue
                            # Forward any non-endpoint event with JSON payload as JSON-RPC
                            if event.data and event.event != 'endpoint':
                                try:
                                    # Parse SSE data as JSON-RPC message and wrap in SessionMessage
                                    data = json.loads(event.data)
                                    jsonrpc_message = JSONRPCMessage(**data)
                                    message = SessionMessage(message=jsonrpc_message)
                                    await server_to_client_stream.send(message)
                                    logger.debug("Forwarded SSE message to client")
                                except Exception as e:
                                    logger.warning("Failed to parse SSE event: %s", e)
                except Exception as e:
                    logger.error("SSE event processing failed: %s", e, exc_info=True)
                    # Try to send error through the stream if still open
                    try:
                        error_msg = SessionMessage(message=JSONRPCMessage(
                            jsonrpc="2.0",
                            error={"code": -32000, "message": str(e)},
                            id=None
                        ))
                        await server_to_client_stream.send(error_msg)
                    except Exception as stream_err:
                        logger.debug("Could not send error through closed stream: %s", stream_err)
                finally:
                    try:
                        await event_client.aclose()
                    except Exception as close_err:
                        logger.debug("Error closing event client: %s", close_err)

            # Start event processing in background (discovers messages_url and handles responses)
            event_task = asyncio.create_task(process_events())

            async def message_sender():
                """Send messages from client to server via HTTP POST"""
                try:
                    # Wait until the messages endpoint is known for this SSE session
                    await messages_ready.wait()
                    assert messages_url is not None
                    async for message in server_from_client_stream:
                        # Convert message to JSON and POST to messages endpoint
                        message_json = json.dumps(message.message.dict())

                        # Build absolute URL for messages endpoint from the original SSE URL origin
                        import urllib.parse
                        origin = urllib.parse.urlsplit(url)
                        base_origin = f"{origin.scheme}://{origin.netloc}"
                        # messages_url is expected to start with '/messages/...'
                        full_url = urllib.parse.urljoin(base_origin, messages_url)
                        # Ensure timeout param is present for long polling
                        parsed = urllib.parse.urlsplit(full_url)
                        q = (parsed.query + "&" if parsed.query else "") + "timeout=30"
                        full_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, q, parsed.fragment))

                        # Send POST request to messages endpoint with longer timeout
                        response = await client.post(
                            full_url,
                            content=message_json,
                            headers={"Content-Type": "application/json"},
                            timeout=30.0  # Increase timeout to prevent premature connection closure
                        )

                        if response.status_code != 202:  # 202 Accepted is expected
                            logger.warning("Message POST failed: %s - %s", response.status_code, response.text)
                        else:
                            logger.info("Message sent to %s (status=%s)", full_url, response.status_code)
                except Exception as e:
                    logger.error("Message sender error: %s", e)

            # Start message sender in background
            sender_task = asyncio.create_task(message_sender())

            # Create session with the proper streams
            sess = ClientSession(client_from_server_stream, client_to_server_stream)
            await sess.initialize()
            logger.info("MCP SSE session established: %s", url)

            # Store session and cleanup tasks
            _SESSIONS[url] = sess
            _ACMS[url] = {
                'client': client,
                'event_task': event_task,
                'sender_task': sender_task
            }

            return sess

        except Exception as e:
            last_err = e
            logger.warning("SSE connect failed (%s), retrying in %.1fs", e, d)
            await asyncio.sleep(d)
    raise RuntimeError(f"Failed to connect to MCP SSE at {url}: {last_err}")


async def list_tools_async(server_url: Optional[str] = None) -> Dict[str, Any]:
    logger.debug("list_tools (sse) url=%s", server_url)
    sess = await _ensure_session(server_url)
    res = await sess.list_tools()
    return {"tools": [t.name for t in res.tools]}


async def call_tool_async(name: str, arguments: Dict[str, Any] | None = None, server_url: Optional[str] = None) -> Dict[str, Any]:
    logger.debug("call_tool sse name=%s args=%s url=%s", name, arguments, server_url)
    sess = await _ensure_session(server_url)
    res = await sess.call_tool(name=name, arguments=arguments or {})
    out: Dict[str, Any] = {"is_error": bool(res.isError)}
    if res.structuredContent is not None:
        out["structured"] = res.structuredContent
    texts = []
    for block in res.content:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    if texts:
        out["text"] = "\n".join(texts)
    return out


def call_tool(name: str, arguments: Dict[str, Any] | None = None, server_url: Optional[str] = None) -> Dict[str, Any]:
    return asyncio.run(call_tool_async(name, arguments, server_url))
