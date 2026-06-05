"""MCP clients over SSE (Task 6.2) — the agent operating as the MCP Client.

The agent connects to the Phase-2 Elastic and Arize MCP servers over **SSE** and calls their tools.
(ADK's ``McpToolset`` wraps this same MCP session to expose the tools to the LLM; the deterministic
graph nodes call the tools directly through the session here.) MCP is async; each call opens a short
SSE session and runs it on a private event loop so the synchronous graph nodes can call it.

Failures in the Arize client surface as exceptions; the graph catches them at node 6 and degrades to
a safe lower autonomy tier — a tracing/eval hiccup must never crash incident handling. Heavy ``mcp``
imports are module-level (only the agent process loads this module).
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from lib.logging import get_logger

logger = get_logger("opssentinel.agent.mcp")


def _parse_tool_result(result: Any) -> Any:
    """Extract the structured payload from an MCP CallToolResult."""
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    content = getattr(result, "content", None) or []
    if content and getattr(content[0], "text", None) is not None:
        import json

        return json.loads(content[0].text)
    return None


class SseMcpClient:
    """Synchronous wrapper that calls a named tool over a fresh SSE MCP session."""

    def __init__(self, sse_url: str) -> None:
        self._url = sse_url

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        return asyncio.run(self._call(tool, arguments))

    async def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        async with sse_client(self._url) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            return _parse_tool_result(result)


class ElasticMcpKnowledgeClient:
    """Concrete :class:`app.interfaces.KnowledgeClient` over the Elastic MCP server."""

    def __init__(self, sse_url: str) -> None:
        self._mcp = SseMcpClient(sse_url)

    def fetch_recent_logs(self, service: str, minutes: int = 30) -> list[dict[str, Any]]:
        return self._mcp.call("fetch_recent_logs", {"service": service, "minutes": minutes}) or []

    def search_runbooks(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return self._mcp.call("search_runbooks", {"query": query, "top_k": top_k}) or []

    def write_closure_summary(
        self, incident_id: str, summary: str, tags: list[str]
    ) -> dict[str, Any]:
        return self._mcp.call(
            "write_closure_summary",
            {"incident_id": incident_id, "summary": summary, "tags": tags},
        )


class ArizeMcpEvaluationClient:
    """Concrete :class:`app.interfaces.EvaluationClient` over the Arize MCP server."""

    def __init__(self, sse_url: str) -> None:
        self._mcp = SseMcpClient(sse_url)

    def get_category_accuracy(self, category: str, window: int = 30) -> float:
        return float(
            self._mcp.call("get_category_accuracy", {"category": category, "window": window})
        )

    def get_calibration(self, category: str) -> float:
        return float(self._mcp.call("get_calibration", {"category": category}))

    def is_novel_category(self, category: str) -> bool:
        return bool(self._mcp.call("is_novel_category", {"category": category}))

    def log_outcome(
        self, trace_id: str, incident_id: str, approved: bool, successful: bool
    ) -> dict[str, Any]:
        return self._mcp.call(
            "log_outcome",
            {
                "trace_id": trace_id,
                "incident_id": incident_id,
                "approved": approved,
                "successful": successful,
            },
        )
