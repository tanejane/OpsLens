
"""Run 4C.3 premise investigation, then 4C.4 governed cost discovery.

Usage:
python -m scripts.phase4c4_investigate 2018-02-01 2018-03-01 2018-03-01 2018-04-01
"""

import argparse
import asyncio
import json

from agent.phase4c3_investigation import InvestigationRequest, investigate
from agent.phase4c4_drivers import discover_drivers
from agent.phase4b57_nl_dynamic_finance import mcp_query


async def main():
    parser = argparse.ArgumentParser(
        description="Run a governed OpsLens financial investigation."
    )

    for part in (
        "before_start",
        "before_end",
        "after_start",
        "after_end",
    ):
        parser.add_argument(part)

    args = parser.parse_args()

    from mcp import Client
    from mcp_server.server import mcp

    async with Client(mcp) as client:

        # Phase 4C.3 expects a single aggregate-row dictionary.
        async def reader(sql, purpose):
            return await mcp_query(client, sql, purpose)

        # Phase 4C.4 expects {"rows": [aggregate_row]}.
        async def component_reader(sql, purpose):
            row = await reader(sql, purpose)
            if not isinstance(row, dict):
                raise TypeError("MCP returned an invalid aggregate row")
            return {"rows": [row]}

        # Step 1: Verify the financial premise and decomposition.
        core = await investigate(
            InvestigationRequest(
                args.before_start,
                args.before_end,
                args.after_start,
                args.after_end,
            ),
            reader,
        )

        # Step 2: Discover and reconcile cost components.
        result = await discover_drivers(
            core,
            component_reader,
        )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except Exception as exc:
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]

        print(
            "BLOCKED:",
            type(exc).__name__,
            str(exc)[:450],
        )

        raise SystemExit(1)
