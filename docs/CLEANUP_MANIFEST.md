# File audit and rename manifest

This is a **non-destructive source cleanup**, not an assertion that all historic files are unused. Files without proven removal safety remain in place.

- Original files: **189**
- Kept original files (including renamed): **181**
- Removed: **8** (one `.env` plus Python cache files)
- Renamed/moved: **26**
- Text/code files with updated references: **13**

## Renamed or moved

| Old path | New path |
|---|---|
| `README_PHASE2A.md` | `docs/phase-history/2a.md` |
| `README_PHASE2B.md` | `docs/phase-history/2b.md` |
| `README_PHASE2C.md` | `docs/phase-history/2c.md` |
| `README_PHASE2D.md` | `docs/phase-history/2d.md` |
| `README_PHASE3A.md` | `docs/phase-history/3a.md` |
| `README_PHASE3B.md` | `docs/phase-history/3b.md` |
| `README_PHASE3C.md` | `docs/phase-history/3c.md` |
| `README_PHASE3D.md` | `docs/phase-history/3d.md` |
| `README_PHASE3E.md` | `docs/phase-history/3e.md` |
| `README_PHASE3E_V2.md` | `docs/phase-history/3e-v2.md` |
| `README_PHASE3F.md` | `docs/phase-history/3f.md` |
| `README_PHASE3G.md` | `docs/phase-history/3g.md` |
| `README_PHASE3G_GEMINI.md` | `docs/phase-history/3g-gemini.md` |
| `README_PHASE3G_GEMINI_V2.md` | `docs/phase-history/3g-gemini-v2.md` |
| `agent/context_phase4a.py` | `agent/phase4a_context.py` |
| `agent/live_context_phase4a1.py` | `agent/phase4a1_live_context.py` |
| `agent/plan_phase4a.py` | `agent/phase4a_plan_contract.py` |
| `agent/planner_phase4a.py` | `agent/phase4a_planner.py` |
| `agent/playground_phase4b.py` | `agent/phase4b_investigation_playground.py` |
| `agent/playground_utils_phase4b.py` | `agent/phase4b_playground_utils.py` |
| `agent/semantic_playground_phase4b1.py` | `agent/phase4b1_semantic_playground.py` |
| `agent/semantic_query_phase4b1.py` | `agent/phase4b1_semantic_query.py` |
| `scripts/diagnose_phase4b1.py` | `scripts/phase4b1_diagnose_query.py` |
| `scripts/validate_phase4b1_date_fix.py` | `scripts/phase4b1_validate_date_casts.py` |
| `scripts/validate_phase4b1_offline.py` | `scripts/phase4b1_validate_semantic_queries.py` |
| `scripts/validate_phase4b_offline.py` | `scripts/phase4b_validate_investigation.py` |

## Excluded

- `.env` — contains local configuration/secrets; intentionally omitted.
- `agent/__pycache__/__init__.cpython-313.pyc` — generated Python cache
- `agent/__pycache__/semantic_playground_phase4b1.cpython-313.pyc` — generated Python cache
- `agent/__pycache__/semantic_query_phase4b1.cpython-313.pyc` — generated Python cache
- `mcp_server/__pycache__/__init__.cpython-313.pyc` — generated Python cache
- `mcp_server/__pycache__/runtime_tools.cpython-313.pyc` — generated Python cache
- `mcp_server/__pycache__/server.cpython-313.pyc` — generated Python cache
- `retrieval/__pycache__/hybrid.cpython-313.pyc` — generated Python cache

## Preserved on purpose

- All `data/` datasets including raw, processed, synthetic, and evaluator ground truth; dependencies and reproducibility were not established well enough to delete them.
- Historical agent prototypes, validators, data-generation scripts, and prior requirements files. Some may be needed to reproduce evaluation incidents.
- All SQL migrations and metric definitions.
- Historical phase READMEs moved into `docs/phase-history/`, not deleted.

## Automatic static checks

- Python AST parsed: **73** modules.
- Local import issues detected: 0
- Old module references after replacement: 0

## Next cleanup stage

Once tests run in the real local Windows project, unused scripts can be retired based on execution/import coverage, then dependencies can be consolidated. **No speculative code deletions were made.**