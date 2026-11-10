
"""OpsLens Stage 4.5 â€” Saved replay isolation tests.

Tests the real TraceStore and FastAPI replay handler.
No live investigation, MCP, PostgreSQL or Gemini calls.

Run:
    python -m unittest scripts.test_replay_isolation -v
"""

import copy
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from investigation_traces import TraceStore


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def saved_record():
    """Minimal synthetic canonical record for replay testing."""
    return {
        "schema_version": "opslens.investigation.v1",
        "question": "Fixture: why did profit decline?",
        "payload": {
            "causal_claim": False,
            "metric_results": {
                "contribution_profit": {
                    "before": 100,
                    "after": 80,
                }
            },
            "agent_trace_v2": {
                "schema_version": "opslens.agent_trace.v2",
                "ordering": "SOURCE_LOCAL_ONLY",
                "global_sequence_verified": False,
                "events": [
                    {
                        "id": "orchestration:0",
                        "source": "orchestration",
                        "stage": "decision",
                        "decision": "COMPLETED",
                    }
                ],
                "stop_conditions": [
                    {
                        "id": "orchestration:stop",
                        "source": "orchestration",
                        "reason": "QUESTION_ADDRESSED",
                    }
                ],
            },
            "observability": {
                "run_id": "fixture-run-001",
                "replay_mode": "SAVED_EVIDENCE_ONLY",
                "persistence": "SAVED",
            },
        },
    }


def request_without_cookies():
    return Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/test",
        "query_string": b"",
        "headers": [],
        "server": ("localhost", 8000),
        "client": ("127.0.0.1", 50000),
    })


class TraceStoreReplayTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()

        self.store = TraceStore(
            path=Path(self.temp.name) / "replay-test.sqlite3",
            ttl=20,
            max_runs=10,
            per_session=5,
            clock=self.clock,
        )

        self.record = saved_record()
        self.session = "fixture-session"
        self.owner = "fixture-owner"
        self.run_id = "fixture-run-001"

        self.store.save(
            self.session,
            self.owner,
            self.record,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_01_replay_preserves_original_canonical_record(self):
        first = self.store.load(
            self.session,
            self.owner,
            self.run_id,
        )

        second = self.store.load(
            self.session,
            self.owner,
            self.run_id,
        )

        self.assertEqual(
            first["canonical_result"],
            self.record,
        )
        self.assertEqual(first, second)

        self.assertEqual(
            first["replay"]["mode"],
            "SAVED_EVIDENCE_ONLY",
        )
        self.assertEqual(
            first["replay"]["external_calls"],
            0,
        )

        self.assertEqual(
            first["canonical_result"]["payload"]
            ["agent_trace_v2"]["schema_version"],
            "opslens.agent_trace.v2",
        )

    def test_02_wrong_owner_cannot_access_saved_run(self):
        with self.assertRaises(KeyError):
            self.store.load(
                self.session,
                "different-owner",
                self.run_id,
            )

    def test_03_wrong_session_cannot_access_saved_run(self):
        with self.assertRaises(KeyError):
            self.store.load(
                "different-session",
                self.owner,
                self.run_id,
            )

    def test_04_expired_saved_run_is_unavailable(self):
        self.clock.advance(21)

        with self.assertRaises(KeyError):
            self.store.load(
                self.session,
                self.owner,
                self.run_id,
            )

    def test_05_modified_record_fails_integrity_check(self):
        with closing(sqlite3.connect(self.store.path)) as db, db:
            row = db.execute(
                "SELECT body FROM runs WHERE id=?",
                (self.run_id,),
            ).fetchone()

            altered = json.loads(row[0])
            altered["payload"]["metric_results"][
                "contribution_profit"
            ]["after"] = 999

            db.execute(
                "UPDATE runs SET body=? WHERE id=?",
                (
                    json.dumps(altered),
                    self.run_id,
                ),
            )

        with self.assertRaisesRegex(
            ValueError,
            "integrity",
        ):
            self.store.load(
                self.session,
                self.owner,
                self.run_id,
            )


class ReplayApiTests(unittest.IsolatedAsyncioTestCase):

    async def test_06_replay_handler_does_not_invoke_runtime(self):
        import api

        record = saved_record()

        replay_result = {
            "canonical_result": copy.deepcopy(record),
            "replay": {
                "mode": "SAVED_EVIDENCE_ONLY",
                "sha256": "fixture-checksum",
                "external_calls": 0,
            },
        }

        entry = SimpleNamespace(
            id="fixture-session",
            owner="fixture-owner",
            lock=MagicMock(),
        )

        request = request_without_cookies()

        with (
            patch.object(
                api.sessions,
                "acquire",
                return_value=entry,
            ) as acquire,
            patch.object(
                api.traces,
                "load",
                return_value=replay_result,
            ) as load,
            patch.object(
                api,
                "_execute_investigation",
                create=True,
                side_effect=AssertionError(
                    "Replay invoked the investigation runtime"
                ),
            ) as execute,
        ):
            result = await api.replay_investigation(
                entry.id,
                "fixture-run-001",
                request,
            )

        self.assertEqual(result, replay_result)
        self.assertEqual(
            result["canonical_result"],
            record,
        )

        acquire.assert_called_once_with(
            entry.id,
            request.cookies.get(api.COOKIE),
        )

        load.assert_called_once_with(
            entry.id,
            entry.owner,
            "fixture-run-001",
        )

        execute.assert_not_called()
        entry.lock.release.assert_called_once()

    async def test_07_api_maps_storage_errors_safely(self):
        import api

        for storage_error, expected_status in (
            (KeyError("missing"), 404),
            (ValueError("corrupted"), 503),
            (sqlite3.Error("unavailable"), 503),
        ):
            with self.subTest(
                storage_error=type(storage_error).__name__,
            ):
                entry = SimpleNamespace(
                    id="fixture-session",
                    owner="fixture-owner",
                    lock=MagicMock(),
                )

                with (
                    patch.object(
                        api.sessions,
                        "acquire",
                        return_value=entry,
                    ),
                    patch.object(
                        api.traces,
                        "load",
                        side_effect=storage_error,
                    ),
                    patch.object(
                        api,
                        "_execute_investigation",
                        create=True,
                        side_effect=AssertionError(
                            "Runtime must not execute during replay"
                        ),
                    ) as execute,
                ):
                    with self.assertRaises(
                        HTTPException
                    ) as caught:
                        await api.replay_investigation(
                            entry.id,
                            "fixture-run-001",
                            request_without_cookies(),
                        )

                self.assertEqual(
                    caught.exception.status_code,
                    expected_status,
                )
                execute.assert_not_called()
                entry.lock.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
