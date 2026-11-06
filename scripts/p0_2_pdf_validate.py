"""Independent PDF parser/layout checks after frontend/tests/export-pdf-qa.mjs.

Run with the bundled document Python runtime (pypdf and pdfplumber).
"""
import json
from pathlib import Path
from pypdf import PdfReader
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
expected = json.loads((ROOT / 'frontend/tests/fixtures/p0_2_variants.json').read_text(
    encoding='utf-8'))['cases']['cross_domain']['api_response']['canonical_result']
results = []
for mode in ('business', 'analyst'):
    path = ROOT / f'tmp/pdfs/p0_2-{mode}.pdf'
    reader = PdfReader(path)
    exact = json.loads(reader.attachments['opslens-investigation.json'][0]) == expected
    overflow = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages):
            outside = [char for char in page.chars if char['x0'] < 50 or char['x1'] > page.width - 49
                or char['top'] < 15 or char['bottom'] > page.height - 20]
            if outside:
                overflow.append({'page': index + 1, 'characters': len(outside)})
    results.append({'mode': mode, 'pages': len(reader.pages), 'attachment_exact': exact, 'overflow': overflow})
(ROOT / 'reports/p0_2_pdf_validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))
assert all(result['attachment_exact'] and not result['overflow'] for result in results)
