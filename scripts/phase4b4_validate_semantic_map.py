"""Offline tests using declarative map, no database or API usage."""
from agent.phase4b4_semantic_map import SemanticMap,SemanticMapRejected

def reject(fn, phrase):
    try: fn()
    except SemanticMapRejected as exc:
        assert phrase in str(exc), str(exc)
        return
    raise AssertionError("Unsafe semantic request was accepted")

def run():
    m=SemanticMap()
    assert m.describe()["sources"]>=8
    print("PASS: Versioned semantic map loaded")
    assert [e["id"] for e in m.path("commerce.orders","catalog.products")] == ["orders_to_items","items_to_products"]
    print("PASS: Multi-hop relationship discovery")
    reject(lambda: m.path("commerce.orders","behavior.sessions"),"cannot be joined")
    print("PASS: Cross-environment join prohibited")
    reject(lambda: m.resolve("incident_gross_margin_pct",["incident_category"],"2018-06-01","2018-07-01"),"outside recorded coverage")
    print("PASS: September 2017 incident source rejected for June 2018")
    reject(lambda: m.resolve("gross_margin_pct",["category"]),"incompatible")
    print("PASS: Cannot invent marketplace category margin via order economics")
    reject(lambda: m.resolve("unique_orders",["seller_id"]),"independent live cardinality audit")
    print("PASS: Relationship declaration alone is not execution approval")
    out=m.resolve("unique_orders",["seller_id"],verified_relationships=["orders_to_items"])
    assert out["status"]=="CATALOG_CANDIDATE_NOT_EXECUTABLE"
    print("PASS: Declared graph path remains non-executable without live metadata")
    reject(
        lambda: m.resolve(
            "unique_orders",
            ["seller_id"],
            # Isolate missing relation metadata, rather than simultaneously
            # failing a column check in nondeterministic set iteration order.
            live_columns={"commerce.orders": {"order_id", "order_purchase_timestamp"}},
            verified_relationships=["orders_to_items"],
        ),
        "Missing live metadata",
    )
    print("PASS: Missing metadata blocked")
    out=m.resolve("gross_margin_pct",["business_date"],"2018-06-01","2018-07-01")
    assert out["coverage"]=="UNKNOWN_REQUIRES_LIVE_PROBE"
    print("PASS: Unknown source coverage exposed")
    print("Checks passed: 9/9")

if __name__=="__main__":run()
