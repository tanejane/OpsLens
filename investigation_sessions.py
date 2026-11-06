"""Bounded process-local session persistence; owner credentials are not enterprise auth."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import secrets
import threading
import time
from fastapi import HTTPException

COOKIE = 'opslens_owner'


@dataclass
class Session:
    id: str
    owner: str
    expires: float
    lock: object = field(default_factory=threading.Lock)
    revision: int = 0
    recovery: object = None
    last_valid: dict | None = None
    last_valid_turn: int | None = None
    history: list = field(default_factory=list)
    evicted: int = 0
    size: int = 0


class SessionStore:
    def __init__(self, *, ttl=1800, max_sessions=64, max_turns=8, max_bytes=2_000_000, total_bytes=32_000_000, clock=time.monotonic):
        self.ttl,self.max_sessions,self.max_turns = ttl,max_sessions,max_turns
        self.max_bytes,self.total_bytes,self.clock = max_bytes,total_bytes,clock
        self.entries = {}
        self.guard = threading.RLock()

    @staticmethod
    def owner(token): return hashlib.sha256(token.encode()).hexdigest()

    def cleanup(self):
        for key,value in list(self.entries.items()):
            if value.expires <= self.clock() and not value.lock.locked(): del self.entries[key]

    def create(self, owner):
        with self.guard:
            self.cleanup()
            if len(self.entries) >= self.max_sessions: raise HTTPException(429,'Session capacity reached; retry after expiration')
            value = Session(secrets.token_urlsafe(32),self.owner(owner),self.clock()+self.ttl)
            self.entries[value.id] = value
            return value

    def acquire(self, id, owner, revision=None):
        with self.guard:
            self.cleanup()
            value = self.entries.get(id)
            if not owner or not value or value.expires <= self.clock() or not secrets.compare_digest(value.owner,self.owner(owner)):
                raise HTTPException(404,'Investigation session unavailable or expired')
            if not value.lock.acquire(blocking=False): raise HTTPException(409,'A session request is already running; refresh before retrying')
            if revision is not None and value.revision != revision:
                value.lock.release()
                raise HTTPException(409,'Session revision changed; refresh before retrying')
            return value

    def snapshot(self, value):
        return {'id':value.id,'revision':value.revision,'expires_in_seconds':max(0,int(value.expires-self.clock())),
            'history':deepcopy(value.history),'last_validated_result':deepcopy(value.last_valid),
            'last_validated_turn':value.last_valid_turn,'evicted_turns':value.evicted,
            'retention':{'max_turns':self.max_turns,'max_bytes':self.max_bytes,'process_local':True},
            'clarification':{'sales':deepcopy(vars(value.recovery.pending)) if value.recovery and value.recovery.pending else None,
                'investigation':deepcopy(value.recovery.investigation_pending) if value.recovery else None}}

    def commit(self, value, record, recovery, *, validated, clarify):
        with self.guard:
            history = [*value.history,{'turn':value.revision+1,'canonical_result':deepcopy(record)}]
            evicted = value.evicted
            last_valid = deepcopy(record) if validated else value.last_valid
            while len(history)>self.max_turns:
                history.pop(0);evicted+=1
            def size(): return len(json.dumps({'history':history,'last_valid':last_valid},ensure_ascii=False).encode())
            while size()>self.max_bytes and len(history)>1:
                history.pop(0);evicted+=1
            amount = size()
            if amount>self.max_bytes or sum(s.size for s in self.entries.values())-value.size+amount>self.total_bytes:
                raise HTTPException(413,'Session evidence storage limit reached; previous state retained')
            if validated:
                value.recovery = deepcopy(recovery)
                value.last_valid_turn = value.revision+1
            elif clarify:
                if value.recovery is None: value.recovery = deepcopy(recovery)
                else:
                    value.recovery.pending = deepcopy(recovery.pending)
                    value.recovery.investigation_pending = deepcopy(recovery.investigation_pending)
            value.last_valid,value.history,value.evicted,value.size = last_valid,history,evicted,amount
            value.revision += 1
            value.expires = self.clock()+self.ttl

    def delete(self, value):
        with self.guard: self.entries.pop(value.id,None)
