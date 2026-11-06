"""Real HTTP/MCP/database document checkpoint; no fixtures or patched boundaries."""
import json,time
from pathlib import Path
import httpx

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=180) as client:
    session=client.post('/api/investigation-sessions').raise_for_status().json()['session']
    results=[]
    for q in ['Why did revenue rise and contribution profit fall in March 2018 compared with February 2018?', 'Cross-check that with documents']:
        start=time.monotonic()
        response=client.post('/api/investigations',json={'question':q,'session_id':session['id'],'revision':session['revision']})
        body=response.json()
        if response.is_success:session=body['session']
        record=body.get('canonical_result')
        results.append({'question':q,'http_status':response.status_code,'latency_seconds':round(time.monotonic()-start,3),'canonical_result':record,'error':body.get('detail')})
        Path('reports/p2_1_live.json').write_text(json.dumps({'scope':'Real HTTP, Gemini finance interpretation, MCP SQL and hybrid knowledge retrieval','results':results},indent=2),encoding='utf-8')
        print(response.status_code,record['payload'].get('status') if record else 'FAILED',record['payload'].get('document_evidence',{}).get('status') if record else '',flush=True)
