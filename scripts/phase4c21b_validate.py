import csv,tempfile,json
from pathlib import Path
from agent.phase4c21b_aliases import template,compile_aliases,resolve,HEADERS
from agent.phase4c21_category_catalog import CatalogRejected

def fake():
    return {'contract':'opslens_product_categories_census_v1','categories':[
        {'raw_category':'beleza_saude','products':5,'item_units':10,'distinct_orders':8,'item_gmv':'100.00'},
        {'raw_category':'moveis_decoracao','products':3,'item_units':6,'distinct_orders':4,'item_gmv':'120.00'},
        {'raw_category':None,'products':1,'item_units':2,'distinct_orders':2,'item_gmv':'20.00'}],
        'source_product_count':9,'source_item_count':18,'source_item_gmv':'240.00'}

def check(name,fn,should_fail=False):
    try:
        fn()
        if should_fail:raise AssertionError('Expected rejection')
    except CatalogRejected:
        if not should_fail:raise
    print('PASS:',name)

def main():
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'review.csv';data=fake();n=0
        check('empty review template',lambda:template(data,path));n+=1
        check('no automatic aliases',lambda:assert_eq(compile_aliases(data,path)['approved_new_alias_count'],0));n+=1
        check('verified alias',lambda:assert_eq(resolve(data,path,'health and beauty')['canonical_category'],'beleza_saude'));n+=1
        check('exact canonical',lambda:assert_eq(resolve(data,path,'moveis_decoracao')['canonical_category'],'moveis_decoracao'));n+=1
        check('unreviewed english blocked',lambda:resolve(data,path,'furniture'),True);n+=1
        def rows(items):
            with path.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader();w.writerows(items)
        def row(alias='furniture',canonical='moveis_decoracao',approved='yes',reviewer='reviewer',note='Confirmed explicit mapping'):
            return dict(canonical_category=canonical,english_alias=alias,approved=approved,reviewer=reviewer,review_note=note)
        rows([row()]);check('approved mapping',lambda:assert_eq(resolve(data,path,'FURNITURE')['canonical_category'],'moveis_decoracao'));n+=1
        check('approved count',lambda:assert_eq(compile_aliases(data,path)['approved_new_alias_count'],1));n+=1
        for name,rr in [
            ('unreviewed',row(approved='no')),('empty name',row(alias='',approved='no'))]:
            rows([rr]);check(name,lambda:assert_eq(compile_aliases(data,path)['approved_new_alias_count'],0));n+=1
        for name,rr in [
            ('unknown canonical',row(canonical='not_in_catalog')),
            ('empty approved',row(alias='')),
            ('missing reviewer',row(reviewer='')),
            ('missing note',row(note='')),
            ('SQL punctuation',row(alias='furniture;DROP')),
            ('inactive category',row(canonical='none')),
            ('verified alias hijack',row(alias='health and beauty')),
            ('canonical hijack',row(alias='beleza_saude')),
            ('invalid approved',row(approved='maybe')),
            ('unapproved malicious alias',row(alias='no; drop',approved='no'))]:
            rows([rr]);check(name,lambda:compile_aliases(data,path),True);n+=1
        rows([row(),row(alias='furniture',canonical='moveis_decoracao')]);check('duplicate aliases',lambda:compile_aliases(data,path),True);n+=1
        rows([row(alias='furniture',approved='no'),row(alias='furniture')]);check('duplicate across approvals',lambda:compile_aliases(data,path),True);n+=1
        rows([row(alias='health & beauty',canonical='beleza_saude')]);check('existing alias not new',lambda:assert_eq(compile_aliases(data,path)['approved_new_alias_count'],0));n+=1
        rows([row(alias='furniture')]);check('unknown still blocked',lambda:resolve(data,path,'electronics'),True);n+=1
        rows([row(alias='furniture')]);check('not MCP approved',lambda:assert_eq(compile_aliases(data,path)['approved_for_mcp'],False));n+=1
        rows([row(alias='furniture')]);check('no inventory claims',lambda:assert_eq(compile_aliases(data,path)['inventory_claim_allowed'],False));n+=1
        path.write_text('wrong,header\n',encoding='utf-8');check('invalid headers',lambda:compile_aliases(data,path),True);n+=1
        print(f'Checks passed: {n}/{n}')

def assert_eq(x,y):
    if x!=y:raise AssertionError(f'{x!r} != {y!r}')
if __name__=='__main__':main()
