"""Explore available and missing analytical capabilities without DB or LLM."""
import argparse, json
from agent.phase4c8_capabilities import registry_snapshot
from agent.phase4c8_planning import PlanningRequest, plan, SUPPORTED_INTENTS

def main():
    p=argparse.ArgumentParser(description='OpsLens governed capability discovery')
    p.add_argument('--list',action='store_true')
    p.add_argument('--intent',choices=sorted(SUPPORTED_INTENTS))
    p.add_argument('--explicit-periods',action='store_true')
    p.add_argument('--max-steps',type=int,default=3)
    args=p.parse_args()
    out=plan(PlanningRequest(args.intent,args.explicit_periods,args.max_steps)) if args.intent else registry_snapshot()
    print(json.dumps(out,indent=2))

if __name__=='__main__': main()
