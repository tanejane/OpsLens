from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.phase4b1_semantic_query import QuerySpec, QueryRejected, compile_query

approved={"commerce.orders"}
columns={"order_id":"text", "order_purchase_timestamp":"text", "order_status":"text"}
spec=QuerySpec(relation="commerce.orders", aggregate="count", date_column="order_purchase_timestamp", start_date="2018-06-01", end_date_exclusive="2018-07-01")
checks=[]
def test(label, passed):
    checks.append(bool(passed)); print(("PASS" if passed else "FAIL")+": "+label)
sql=compile_query(spec,columns,approved)
test("Textual order date is compiled as guarded timestamp", "pg_input_is_valid" in sql and "::timestamp" in sql)
test("Correct June range retained", "2018-06-01" in sql and "2018-07-01" in sql)
test("Bounded count", "COUNT(*)" in sql and "LIMIT 200" in sql)
try:
    compile_query(spec.model_copy(update={"date_column":"order_status"}),columns,approved)
    test("Arbitrary text column rejected", False)
except QueryRejected:
    test("Arbitrary text column rejected", True)
try:
    compile_query(spec, {**columns, "order_purchase_timestamp":"integer"}, approved)
    test("Non-date numeric column rejected",False)
except QueryRejected:
    test("Non-date numeric column rejected",True)
print(f"Checks passed: {sum(checks)}/{len(checks)}")
if not all(checks): raise SystemExit(1)
