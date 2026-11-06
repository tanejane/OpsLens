// Manual QA artifact generation; no server, database or Gemini access.
import { readFile, mkdir, writeFile } from "node:fs/promises";
import ts from "typescript";
const urls = {};
for (const name of ["investigation", "report-presentation", "report-pdf"]) {
  const source = await readFile(new URL(`../lib/${name}.ts`, import.meta.url), "utf8");
  let compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const [dependency, url] of Object.entries(urls)) compiled = compiled.replace(`from "./${dependency}"`, `from "${url}"`);
  urls[name] = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
}
const { normalizeInvestigation } = await import(urls.investigation);
const { createInvestigationPdf } = await import(urls["report-pdf"]);
const fixtures = JSON.parse(await readFile(new URL("./fixtures/p0_2_variants.json", import.meta.url), "utf8"));
const report = normalizeInvestigation(fixtures.cases.cross_domain.api_response);
const directory = new URL("../../tmp/pdfs/", import.meta.url);
await mkdir(directory, { recursive: true });
for (const mode of ["Business", "Analyst"]) {
  const path = new URL(`p0_2-${mode.toLowerCase()}.pdf`, directory);
  await writeFile(path, Buffer.from(await createInvestigationPdf(report, mode).arrayBuffer()));
  console.log(path.pathname);
}
