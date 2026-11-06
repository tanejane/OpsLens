from agent.phase4c9_operational_audit import assess
import copy

def fixture():
    return {'audit_version':'4c9.1','query_type':'read_only','source_views':['commerce.orders','operations.delivery_effective','cx.effective_reviews'],
            'orders':{'rows':100,'unique_orders':100,'null_keys':0},
            'delivery':{'rows':100,'unique_orders':100,'null_keys':0,'missing_delivered':4,'missing_estimated':0,'missing_purchased':0,'negative_elapsed':0},
            'reviews':{'rows':85,'unique_orders':80,'null_keys':0,'missing_score':1,'out_of_range_score':0,'out_of_range_raw_score':0},
            'review_orphans':0,'delivery_orphans':0,'review_cardinality':{'multi_review_orders':5,'max_reviews_per_order':2},
            'coverage':{'reviewed_delivered_orders':77}}

def main():
    checks=[]
    def check(name, f): f(); checks.append(name); print('PASS:',name)
    check('base audit pass',lambda: assert_true(assess(fixture())['status']=='SOURCE_GRAIN_AUDIT_PASSED'))
    check('never grants MCP access',lambda: assert_true(not assess(fixture())['approved_for_mcp']))
    check('multi-review warning',lambda: assert_true('MULTIPLE_REVIEWS_PER_ORDER_REQUIRE_AGGREGATION' in assess(fixture())['warnings']))
    for name, section,field,value,expected in [
        ('delivery duplicates','delivery','rows',101,'DELIVERY_GRAIN_INVALID'),
        ('order duplicates','orders','rows',101,'ORDER_GRAIN_INVALID'),
        ('review orphan','root','review_orphans',1,'REVIEW_ORPHANS'),
        ('delivery orphan','root','delivery_orphans',1,'DELIVERY_ORPHANS'),
        ('bad effective score','reviews','out_of_range_score',1,'OUT_OF_RANGE_SCORE'),
        ('negative transit','delivery','negative_elapsed',1,'NEGATIVE_DELIVERY_ELAPSED'),
        ('delivery coverage mismatch','delivery','unique_orders',99,'DELIVERY_ORDER_COVERAGE_MISMATCH'),
        
    ]:
        def run(section=section,field=field,value=value,expected=expected):
            x=fixture(); (x if section=='root' else x[section])[field]=value
            assert_true(expected in assess(x)['failures'])
        check(name,run)
    def empty_reviews():
        x=fixture(); x['reviews']['rows']=0; x['reviews']['unique_orders']=0; x['coverage']['reviewed_delivered_orders']=0; x['review_cardinality']={'multi_review_orders':0,'max_reviews_per_order':0}
        assert_true('EMPTY_REQUIRED_SOURCE' in assess(x)['failures'])
    check('empty review source',empty_reviews)
    for name,section,field,value in [('boolean count','orders','rows',True),('negative count','reviews','rows',-1),
            ('invalid population','coverage','reviewed_delivered_orders',101)]:
        def run(section=section,field=field,value=value):
            x=fixture(); x[section][field]=value
            try: assess(x)
            except ValueError: return
            raise AssertionError('Should reject forged evidence')
        check(name,run)
    check('no review date overlap',lambda: assert_true('NO_REVIEWED_DELIVERED_ORDER_OVERLAP' in assess({**fixture(),'coverage':{'reviewed_delivered_orders':0}})['warnings']))
    print(f'Checks passed: {len(checks)}/{len(checks)}')

def assert_true(expr):
    if not expr: raise AssertionError()
if __name__=='__main__':main()
