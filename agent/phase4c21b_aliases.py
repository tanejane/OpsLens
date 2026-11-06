"""Human-reviewed, catalog-backed aliases; no guessed translations or SQL."""
import csv, re
from pathlib import Path
from agent.phase4c21_category_catalog import CategoryResolver, CatalogRejected, VERIFIED_ALIASES

HEADERS=('canonical_category','english_alias','approved','reviewer','review_note')
SAFE_ALIAS=re.compile(r"^[a-z][a-z0-9 &/()'_-]{1,79}$")

def normalize(s):
    if not isinstance(s,str):raise CatalogRejected('INVALID_ALIAS')
    return re.sub(r'\s+',' ',s.strip().lower())

def template(catalog,output):
    resolver=CategoryResolver(catalog)
    path=Path(output)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader()
        for canonical in sorted(resolver.active):
            w.writerow(dict(canonical_category=canonical,english_alias='',approved='no',reviewer='',review_note='Human review required; do not guess translation'))
    return {'status':'ALIAS_REVIEW_TEMPLATE_CREATED','canonical_categories':len(resolver.active),'path':str(path),'approved_new_aliases':0}

def compile_aliases(catalog,path):
    resolver=CategoryResolver(catalog)
    lookup={normalize(x):y for x,y in VERIFIED_ALIASES.items()}
    # Reserve canonical source names so a human alias cannot redirect one category to another.
    lookup.update({normalize(x):x for x in resolver.available})
    reviewed={}; rejected=[]; seen=set()
    with Path(path).open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None or tuple(reader.fieldnames)!=HEADERS:raise CatalogRejected('INVALID_REVIEW_COLUMNS')
        for i,row in enumerate(reader,start=2):
            if None in row or any(v is None for v in row.values()):raise CatalogRejected(f'MALFORMED_ROW_{i}')
            canonical=row['canonical_category'].strip()
            if canonical not in resolver.available:raise CatalogRejected(f'UNKNOWN_CANONICAL_ROW_{i}')
            name=normalize(row['english_alias']);approval=normalize(row['approved'])
            if approval not in ('yes','no'):raise CatalogRejected(f'INVALID_APPROVAL_ROW_{i}')
            if not name:
                if approval=='yes':raise CatalogRejected(f'EMPTY_APPROVED_ALIAS_ROW_{i}')
                continue
            if not SAFE_ALIAS.fullmatch(name):raise CatalogRejected(f'UNSAFE_ALIAS_ROW_{i}')
            if name in seen:raise CatalogRejected(f'DUPLICATE_ALIAS_ROW_{i}')
            seen.add(name)
            if approval!='yes':continue
            if canonical not in resolver.active:raise CatalogRejected(f'INACTIVE_CANONICAL_ROW_{i}')
            if not row['reviewer'].strip() or not row['review_note'].strip():raise CatalogRejected(f'MISSING_REVIEW_PROVENANCE_ROW_{i}')
            if name in lookup and lookup[name]!=canonical:raise CatalogRejected(f'ALIAS_COLLISION_ROW_{i}')
            if name in lookup:continue # Existing verified alias or canonical spelling; never counts as new.
            reviewed[name]=canonical;lookup[name]=canonical
    return {'status':'REVIEWED_ALIASES_VALIDATED','new_english_aliases':reviewed,'approved_new_alias_count':len(reviewed),'source':'audited_catalog_plus_explicit_human_review','approved_for_mcp':False,'inventory_claim_allowed':False}

def resolve(catalog,review_csv,alias):
    resolver=CategoryResolver(catalog)
    report=compile_aliases(catalog,review_csv)
    name=normalize(alias)
    if name in report['new_english_aliases']:
        return {'status':'CATEGORY_RESOLVED','canonical_category':report['new_english_aliases'][name],'alias_type':'reviewed_english','source':'phase4c21b_reviewed_aliases'}
    resolved=resolver.resolve(alias)
    return {'status':'CATEGORY_RESOLVED',**resolved}
