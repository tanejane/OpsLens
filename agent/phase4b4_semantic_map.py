"""Phase 4B.4 semantic-map foundation: discovery, compatibility, fail-closed execution gate.

No model-authored SQL and no assumed live database truth. Join declarations are NOT approvals.
"""
from __future__ import annotations
from collections import deque
from datetime import date
from pathlib import Path
import json

DEFAULT_MAP = Path(__file__).resolve().parents[1] / "config" / "phase4b4_semantic_map.json"

class SemanticMapRejected(ValueError):
    pass

class SemanticMap:
    def __init__(self, path=DEFAULT_MAP):
        self.document=json.loads(Path(path).read_text(encoding="utf-8"))
        self.sources={x["id"]:x for x in self.document["sources"]}
        self.metrics={x["id"]:x for x in self.document["metrics"]}
        self.dimensions={x["id"]:x for x in self.document["dimensions"]}
        self.relations=self.document["relationships"]
        self._validate_map()

    def _validate_map(self):
        for edge in self.relations:
            if edge["left"] not in self.sources or edge["right"] not in self.sources:
                raise SemanticMapRejected("Relationship references unknown source")
            if self.sources[edge["left"]]["environment"] != self.sources[edge["right"]]["environment"]:
                raise SemanticMapRejected("Cross-environment relationship is prohibited")
            for node,key in ((edge["left"],edge["left_key"]),(edge["right"],edge["right_key"])):
                if key not in self.sources[node]["columns"]:
                    raise SemanticMapRejected("Join key not in declared source columns: "+node+"."+key)
        for metric in self.metrics.values():
            if metric["source"] not in self.sources: raise SemanticMapRejected("Metric has unknown source")
        for dim in self.dimensions.values():
            if dim["source"] not in self.sources: raise SemanticMapRejected("Dimension has unknown source")

    def path(self, src, dst):
        if src not in self.sources or dst not in self.sources:
            raise SemanticMapRejected("Unknown source")
        if self.sources[src]["environment"]!=self.sources[dst]["environment"]:
            raise SemanticMapRejected("Olist and GA4 cannot be joined")
        queue=deque([(src,[])])
        visited={src}
        while queue:
            current, route=queue.popleft()
            if current==dst: return route
            for edge in self.relations:
                other=edge["right"] if edge["left"]==current else edge["left"] if edge["right"]==current else None
                if other and other not in visited:
                    visited.add(other)
                    queue.append((other,route+[edge]))
        raise SemanticMapRejected("No declared relationship path")

    def resolve(self, metric_id, dimensions=(), start_date=None, end_date_exclusive=None, live_columns=None, verified_relationships=()):
        """Return an explainable candidate. Never manufacture equivalent source or SQL."""
        if metric_id not in self.metrics: raise SemanticMapRejected("Unknown metric: "+metric_id)
        metric=self.metrics[metric_id]
        src=self.sources[metric["source"]]
        if bool(start_date)!=bool(end_date_exclusive): raise SemanticMapRejected("Both date boundaries required")
        if start_date:
            low,high=date.fromisoformat(start_date),date.fromisoformat(end_date_exclusive)
            if low>=high: raise SemanticMapRejected("Invalid date interval")
            coverage=src.get("coverage")
            if coverage and (low<date.fromisoformat(coverage["start"]) or high>date.fromisoformat(coverage["end_exclusive"])):
                raise SemanticMapRejected("Source outside recorded coverage: "+src["id"]+" ["+coverage["start"]+", "+coverage["end_exclusive"]+")")
            if not src.get("date_column") and not self._has_declared_date_path(src["id"]):
                raise SemanticMapRejected("No verified date scope")
        paths=[]
        needed={src["id"]}
        for name in dimensions:
            if name not in self.dimensions: raise SemanticMapRejected("Unknown dimension: "+name)
            dim=self.dimensions[name]
            if name not in metric["allowed_dimensions"]:
                raise SemanticMapRejected("Metric/dimension incompatible: "+metric_id+" / "+name)
            path=self.path(src["id"],dim["source"])
            paths.append({"dimension":name,"edges":[x["id"] for x in path]})
            needed.add(dim["source"])
            for edge in path: needed.update((edge["left"],edge["right"]))
        missing=set(e["id"] for p in paths for e in self.relations if e["id"] in p["edges"])-set(verified_relationships)
        if missing: raise SemanticMapRejected("Relationships require independent live cardinality audit: "+", ".join(sorted(missing)))
        if live_columns is None:
            return {"status":"CATALOG_CANDIDATE_NOT_EXECUTABLE","metric":metric_id,"source":src["id"],"dimensions":list(dimensions),"paths":paths,"coverage":"DECLARED" if src.get("coverage") else "UNKNOWN_REQUIRES_LIVE_PROBE","requires_live_metadata":sorted(needed)}
        for name in needed:
            if name not in live_columns: raise SemanticMapRejected("Missing live metadata: "+name)
            required=set(self.sources[name]["grain"])
            if name==src["id"] and src.get("date_column"): required.add(src["date_column"])
            for dim in self.dimensions.values():
                if dim["source"]==name and dim["id"] in dimensions: required.add(dim["column"])
            for edge in self.relations:
                if edge["id"] in {id for p in paths for id in p["edges"]}:
                    if edge["left"]==name:required.add(edge["left_key"])
                    if edge["right"]==name:required.add(edge["right_key"])
            if required-set(live_columns[name]):
                raise SemanticMapRejected("Required columns absent from live schema: "+name+": "+str(sorted(required-set(live_columns[name]))))
        return {"status":"METADATA_VALIDATED_NOT_SQL_APPROVED","metric":metric_id,"source":src["id"],"dimensions":list(dimensions),"paths":paths,"coverage":"DECLARED" if src.get("coverage") else "UNKNOWN_REQUIRES_LIVE_PROBE","requires_live_cardinality_audit":True}

    def _has_declared_date_path(self, source):
        return any(x["left"]==source or x["right"]==source for x in self.relations)

    def describe(self):
        return {"sources":len(self.sources),"metrics":len(self.metrics),"dimensions":len(self.dimensions),"relationships":len(self.relations),"execution":"disabled_pending_live_verification"}
