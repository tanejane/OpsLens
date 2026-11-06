import unittest
from mcp_server.runtime_tools import _validate_select_sql
from agent.delivery_review_comparison import compile_comparison
from agent.seller_concentration import compile_plan

class GuardTests(unittest.TestCase):
    def test_new_finance_topic_does_not_reuse_delivery(self):
        from agent.delivery_review_routing import contextual
        self.assertIsNone(contextual('Why did revenue rise and contribution profit fall in March 2018 compared with February 2018',{'route':'delivery_review_comparison'}, {}, {'payload':{'route':'delivery_review_comparison'}}))
    def test_captured_provider_period_envelope(self):
        import json
        from pathlib import Path
        from agent.delivery_review_routing import period_proposal
        raw=Path('reports/live_period_interpretation.json').read_text()
        expected={'start':'2018-03-01','end':'2018-04-01'}
        self.assertEqual(period_proposal(raw),expected)
        self.assertNotEqual(period_proposal(json.dumps([expected,expected])),expected)
        self.assertNotEqual(period_proposal(json.dumps([{**expected,'sql':'SELECT 1'}])),expected)
    def test_registered_cte_compilers(self):
        for plan in (compile_comparison('2018-03-01','2018-04-01'),compile_plan('2018-03-01','2018-04-01')):
            _,relations=_validate_select_sql(plan['sql'])
            self.assertIn('semantic.order_delivery_evidence_v1',relations)
            self.assertNotIn('joined',relations)
    def test_hidden_forbidden_relation(self):
        with self.assertRaises(ValueError):_validate_select_sql('WITH x AS (SELECT * FROM staging.secret) SELECT * FROM x')
    def test_alias_does_not_authorize_unqualified_table(self):
        with self.assertRaises(ValueError):_validate_select_sql('WITH x AS (SELECT * FROM commerce.orders) SELECT * FROM x JOIN secret ON true')
    def test_out_of_scope_alias_rejected(self):
        with self.assertRaises(ValueError):_validate_select_sql('SELECT * FROM (WITH x AS (SELECT * FROM commerce.orders) SELECT * FROM x) q JOIN x ON true')
    def test_write_cte_rejected(self):
        with self.assertRaises(ValueError):_validate_select_sql('WITH x AS (DELETE FROM commerce.orders RETURNING *) SELECT * FROM x')
    def test_schema_qualified_alias_still_checked(self):
        with self.assertRaises(ValueError):_validate_select_sql('WITH x AS (SELECT * FROM commerce.orders) SELECT * FROM pg_catalog.x')

if __name__=='__main__':unittest.main()
