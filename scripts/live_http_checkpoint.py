"""Actual frontend-proxy HTTP journey; no monkeypatching or synthetic responses."""
import json,time
from pathlib import Path
import httpx

def main():
    results=[]
    with httpx.Client(base_url='http://localhost:3000',timeout=180) as client:
        session=client.post('/api/investigation-sessions').raise_for_status().json()['session']
        for question in ['Compare late versus on-time order ratings in March 2018.',
                         'Are delivery delays concentrated among sellers?',
                         'What about February?',
                         'Why did revenue rise and contribution profit fall in March 2018 compared with February 2018?',
                         'Are delivery delays concentrated among sellers in December 2016?']:
            start=time.monotonic()
            response=client.post('/api/investigations',json={'question':question,'session_id':session['id'],'revision':session['revision']})
            body=response.json()
            if response.is_success:session=body['session']
            elif isinstance(body.get('detail'),dict) and body['detail'].get('session'):session=body['detail']['session']
            results.append({'question':question,'http_status':response.status_code,'latency_seconds':round(time.monotonic()-start,3),
                'canonical_result':body.get('canonical_result') or body.get('detail',{}).get('canonical_result'),
                'error':body.get('detail') if not response.is_success else None})
            Path('reports/live_http_journey.json').write_text(json.dumps({'scope':'Actual Next.js proxy to FastAPI, real MCP/PostgreSQL; Gemini unavailable unless configured','results':results},indent=2),encoding='utf-8')
            print(response.status_code,question,flush=True)
        # Session remains live for browser ownership; never persist the owner cookie.
        restored=client.get('/api/investigation-sessions/'+session['id']).raise_for_status().json()['session']
        print('restored revision',restored['revision'],flush=True)

if __name__=='__main__':main()
