"""Construction smoke test for the real Google ADK agent (Phase 6, Task 4).

Verifies offline (no Gemini key, no MCP servers) that the agent + its two MCP toolsets + the JSON
parsing build correctly. The live invocation (Runner driving Gemini + MCP tools) is validated on the
live stack per Phase 6 Task 3.
"""

import pathlib
import sys

_AGENT = pathlib.Path(__file__).resolve().parent.parent / "services" / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from app import adk_app  # noqa: E402  (imports google.adk)
from app.models import AgentProposal  # noqa: E402


def test_build_agent_constructs_with_two_mcp_toolsets():
    agent = adk_app.build_agent()
    assert agent.name == "opssentinel_reasoner"
    assert agent.model == "gemini-2.0-flash"
    assert len(agent.tools) == 2  # Elastic MCP toolset + Arize MCP toolset over SSE


def test_extract_json_tolerates_fences_and_prose():
    assert adk_app._extract_json('```json\n{"category":"X"}\n```')["category"] == "X"
    assert adk_app._extract_json('here is the result {"a": 1} thanks')["a"] == 1
    assert adk_app._extract_json("not json at all") == {}


def test_proposal_from_dict_is_tolerant():
    p = AgentProposal.from_dict(
        {"category": "Database Connection Pool", "severity": "P1", "confidence": "0.9"}
    )
    assert p.category == "Database Connection Pool"
    assert p.confidence == 0.9
    assert p.steps == []  # missing keys default safely
    assert p.is_novel is False
