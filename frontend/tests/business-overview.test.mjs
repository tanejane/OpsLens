import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
const require=createRequire(import.meta.url);
async function compile(path,replacements={}) {
 let code=ts.transpileModule(await readFile(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 for(const name of ['react/jsx-runtime','react','lucide-react'])replacements[name]=pathToFileURL(require.resolve(name)).href;
 for(const [key,value] of Object.entries(replacements))code=code.replaceAll(`from "${key}"`,`from "${value}"`);
 return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
const modelUrl=await compile('../lib/business-overview.ts');
const model=await import(modelUrl);
const primitivesUrl=await compile('../components/business-primitives.tsx',{'../lib/business-overview':modelUrl});
const {ComparisonBars}=await import(primitivesUrl);
const metric=(before,current,unit='dataset_currency')=>({status:'MEASURED',unit,previous:{value:before},current:{value:current},delta:String(Number(current)-Number(before))});

test('missing, blank and non-finite values cannot become zero or measured cards',()=>{
 for(const x of [null,undefined,'', '  ',true,Infinity,'NaN',{},[]])assert.equal(model.finiteReading(x),null);
 assert.equal(model.formatReading(0),'0');
 assert.equal(model.isMeasured(metric(null,'10')),false);
 assert.equal(model.isMeasured({...metric('1','2'),status:'UNAVAILABLE'}),false);
 assert.equal(model.changeText(metric('',10)),'Comparison unavailable');
});
test('changes preserve signed absolute units and percentage points, not invented percentages',()=>{
 assert.equal(model.changeText(metric(100,120)),'+20');
 assert.equal(model.changeText({...metric(12,10,'percent'),delta_unit:'percentage_points'}),'-2 pp');
 assert.equal(model.changeText({...metric(4,4.2,'score_1_to_5'),delta_unit:'score_points'}),'+0.2 pts');
 assert.equal(model.changeText(metric(0,0,'orders')),'0 orders');
});
test('returned data must match the requested historical month and valid periods',()=>{
 const valid={month:'2018-06',metrics:{},periods:{previous:['2018-05-01','2018-06-01'],current:['2018-06-01','2018-07-01']}};
 assert.equal(model.validDashboard(valid,'2018-06'),true);
 assert.equal(model.validDashboard(valid,'2026-11'),false);
 assert.equal(model.validDashboard({...valid,periods:{...valid.periods,current:['bad','worse']}},'2018-06'),false);
});
test('comparisons render two returned values on zero-based magnitude scales and retain negative signs',()=>{
 const html=renderToStaticMarkup(React.createElement(ComparisonBars,{name:'Profit',metric:metric(-100,50),previous:'May 2018',current:'June 2018'}));
 assert.match(html,/width:100%/);assert.match(html,/width:50%/);
 assert.match(html,/-100/);assert.match(html,/negative values indicate losses/);
 assert.doesNotMatch(html,/sparkline|polyline/);
 const empty=renderToStaticMarkup(React.createElement(ComparisonBars,{name:'Profit',metric:metric(null,50),previous:'May',current:'June'}));
 assert.match(empty,/Comparison unavailable/);assert.doesNotMatch(empty,/overview-bar-track/);
});
test('recent investigation status never promotes partial or unsupported evidence',()=>{
 const record=status=>({payload:{status,executable:true,causal_claim:false}});
 assert.equal(model.disposition(record('PARTIAL_GOVERNED_EVIDENCE')),'Partial evidence');
 assert.equal(model.disposition(record('NOT_YET_SUPPORTED')),'Not supported');
 assert.equal(model.disposition(record('ACTIONABLE_EVIDENCE_GAP')),'Evidence gap');
 assert.equal(model.disposition(record('MEASURED_WITH_LIMITATIONS')),'Measured · scope limits');
});
test('saved replay requires owned-session provenance and confirmed saved persistence',()=>{
 const record={payload:{context_provenance:{session_id:'session/a'},observability:{run_id:'run/b',persistence:'SAVED'}}};
 assert.equal(model.replayUrl(record),'/api/investigation-sessions/session%2Fa/runs/run%2Fb/replay');
 assert.equal(model.replayUrl({payload:{...record.payload,observability:{run_id:'run',persistence:'UNAVAILABLE'}}}),null);
 assert.equal(model.replayUrl({}),null);
});

const apiUrl=await compile('../lib/api-client.ts');
const periodsUrl=await compile('../lib/dashboard.ts');
const {BusinessLanding}=await import(await compile('../components/business-landing.tsx',{'../lib/business-overview':modelUrl,'../lib/api-client':apiUrl,'../lib/dashboard':periodsUrl,'./business-primitives':primitivesUrl}));
test('landing retains recent session questions and replay access without presenting them as new findings',()=>{
 const record={question:'Did costs change?',payload:{status:'ACTIONABLE_EVIDENCE_GAP',context_provenance:{session_id:'owned'},observability:{run_id:'saved',persistence:'SAVED'}}};
 const html=renderToStaticMarkup(React.createElement(BusinessLanding,{history:[{turn:2,canonical_result:record}],sessionReady:true,onInvestigate:()=>{},onOpen:()=>{}}));
 assert.match(html,/Did costs change/);assert.match(html,/Evidence gap/);
 assert.match(html,/\/api\/investigation-sessions\/owned\/runs\/saved\/replay/);
 assert.match(html,/historical, not revalidated/);assert.match(html,/Prepare investigation/);
 assert.doesNotMatch(html,/844,178|983,213|Caused by/);
});
