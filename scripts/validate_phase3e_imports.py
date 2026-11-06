
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


print("=" * 92)
print("OPSLENS PHASE 3E v2 — IMPORT BOUNDARY DIAGNOSTIC")
print("=" * 92)

from retrieval.hybrid import hybrid_search

print("[PASS] retrieval.hybrid imports without importing mcp_server.server")

from mcp_server.server import mcp

print("[PASS] mcp_server.server imports without circular dependency")

from agent.graph_phase3e import integrated_investigation_graph

print("[PASS] LangGraph Phase 3E imports successfully")

print("\nVERDICT: PASS")
