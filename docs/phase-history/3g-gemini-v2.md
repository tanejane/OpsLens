# OpsLens Phase 3G Gemini v2

The first Gemini smoke test proved the API key, SDK, model call and structured
output all work.

It also exposed a semantic mismatch: Gemini proposed `schema_discovery` for H1,
while the application compiler currently allows schema discovery only for H2/H4.

v2 aligns the planner prompt with the compiler's governed action rules.

Run:

```powershell
python scripts/smoke_phase3g_gemini_v2.py
```

Only after that passes, run:

```powershell
python scripts/validate_phase3g_gemini.py
```
