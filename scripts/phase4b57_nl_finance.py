"""Interactive Gemini -> governed dynamic finance, preserving context only on success."""
import asyncio,json
from agent.phase4b57_nl_dynamic_finance import Interpreter,resolve,execute,Context,mcp_query,interpret_with_retries,ModelUnavailable,ModelResponseInvalid,NoSourceCoverage,Rejected

async def main():
    interpreter=Interpreter()
    previous=None
    print('OpsLens Phase 4B.5.7 — finance-only NL; type exit to quit')
    from mcp import Client
    from mcp_server.server import mcp
    async with Client(mcp) as client:
        while True:
            try: question=input('\nOpsLens > ').strip()
            except (EOFError,KeyboardInterrupt):break
            if question.lower() in ('exit','quit'):break
            if not question:continue
            try:
                intent=interpret_with_retries(interpreter,question,previous)
                metric,before,after=resolve(intent,previous)
                print('GROUNDED:',json.dumps({'metric':metric,'before':vars(before) if before else None,'after':vars(after)},indent=2))
                async def reader(sql,purpose):return await mcp_query(client,sql,purpose)
                result=await execute(metric,before,after,reader)
                print('EVIDENCE:',json.dumps(result,indent=2,default=str))
                previous=Context(metric,after.start,after.end)
                print('Context saved. Descriptive measurement; no causal conclusion.')
            except Exception as exc:
                while isinstance(exc,BaseExceptionGroup) and exc.exceptions:exc=exc.exceptions[0]
                code=('MODEL_UNAVAILABLE' if isinstance(exc,ModelUnavailable) else
                      'MODEL_RESPONSE_INVALID' if isinstance(exc,ModelResponseInvalid) else
                      'NO_SOURCE_COVERAGE' if isinstance(exc,NoSourceCoverage) else
                      'REQUEST_NOT_GROUNDED' if isinstance(exc,Rejected) else
                      'EXECUTION_FAILED')
                print('BLOCKED:',code,type(exc).__name__,str(exc)[:500])
                print('Previous successful context unchanged.')
if __name__=='__main__':asyncio.run(main())
