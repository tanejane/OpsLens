from agent.phase4b41_live_verifier import (AuditError,source_sql,uniqueness_sql,coverage_sql,relationship_sql,classify_key,classify_relationship)

def main():
    assert 'COUNT(DISTINCT ("order_id", "order_item_id"))' in uniqueness_sql('commerce.order_items',['order_id','order_item_id']);print('PASS: composite keys checked')
    try: source_sql('staging.secret')
    except AuditError: print('PASS: unapproved schema rejected')
    else: raise AssertionError('Unapproved schema allowed')
    try: source_sql('commerce.orders;DROP TABLE x')
    except AuditError:print('PASS: SQL identifiers guarded')
    else:raise AssertionError('Unsafe identifier allowed')
    assert 'pg_input_is_valid' in coverage_sql('commerce.orders','order_purchase_timestamp','text');print('PASS: text timestamp guarded')
    try: coverage_sql('commerce.orders','customer_id','text')
    except AuditError:print('PASS: arbitrary text not cast as dates')
    else:raise AssertionError('Bad date column allowed')
    r={'left':'commerce.orders','right':'commerce.order_items','left_key':'order_id','right_key':'order_id','cardinality':'one_to_many'}
    assert 'NOT EXISTS' in relationship_sql(r,'right');print('PASS: anti-join audit avoids fanout')
    assert classify_key({'total_rows':10,'null_key_rows':0,'repeated_key_rows':1})=='REJECTED';print('PASS: repeated keys rejected')
    assert classify_relationship(r,'VERIFIED','REJECTED',{}, {'child_rows':20,'null_keys':0,'unmatched_rows':0})=='STRUCTURALLY_VERIFIED';print('PASS: one-to-many child duplicates permitted')
    assert classify_relationship(r,'VERIFIED','REJECTED',{}, {'child_rows':20,'null_keys':0,'unmatched_rows':3})=='UNMATCHED_FOREIGN_KEYS';print('PASS: orphan keys detected')
    print('Checks passed: 9/9')

if __name__=='__main__':main()
