# Phase 4C.27A — Gemini proposal-only multilingual interpreter

This is an **additive opt-in** interpretation module. It does not modify existing routing, create SQL, invoke MCP tools, or grant new authorization. Live integration is reserved for Phase 4C.27B after independently evaluating whether Gemini reliably preserves meaning and ambiguity.

## Merge / offline checks

Copy `agent/`, `scripts/` and `docs/` into the existing repo. No database migration or environment changes for offline validation:

```powershell
python -m scripts.phase4c27a_validate
python -m scripts.phase4c26_validate
```

## Live Gemini smoke test (no MCP execution)

Uses your installed `google-genai` package and the configured `GOOGLE_API_KEY` or `GEMINI_API_KEY`. Optional model override `OPSLENS_INTERPRETER_MODEL`, default `gemini-3.5-flash-lite`. **Do not paste your secret key in chat.**

```powershell
python -m scripts.phase4c27a_smoke '为什么六月的 revenue 增加，但 profit 下降？'
python -m scripts.phase4c27a_smoke 'how much beuty item GMV in Jun 2018?'
python -m scripts.phase4c27a_smoke 'eh how was sales in june ah?'
```

Expected successful *structural* status `INTERPRETATION_PROPOSED`, `executable: false`, `approved_for_mcp: false`. If Gemini chooses an unapproved identifier or malformed JSON, the wrapper **fails closed** (`INTERPRETATION_NOT_VALIDATED`). Inspect the semantic correctness manually: correct extraction is **not** guaranteed merely because the JSON shape is valid.

## Limitations and next acceptance gates

- Output parsing is strict, but structural validity does **not** prove factual or semantic accuracy. An approved metric can still be the wrong interpretation; independent comparison with gold labels is necessary.
- Current product category whitelist intentionally covers *only* `beleza_saude`. Do not translate the remaining catalog automatically. Numeric dates or relative periods without explicit disambiguation require separate support.
- No claim that Gemini is a trustworthy source of metric definitions or time coverage.
- Phase B must cross-validate model proposals against original user text, existing clarification memory, current audited catalog, and governed domain contracts, preventing silent incorrect routing and hidden instruction execution.
- Benchmark deterministic path against model path for accuracy, latency, cost, and fallback rates. Avoid sending private tool outputs or arbitrary retrieved document text to the interpretation model.
