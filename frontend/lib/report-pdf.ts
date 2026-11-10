import { plainLanguageLimitation, type JsonObject, type NormalizedInvestigation } from "./investigation";
import { buildReportPresentation } from "./report-presentation";

type PdfMode = "Business" | "Analyst";
type Page = { ops: string[]; y: number };
const PAGE_W = 595.28; const PAGE_H = 841.89; const MARGIN = 55; const CONTENT_W = PAGE_W - MARGIN * 2;
const clean = (value: unknown) => String(value ?? "").replace(/[→–—·]/g, (c) => ({ "→": "to", "–": "-", "—": "-", "·": "|" })[c] ?? c).replace(/[^\x20-\x7E]/g, "?");
function number(value: unknown): number | undefined { if (value === undefined || value === null || value === "") return undefined; const n = Number(value); return Number.isFinite(n) ? n : undefined; }
function fmt(value: unknown, fraction = 2) { const n = number(value); return n === undefined ? clean(value) || "Not provided" : new Intl.NumberFormat("en-US", { maximumFractionDigits: fraction }).format(n); }
function human(value: unknown) { return clean(value).replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function pdfEscape(s: string) { return clean(s).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)"); }
// Standard PDF Times-Roman font widths (ASCII), in 1/1000 em. Times-style serif substitutes for Times New Roman without bundling proprietary fonts.
const HELVETICA = [250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 278, 278, 564, 564, 564, 444, 921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722, 556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500, 500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541];
const HELVETICA_BOLD = [250, 333, 555, 500, 500, 1000, 833, 278, 333, 333, 500, 570, 250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 333, 333, 570, 570, 570, 500, 930, 722, 667, 722, 722, 667, 611, 778, 778, 389, 500, 778, 667, 944, 722, 778, 611, 778, 722, 556, 667, 722, 722, 1000, 722, 722, 667, 333, 278, 333, 581, 500, 333, 500, 556, 444, 556, 444, 333, 500, 556, 278, 333, 556, 278, 833, 556, 500, 556, 556, 444, 389, 333, 556, 500, 722, 500, 500, 444, 394, 220, 394, 520];
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
  const font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>"); const bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>");
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

export function createInvestigationPdf(report: NormalizedInvestigation, _legacyView?: PdfMode): Blob {
  const mode: PdfMode = _legacyView === "Analyst" ? "Analyst" : "Business";
  const presentation = buildReportPresentation(report);
  const pages: Page[] = []; let page!: Page;
  const newPage = (continuation = false) => { page = { ops: [], y: PAGE_H - 66 }; pages.push(page); page.ops.push(`BT /F2 9 Tf 0.15 0.15 0.15 rg ${MARGIN} ${PAGE_H - 37} Td (${pdfEscape(continuation ? "OPSLENS REPORT  |  CONTINUED" : "OPSLENS REPORT")}) Tj ET`); };
  const ensure = (height: number, keepTogether = false) => { if (page.y - height < 62) newPage(true); if (keepTogether && page.y < PAGE_H - 66 && page.y - height < 62) newPage(true); };
  // PDF Times-Roman glyphs occupy approximately 1.33 em vertically.
  // Word-style 1.15 line spacing is measured against the natural font line box,
  // not only the nominal font size. The previous size*1.15 advance caused
  // adjacent Times-Roman lines to overlap in exported PDFs.
  const NATURAL_LINE_BOX = 1.34;
  const REQUESTED_LINE_SPACING = 1.15;
  const LINE_ADVANCE = NATURAL_LINE_BOX * REQUESTED_LINE_SPACING;
  // Justify wrapped body lines only; leave paragraph endings and headings aligned left.
  const drawLine = (line: string, size: number, boldText: boolean, indent: number, color: string, justify = false) => {
    ensure(size * LINE_ADVANCE + 2);
    const spaces = (line.match(/ /g) ?? []).length;
    const spare = CONTENT_W - indent - textWidth(line, size, boldText);
    const wordSpacing = justify && spaces > 0 && spare > 0 && spare < CONTENT_W * 0.30 ? spare / spaces : 0;
    page.ops.push(`BT /${boldText ? "F2" : "F1"} ${size} Tf ${color} rg ${wordSpacing.toFixed(3)} Tw ${MARGIN + indent} ${page.y} Td (${pdfEscape(line)}) Tj 0 Tw ET`);
    page.y -= size * LINE_ADVANCE;
  };
  const text = (value: string, size = 10.5, boldText = false, indent = 0, color = "0.13 0.13 0.13", keepTogether = false) => {
    const lines = wrap(value, CONTENT_W - indent, size, boldText);
    if (!lines.length) return;
    if (keepTogether) ensure(lines.length * size * LINE_ADVANCE + 4, true);
    lines.forEach((line, i) => drawLine(line, size, boldText, indent, color, !boldText && i < lines.length - 1));
    page.y -= 5;
  };
  const section = (title: string, subtitle?: string) => {
    ensure(subtitle ? 105 : 77, true);
    page.y -= 13;
    text(title, 12.5, true, 0, "0.12 0.12 0.12");
    if (subtitle) {
      const size = 9;
      const lines = wrap(subtitle, CONTENT_W, size, false);
      for (const line of lines) {
        const baseline = page.y;
        drawLine(line, size, false, 0, "0.25 0.25 0.25");
        const length = Math.min(textWidth(line, size), CONTENT_W);
        page.ops.push(`q 0.40 0.40 0.40 RG 0.4 w ${MARGIN} ${baseline - 2} m ${MARGIN + length} ${baseline - 2} l S Q`);
      }
      page.y -= 6;
    }
  };
  const bullet = (value: string, index?: number, keepTogether = true) => text(`${index === undefined ? "-" : `${index + 1}.`}  ${value}`, 9.5, false, 8, "0.15 0.15 0.15", keepTogether);
  const bulletBlock = (values: string[]) => {
    const totalHeight = values.reduce((sum, value) => sum + wrap(`-  ${value}`, CONTENT_W - 5, 9).length * 9 * LINE_ADVANCE, 0) + 5;
    ensure(totalHeight, true); values.forEach((value) => bullet(value));
  };
  let repeatedHeader: { cells: string[]; widths: number[] } | null = null;
  const tableRow = (cells: string[], widths: number[], header = false, keepTogether = true) => {
    const size = header ? 7 : 8; const linesByCell = cells.map((cell, i) => wrap(cell, widths[i] - 12, size, header)); const rowHeight = Math.max(1, ...linesByCell.map((v) => v.length)) * 13 + 11;
    const originalPage = page; ensure(rowHeight, keepTogether);
    if (originalPage !== page && !header && repeatedHeader) { const saved = repeatedHeader; repeatedHeader = null; tableRow(saved.cells, saved.widths, true, false); repeatedHeader = saved; ensure(rowHeight, keepTogether); }
    page.ops.push(`q ${header ? "0.93 0.92 0.89" : "0.99 0.99 0.98"} rg ${MARGIN} ${page.y - rowHeight + 4} ${CONTENT_W} ${rowHeight} re f Q`);
    let x = MARGIN + 6;
    cells.forEach((cell, i) => { const lines = linesByCell[i]; lines.forEach((line, lineIndex) => { const alignRight = !header && i > 0 && /^-?[\d,.]+%?$/.test(cell.trim()); const dx = alignRight ? Math.max(3, widths[i] - 12 - textWidth(line, size, header)) : 0; page.ops.push(`BT /${header ? "F2" : "F1"} ${size} Tf ${header ? "0.42 0.42 0.39" : "0.20 0.20 0.19"} rg ${x + dx} ${page.y - 9 - lineIndex * 13} Td (${pdfEscape(line)}) Tj ET`); }); x += widths[i]; });
    page.y -= rowHeight; page.ops.push(`q 0.86 0.85 0.82 RG ${MARGIN} ${page.y + 4} m ${PAGE_W - MARGIN} ${page.y + 4} l S Q`);
  };

  const declaredPeriod = Object.entries(report.periods).map(([k, v]) => `${human(k)}: ${periodText(v)}`).filter((v) => !v.endsWith(": ")).join("  |  ");
  const evidencePeriods = [...new Set(report.measures.map((m) => periodText(m.period)).filter(Boolean))];
  const reportingPeriod = declaredPeriod || (evidencePeriods.length ? evidencePeriods.join("  |  ") : "");
  const title = businessHeadline(report);
  newPage(); text(title, 19, true, 0, "0.10 0.10 0.10");
  text(`${statusLabel(report.status)}${report.domains.length ? `  |  ${report.domains.map(human).join("  |  ")}` : ""}`, 9, false, 0, "0.40 0.40 0.37");
  if (reportingPeriod) text(reportingPeriod, 8, false, 0, "0.40 0.40 0.37");
  text(`Generated ${new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date())}`, 7.5, false, 0, "0.52 0.52 0.49");

  section("Direct answer");
  const singleMetric = report.status === "measured" && report.measures.length === 1 && report.measures[0].before === undefined && report.measures[0].after === undefined ? report.measures[0] : null;
  if (singleMetric) {
    const metricName = report.productContext.category && singleMetric.id === "item_gmv" ? `${human(String(report.productContext.category))} category item GMV` : human(singleMetric.id);
    text(`${metricName}: ${measureValue(singleMetric)}.`, 11, true);
    if (periodText(singleMetric.period)) text(`Period: ${periodText(singleMetric.period)}.`, 9.5);
  } else {
    text(presentation.answer, 10.5);
  }
  if (presentation.premise && !/^(measurements are available|the requested metrics were measured)/i.test(presentation.premise)) text(presentation.premise, 9.5);


  // Finance premise deltas are measured values even when no metric rows were returned.
  const financeDeltas = report.status === "measured" ? presentation.metrics.filter((m) =>
    ["Revenue change", "Contribution profit change"].includes(m.label) && number(m.delta) !== undefined) : [];
  if (financeDeltas.length) {
    section("Finance changes", "Signed changes in dataset-reported currency units; not causal attribution.");
    financeDeltas.forEach((m) => bullet(`${m.label}: ${fmt(m.delta)} currency units.`));
  }
  const measured = report.measures.filter((m) => m.before !== undefined || m.after !== undefined || m.value !== undefined);
  if (measured.length) {
    section("Measured results", "Values are descriptive and follow the documented reporting scope.");
    const comparable = measured.some((m) => m.before !== undefined || m.after !== undefined);
    if (comparable) {
      const widths = [181, 103, 103, CONTENT_W - 387];
      tableRow(["Measure", "Earlier", "Later", "Change"], widths, true, false);
      repeatedHeader = { cells: ["Measure", "Earlier", "Later", "Change"], widths };
      for (const m of measured) {
        tableRow([`${human(m.id)}${m.unit ? ` (${unitLabel(m.unit)})` : ""}`, m.before !== undefined ? fmt(m.before) : "-", m.after !== undefined ? fmt(m.after) : fmt(m.value), m.delta !== undefined ? `${fmt(m.delta)} ${unitLabel(m.deltaUnit || m.unit)}`.trim() : "-"], widths);
      }
    } else {
      const widths = [275, CONTENT_W - 275];
      tableRow(["Measure", "Measured value"], widths, true, false);
      repeatedHeader = { cells: ["Measure", "Measured value"], widths };
      for (const m of measured) tableRow([human(m.id), measureValue(m)], widths);
    }
    repeatedHeader = null;
    page.y -= 7; // Separate the table border from the following report note.
    if (measured.some((m) => m.unit === "money" || m.unit === "currency" || m.unit === "dataset_currency")) {
      text("Monetary values are in dataset-reported units unless a currency is explicitly established by the source.", 9);
    }
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
    bullet('Documents are context, not causal proof. Authoritative version history is unavailable. Full passages and conflicts are preserved in the embedded canonical JSON attachment.',0);
  }
  const findings = presentation.findings;
  if (findings.length && !singleMetric) { section("Key findings"); findings.slice(0, 3).forEach((finding, i) => bullet(finding, i)); }

  if (report.accountingHypotheses.length) {
    section("Accounting Bridge | Ranked Components", "Returned ranking, not the complete bridge. Signed contribution to profit; negative values reduced profit.");
    const widths = [34, 250, CONTENT_W - 34 - 250];
    const accountingHeader = ["Rank", "Cost component", "Profit impact"];
    tableRow(accountingHeader, widths, true, false); repeatedHeader = { cells: accountingHeader, widths };
    presentation.accounting.forEach((row, i) => tableRow([String(i + 1).padStart(2, "0"), row.label, fmt(row.impact)], widths));
    repeatedHeader = null;
  }
  if (report.accountingBridge.length) {
    section("Accounting identity", "The residual is not a verified operational cause.");
    report.accountingBridge.forEach((row) => bullet(`${human(row.component)}: change ${fmt(row.delta)}; contribution to profit change ${fmt(row.contribution_to_profit_delta)}${row.limitation ? `; ${clean(row.limitation)}` : ""}`));
  }
  if (report.perOrderCostEvidence.validated) {
    section("Per-order Cost Evidence", report.perOrderCostEvidence.populationBasis);
    text(`Before orders: ${report.perOrderCostEvidence.beforeOrders}; after orders: ${report.perOrderCostEvidence.afterOrders}`);
    report.perOrderCostEvidence.components.filter((row) => Math.abs(Number(row.changePerOrder)) > 0.005).slice(0, 6).forEach((row) => bullet(`${human(row.component)}: ${fmt(row.beforePerOrder)} to ${fmt(row.afterPerOrder)}; change ${fmt(row.changePerOrder)}`));
    report.perOrderCostEvidence.limitations.forEach((line) => bullet(line));
  }
  if (report.graphRows.length) {
    section("Grouped Measurements", "Returned dimensions and metric values, without population inference.");
    report.graphRows.slice(0, 8).forEach((row, i) => bullet(`Row ${i + 1}: ${Object.entries(row).map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join("; ")}`, undefined, false));
  }
  if (false && report.measures.some((m) => m.before !== undefined && m.after !== undefined)) {
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
  if (presentation.validations.length) {
    section("Recommended Next Validations", "Evidence-grounded proposals only; not approved actions or proven remedies.");
    presentation.validations.slice(0, 5).forEach((v, i) => bullet(v, i));
  }
  if (Object.keys(report.untestedHypotheses).length && mode === "Analyst") {
    section("Hypotheses Not Tested");
    Object.entries(report.untestedHypotheses).forEach(([key, value]) => bullet(`${human(key)}: ${clean(value)}`));
  }
  const renderedLimitations = presentation.limitations.map((x) => mode === "Business" ? plainLanguageLimitation(x) : x);
  const limitations = [...new Set(renderedLimitations)].slice(0, 8).map(String);
  if (limitations.length || report.causalClaim !== false || report.status !== "measured") {
    section("What Remains Unverified");
    const openingLimitation = report.causalClaim === false
      ? "Observed changes are descriptive and do not establish what caused them."
      : report.status === "evidence_gap"
      ? "Required evidence was unavailable; this is not a completed measurement."
      : "No verified causal conclusion is established by this result.";
    bullet(openingLimitation);
    limitations.filter((x) => x.trim().toLowerCase() !== openingLimitation.toLowerCase()).forEach((x) => bullet(x));
    if (report.evidenceRequirements.length && report.status === "measured") report.evidenceRequirements.forEach((x) => bullet(`Unresolved evidence: ${x}`));
  }
  section("Sources and methodology", "Original source details and complete audit data remain in the embedded JSON record.");
  const sources = [...new Set([...report.measures.map((m) => m.source), ...presentation.accountingGroup.sources].filter((v): v is string => Boolean(v)))];
  for (const source of sources) bullet(`Source: ${source}`);
  const scopeItems = report.measures.flatMap((m) => Object.entries(m.population ?? {}).map(([k, v]) => `${human(k)}: ${fmt(v)}`));
  for (const item of [...new Set(scopeItems)].slice(0, 6)) bullet(String(item));
  if (report.causalClaim === false) text("This document reports measured descriptive evidence, not causal attribution.", 9.5);
  text("The full canonical investigation record is embedded as opslens-investigation.json, preserving unrounded figures, source metadata, and execution traces without printing them as report pages.", 9.5);
  return makePdf(pages, title, reportingPeriod, report);
}


