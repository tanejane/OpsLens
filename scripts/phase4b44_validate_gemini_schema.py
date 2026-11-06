"""Regression: Gemini request serialization avoids additionalProperties; local model stays strict."""
from agent.phase4b44_gemini_interpreter import GEMINI_INTERPRETATION_SCHEMA
from agent.phase4b44_context_grounding import Interpretation
from pydantic import ValidationError
import json

def run():
    raw=json.dumps(GEMINI_INTERPRETATION_SCHEMA)
    assert "additionalProperties" not in raw and "additional_properties" not in raw
    print("PASS: Gemini request schema contains no unsupported additional_properties")
    assert GEMINI_INTERPRETATION_SCHEMA["properties"]["intent"]["enum"] == ["descriptive","ranking","comparison","investigation","clarification"]
    print("PASS: Intent vocabulary constrained at API boundary")
    assert "metric_id" in GEMINI_INTERPRETATION_SCHEMA["properties"]
    print("PASS: Semantic field mapping retained")
    obj=Interpretation.model_validate({"intent":"ranking","metric_id":"unique_orders","dimensions":["seller_id"],"start_date":"2018-06-01","end_date_exclusive":"2018-07-01","order":"desc","limit":5})
    assert obj.metric_id=="unique_orders"
    print("PASS: Valid Gemini result parses through Pydantic")
    try:
        Interpretation.model_validate({"intent":"ranking","invented_sql":"DROP TABLE x"})
    except ValidationError:
        print("PASS: Unknown response fields still rejected locally")
    else:
        raise AssertionError("extra fields must fail")
    try:
        Interpretation.model_validate({"intent":"fake_action"})
    except ValidationError:
        print("PASS: Unknown intents still rejected locally")
    else:
        raise AssertionError("invalid intent must fail")
    print("Checks passed: 6/6")

if __name__=="__main__":run()
