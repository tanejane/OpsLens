"""Offline tampering and population checks for the delivery audit assessor."""
import copy
from agent.phase4c14_delivery_audit import assess

BASE={'audit_version':'4c14.1','source':'operations.delivery_effective','view':'semantic.order_delivery_evidence_v1',
      'policy':'late_iff_actual_gt_estimated_on_eligible_orders','time_basis':'order_purchase_time',
      'read_only':True,'mcp_approved':False,
      'raw':{'orders':100,'unique_orders':100,'null_keys':0,'missing_actual':3,'missing_estimated':1,
             'missing_purchase':0,'lateness_eligible':96,'late_orders':12,'duration_eligible':97,
             'negative_duration':0,'mean_delivery_days':12.25},
      'derived':{'orders':100,'unique_orders':100,'null_keys':0,'missing_actual':3,'missing_estimated':1,
             'missing_purchase':0,'lateness_eligible':96,'late_orders':12,'duration_eligible':97,
             'negative_duration':0,'mean_delivery_days':12.25,
             'invalid_late_flags':0,'invalid_duration_values':0,'missing_eligible_flags':0,'missing_eligible_duration':0},
      'monthly':{'month_rows':100,'distinct_months':2,'missing_purchase_rows':0}}

def check(label,change,expected):
    evidence=copy.deepcopy(BASE)
    change(evidence)
    try: result=assess(evidence)
    except (ValueError,TypeError,KeyError): result={'status':'REJECTED'}
    assert result['status']==expected, (label,result)
    print('PASS:',label)

def main():
    checks=[
      ('valid',lambda a:None,'DELIVERY_EVIDENCE_AUDIT_PASSED'),
      ('bad version',lambda a:a.update(audit_version='bad'),'REJECTED'),
      ('source forged',lambda a:a.update(source='fake'),'REJECTED'),
      ('view forged',lambda a:a.update(view='fake'),'REJECTED'),
      ('policy forged',lambda a:a.update(policy='any'),'REJECTED'),
      ('time basis forged',lambda a:a.update(time_basis='delivery_time'),'REJECTED'),
      ('write permission',lambda a:a.update(read_only=False),'REJECTED'),
      ('mcp approval forged',lambda a:a.update(mcp_approved=True),'REJECTED'),
      ('missing evidence',lambda a:a.pop('raw'),'REJECTED'),
      ('bool count',lambda a:a['raw'].update(orders=True),'REJECTED'),
      ('negative count',lambda a:a['raw'].update(orders=-1),'REJECTED'),
      ('impossible count',lambda a:a['raw'].update(late_orders=101),'REJECTED'),
      ('impossible late population',lambda a:a['raw'].update(late_orders=97),'REJECTED'),
      ('raw vs view mismatch',lambda a:a['derived'].update(late_orders=11),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('duplicate grain',lambda a:(a['raw'].update(unique_orders=99),a['derived'].update(unique_orders=99)),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('missing eligible flags',lambda a:a['derived'].update(missing_eligible_flags=1),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('invalid extra flag',lambda a:a['derived'].update(invalid_late_flags=1),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('negative duration',lambda a:(a['raw'].update(negative_duration=1),a['derived'].update(negative_duration=1)),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('monthly mismatch',lambda a:a['monthly'].update(month_rows=99),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('different average',lambda a:a['derived'].update(mean_delivery_days=13),'DELIVERY_EVIDENCE_AUDIT_BLOCKED'),
      ('nan average',lambda a:a['derived'].update(mean_delivery_days='NaN'),'REJECTED'),
    ]
    for label,fn,expected in checks:check(label,fn,expected)
    print(f'Checks passed: {len(checks)}/{len(checks)}')
if __name__=='__main__':main()
