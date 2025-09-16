from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.client.sse import aconnect_sse
from mcp.client.session import ClientSession
from .debug import get_logger


logger = get_logger("mcp_client_sse")

_SESSIONS: dict[str, ClientSession] = {}
_ACMS: dict[str, any] = {}


def _load_mcp_url() -> Optional[str]:
    # Prefer explicit env var
    url = os.getenv("MCP_SSE_URL")
    if url:
        return url
    # Default to local SSE server without trailing slash
    return "http://localhost:8000/sse"


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

            # Get the messages endpoint from SSE
            messages_url = None

            # Use a separate client for endpoint discovery to avoid stream conflicts
            endpoint_client = httpx.AsyncClient()
            try:
                async with aconnect_sse(endpoint_client, "GET", url) as event_source:
                    # Process endpoint event
                    async for event in event_source.aiter_sse():
                        if event.event == 'endpoint' and event.data:
                            messages_url = event.data.strip()
                            logger.info("Messages endpoint: %s", messages_url)
                            break
            finally:
                await endpoint_client.aclose()

            if not messages_url:
                raise RuntimeError("No messages endpoint received from SSE server")

            # Long-lived event processing task
            async def process_events():
                """Continuously read SSE events and forward to client"""
                event_client = httpx.AsyncClient()
                try:
                    async with aconnect_sse(event_client, "GET", url) as event_source:
                        logger.debug("SSE event processing started")
                        async for event in event_source.aiter_sse():
                            logger.debug("Received SSE event: %s - %s", event.event, event.data[:100] if event.data else None)
                            if event.event == 'message' and event.data:
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
                    # Send error through the stream instead of the stream itself
                    error_msg = SessionMessage(message=JSONRPCMessage(
                        jsonrpc="2.0",
                        error={"code": -32000, "message": str(e)},
                        id=None
                    ))
                    await server_to_client_stream.send(error_msg)
                finally:
                    await event_client.aclose()

            # Start event processing in background
            event_task = asyncio.create_task(process_events())

            async def message_sender():
                """Send messages from client to server via HTTP POST"""
                try:
                    async for message in server_from_client_stream:
                        # Convert message to JSON and POST to messages endpoint
                        message_json = json.dumps(message.message.dict())

                        # Send POST request to messages endpoint
                        response = await client.post(
                            f"http://127.0.0.1:8000{messages_url}",
                            content=message_json,
                            headers={"Content-Type": "application/json"}
                        )

                        if response.status_code != 202:  # 202 Accepted is expected
                            logger.warning("Message POST failed: %s - %s", response.status_code, response.text)
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
