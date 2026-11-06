"""Launch live, read-only semantic map audit through the existing MCP server."""
import argparse
import asyncio
from agent.phase4b41_live_verifier import live_main

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='reports/phase4b41_live_semantic_audit.json')
    args=p.parse_args()
    asyncio.run(live_main(args.output))
