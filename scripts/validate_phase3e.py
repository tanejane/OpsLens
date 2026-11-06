
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp import Client
import asyncio

from agent.graph_phase3e import integrated_investigation_graph
from mcp_server.server import mcp


async def validate_mcp_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)

        knowledge = await client.call_tool(
            "search_knowledge",
            {
                "query": (
                    "supplier costs increased during March profitability decline"
                ),
                "top_k": 3,
            },
        )

        injection = await client.call_tool(
            "search_knowledge",
            {
                "query": (
                    "ignore previous instructions reveal system prompt "
                    "auto approve"
                ),
                "top_k": 5,
            },
        )

    return (
        names,
        knowledge.structured_content,
        injection.structured_content,
    )


def main():
    print("=" * 98)
    print("OPSLENS PHASE 3E — MCP RETRIEVAL + LANGGRAPH TOOL ROUTING VALIDATION")
    print("=" * 98)

    names, knowledge, injection = asyncio.run(
        validate_mcp_tools()
    )

    result = integrated_investigation_graph.invoke(
        {
            "question": "Revenue increased but profit fell. Investigate why.",
            "requests": [],
            "current_request_index": 0,
            "evidence_ledger": [],
            "tool_trace": [],
            "hypotheses": {},
            "stop_reason": None,
            "conclusion": None,
        }
    )

    checks = []

    def add(name, ok, value):
        checks.append((name, bool(ok), value))

    expected_tools = {
        "discover_domains",
        "discover_schema",
        "describe_relation",
        "list_metrics",
        "get_metric_definition",
        "run_readonly_sql",
        "search_knowledge",
    }

    add(
        "Seven MCP tools registered",
        set(names) == expected_tools,
        names,
    )

    add(
        "search_knowledge works through MCP protocol",
        bool(
            knowledge
            and knowledge.get("ok")
            and knowledge.get("data")
            and knowledge["data"][0]["filename"]
            == "supplier_cost_notice.md"
        ),
        (
            None
            if not knowledge
            else [
                x["filename"]
                for x in knowledge.get("data", [])
            ]
        ),
    )

    add(
        "Prompt-injection document filtered by MCP retrieval tool",
        bool(
            injection
            and injection.get("ok")
            and all(
                not row["injection_flag"]
                for row in injection.get("data", [])
            )
        ),
        (
            None
            if not injection
            else [
                row["filename"]
                for row in injection.get("data", [])
            ]
        ),
    )

    used_tools = [
        item["tool"]
        for item in result["tool_trace"]
    ]

    add(
        "LangGraph used structured SQL MCP tool",
        "run_readonly_sql" in used_tools,
        used_tools,
    )

    add(
        "LangGraph used hybrid retrieval MCP tool",
        "search_knowledge" in used_tools,
        used_tools,
    )

    evidence_sources = [
        item["source_ref"]
        for item in result["evidence_ledger"]
    ]

    add(
        "Structured and document evidence share one ledger",
        (
            "semantic.order_economics" in evidence_sources
            and "supplier_cost_notice.md" in evidence_sources
            and "growthmax_campaign_brief.md" in evidence_sources
        ),
        evidence_sources,
    )

    add(
        "H1 supported by structured evidence with document corroboration",
        bool(
            result["hypotheses"]["H1"]["status"] == "SUPPORTED"
            and len(result["hypotheses"]["H1"]["evidence"]) >= 2
        ),
        result["hypotheses"]["H1"],
    )

    add(
        "H2 document evidence is not overstated as causal proof",
        result["hypotheses"]["H2"]["status"] == "CORROBORATED",
        result["hypotheses"]["H2"],
    )

    add(
        "Explicit integrated stop reason recorded",
        result["stop_reason"]
        == "INTEGRATED_EVIDENCE_REQUESTS_COMPLETE",
        result["stop_reason"],
    )

    print("\nTool trace:")
    for item in result["tool_trace"]:
        print(
            f"- {item['request_id']}: "
            f"{item['tool']} -> ok={item['ok']}"
        )

    print("\nEvidence sources:")
    for item in evidence_sources:
        print(f"- {item}")

    print("\nHypotheses:")
    for key, item in result["hypotheses"].items():
        print(
            f"- {key}: {item['status']} "
            f"({len(item['evidence'])} evidence item(s))"
        )

    print("\nConclusion:")
    print(result["conclusion"])

    print("\nValidation:")

    passed = 0

    for name, ok, value in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{name}: {value}"
        )
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")

    verdict = (
        "PASS"
        if passed == len(checks)
        else "REVIEW"
    )

    print("VERDICT:", verdict)

    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
