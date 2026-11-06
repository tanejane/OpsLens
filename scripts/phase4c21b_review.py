"""python -m scripts.phase4c21b_review template|validate|resolve CATALOG.json REVIEW.csv [ALIAS]"""
import json,sys
from agent.phase4c21_category_catalog import load,CatalogRejected
from agent.phase4c21b_aliases import template,compile_aliases,resolve
if __name__=='__main__':
    try:
        if len(sys.argv)<4:raise CatalogRejected('USAGE: template|validate|resolve catalog.json review.csv [alias]')
        command=sys.argv[1];data=load(sys.argv[2]);csvpath=sys.argv[3]
        if command=='template' and len(sys.argv)==4:r=template(data,csvpath)
        elif command=='validate' and len(sys.argv)==4:r=compile_aliases(data,csvpath)
        elif command=='resolve' and len(sys.argv)==5:r=resolve(data,csvpath,sys.argv[4])
        else:raise CatalogRejected('INVALID_COMMAND')
        print(json.dumps(r,indent=2,ensure_ascii=False))
    except (CatalogRejected,OSError) as e:
        print(json.dumps({'status':'CATEGORY_ALIAS_REVIEW_FAILED','reason':str(e)},indent=2));sys.exit(1)
