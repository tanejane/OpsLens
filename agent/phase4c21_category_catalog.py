"""Evidence-audited product categories. No guessed translations, no automatic approvals."""
import json,re
from decimal import Decimal,InvalidOperation
from pathlib import Path

CONTRACT='opslens_product_categories_census_v1'
CANONICAL=re.compile(r'^[a-z0-9_]+$')
# Only translation previously checked against live source in Phase 4C.19B.
VERIFIED_ALIASES={'health and beauty':'beleza_saude','health & beauty':'beleza_saude','health_beauty':'beleza_saude'}

class CatalogRejected(ValueError):pass

def _integer(v):
    if type(v) is not int or v<0:raise CatalogRejected('INVALID_COUNT')
    return v

def _money(v):
    if isinstance(v,bool):raise CatalogRejected('INVALID_MONEY')
    try: d=Decimal(str(v))
    except (InvalidOperation,TypeError,ValueError):raise CatalogRejected('INVALID_MONEY')
    if not d.is_finite() or d<0 or d.as_tuple().exponent < -2:raise CatalogRejected('INVALID_MONEY')
    return d

def audit(data):
    if not isinstance(data,dict) or data.get('contract')!=CONTRACT:raise CatalogRejected('WRONG_CONTRACT')
    rows=data.get('categories')
    if not isinstance(rows,list) or not rows:raise CatalogRejected('EMPTY_CATALOG')
    seen=set();sum_products=0;sum_units=0;sum_gmv=Decimal('0');unknown=0;items_positive=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'raw_category','products','item_units','distinct_orders','item_gmv'}:raise CatalogRejected('ROW_SHAPE')
        name=row['raw_category']
        if name is not None and (not isinstance(name,str) or not CANONICAL.fullmatch(name)):raise CatalogRejected('UNSAFE_CATEGORY')
        if name in seen:raise CatalogRejected('DUPLICATE_CATEGORY')
        seen.add(name)
        products=_integer(row['products']);units=_integer(row['item_units']);orders=_integer(row['distinct_orders']);gmv=_money(row['item_gmv'])
        if orders>units or (units==0 and (orders or gmv)) or (units>0 and orders==0):raise CatalogRejected('INCONSISTENT_GRAIN')
        sum_products+=products;sum_units+=units;sum_gmv+=gmv
        if name is None:unknown+=units
        if units and name is not None:items_positive.append(name)
    if sum_products!=_integer(data.get('source_product_count')):raise CatalogRejected('PRODUCT_TOTAL_MISMATCH')
    if sum_units!=_integer(data.get('source_item_count')):raise CatalogRejected('ITEM_TOTAL_MISMATCH')
    if sum_gmv!=_money(data.get('source_item_gmv')):raise CatalogRejected('GMV_TOTAL_MISMATCH')
    if 'beleza_saude' not in seen:raise CatalogRejected('VERIFIED_CATEGORY_MISSING')
    return {'status':'PRODUCT_CATEGORY_CATALOG_AUDITED','category_rows':len(rows),'categories_with_items':len(items_positive),'source_products':sum_products,'source_items':sum_units,'source_item_gmv':str(sum_gmv),'null_category_item_units':unknown,'approved_english_aliases':['health and beauty','health & beauty','health_beauty'],'catalog_scope':'canonical_raw_categories_only','new_translations_approved':False,'approved_for_mcp':False,'next_gate':'Review canonical names and separately approve new aliases; then integrate with NLP and live test'}

def load(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig').strip())
    except (OSError,ValueError) as e:raise CatalogRejected('INVALID_CATALOG_FILE') from e

class CategoryResolver:
    def __init__(self,data):
        self.report=audit(data)
        self.available={r['raw_category'] for r in data['categories'] if r['raw_category'] is not None}
        self.active={r['raw_category'] for r in data['categories'] if r['raw_category'] is not None and r['item_units']>0}
    def resolve(self,text):
        if not isinstance(text,str) or not text.strip():raise CatalogRejected('CATEGORY_REQUIRED')
        key=re.sub(r'\s+',' ',text.strip().lower())
        canonical=VERIFIED_ALIASES.get(key,key)
        if canonical not in self.available:raise CatalogRejected('UNRECOGNIZED_CATEGORY')
        if canonical not in self.active:raise CatalogRejected('NO_ITEM_EVIDENCE')
        return {'canonical_category':canonical,'alias_type':'verified_english' if key in VERIFIED_ALIASES else 'exact_canonical','source':'audited_product_category_catalog_v1'}
