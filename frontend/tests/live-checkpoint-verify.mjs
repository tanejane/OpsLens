// Component/PDF tests over captured REAL MCP results, not browser visual QA.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
const require=createRequire(import.meta.url), urls={};
async function compile(path,replacements={}){
 let code=ts.transpileModule(await readFile(new URL(path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 replacements['react/jsx-runtime']=pathToFileURL(require.resolve('react/jsx-runtime')).href;
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from "${url}"`);
 return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
for(const name of ['investigation','report-presentation','report-pdf']){
 urls[name]=await compile(`../lib/${name}.ts`,Object.fromEntries(Object.entries(urls).map(([n,u])=>['./'+n,u])));
}
const {normalizeInvestigation}=await import(urls.investigation);
const {createInvestigationPdf}=await import(urls['report-pdf']);
const evidence=await compile('../components/investigation-evidence.tsx');
const {DeliveryReviewComparison}=await import(await compile('../components/delivery-review-comparison.tsx',{'./investigation-evidence':evidence}));
const {SellerConcentration}=await import(await compile('../components/seller-concentration.tsx',{'./investigation-evidence':evidence}));
const httpMode=process.argv.includes('--http');
const live=JSON.parse(await readFile(new URL(httpMode?'../../reports/live_http_journey.json':'../../reports/live_database_checkpoint.json',import.meta.url),'utf8'));
const checks=[];
for(const entry of live.results){
 if(httpMode){assert.equal(entry.http_status,200);assert.equal(entry.canonical_result.payload.executable,true);}
 else assert.equal(entry.status,'LIVE_VALIDATED');
 const record=entry.canonical_result, report=normalizeInvestigation(record);
 assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst']){
  let html;
  if(report.route==='seller_concentration')html=renderToStaticMarkup(React.createElement(SellerConcentration,{report,mode}));
  if(report.route==='delivery_review_comparison')html=renderToStaticMarkup(React.createElement(DeliveryReviewComparison,{report,mode}));
  if(html){if(report.route!=='seller_concentration'||record.payload.seller_analysis)assert.match(html,/role="img"/);assert.match(html,/semantic/);}
  const blob=createInvestigationPdf(report,mode);
  const pdf=await blob.text();assert.match(pdf,/opslens.investigation.v1/);
  checks.push({case:entry.name??entry.question,mode,canonical_equal:true,component_chart:!!html&&html.includes('role="img"'),pdf_bytes:blob.size});
 }
}
await writeFile(new URL('../../reports/live_frontend_verification.json',import.meta.url),JSON.stringify({scope:'Actual live MCP captures through production normalizer/components/PDF; not interactive browser verification',checks},null,2));
console.log(`${checks.length}/${checks.length} live-record presentation checks passed`);
