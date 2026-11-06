"""Optional live Gemini smoke test. Never executes MCP or domain queries."""
import asyncio,json,sys
from agent.phase4c27a_interpreter import interpret,gemini_client,InterpretationRejected
async def main():
    question=' '.join(sys.argv[1:]).strip() or '为什么六月的 revenue 增加但 profit 下降？'
    try:
        result=await interpret(question,gemini_client)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (RuntimeError,InterpretationRejected,ImportError) as e:
        print(json.dumps({'status':'INTERPRETATION_NOT_VALIDATED','reason':str(e),'executable':False},ensure_ascii=False))
        raise SystemExit(1)
if __name__=='__main__':asyncio.run(main())
