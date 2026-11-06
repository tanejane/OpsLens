"""Inspect the map without invoking Gemini or PostgreSQL."""
import json
from agent.phase4b4_semantic_map import SemanticMap
m=SemanticMap()
print(json.dumps(m.describe(),indent=2))
for r in m.relations:
 print(f"{r['id']}: {r['left']} -> {r['right']} ({r['cardinality']}; {r['status']})")
