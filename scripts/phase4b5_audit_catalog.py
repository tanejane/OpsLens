"""Run from project root: python -m scripts.phase4b5_audit_catalog"""
from pathlib import Path
import argparse, json
from agent.phase4b5_semantic_expansion import ROOT, build_report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', default=str(ROOT / 'reports/phase4b42_relationship_audit.json'))
    parser.add_argument('--output', default=str(ROOT / 'reports/phase4b5_metric_contract_audit.json'))
    args = parser.parse_args()
    report = build_report(ROOT/'config/metric_catalog.json', args.audit, ROOT/'config/phase4b5_metric_candidates.json')
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report, indent=2),encoding='utf-8')
    print('Saved:',output)
    for row in report['existing_metrics']:
        print('EXISTING',row['metric'],row['source_contract_status'], '; '.join(row['issues']))
    for row in report['candidate_metrics']:
        print('CANDIDATE',row['metric'],row['status'],('missing: '+', '.join(row['missing_columns'])) if row['missing_columns'] else '')
    print('No metric or join automatically execution-approved.')
if __name__=='__main__': main()
