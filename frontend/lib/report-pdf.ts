import { plainLanguageLimitation, type JsonObject, type NormalizedInvestigation } from "./investigation";
import { buildReportPresentation, evidenceSummary } from "./report-presentation";

type PdfMode = "Business" | "Analyst";
type Page = { ops: string[]; y: number };
const PAGE_W = 595.28; const PAGE_H = 841.89; const MARGIN = 52; const CONTENT_W = PAGE_W - MARGIN * 2;
const clean = (value: unknown) => String(value ?? "").replace(/[→–—·]/g, (c) => ({ "→": "to", "–": "-", "—": "-", "·": "|" })[c] ?? c).replace(/[^\x20-\x7E]/g, "?");
function number(value: unknown): number | undefined { if (value === undefined || value === null || value === "") return undefined; const n = Number(value); return Number.isFinite(n) ? n : undefined; }
function fmt(value: unknown, fraction = 2) { const n = number(value); return n === undefined ? clean(value) || "Not provided" : new Intl.NumberFormat("en-US", { maximumFractionDigits: fraction }).format(n); }
function human(value: unknown) { return clean(value).replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function pdfEscape(s: string) { return clean(s).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)"); }
// Standard PDF Helvetica AFM widths (ASCII), in 1/1000 em; no font dependency.
const HELVETICA = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584];
const HELVETICA_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584];
function textWidth(value: string, size: number, bold = false): number {
  const widths = bold ? HELVETICA_BOLD : HELVETICA;
  return [...clean(value)].reduce((sum, char) => sum + (widths[char.charCodeAt(0) - 32] ?? 556), 0) * size / 1000;
}
function wrap(input: string, maxWidth: number, size = 9, bold = false) {
  const words = clean(input).trim().split(/\s+/).filter(Boolean); const lines: string[] = []; let line = "";
  for (const word of words) {
    if (textWidth((line + " " + word).trim(), size, bold) <= maxWidth) { line = (line + " " + word).trim(); continue; }
    if (line) { lines.push(line); line = ""; }
    for (const char of word) {
      if (line && textWidth(line + char, size, bold) > maxWidth) { lines.push(line); line = ""; }
      line += char;
    }
  }
  if (line) lines.push(line); return lines;
}
function periodText(value: unknown): string {
  if (Array.isArray(value)) return value.map((x) => clean(x)).filter(Boolean).join(" to ");
  if (value && typeof value === "object") return Object.entries(value as JsonObject).map(([k, v]) => `${human(k)}: ${periodText(v)}`).join("; ");
  return clean(value);
}
function statusLabel(value: string) { return ({ measured: "Measured descriptive evidence", evidence_gap: "Evidence gap", clarification: "Clarification required", failed: "Execution failed", unverified: "Unverified result" } as Record<string, string>)[value] ?? "Unverified result"; }
function unitLabel(unit?: string) { return ({ percentage_points: "percentage points", percent: "%", score_points: "score points", score_1_to_5: "out of 5", currency: "currency units", dataset_currency: "dataset currency units", orders: "orders" } as Record<string, string>)[unit ?? ""] ?? (unit ? human(unit) : ""); }
function measureValue(m: NormalizedInvestigation["measures"][number]) {
  const unit = unitLabel(m.unit);
  const deltaUnit = unitLabel(m.deltaUnit || m.unit);
  if (m.before !== undefined || m.after !== undefined) return `${fmt(m.before)} to ${fmt(m.after)}${unit ? ` ${unit}` : ""}${m.delta !== undefined ? `; change ${fmt(m.delta)}${deltaUnit ? ` ${deltaUnit}` : ""}` : ""}`;
  return `${fmt(m.value)}${unit ? ` ${unit}` : ""}`;
}
function measurePeriod(m: NormalizedInvestigation["measures"][number], report: NormalizedInvestigation) {
  return periodText(m.period) || (Object.keys(report.periods).length ? periodText(report.periods) : "");
}
function businessHeadline(report: NormalizedInvestigation) {
  if (report.status !== "measured") return report.status === "evidence_gap" ? "Available evidence cannot answer this question" : report.status === "clarification" ? "More detail is needed to investigate" : report.status === "failed" ? "The investigation could not be completed" : "The result is not verified";
  if (report.financialPremise.divergence_confirmed === false) return "The financial divergence premise was not confirmed";
  if (report.financialPremise.divergence_confirmed === true) return "Revenue increased while contribution profit declined";
  const m = report.measures[0];
  if (m?.before !== undefined) return `${human(m.id)} ${Number(m.delta) < 0 ? "decreased" : Number(m.delta) > 0 ? "increased" : "was unchanged"}`;
  return report.findings[0] ?? (report.domains.length ? `${report.domains.map(human).join(" and ")} performance was measured` : "Investigation completed with descriptive evidence");
}
function analystTitle(report: NormalizedInvestigation) {
  const raw = report.title.replaceAll("_", " ").trim();
  if (raw && !["investigation", "investigation planner", "three domain investigation"].includes(raw.toLowerCase())) return human(raw);
  if (report.domains.length) return `${report.domains.map(human).join(" and ")} Investigation`;
  const ids = report.measures.map((m) => human(m.id));
  if (ids.length === 1) return `${ids[0]} Investigation`;
  if (report.accountingHypotheses.length || Object.keys(report.financialPremise).length) return "Financial Performance Investigation";
  if (ids.length > 1) return `${ids.slice(0, 2).join(" and ")} Investigation`;
  return "Business Investigation Report";
}
function hasValue(value: unknown) { return value !== undefined && value !== null && value !== ""; }
function detailFields(value: unknown, depth = 0): string[] {
  if (depth > 2 || value === null || value === undefined) return [];
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return [clean(value)];
  if (Array.isArray(value)) return value.flatMap((x) => detailFields(x, depth + 1));
  if (typeof value === "object") return Object.entries(value as JsonObject).flatMap(([key, v]) => {
    if (!hasValue(v)) return [];
    if (typeof v === "object") return detailFields(v, depth + 1).map((entry) => `${human(key)}: ${entry}`);
    return [`${human(key)}: ${typeof v === "number" ? fmt(v) : clean(v)}`];
  });
  return [];
}
function makePdf(pages: Page[], title: string, reportingPeriod: string, report: NormalizedInvestigation): Blob {
  const objects: string[] = ["", "<< /Type /Catalog /Pages 2 0 R >>", ""];
  const add = (value: string) => { objects.push(value); return objects.length - 1; };
  const font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"); const bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");
  const pageIds: number[] = []; const total = pages.length;
  pages.forEach((page, index) => {
    page.ops.push(`q 0.89 0.88 0.85 RG ${MARGIN} 43 m ${PAGE_W - MARGIN} 43 l S Q`);
    const footer = wrap(`OpsLens  |  ${title}  |  ${reportingPeriod || "Period not specified"}`, CONTENT_W - 55, 7).slice(0, 2);
    footer.forEach((line, lineIndex) => page.ops.push(`BT /F1 7 Tf 0.42 0.42 0.39 rg ${MARGIN} ${32 - lineIndex * 10} Td (${pdfEscape(line)}) Tj ET`));
    page.ops.push(`BT /F1 7 Tf 0.42 0.42 0.39 rg ${PAGE_W - MARGIN - 42} 29 Td (${index + 1} / ${total}) Tj ET`);
    const stream = page.ops.join("\n"); const contentId = add(`<< /Length ${new TextEncoder().encode(stream).length} >>\nstream\n${stream}\nendstream`);
    pageIds.push(add(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_W} ${PAGE_H}] /Resources << /Font << /F1 ${font} 0 R /F2 ${bold} 0 R >> >> /Contents ${contentId} 0 R >>`));
  });
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageIds.length} >>`;
  // An exact UTF-8 attachment complements the readable appendix: no rounding,
  // character substitution, depth limit or schema projection touches this copy.
  const bytes = new TextEncoder().encode(JSON.stringify(report.canonicalRecord));
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("") + ">";
  const embedded = add(`<< /Type /EmbeddedFile /Subtype /application#2Fjson /Filter /ASCIIHexDecode /Length ${hex.length} /Params << /Size ${bytes.length} >> >>\nstream\n${hex}\nendstream`);
  const file = add(`<< /Type /Filespec /F (opslens-investigation.json) /UF (opslens-investigation.json) /Desc (Complete canonical investigation record) /EF << /F ${embedded} 0 R >> >>`);
  objects[1] = `<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles << /Names [(opslens-investigation.json) ${file} 0 R] >> >> >>`;
  const chunks = ["%PDF-1.4\n%OpsLens\n"]; const offsets = [0]; let byteLength = new TextEncoder().encode(chunks[0]).length;
  for (let id = 1; id < objects.length; id++) { offsets[id] = byteLength; const part = `${id} 0 obj\n${objects[id]}\nendobj\n`; chunks.push(part); byteLength += new TextEncoder().encode(part).length; }
  const xrefOffset = byteLength; let xref = `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objects.length; id++) xref += `${String(offsets[id]).padStart(10, "0")} 00000 n \n`;
  chunks.push(`${xref}trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`);
  return new Blob(chunks, { type: "application/pdf" });
}

export function createInvestigationPdf(report: NormalizedInvestigation, mode: PdfMode): Blob {
  const presentation = buildReportPresentation(report);
  const pages: Page[] = []; let page!: Page;
  const newPage = (continuation = false) => { page = { ops: [], y: PAGE_H - 66 }; pages.push(page); page.ops.push(`BT /F2 7 Tf 0.43 0.45 0.40 rg ${MARGIN} ${PAGE_H - 37} Td (${pdfEscape(continuation ? "OPSLENS  |  INVESTIGATION REPORT  |  CONTINUED" : `OPSLENS  |  ${mode.toUpperCase()} VIEW`)}) Tj ET`); };
  const ensure = (height: number, keepTogether = false) => { if (page.y - height < 62) newPage(true); if (keepTogether && page.y < PAGE_H - 66 && page.y - height < 62) newPage(true); };
  const drawLine = (line: string, size: number, boldText: boolean, indent: number, color: string) => {
    ensure(size * 1.55); page.ops.push(`BT /${boldText ? "F2" : "F1"} ${size} Tf ${color} rg ${MARGIN + indent} ${page.y} Td (${pdfEscape(line)}) Tj ET`); page.y -= size * 1.55;
  };
  const text = (value: string, size = 9.5, boldText = false, indent = 0, color = "0.17 0.17 0.16", keepTogether = false) => {
    const lines = wrap(value, CONTENT_W - indent, size, boldText);
    if (keepTogether) ensure(lines.length * size * 1.55 + 2, true);
    lines.forEach((line) => drawLine(line, size, boldText, indent, color));
  };
  const section = (title: string, subtitle?: string) => {
    ensure(subtitle ? 64 : 50, true); page.y -= 11;
    page.ops.push(`q 0.85 0.84 0.80 RG ${MARGIN} ${page.y + 7} m ${PAGE_W - MARGIN} ${page.y + 7} l S Q`);
    page.y -= 9; text(title, 11, true, 0, "0.20 0.21 0.19");
    if (subtitle) text(subtitle, 8, false, 0, "0.44 0.44 0.41"); page.y -= 3;
  };
  const bullet = (value: string, index?: number, keepTogether = true) => text(`${index === undefined ? "-" : `${index + 1}.`}  ${value}`, 9, false, 5, "0.22 0.22 0.20", keepTogether);
  const bulletBlock = (values: string[]) => {
    const totalHeight = values.reduce((sum, value) => sum + wrap(`-  ${value}`, CONTENT_W - 5, 9).length * 9 * 1.55, 0) + 5;
    ensure(totalHeight, true); values.forEach((value) => bullet(value));
  };
  let repeatedHeader: { cells: string[]; widths: number[] } | null = null;
  const tableRow = (cells: string[], widths: number[], header = false, keepTogether = true) => {
    const size = header ? 7 : 8; const linesByCell = cells.map((cell, i) => wrap(cell, widths[i] - 12, size, header)); const rowHeight = Math.max(1, ...linesByCell.map((v) => v.length)) * 13 + 11;
    const originalPage = page; ensure(rowHeight, keepTogether);
    if (originalPage !== page && !header && repeatedHeader) { const saved = repeatedHeader; repeatedHeader = null; tableRow(saved.cells, saved.widths, true, false); repeatedHeader = saved; ensure(rowHeight, keepTogether); }
    page.ops.push(`q ${header ? "0.93 0.92 0.89" : "0.99 0.99 0.98"} rg ${MARGIN} ${page.y - rowHeight + 4} ${CONTENT_W} ${rowHeight} re f Q`);
    let x = MARGIN + 6;
    cells.forEach((cell, i) => { const lines = linesByCell[i]; lines.forEach((line, lineIndex) => { const alignRight = !header && i > 0; const dx = alignRight ? Math.max(3, widths[i] - 12 - textWidth(line, size, header)) : 0; page.ops.push(`BT /${header ? "F2" : "F1"} ${size} Tf ${header ? "0.42 0.42 0.39" : "0.20 0.20 0.19"} rg ${x + dx} ${page.y - 9 - lineIndex * 13} Td (${pdfEscape(line)}) Tj ET`); }); x += widths[i]; });
    page.y -= rowHeight; page.ops.push(`q 0.86 0.85 0.82 RG ${MARGIN} ${page.y + 4} m ${PAGE_W - MARGIN} ${page.y + 4} l S Q`);
  };

  const declaredPeriod = Object.entries(report.periods).map(([k, v]) => `${human(k)}: ${periodText(v)}`).filter((v) => !v.endsWith(": ")).join("  |  ");
  const evidencePeriods = [...new Set(report.measures.map((m) => periodText(m.period)).filter(Boolean))];
  const reportingPeriod = declaredPeriod || (evidencePeriods.length ? evidencePeriods.join("  |  ") : "");
  const title = mode === "Business" ? businessHeadline(report) : analystTitle(report);
  newPage(); text(title, 22, true, 0, "0.12 0.12 0.11");
  text(`${statusLabel(report.status)}${report.domains.length ? `  |  ${report.domains.map(human).join("  |  ")}` : ""}`, 9, false, 0, "0.40 0.40 0.37");
  if (reportingPeriod) text(reportingPeriod, 8, false, 0, "0.40 0.40 0.37");
  text(`Generated ${new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date())}`, 7.5, false, 0, "0.52 0.52 0.49");

  section("Direct Answer and Verified Premise");
  bullet(presentation.answer, undefined, false);
  bullet(presentation.premise, undefined, false);

  const measured = report.measures.filter((m) => m.before !== undefined || m.after !== undefined || m.value !== undefined);
  if (measured.length || hasValue(report.financialPremise.revenue_delta) || hasValue(report.financialPremise.contribution_profit_delta)) {
    section("Key Metrics", "Observed values from the requested scope; comparisons are descriptive.");
    const widths = mode === "Analyst" ? [116, 200, 108, 67] : [150, 240, 101];
    const metricHeader = mode === "Analyst" ? ["Metric", "Observed values", "Period", "Unit"] : ["Measure", "Observed comparison", "Period"];
    tableRow(metricHeader, widths, true, false); repeatedHeader = { cells: metricHeader, widths };
    for (const m of measured) {
      const cells = mode === "Analyst" ? [human(m.id), measureValue(m), measurePeriod(m, report) || "", unitLabel(m.unit)] : [human(m.id), measureValue(m), measurePeriod(m, report) || ""];
      tableRow(cells, widths);
    }
    if (hasValue(report.financialPremise.revenue_delta) || hasValue(report.financialPremise.contribution_profit_delta)) {
      const widths = mode === "Analyst" ? [116, 200, 108, 67] : [150, 240, 101];
      if (hasValue(report.financialPremise.revenue_delta)) tableRow(mode === "Analyst" ? ["Revenue movement", fmt(report.financialPremise.revenue_delta), reportingPeriod, "currency units"] : ["Revenue movement", `${fmt(report.financialPremise.revenue_delta)} currency units`, reportingPeriod], widths);
      if (hasValue(report.financialPremise.contribution_profit_delta)) tableRow(mode === "Analyst" ? ["Contribution profit movement", fmt(report.financialPremise.contribution_profit_delta), reportingPeriod, "currency units"] : ["Contribution profit movement", `${fmt(report.financialPremise.contribution_profit_delta)} currency units`, reportingPeriod], widths);
    }
    repeatedHeader = null;
  }

  if (report.route === "delivery_review_comparison") {
    const evidence = report.canonicalRecord.payload.evidence as { cohorts: Record<string, Record<string, unknown>>; methodology: string };
    section("Late versus on-time order ratings");
    bullet(String(report.canonicalRecord.payload.reason), 0);
    const widths = [110, 80, 80, 110, CONTENT_W - 380];
    tableRow(["Cohort", "Orders", "Reviewed", "Mean rating", "Low ratings"], widths, true, false);
    for (const [name, raw] of Object.entries(evidence.cohorts)) {
      const row = raw as Record<string, unknown>;
      tableRow([name, String(row.orders), String(row.reviewed), row.average_score == null ? "Unavailable" : Number(row.average_score).toFixed(2), String(row.low)], widths);
    }
    bullet(String(evidence.methodology), 1);
  }
  if (report.route === "seller_concentration" && report.canonicalRecord.payload.seller_analysis) {
    const proof=report.canonicalRecord.payload.seller_analysis as {sellers:Record<string,unknown>[];buckets:Record<string,{orders:number;eligible:number;late:number}>;methodology:string};
    section("Seller concentration | single-seller orders");
    const widths=[210,70,70,CONTENT_W-350];
    tableRow(["Seller","Late","Eligible","Late rate %"],widths,true,false);
    for (const row of proof.sellers) tableRow([String(row.seller_id),String(row.late),String(row.eligible),row.late_rate_pct==null?'Unavailable':Number(row.late_rate_pct).toFixed(2)],widths);
    bullet(proof.methodology,0);
    for (const [name,bucket] of Object.entries(proof.buckets)) bullet(`${name.replaceAll('_',' ')}: ${bucket.orders} orders; ${bucket.eligible} eligible; ${bucket.late} late.`,0);
  }
  if(report.canonicalRecord.payload.refund_analysis){
    const proof=report.canonicalRecord.payload.refund_analysis as {sellers:{seller_id:string;refund_amount:string;orders:number;returned_orders:number;share_of_all_refunds_pct:string|null}[];methodology:string};
    section('Order-linked refund concentration');
    for(const seller of (mode==='Business'?proof.sellers.slice(0,10):proof.sellers))bullet(`${seller.seller_id}: refunds ${seller.refund_amount}; ${seller.returned_orders}/${seller.orders} orders with returns; share of all linked refunds ${seller.share_of_all_refunds_pct===null?'unavailable':seller.share_of_all_refunds_pct+'%'}.`,0);
    if(mode==='Business'&&proof.sellers.length>10)bullet('Top 10 sellers shown; all seller cohorts remain in the canonical evidence attachment.',0);
    bullet(proof.methodology,0);
  }
  if(report.canonicalRecord.payload.document_evidence){
    const docs=report.canonicalRecord.payload.document_evidence as {summary:string;sources:{source:{filename?:string;source_date?:string};disposition:string}[]};
    section('Document cross-check');bullet(docs.summary,0);
    for(const doc of docs.sources)bullet(`${doc.source.filename??'Unknown source'} | ${doc.source.source_date??'Date unknown'} | ${doc.disposition}`,0);
    bullet('Documents are context, not causal proof. Authoritative version history is unavailable. Full passages and conflicts are preserved in the evidence appendix and canonical attachment.',0);
  }
  const findings = presentation.findings;
  if (findings.length) { section("Key Findings"); findings.forEach((finding, i) => bullet(finding, i)); }

  if (report.accountingHypotheses.length) {
    section("Accounting Bridge | Ranked Components", "Returned ranking, not the complete bridge. Signed contribution to profit; negative values reduced profit.");
    const widths = [34, 250, CONTENT_W - 34 - 250];
    const accountingHeader = ["Rank", "Cost component", "Profit impact"];
    tableRow(accountingHeader, widths, true, false); repeatedHeader = { cells: accountingHeader, widths };
    presentation.accounting.forEach((row, i) => tableRow([String(i + 1).padStart(2, "0"), row.label, fmt(row.impact)], widths));
    repeatedHeader = null;
  }
  if (report.accountingBridge.length) {
    section("Complete Accounting Bridge", "Original accounting identity; the residual is not a causal explanation.");
    report.accountingBridge.forEach((row) => bullet(`${human(row.component)}: change ${clean(row.delta)}; contribution to profit change ${clean(row.contribution_to_profit_delta)}${row.limitation ? `; ${clean(row.limitation)}` : ""}`));
  }
  if (report.perOrderCostEvidence.validated) {
    section("Per-order Cost Evidence", report.perOrderCostEvidence.populationBasis);
    text(`Before orders: ${report.perOrderCostEvidence.beforeOrders}; after orders: ${report.perOrderCostEvidence.afterOrders}`);
    report.perOrderCostEvidence.components.forEach((row) => bullet(`${human(row.component)}: ${clean(row.beforePerOrder)} to ${clean(row.afterPerOrder)}; change ${clean(row.changePerOrder)}`));
    report.perOrderCostEvidence.limitations.forEach((line) => bullet(line));
  }
  if (report.graphRows.length) {
    section("Grouped Measurements", "Returned dimensions and metric values, without population inference.");
    report.graphRows.forEach((row, i) => bullet(`Row ${i + 1}: ${Object.entries(row).map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join("; ")}`, undefined, false));
  }
  if (report.measures.some((m) => m.before !== undefined && m.after !== undefined)) {
    section("Measured Comparisons", "Bars use a separate scale per measure and show the two observed period values.");
    for (const m of report.measures.filter((x) => number(x.before) !== undefined && number(x.after) !== undefined)) {
      ensure(38, true); const a = number(m.before)!; const b = number(m.after)!; const max = Math.max(Math.abs(a), Math.abs(b), 0.0001); const y = page.y - 3; const barW = CONTENT_W - 105;
      text(`${human(m.id)}   ${measureValue(m)}`, 8, true, 0, "0.25 0.25 0.23");
      page.ops.push(`q 0.90 0.89 0.86 rg ${MARGIN} ${page.y - 2} ${barW} 5 re f 0.43 0.47 0.40 rg ${MARGIN} ${page.y - 2} ${barW * Math.abs(a) / max} 5 re f 0.90 0.89 0.86 rg ${MARGIN} ${page.y - 11} ${barW} 5 re f 0.25 0.26 0.24 rg ${MARGIN} ${page.y - 11} ${barW * Math.abs(b) / max} 5 re f Q`);
      page.ops.push(`BT /F1 7 Tf 0.38 0.38 0.35 rg ${MARGIN + barW + 9} ${y} Td (Before / After) Tj ET`); page.y -= 20;
    }
  }
  if (report.productContext.category || hasValue(report.productContext.category_item_gmv)) {
    section("Product Scope", "Governed item-level context; not inventory or audited financial revenue.");
    if (report.productContext.category) bullet(`Category: ${human(report.productContext.category)}`);
    if (hasValue(report.productContext.category_item_gmv)) bullet(`Category item GMV: ${fmt(report.productContext.category_item_gmv)}; total item GMV: ${fmt(report.productContext.total_item_gmv)}`);
  }

  if (report.status !== "measured" && report.evidenceRequirements.length) { section("Evidence Needed"); report.evidenceRequirements.forEach((x) => bullet(x)); }
  if (report.cohortEvidence.exact_order_id_sets_verified === true || Object.keys(report.cohortEvidence).length) {
    section("Evidence & Methodology | Cohort Audit");
    if (hasValue(report.cohortEvidence.status)) bullet(`Audit status: ${human(report.cohortEvidence.status)}`);
    if (hasValue(report.cohortEvidence.limitation)) bullet(`Scope: ${clean(report.cohortEvidence.limitation)}`);
    const months = Array.isArray(report.cohortEvidence.months) ? report.cohortEvidence.months : [];
    months.forEach((v) => { const x = v as JsonObject; bullet(`${clean(x.month)}: ${fmt(x.orders)} audited orders`); });
    if (report.cohortEvidence.exact_order_id_sets_verified === true) bullet("Exact operational order-ID sets reconciled. This does not certify finance population equality.");
  }
  if (mode === "Analyst") {
    const evidenceRows = report.measures.filter((m) => m.source || m.policy || m.timeBasis || Object.keys(m.population ?? {}).length || m.definition);
    if (evidenceRows.length || report.sourceEvidence.length) {
      section("Evidence & Methodology | Provenance", "Only metadata returned by the governed result is shown.");
      evidenceRows.forEach((m) => {
        const lines = [m.definition && `Definition: ${m.definition}`, m.source && `Source: ${m.source}`, m.timeBasis && `Time basis: ${human(m.timeBasis)}`, Object.keys(m.population ?? {}).length > 0 && `Eligible population: ${detailFields(m.population).join("; ")}`, m.policy && `Eligibility rule: ${m.policy}`, ...m.limitations.map((x) => `Limitation: ${x}`)].filter((x): x is string => Boolean(x));
        const lineHeight = 9 * 1.55; const headingHeight = lineHeight + 4;
        const bodyHeight = lines.reduce((sum, value) => sum + wrap(`-  ${value}`, CONTENT_W - 5, 9).length * lineHeight, 0);
        ensure(headingHeight + bodyHeight + 5, true);
        text(human(m.id), 9, true, 0, "0.20 0.20 0.18", true);
        bulletBlock(lines);
      });
      const representedMetrics = new Set(evidenceRows.map((m) => m.id));
      report.sourceEvidence.filter((e) => !representedMetrics.has(clean(e.metric_id))).forEach((e) => bullet(`${human(e.metric_id)}${e.source ? ` | ${clean(e.source)}` : ""}${e.unit ? ` | ${human(e.unit)}` : ""}${hasValue(e.value) ? ` | ${fmt(e.value)}` : ""}${e.period ? ` | ${periodText(e.period)}` : ""}${Object.keys((e.population as JsonObject) ?? {}).length ? ` | eligible population ${detailFields(e.population).join("; ")}` : ""}`));
    }
  }
  if (report.accountingHypotheses.length && mode === "Analyst") {
    const sourced = report.accountingHypotheses.filter((h) => h.source || h.causal_claim === false);
    if (sourced.length) { section("Accounting Evidence"); sourced.forEach((h) => bullet(`${clean(h.label ?? human(h.hypothesis_id))}${h.source ? ` | ${clean(h.source)}` : ""}${h.causal_claim === false ? " | non-causal contribution" : ""}`)); }
  }
  if (presentation.validations.length) {
    section("Recommended Next Validations", "Evidence-grounded proposals only; not approved actions or proven remedies.");
    presentation.validations.forEach((v, i) => bullet(v, i));
  }
  if (Object.keys(report.untestedHypotheses).length && mode === "Analyst") {
    section("Hypotheses Not Tested");
    Object.entries(report.untestedHypotheses).forEach(([key, value]) => bullet(`${human(key)}: ${clean(value)}`));
  }
  const renderedLimitations = presentation.limitations.map((x) => mode === "Business" ? plainLanguageLimitation(x) : x);
  const limitations = [...new Set(renderedLimitations)];
  if (limitations.length || report.causalClaim !== false || report.status !== "measured") {
    section("What Remains Unverified");
    if (report.causalClaim === false) bullet("Observed changes are descriptive and do not establish what caused them.");
    else bullet(report.status === "evidence_gap" ? "Required evidence was unavailable; this is not a completed measurement." : "No verified causal conclusion is established by this result.");
    limitations.forEach((x) => bullet(x));
    if (report.evidenceRequirements.length && report.status === "measured") report.evidenceRequirements.forEach((x) => bullet(`Unresolved evidence: ${x}`));
  }
  {
    section("Evidence & Methodology", "Expandable in the web report; exact returned metadata is consolidated here.");
    const accountingDetails = evidenceSummary(presentation.accountingGroup);
    accountingDetails.forEach((value) => bullet(value));
    if (mode === "Analyst") {
      report.measures.forEach((m) => {
        const detail = [m.definition && `Definition: ${m.definition}`, m.source && `Source: ${m.source}`, m.timeBasis && `Time basis: ${human(m.timeBasis)}`, Object.keys(m.population ?? {}).length > 0 && `Eligible population: ${detailFields(m.population).join("; ")}`, m.policy && `Eligibility rule: ${m.policy}`].filter((v): v is string => typeof v === "string" && v.length > 0);
        if (detail.length) { text(human(m.id), 9, true); detail.forEach((v) => bullet(v)); }
      });
      if (Object.keys(report.cohortEvidence).length) {
        if (hasValue(report.cohortEvidence.status)) bullet(`Cohort audit status: ${human(String(report.cohortEvidence.status))}`);
        if (hasValue(report.cohortEvidence.limitation)) bullet(`Cohort scope: ${clean(report.cohortEvidence.limitation)}`);
        const months = Array.isArray(report.cohortEvidence.months) ? report.cohortEvidence.months : [];
        months.forEach((v) => { const row = v as JsonObject; bullet(`${clean(row.month)}: ${fmt(row.orders)} audited orders`); });
      }
      report.toolTrace.forEach((trace, i) => { const fields = detailFields(trace); if (fields.length) bullet(`Governed trace ${i + 1}: ${fields.join("; ")}`); });
    }
    if (!accountingDetails.length && !report.cohortEvidence && !report.measures.some((m) => m.source || m.policy || m.timeBasis || Object.keys(m.population ?? {}).length || m.definition) && report.toolTrace.length === 0) bullet("No additional provenance or methodology metadata was returned.");
  }
  if (mode === "Analyst" && report.toolTrace.length) {
    section("Technical Appendix | Governed Tool Trace");
    report.toolTrace.forEach((trace, i) => {
      const details = detailFields(trace).join("; "); if (details) bullet(`Step ${i + 1}: ${details}`);
    });
  }
  if (report.status === "measured" && report.nextValidations.length === 0 && report.evidenceRequirements.length === 0) {
    section("Review Note"); bullet("No additional validation steps were returned for this investigation.");
  }
  section("Complete Evidence Appendix", "Exact values follow by JSON Pointer path. Stage limitations retain their original scope; summaries above are projections.");
  text("The complete UTF-8 canonical record is also embedded as opslens-investigation.json. Non-ASCII characters below use reversible JSON Unicode escapes. Retention does not certify evidence or grant query permissions.", 8);
  const asciiJson = (value: string) => value.replace(/[^\x20-\x7E]/g, (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
  report.evidenceEntries.forEach((entry) => {
    ensure(wrap(asciiJson(entry.path), CONTENT_W, 7, true).length * 7 * 1.55 + 8 * 1.55 + 3, true);
    text(asciiJson(entry.path), 7, true, 0, "0.17 0.17 0.16", true);
    text(asciiJson(entry.value), 8, false, 8);
  });
  return makePdf(pages, title, reportingPeriod, report);
}


