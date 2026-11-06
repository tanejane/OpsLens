import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
const require=createRequire(import.meta.url);
async function moduleUrl(path,replacements={}) {
  let code=ts.transpileModule(await readFile(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  replacements['react/jsx-runtime']=pathToFileURL(require.resolve('react/jsx-runtime')).href;
  for(const [key,value] of Object.entries(replacements))code=code.replaceAll(`from "${key}"`,`from "${value}"`);
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
const {normalizeInvestigation}=await import(await moduleUrl('../lib/investigation.ts'));
const {InvestigationTimeline}=await import(await moduleUrl('../components/investigation-timeline.tsx'));
test('timeline and replay are optional Analyst-only diagnostics',()=>{
 const canonical={schema_version:'opslens.investigation.v1',question:'Revenue',payload:{
  observability:{run_id:'run-fixture',latency_ms:12,validation_decision:'VALIDATED',stop_reason:'SUFFICIENT',persistence:'SAVED',evidence:[],model_metadata:{}},
  context_provenance:{session_id:'session-fixture'},execution_trace:[{tool:'search_knowledge',latency_ms:4,outcome:'RETURNED'}]}};
 const report=normalizeInvestigation(canonical);
 assert.equal(renderToStaticMarkup(React.createElement(InvestigationTimeline,{report,mode:'Business'})),'');
 const html=renderToStaticMarkup(React.createElement(InvestigationTimeline,{report,mode:'Analyst'}));
 assert.match(html,/run-fixture/);assert.match(html,/search_knowledge/);assert.match(html,/\/runs\/run-fixture\/replay/);
 assert.doesNotMatch(html,/<details[^>]*open/);
});
const evidence=await moduleUrl('../components/investigation-evidence.tsx');
const {RefundConcentration}=await import(await moduleUrl('../components/refund-concentration.tsx',{'./investigation-evidence':evidence}));
for(const mode of ['Business','Analyst'])test(`${mode} renders refund cohort amounts and attribution without SKU claims`,async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_3_refunds.json',import.meta.url),'utf8'));
 const html=renderToStaticMarkup(React.createElement(RefundConcentration,{report:normalizeInvestigation(record),mode}));
 assert.match(html,/60.5/);assert.match(html,/30.5/);assert.match(html,/multi seller/);assert.match(html,/unknown/);
 assert.match(html,/role="img"/);assert.match(html,/do not identify seller responsibility/);
 if(mode==='Analyst'){assert.match(html,/multi_item_orders/);assert.match(html,/Source-wide unlinked return events: 2/);}
});
const {DeliveryReviewComparison}=await import(await moduleUrl('../components/delivery-review-comparison.tsx',{'./investigation-evidence':evidence}));
const record=JSON.parse(await readFile(new URL('./fixtures/p1_1_comparison.json',import.meta.url),'utf8'));
for(const mode of ['Business','Analyst'])test(`${mode} renders the same cohort figures and comparison chart`,()=>{
  const html=renderToStaticMarkup(React.createElement(DeliveryReviewComparison,{report:normalizeInvestigation(record),mode}));
  assert.match(html,/3.00/);assert.match(html,/4.00/);assert.match(html,/role="img"/);
  assert.match(html,/does not establish/);
  if(mode==='Analyst'){assert.match(html,/Score sum/);assert.match(html,/Multiple reviews/);assert.match(html,/Left join by unique order ID/);}
  else assert.doesNotMatch(html,/<table>/);
});

test('adaptive Business findings hide orchestration while Analyst exposes optional steps',async()=>{
  const cases=JSON.parse(await readFile(new URL('./fixtures/p1_2_adaptive.json',import.meta.url),'utf8'));
  const report=normalizeInvestigation(cases.expanded);
  for(const mode of ['Business','Analyst']){
    const html=renderToStaticMarkup(React.createElement(DeliveryReviewComparison,{report,mode}));
    assert.match(html,/additional evidence shows/);assert.match(html,/broader population/);
    if(mode==='Analyst')assert.match(html,/Investigation steps/);
    else assert.doesNotMatch(html,/<summary>Investigation steps/);
  }
});

test('seller workspaces show the same partition and counts with an accessible chart',async()=>{
 const {SellerConcentration}=await import(await moduleUrl('../components/seller-concentration.tsx',{'./investigation-evidence':evidence}));
 const record=JSON.parse(await readFile(new URL('./fixtures/p1_3_seller.json',import.meta.url),'utf8'));
 for(const mode of ['Business','Analyst']){
  const html=renderToStaticMarkup(React.createElement(SellerConcentration,{report:normalizeInvestigation(record),mode}));
  assert.match(html,/75.00%/);assert.match(html,/multi seller/);assert.match(html,/role="img"/);
  assert.match(html,/not seller responsibility/);
  if(mode==='Analyst')assert.match(html,/Investigation steps/);
 }
});

test('document context has distinct Business and Analyst presentations',async()=>{
 const {DocumentEvidence}=await import(await moduleUrl('../components/document-evidence.tsx'));
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_1_documents.json',import.meta.url),'utf8'));
 for(const mode of ['Business','Analyst']){
  const html=renderToStaticMarkup(React.createElement(DocumentEvidence,{report:normalizeInvestigation(record),mode}));
  assert.match(html,/Conflicts with the measured figures/);assert.match(html,/Agrees with the measured figures/);
  if(mode==='Analyst'){assert.match(html,/Content SHA-256/);assert.match(html,/Measurement:/);}
  else {assert.match(html,/Document excerpt/);assert.doesNotMatch(html,/Content SHA-256/);}
 }
});
