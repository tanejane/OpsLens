"""Inspect Phase 4B.1 failures without hiding nested async/MCP errors."""
from __future__ import annotations
import asyncio
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.phase4b1_semantic_playground import run_question


def render_error(error: BaseException, indent: int = 0) -> None:
    p = ' ' * indent
    print(f'{p}{type(error).__name__}: {error}')
    if isinstance(error, BaseExceptionGroup):
        for number, nested in enumerate(error.exceptions, 1):
            print(f'{p}  nested #{number}:')
            render_error(nested, indent + 4)
    elif error.__cause__ is not None:
        print(f'{p}  caused by:')
        render_error(error.__cause__, indent + 4)
    elif error.__context__ is not None and not error.__suppress_context__:
        print(f'{p}  context:')
        render_error(error.__context__, indent + 4)


async def main() -> None:
    question = ' '.join(sys.argv[1:]).strip() or 'How many orders were placed in June 2018?'
    print('OpsLens 4B.1 diagnostic — one question only')
    print('Question:', question)
    try:
        await run_question(question)
    except BaseException as exc:
        print('\nROOT-CAUSE TREE:')
        render_error(exc)
        print('\nTRACEBACK:')
        traceback.print_exception(exc, file=sys.stdout)
        raise SystemExit(1)
    print('\nDiagnostic execution completed.')


if __name__ == '__main__':
    asyncio.run(main())
