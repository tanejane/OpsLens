"""Real HTTP and Next proxy, isolated executor fixtures and trace storage."""
import socket
import subprocess
import threading
import time
import os
import httpx
from decimal import Decimal

import uvicorn
from fastapi import HTTPException
import api
from agent.investigation_result import investigation_response
from investigation_sessions import SessionStore
from investigation_traces import TraceStore
from fastapi.testclient import TestClient


def test_database_outage_preserves_liveness(monkeypatch):
    from mcp_server import readiness
    def unavailable():
        raise ConnectionError("fixture database offline")
    monkeypatch.setattr(readiness, "inspect_runtime", unavailable)
    with TestClient(api.app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "NOT_READY"


def test_registered_finance_subquestion_keeps_grounded_periods():
    from agent.phase4c6_nl_investigation import CompiledComparisonInterpreter, ground_interpretation
    from agent.delivery_review_routing import relevant
    assert not relevant("Compare finance, late delivery and review scores from February 2018 to March 2018")
    question = "Why did revenue increase while profit decreased in March 2018 compared with February 2018?"
    request, blocked = ground_interpretation(question, CompiledComparisonInterpreter.interpret(question))
    assert blocked is None
    assert (request.before_start, request.before_end, request.after_start, request.after_end) == (
        "2018-02-01", "2018-03-01", "2018-03-01", "2018-04-01")
    ambiguous = "Why did profit drop in March 2018?"
    request, blocked = ground_interpretation(ambiguous, CompiledComparisonInterpreter.interpret(ambiguous))
    assert request is None and blocked["status"] == "NEEDS_CLARIFICATION"


def test_next_proxy_against_fastapi(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'FRONTEND_ORIGINS', ('http://localhost:3000', 'http://192.168.100.20:3000'))
    async def execute(request, **kwargs):
        status = {"partial": "PARTIAL_GOVERNED_EVIDENCE", "failure": "EXECUTION_FAILED"}.get(
            request.question, "MEASURED_WITH_SCOPE_LIMITS")
        payload = dict(status=status, executable=status != "EXECUTION_FAILED", causal_claim=False,
                       value=Decimal("10.2300"), unknown={"count": 2**55})
        if request.question == "oversized":
            payload["evidence_fixture"] = "x" * 30000
        body = investigation_response(request.question, payload)
        if request.question == "failure":
            raise HTTPException(503, {"canonical_result": body["canonical_result"], "reason": "fixture failure"})
        return body

    monkeypatch.setattr(api, "_execute_investigation", execute)
    monkeypatch.setattr(api, "sessions", SessionStore(max_bytes=20000))
    monkeypatch.setattr(api, "traces", TraceStore(tmp_path / "replay.db"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(api.app, log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets":[sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started
            with socket.socket() as frontend_socket:
                frontend_socket.bind(('127.0.0.1', 0))
                port = frontend_socket.getsockname()[1]
            env = {**os.environ, 'OPSLENS_API_URL': f'http://127.0.0.1:{sock.getsockname()[1]}'}
            with open(tmp_path / 'next.log', 'w') as log:
                next_server = subprocess.Popen(['node', 'node_modules/next/dist/bin/next', 'start',
                    '--hostname', '127.0.0.1', '--port', str(port)], cwd=api.ROOT / 'frontend',
                    env=env, stdout=log, stderr=log)
                try:
                    base = f'http://127.0.0.1:{port}'
                    for _ in range(100):
                        try:
                            if httpx.get(base + '/api/health', timeout=1).status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(.1)
                    else:
                        raise AssertionError('Next production server did not become ready')
                    subprocess.run(['node', 'tests/release-proxy.mjs', base], check=True,
                        cwd=api.ROOT / 'frontend', timeout=60)
                finally:
                    next_server.terminate()
                    next_server.wait(timeout=10)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
