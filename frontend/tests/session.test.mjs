import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const require=createRequire(import.meta.url);
async function compile(path,replacements={}) {
  let output=ts.transpileModule(await readFile(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
  for(const [name,url] of Object.entries(replacements)) output=output.replace(`from "${name}"`,`from "${url}"`);
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`;
}
const apiUrl=await compile('../lib/api-client.ts');
const {ApiRequestError}=await import(apiUrl);
const {InvestigationSessionClient}=await import(await compile('../lib/investigation-session.ts',{'./api-client':apiUrl}));
const record=(question)=>({schema_version:'opslens.investigation.v1',question,payload:{status:'NEEDS_CLARIFICATION',executable:false,causal_claim:false,reason:'Choose a baseline'}});
function harness() {
  const calls=[], saved=new Map();
  let state={id:'opaque-session-id',revision:0,history:[],evicted_turns:0};
  let failure;
  const request=async(url,init={})=>{
    calls.push({url,...init});
    if(init.method==='DELETE') return {status:'RESET'};
    if(url==='/api/investigation-sessions') return {session:structuredClone(state)};
    if(url.startsWith('/api/investigation-sessions/')) {
      if(failure?.status===404) throw failure;
      return {session:structuredClone(state)};
    }
    if(failure) throw failure;
    const body=JSON.parse(init.body);
    assert.equal(body.session_id,state.id);
    assert.equal(body.revision,state.revision);
    state={...state,revision:state.revision+1,history:[...state.history,{turn:state.revision+1,canonical_result:record(body.question)}]};
    return {session:structuredClone(state),canonical_result:record(body.question)};
  };
  return {calls,request,client:new InvestigationSessionClient(request),storage:{getItem:k=>saved.get(k)??null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},saved,
    setFailure:e=>{failure=e;},setState:s=>{state=s;},getState:()=>structuredClone(state)};
}

test('session client preserves context across turns and stores only opaque ID',async()=>{
  const h=harness();await h.client.restore(h.storage);
  await h.client.turn('Why did profit decline in March 2018?');
  await h.client.turn('Compare that with February');
  assert.equal(h.calls.filter(x=>x.url==='/api/investigation-sessions').length,1);
  assert.equal(h.client.session.revision,2);
  assert.deepEqual([...h.saved.values()],['opaque-session-id']);
  assert.equal(JSON.parse(h.calls.at(-1).body).question,'Compare that with February');
});

test('reload restores canonical result without executing a turn',async()=>{
  const h=harness();await h.client.restore(h.storage);const expected=await h.client.turn('March profit');
  const next=new InvestigationSessionClient(h.request);const count=h.calls.length;
  assert.deepEqual(await next.restore(h.storage),expected);
  assert.equal(h.calls.length,count+1);assert.equal(h.calls.at(-1).method,undefined);
  assert.equal(next.session.revision,1);
});

test('explicit reset revokes server session and clears local reference',async()=>{
  const h=harness();await h.client.restore(h.storage);await h.client.turn('question');
  await h.client.reset();assert.equal(h.calls.at(-1).method,'DELETE');
  assert.equal(h.client.session,undefined);assert.equal(h.saved.size,0);
});

test('failed reset preserves the active session',async()=>{
  let deleted=false;
  const request=async(url,init={})=>{
    if(init.method==='DELETE'){deleted=true;throw new Error('offline');}
    return {session:{id:'id',revision:0,history:[],evicted_turns:0},canonical_result:record('q')};
  };
  const client=new InvestigationSessionClient(request);await client.turn('q');
  await assert.rejects(client.reset(),/offline/);assert.ok(deleted);assert.equal(client.session.id,'id');
});

test('failed turn accepts server revision and preserves failure evidence without replay',async()=>{
  const h=harness();await h.client.turn('first');
  const failed={...record('failed'),payload:{status:'EXECUTION_FAILED',executable:false,validated_evidence:[{id:'original-proof'}]}};
  const snapshot={...h.getState(),revision:2};
  h.setFailure(new ApiRequestError('failed',failed,snapshot,503));
  await assert.rejects(h.client.turn('next'),error=>{assert.deepEqual(error.canonicalResult,failed);return true;});
  assert.equal(h.client.session.revision,2);
  assert.equal(h.calls.filter(x=>x.url==='/api/investigations').length,2);
});

test('conflict refreshes the visible canonical record without automatically replaying tools',async()=>{
  const h=harness();await h.client.turn('first');
  const latest=record('another committed turn');h.setState({...h.getState(),revision:2,history:[{turn:2,canonical_result:latest}]});
  h.setFailure(new ApiRequestError('conflict',undefined,undefined,409));
  await assert.rejects(h.client.turn('next'),error=>{assert.deepEqual(error.canonicalResult,latest);return true;});
  assert.equal(h.client.session.revision,2);
  assert.equal(h.calls.filter(x=>x.url==='/api/investigations').length,2);
});

test('expired session requires explicit new investigation rather than silent context loss',async()=>{
  const h=harness();await h.client.restore(h.storage);await h.client.turn('first');
  h.setFailure(new ApiRequestError('expired',undefined,undefined,404));
  await assert.rejects(h.client.turn('next'),/expired/);const count=h.calls.length;
  await assert.rejects(h.client.turn('repeat'),/New investigation/);assert.equal(h.calls.length,count);
  await h.client.reset();h.setFailure(undefined);await h.client.turn('new');
  assert.equal(h.calls.filter(x=>x.url==='/api/investigation-sessions').length,2);
});

test('Business/Analyst switching shares the controller and only changes presentation',async()=>{
  const page=await readFile(new URL('../app/page.tsx',import.meta.url),'utf8');
  assert.match(page,/useState\(\(\) => new InvestigationSessionClient\(requestJson\)\)/);
  assert.match(page,/onClick=\{\(\) => setReportMode\(mode\)\}/);
  assert.match(page,/sessionClient\.turn\(value\)/);
  assert.match(page,/disabled=\{loading \|\| !sessionReady\} onClick=\{newInvestigation\}/);
  assert.doesNotMatch(page,/useEffect\([^]*?runInvestigation[^]*?\[reportMode\]/);
});

test('Next proxy forwards owner credential and origin and returns HttpOnly cookie',async()=>{
  const nextUrl=pathToFileURL(require.resolve('next/server')).href;
  const proxy=await import(await compile('../app/api/[...path]/route.ts',{'next/server':nextUrl}));
  const {NextRequest}=await import(nextUrl);
  const original=globalThis.fetch;let forwarded;
  try{
    globalThis.fetch=async(url,init)=>{forwarded=init;return new Response(JSON.stringify({session:{id:'id'}}),{headers:{'content-type':'application/json','set-cookie':'opslens_owner=credential; HttpOnly; Path=/api; SameSite=Strict'}});};
    const response=await proxy.POST(new NextRequest('http://localhost:3000/api/investigation-sessions',{method:'POST',headers:{cookie:'opslens_owner=credential',origin:'http://localhost:3000'}}),{params:Promise.resolve({path:['investigation-sessions']})});
    assert.equal(forwarded.headers.cookie,'opslens_owner=credential');assert.equal(forwarded.headers.origin,'http://localhost:3000');
    assert.match(response.headers.get('set-cookie'),/HttpOnly/);assert.equal(response.headers.get('cache-control'),'no-store');
    assert.equal(typeof proxy.DELETE,'function');
  }finally{globalThis.fetch=original;}
});
