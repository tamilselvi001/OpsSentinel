"""Elastic MCP server: SSE at ``/sse`` (+ ``/health``), exposing the three Section-3 tools.

The agent (Phase 3) connects as an MCP client over SSE via ADK's McpToolset. Tools are thin
wrappers over :class:`app.elastic_client.ElasticKnowledge`; the client is created lazily so the
process starts (and ``/health`` responds) even before the first tool call.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.elastic_client import ElasticKnowledge

mcp = FastMCP("mcp-elastic")
_knowledge: ElasticKnowledge | None = None


def _kb() -> ElasticKnowledge:
    global _knowledge
    if _knowledge is None:
        _knowledge = ElasticKnowledge()
    return _knowledge


@mcp.tool()
def search_runbooks(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Top-k similar historical runbooks via hybrid KNN + full-text RRF."""
    return _kb().search_runbooks(query, top_k)


@mcp.tool()
def fetch_recent_logs(service: str, minutes: int = 30) -> list[dict[str, Any]]:
    """Recent application/APM log lines for a service, for incident context."""
    return _kb().fetch_recent_logs(service, minutes)


@mcp.tool()
def write_closure_summary(incident_id: str, summary: str, tags: list[str]) -> dict[str, Any]:
    """Index a resolved incident back into the knowledge base (institutional memory)."""
    return _kb().write_closure_summary(incident_id, summary, tags)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp-elastic"})


def build_app() -> Starlette:
    return Starlette(routes=[Route("/health", health), Mount("/", app=mcp.sse_app())])


app = build_app()
