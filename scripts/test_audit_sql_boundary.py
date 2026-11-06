import pytest

from mcp_server.runtime_tools import _validate_select_sql


@pytest.mark.parametrize("function", [
    "pg_catalog.query_to_xml", "QUERY_TO_XMLSCHEMA", '"query_to_xml_and_xmlschema"',
    "table_to_xml", "schema_to_xml", "database_to_xml",
])
def test_xml_access_cannot_hide_behind_approved_relation(function):
    with pytest.raises(ValueError, match="Indirect XML"):
        _validate_select_sql(f"SELECT {function}('unused', true, false, '') FROM commerce.orders")


def test_approved_aggregate_still_passes():
    _, relations = _validate_select_sql("SELECT COUNT(DISTINCT order_id) FROM commerce.orders")
    assert relations == ["commerce.orders"]
