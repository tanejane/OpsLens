import pytest
from mcp_server.runtime_tools import _validate_select_sql
from scripts.release_query_corpus import saved_queries


def test_saved_governed_corpus():
    queries = saved_queries()
    assert queries
    for query in queries:
        _validate_select_sql(query)


@pytest.mark.parametrize("query", [
    "SELECT public.sum(order_id) FROM commerce.orders",
    "SELECT pg_sleep(1) FROM commerce.orders",
    "SELECT set_config('search_path','public',false) FROM commerce.orders",
    "SELECT pg_input_is_valid(order_id,'regclass') FROM commerce.orders",
    "SELECT order_id::regclass FROM commerce.orders",
    "SELECT order_id::public.custom FROM commerce.orders",
    "SELECT 1 OPERATOR(public.+) 2 FROM commerce.orders",
    "SELECT 1 FROM commerce.orders TABLESAMPLE custom(5)",
    "SELECT * FROM semantic.order_cost_components_old",
    "SELECT * FROM db.commerce.orders",
    "WITH x AS (SELECT * FROM staging.olist_orders) SELECT * FROM x",
    "SELECT * INTO TEMP copied FROM commerce.orders",
    "SELECT * FROM commerce.orders FOR UPDATE",
    "SELECT * FROM commerce.orders; SELECT * FROM staging.olist_orders",
])
def test_unregistered_access_is_rejected(query):
    with pytest.raises(ValueError):
        _validate_select_sql(query)
