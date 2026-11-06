# Phase 4C.24 — Conservative Language Understanding Foundation

This package adds `LanguageSession` in front of the existing Phase 4C.20 `ProductNLPSession` (itself delegating to the existing delivery/CX/finance/graph/investigation router). **It does not grant SQL privileges, expand MCP allowlists, create new evidence, or silently enable category translations.**

## Install

Merge `agent/`, `scripts/`, and `docs/` into the existing repository, keeping existing scripts and business logic. Python 3.11+.

```powershell
python -m scripts.phase4c24_validate
python -m scripts.phase4c20_validate
python -m scripts.phase4c19_validate
python -m scripts.phase4c24_unified_playground
```

Suggested interactive checks:

```
How many beuty products were sold in Jun 18?
And the item GMV?
What is the late delivry rate in June 2018?
How is sales doing?
Why did beauty sales decrease in June 2018?
How many shoe products were sold in June 2018?
```

## Supported and unsupported

- Supported: a **small reviewed set** of exact-token typos (`beuty`, `reveneu`, `profitt`, `delivry`), `Jun 18`/`May 18` month abbreviations, `beauty` -> the **already verified** `beleza_saude` mapping, transparent correction audit metadata, clarification for naked `sales` and unresolved Chinese text.
- Important: legacy finance / delivery routes retain their own pre-existing interpretation and permissions. Normalizing one spelling does not certify that the downstream domain accepts every request.
- No general edit-distance fuzzy correction, broad multilingual support, unknown category guessing, or multi-intent parsing. Chinese terms are only preliminary explicit substitutions, with residual Han characters resulting in clarification; meaningful Chinese questions remain an **uncompleted feature**.
- Existing product NLP rejects causality, rankings, unknown categories and comparisons, and requires explicit periods. Inventory and causal claims remain prohibited.
- Does not consult the 4C.21B review CSV yet. No new English aliases are approved by this package.
- Failed ambiguous/suspicious requests do **not** change prior session context; inspect `language` metadata for accepted corrections.

## Testing / next gates

1. Confirm offline tests, then verify actual MCP answers through the opt-in 4C24 playground.
2. Measure typo recovery and false-positive rates using labeled evaluation fixtures across domains.
3. Integrate only explicitly human-approved category aliases from 4C21B after review; separately implement multilingual grammar, time normalization, clarifications, and negative test suites.
