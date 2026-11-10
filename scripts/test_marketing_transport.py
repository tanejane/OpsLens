from decimal import Decimal
"""Regression coverage for the real MCP single-row transport shape."""
import unittest

from agent.marketing_followup import MarketingRejected, analyze
from scripts.test_marketing_followup import finance_result, reader_result


class MarketingTransportTests(unittest.IsolatedAsyncioTestCase):

    async def test_live_mcp_single_row(self):
        async def reader(sql, purpose):
            return reader_result()["rows"][0]

        proof = await analyze(finance_result(), reader)

        self.assertEqual(proof["status"], "DESCRIPTIVE_RECONCILED")
        self.assertFalse(proof["causal_claim"])

    async def test_original_rows_envelope(self):
        async def reader(sql, purpose):
            return reader_result()

        proof = await analyze(finance_result(), reader)

        self.assertEqual(Decimal(proof["spend_change"]), Decimal("49291.24"))

    async def test_unexpected_transport_rejected(self):
        async def reader(sql, purpose):
            return {"campaigns": [], "untrusted_extra": True}

        with self.assertRaises(MarketingRejected):
            await analyze(finance_result(), reader)


if __name__ == "__main__":
    unittest.main()
