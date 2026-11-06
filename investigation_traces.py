"""Bounded local audit snapshots. Replay is retrieval, never execution."""
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

SENSITIVE = re.compile(r'api.?key|authorization|cookie|password|secret|access.?token|refresh.?token|credential|^token$', re.I)
_models=ContextVar('opslens_model_metadata',default=None)

@contextmanager
def model_metadata():
    entries=[];token=_models.set(entries)
    try:yield entries
    finally:_models.reset(token)

def record_model(response,model,component):
    entries=_models.get()
    if entries is None:return
    usage=getattr(response,'usage_metadata',None)
    entries.append({'model':model,'component':component,
        'usage':{k:getattr(usage,k,None) for k in ('prompt_token_count','candidates_token_count','total_token_count','cached_content_token_count')},
        'model_version':getattr(response,'model_version',None)})

def redact(value):
    known = [v for k,v in os.environ.items() if SENSITIVE.search(k) and len(v)>=8]
    def clean(v):
        if isinstance(v,dict):return {k:'[REDACTED]' if SENSITIVE.search(k) else clean(x) for k,x in v.items()}
        if isinstance(v,list):return [clean(x) for x in v]
        if isinstance(v,str):
            for secret in known:v=v.replace(secret,'[REDACTED]')
            v=re.sub(r'(?i)(bearer\s+)[\w.\-]+',r'\1[REDACTED]',v)
            v=re.sub(r'(?i)((?:api[_-]?key|password|secret|access_token)\s*[=:]\s*)[^\s&,;\"\']+',r'\1[REDACTED]',v)
            v=re.sub(r'(://)[^\s/@:]+:[^\s/@]+@',r'\1[REDACTED]@',v)
            return v
        return v
    return clean(deepcopy(value))

def encode(record):return json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(record):return hashlib.sha256(encode(record).encode()).hexdigest()

def annotate(record,elapsed,validated):
    record=redact(record)
    payload=record['payload']
    evidence=[]
    for i,item in enumerate(payload.get('validated_evidence',[])):
        evidence.append({'evidence_id':digest(item),'path':f'/payload/validated_evidence/{i}',
                         'decision':'VALIDATOR_RETURNED','producer':item.get('producer')})
    payload['observability']={'schema_version':'opslens.trace.v1','run_id':secrets.token_urlsafe(24),
        'latency_ms':round(elapsed*1000,3),'validation_decision':'VALIDATED' if validated else 'NOT_CERTIFIED',
        'evidence':evidence,'stop_reason':payload.get('orchestration',{}).get('stop_reason',payload.get('status')),
        'model_metadata':{'calls':payload.get('model_calls',[]),'availability':'Recorded where returned by instrumented adapters; missing counts are unknown'},
        'replay_mode':'SAVED_EVIDENCE_ONLY','persistence':'SAVED'}
    return record

class TraceStore:
    def __init__(self,path=None,*,ttl=1800,max_runs=256,per_session=8,max_record=2_000_000,max_bytes=32_000_000,clock=time.time):
        self.path=Path(path or os.getenv('OPSLENS_TRACE_DB','.runtime/investigation-traces.sqlite3'))
        self.ttl,self.max_runs,self.per_session,self.max_record,self.max_bytes,self.clock=ttl,max_runs,per_session,max_record,max_bytes,clock
        self.lock=threading.RLock()

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        db=sqlite3.connect(self.path,timeout=2)
        os.chmod(self.path,0o600)
        db.execute('PRAGMA secure_delete=ON')
        # Bound allocated database pages as well as logical record bytes.
        page_size=db.execute('PRAGMA page_size').fetchone()[0]
        db.execute(f'PRAGMA max_page_count={max(256,(self.max_bytes+self.max_record+2_000_000)//page_size)}')
        db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, session TEXT, owner TEXT, created REAL, body TEXT, checksum TEXT, size INTEGER)')
        db.execute('DELETE FROM runs WHERE created <= ?', (self.clock()-self.ttl,))
        try:
            with db:yield db
        finally:db.close()

    def save(self,session,owner,record):
        record=redact(record)
        body=encode(record);size=len(body.encode())
        if size>self.max_record or size>self.max_bytes:raise ValueError('Trace size limit')
        with self.lock,self.connect() as db:
            run=record['payload']['observability']['run_id']
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?)',(run,session,owner,self.clock(),body,digest(record),size))
            db.execute('DELETE FROM runs WHERE id IN (SELECT id FROM runs WHERE session=? ORDER BY created DESC,rowid DESC LIMIT -1 OFFSET ?)',(session,self.per_session))
            while True:
                count,total=db.execute('SELECT count(*),coalesce(sum(size),0) FROM runs').fetchone()
                if count<=self.max_runs and total<=self.max_bytes:break
                db.execute('DELETE FROM runs WHERE id=(SELECT id FROM runs ORDER BY created,rowid LIMIT 1)')

    def load(self,session,owner,run):
        with self.lock,self.connect() as db:
            row=db.execute('SELECT body,checksum FROM runs WHERE id=? AND session=? AND owner=?',(run,session,owner)).fetchone()
        if row is None:raise KeyError('Trace unavailable or expired')
        record=json.loads(row[0])
        if not secrets.compare_digest(digest(record),row[1]):raise ValueError('Trace integrity failure')
        return {'canonical_result':record,'replay':{'mode':'SAVED_EVIDENCE_ONLY','sha256':row[1],'external_calls':0}}

    def delete(self,session,owner):
        with self.lock,self.connect() as db:db.execute('DELETE FROM runs WHERE session=? AND owner=?',(session,owner))
