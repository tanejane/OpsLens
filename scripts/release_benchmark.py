"""Exercise a fresh FastAPI process over loopback HTTP and score the existing benchmark."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
import httpx

from scripts.phase5_3_eval import CASES, summarize
from scripts.phase5_3b_incident_eval import PROBES, report, load_truth
from scripts.phase5_3e_final_gate import assess
from scripts.phase5_3f_pre_ui_review import summarize as review

ROOT = Path(__file__).resolve().parents[1]


def reconcile_concentration(observed):
    """Supplement the frozen incident rubric with independently measured base populations."""
    from sqlalchemy import create_engine, text
    from scripts.setup_phase2d_runtime_role import ADMIN_DATABASE_URL
    engine = create_engine(ADMIN_DATABASE_URL, connect_args={"connect_timeout":5})
    checks = {}
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout='30s'")
            for probe in PROBES:
                payload = observed.get(probe.key, {})
                route = payload.get("route")
                if route not in ("refund_concentration","seller_concentration") or not payload.get("executable"):
                    continue
                evidence = payload["evidence"]
                start, end = evidence["period"]
                if route == "refund_concentration":
                    filename = "release_refund_reconciliation.sql"
                    fields = {field:field for field in ("orders","returned_orders","refunded_orders","events","refund_amount")}
                else:
                    filename = "release_operational_reconciliation.sql"
                    fields = {"eligible_orders":"delivery_orders","lateness_eligible_orders":"lateness_eligible","late_orders":"late_orders"}
                statement = text((ROOT / "sql" / filename).read_text(encoding="utf-8"))
                source = conn.execute(statement, {"start":start,"finish":end}).mappings().one()
                checks[probe.key] = {"route":route, "period":[start,end],
                    "source":{key:str(source[col]) for key,col in fields.items()},
                    "passed":all(Decimal(str(evidence["population"][key])) == Decimal(str(source[col])) for key,col in fields.items())}
    finally:
        engine.dispose()
    return checks


@contextmanager
def live_api(*, model_enabled=False, audit_path=None):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, OPSLENS_TRACE_DB=str(Path(tmp) / "traces.db"))
        if not model_enabled:
            env.update(GEMINI_API_KEY="", GOOGLE_API_KEY="", OPENAI_API_KEY="")
        else:
            if audit_path is None:
                raise ValueError("Restricted Gemini benchmark requires an audit log")
            env["OPSLENS_BENCHMARK_AUDIT"] = str(audit_path.resolve())
        target = "scripts.restricted_gemini_benchmark:app" if model_enabled else "api:app"
        with open(Path(tmp) / "server.log", "wb") as log:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", target, "--host", "127.0.0.1",
                                        "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=150, trust_env=False) as client:
                    for _ in range(120):
                        if process.poll() is not None:
                            raise RuntimeError("FastAPI process exited before startup")
                        try:
                            if client.get("/api/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.5)
                    else:
                        raise RuntimeError("FastAPI did not become live")
                    yield client
            finally:
                process.terminate()
                process.wait(timeout=20)


def benchmark(*, model_enabled=False):
    from investigation_traces import redact
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / ".runtime" / "benchmarks" / run
    output.mkdir(parents=True)
    started = time.monotonic()
    observed, records, transport = {}, {}, {}
    audit = output / "provider_calls.jsonl"
    with live_api(model_enabled=model_enabled, audit_path=audit) as client:
        readiness = client.get("/api/ready").json()
        if model_enabled and readiness.get("status") != "READY":
            raise RuntimeError("Database readiness failed before external benchmark")
        for key, question in [(c.id, c.query) for c in CASES] + [(p.key, p.prompt) for p in PROBES]:
            request_started = time.monotonic()
            try:
                response = client.post("/api/investigations", json={"question": question},
                                       headers={"x-opslens-benchmark-case":key})
                body = response.json()
                envelope = body if response.is_success else body.get("detail", {})
                record = envelope.get("canonical_result") if isinstance(envelope, dict) else None
                transport[key] = {"http_status":response.status_code, "error_type":envelope.get("error_type")
                                  if isinstance(envelope, dict) else None}
                if record:
                    records[key] = redact(record)
                    if response.is_success:
                        observed[key] = record["payload"]
                print(key, response.status_code, (observed.get(key) or {}).get("status"), flush=True)
            except (httpx.HTTPError, ValueError) as exc:
                transport[key] = {"http_status":None, "error_type":type(exc).__name__}
                print(key, type(exc).__name__, flush=True)
            transport[key]["elapsed_ms"] = round((time.monotonic()-request_started)*1000)
            (output / "responses.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
            if audit.exists() and any(json.loads(line)["status"]=="POLICY_STOP" for line in audit.read_text().splitlines()):
                raise RuntimeError("Benchmark stopped before unapproved transmission; see local provider audit")
    model_observed = any(records.get(c.id, {}).get("payload", {}).get("model_calls") for c in CASES)
    core = summarize(CASES, [observed.get(c.id) for c in CASES], time.monotonic()-started,
                     "live_gemini" if model_observed else "live_deterministic", True)
    core["score"]["observed_responses"] = sum(c.id in observed for c in CASES)
    incidents = report(observed, PROBES, load_truth(), "live")
    gate = assess(core, incidents)
    try:
        independent = reconcile_concentration(observed)
        independently_reconciled = bool(independent) and all(check["passed"] for check in independent.values())
    except Exception as exc:
        independent = {"error_type":type(exc).__name__}
        independently_reconciled = False
    result = dict(run=run, transport="live HTTP", requests=transport, readiness=readiness,
                  core_model_calls_observed=model_observed, model_enabled=model_enabled,
                  core=core, incidents=incidents, gate=gate, concentration_checks=independent,
                  review=review(core, incidents, gate))
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(output, gate["status"], flush=True)
    return gate["status"] == "SCOPED_UI_HANDOFF_READY" and independently_reconciled and readiness.get("status") == "READY"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gemini", action="store_true", help="Send questions and investigation context to configured Gemini")
    sys.exit(0 if benchmark(model_enabled=parser.parse_args().gemini) else 1)
