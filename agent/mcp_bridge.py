
from __future__ import annotations
from typing import Any
from mcp import Client
from mcp_server.server import mcp

class OpsLensMCPBridge:
    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with Client(mcp) as client:
            result = await client.call_tool(tool_name, arguments)
        return result.structured_content or {
            "ok": False,
            "tool": tool_name,
            "data": None,
            "error": "No structured MCP response",
            "meta": None,
        }

async def run_sql_evidence(query: str, purpose: str, expected_grain: str, max_rows: int = 50):
    return await OpsLensMCPBridge().call(
        "run_readonly_sql",
        {
            "query": query,
            "purpose": purpose,
            "expected_grain": expected_grain,
            "max_rows": max_rows,
        },
    )
