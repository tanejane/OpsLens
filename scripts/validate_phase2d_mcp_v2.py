
from __future__ import annotations

import asyncio
import sys
from pathlib import Path


# =============================================================================
# OpsLens Phase 2D MCP validation
#
# When Python runs `python scripts/validate_phase2d_mcp_v2.py`, it normally adds
# only the `scripts/` folder to sys.path. OpsLens packages such as `mcp_server/`
# live one level above it, so explicitly add the project root.
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from mcp import Client  # noqa: E402
from mcp_server.server import mcp  # noqa: E402


async def main():
    print("=" * 86)
    print("OPSLENS PHASE 2D — MCP SERVER VALIDATION")
    print("=" * 86)
    print(f"Project root: {ROOT}")

    checks = []

    def add(name, ok, value):
        checks.append((name, bool(ok), value))

    # Official MCP v2 client supports an MCPServer object directly for
    # in-memory protocol testing. No subprocess or network port is required.
    async with Client(mcp) as client:
        # ---------------------------------------------------------------------
        # 1. Protocol connection / negotiated version
        # ---------------------------------------------------------------------
        protocol_version = str(client.protocol_version)

        add(
            "MCP protocol connection established",
            bool(protocol_version),
            protocol_version,
        )

        # ---------------------------------------------------------------------
        # 2. Tool registration
        # ---------------------------------------------------------------------
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools.tools)

        expected = sorted(
            [
                "discover_domains",
                "discover_schema",
                "describe_relation",
                "list_metrics",
                "get_metric_definition",
                "run_readonly_sql",
            ]
        )

        add(
            "Six MCP tools registered",
            tool_names == expected,
            tool_names,
        )

        # ---------------------------------------------------------------------
        # 3. Domain discovery
        # ---------------------------------------------------------------------
        domains_result = await client.call_tool(
            "discover_domains",
            {},
        )

        domains = domains_result.structured_content

        add(
            "discover_domains works",
            bool(
                domains
                and domains.get("ok") is True
                and "semantic" in domains.get("data", [])
            ),
            domains,
        )

        # ---------------------------------------------------------------------
        # 4. Governed metric definition
        # ---------------------------------------------------------------------
        metric_result = await client.call_tool(
            "get_metric_definition",
            {"metric_name": "contribution_margin"},
        )

        metric = metric_result.structured_content

        add(
            "metric definition works",
            bool(
                metric
                and metric.get("ok") is True
                and metric.get("data", {}).get("metric_name")
                == "contribution_margin"
            ),
            metric,
        )

        # ---------------------------------------------------------------------
        # 5. Safe business SQL through MCP
        # ---------------------------------------------------------------------
        sql_result = await client.call_tool(
            "run_readonly_sql",
            {
                "query": (
                    "SELECT business_date, revenue, "
                    "contribution_profit, contribution_margin "
                    "FROM semantic.daily_commerce "
                    "ORDER BY business_date"
                ),
                "purpose": (
                    "Inspect daily commerce economics through MCP"
                ),
                "expected_grain": "one row per business date",
                "max_rows": 5,
            },
        )

        safe_sql = sql_result.structured_content

        add(
            "safe SQL executes through MCP",
            bool(
                safe_sql
                and safe_sql.get("ok") is True
                and safe_sql.get("meta", {}).get("row_count") == 5
            ),
            safe_sql.get("meta") if safe_sql else None,
        )

        # ---------------------------------------------------------------------
        # 6. Staging boundary survives the MCP layer
        # ---------------------------------------------------------------------
        staging_result = await client.call_tool(
            "run_readonly_sql",
            {
                "query": "SELECT * FROM staging.olist_orders",
                "purpose": "Verify staging remains inaccessible",
                "expected_grain": "order",
                "max_rows": 1,
            },
        )

        staging = staging_result.structured_content

        add(
            "staging remains blocked through MCP",
            bool(
                staging
                and staging.get("ok") is False
                and "forbidden" in staging.get("error", "").lower()
            ),
            staging,
        )

        # ---------------------------------------------------------------------
        # 7. Write boundary survives the MCP layer
        # ---------------------------------------------------------------------
        write_result = await client.call_tool(
            "run_readonly_sql",
            {
                "query": "DELETE FROM semantic.daily_commerce",
                "purpose": "Verify writes remain blocked",
                "expected_grain": "n/a",
                "max_rows": 1,
            },
        )

        write_blocked = write_result.structured_content

        add(
            "writes remain blocked through MCP",
            bool(
                write_blocked
                and write_blocked.get("ok") is False
            ),
            write_blocked,
        )

    passed = 0

    for name, ok, value in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            f"{name}: {value}"
        )
        passed += int(ok)

    print(f"\nChecks passed: {passed}/{len(checks)}")

    verdict = "PASS" if passed == len(checks) else "REVIEW"
    print("VERDICT:", verdict)

    if verdict != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
