// Executed by scripts/test_release_contract.py with a real isolated FastAPI server.
import assert from "node:assert/strict";
const base = process.argv[2];
let cookie = "";
async function call(method, path, body, status, extra = {}) {
  const result = await fetch(base + '/api/' + path, {method,
    headers:{"content-type":"application/json", origin:"http://192.168.100.20:3000", cookie, ...extra},
    body:body && JSON.stringify(body)});
  assert.equal(result.status, status);
  if (result.headers.has("set-cookie")) {
    assert.match(result.headers.get('set-cookie'), /HttpOnly/i);
    assert.match(result.headers.get('set-cookie'), /SameSite=strict/i);
    cookie = result.headers.get("set-cookie").split(";")[0];
  }
  return result.json();
}
for (const extra of [{origin:'https://untrusted.example'}, {origin:'null'}, {origin:''},
  {origin:base}, {origin:'http://192.168.100.20:3001'}, {'sec-fetch-site':'cross-site'},
  {origin:'https://untrusted.example','x-forwarded-host':'192.168.100.20:3000'}]) {
  await call('POST','investigation-sessions',undefined,403,extra);
  await call('POST','investigations',{question:'fixture'},403,extra);
  await call('DELETE','investigation-sessions/not-an-owned-session',undefined,403,extra);
}
await call('POST','investigation-sessions',undefined,200,{origin:'http://localhost:3000','sec-fetch-site':'same-origin'});
const session = (await call("POST","investigation-sessions",undefined,200)).session;
const folder = "investigation-sessions/" + session.id;
await call('GET',folder,undefined,404,{cookie:''});
const turn = (question,revision,status) => call("POST","investigations",{question,session_id:session.id,revision},status);
await turn("fixture",undefined,422);
for (const [index, [question, status]] of [["fixture","MEASURED_WITH_SCOPE_LIMITS"],["partial","PARTIAL_GOVERNED_EVIDENCE"],["cancel","CANCELLED"]].entries()) {
  const body = await turn(question,index,200);
  assert.equal(body.result.status,status);
  assert.deepEqual(body.result,body.canonical_result.payload);
  if (index !== 2) {
    assert.equal(body.result.value,"10.2300");
    assert.equal(body.canonical_result.number_encodings["/payload/unknown/count"],"integer");
  }
  const replay = await call("GET", folder+"/runs/"+body.result.observability.run_id+"/replay",undefined,200);
  assert.deepEqual(replay.canonical_result,body.canonical_result);
  assert.equal(replay.replay.external_calls,0);
}
await turn("fixture",0,409);
const failed = await turn("failure",3,503);
assert.equal(failed.detail.canonical_result.payload.status,"EXECUTION_FAILED");
const large = await turn("oversized",4,413);
assert.equal(large.detail.session.revision,4);
assert.equal(large.detail.canonical_result.payload.completed_result.payload.value,"10.2300");
await call("DELETE",folder,undefined,200);
await call("GET",folder,undefined,404);
