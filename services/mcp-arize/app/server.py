"""Arize Phoenix MCP server: SSE at ``/sse`` (+ ``/health``), exposing the four Section-3 tools.

These return raw observability metrics; the agent (Phase 3) maps them to an autonomy tier.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app import store

mcp = FastMCP("mcp-arize")


@mcp.tool()
def get_category_accuracy(category: str, window: int = 30) -> float:
    """Recent LLM-as-a-judge accuracy (fraction) for an incident category."""
    return store.get_category_accuracy(category, window)


@mcp.tool()
def get_calibration(category: str) -> float:
    """Calibration error: |stated confidence − empirical accuracy| (target < 0.05)."""
    return store.get_calibration(category)


@mcp.tool()
def is_novel_category(category: str) -> bool:
    """True if the agent has little/no history for this category."""
    return store.is_novel_category(category)


@mcp.tool()
def log_outcome(
    trace_id: str, incident_id: str, approved: bool, successful: bool
) -> dict[str, str]:
    """Record a remediation result into the trace/evaluation history."""
    outcome_id = store.log_outcome(trace_id, incident_id, approved, successful)
    return {"outcome_id": outcome_id}


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp-arize"})


def build_app() -> Starlette:
    return Starlette(routes=[Route("/health", health), Mount("/", app=mcp.sse_app())])


app = build_app()
