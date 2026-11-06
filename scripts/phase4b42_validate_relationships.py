from agent.phase4b42_relationship_auditor import foreign_key_sides,fk_sql,judge,error_status,duplicate_grain_advice

def run():
    many={'cardinality':'many_to_one','left':'commerce.order_items','left_key':'product_id','right':'catalog.products','right_key':'product_id'}
    assert foreign_key_sides(many)==('commerce.order_items','product_id','catalog.products','product_id');print('PASS: many-to-one FK oriented toward products')
    q=fk_sql(many);assert 'FROM "commerce"."order_items" c' in q and 'FROM "catalog"."products"' in q;print('PASS: parent is products, not items')
    one={'cardinality':'one_to_many','left':'commerce.orders','left_key':'order_id','right':'commerce.order_items','right_key':'order_id'}
    assert foreign_key_sides(one)==('commerce.order_items','order_id','commerce.orders','order_id');print('PASS: one-to-many child orientation')
    good={'catalog.products':{'total_rows':12,'null_key_rows':0,'repeated_key_rows':0}}
    fk={'child_rows':35,'null_fk_rows':0,'orphan_fk_rows':0}
    assert judge(many,good,fk)=='STRUCTURALLY_VERIFIED';print('PASS: matching keys structurally verified')
    assert judge(many,good,{**fk,'orphan_fk_rows':2})=='REJECTED_ORPHANS';print('PASS: orphan FK rejected')
    assert judge(many,{'catalog.products':{**good['catalog.products'],'repeated_key_rows':1}},fk)=='REJECTED_PARENT_KEY_NOT_UNIQUE';print('PASS: duplicated parent key rejected')
    assert judge(many,good,{**fk,'null_fk_rows':3})=='VERIFIED_WITH_NULL_FOREIGN_KEYS';print('PASS: nullable FK disclosed')
    assert error_status(Exception('canceling statement due to statement timeout'))=='TIMEOUT';print('PASS: timeout inconclusive')
    assert duplicate_grain_advice('cx.effective_reviews',{'status':'REJECTED','result':{'repeated_key_rows':814}})['repeated_key_rows']==814;print('PASS: duplicate grain flagged without auto-repair')
    try: foreign_key_sides({**many,'cardinality':'many_to_many'})
    except ValueError: print('PASS: unsupported cardinality refused')
    else: raise AssertionError('unsupported cardinality permitted')
    print('Checks passed: 10/10')
if __name__=='__main__':run()
