# OpsLens Phase 3G — Gemini Planner Provider

This adds the first real LLM planner to OpsLens.

## Architecture

```text
user question
    ↓
structured investigation state
    ↓
GeminiPlannerProvider
    ↓
PlannerDecision (Pydantic)
    ↓
OpsLens proposal validator/compiler
    ↓
governed MCP tool
    ↓
evidence ledger
    ↓
Gemini sees updated state
    ↓
next planner decision
```

Gemini does **not** receive permission to execute SQL or tools directly.

## Install

```powershell
pip install -r requirements-phase3g-gemini.txt
```

## Set the API key

For the current PowerShell session:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
```

Do not commit the key into Git.

Optional model override:

```powershell
$env:OPSLENS_GEMINI_MODEL="gemini-flash-latest"
```

## Step 1 — smoke test

```powershell
python scripts/smoke_phase3g_gemini.py
```

Expected:

```text
OPSLENS GEMINI PLANNER SMOKE TEST
...
VERDICT: PASS
```

This makes one planner request only.

## Step 2 — full real-agent test

```powershell
python scripts/validate_phase3g_gemini.py
```

This lets Gemini repeatedly reason over updated OpsLens state.

Target:

```text
Checks passed: 6/6
VERDICT: PASS
```

## Important

The deterministic FakePlannerProvider remains valuable as the baseline.

We should compare:

```text
FakePlannerProvider
vs
GeminiPlannerProvider
```

on:
- correct next action;
- invalid proposal rate;
- tool-call efficiency;
- hypothesis coverage;
- stop behavior;
- final incident accuracy.

That comparison will become part of the later evaluation framework.
