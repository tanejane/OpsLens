"""CLI: python -m scripts.phase4c21_assess phase4c21_category_catalog.json"""
import json,sys
from agent.phase4c21_category_catalog import load,audit,CatalogRejected
if __name__=='__main__':
    try:
        if len(sys.argv)!=2:raise CatalogRejected('USAGE: python -m scripts.phase4c21_assess path.json')
        report=audit(load(sys.argv[1]))
        print(json.dumps(report,indent=2));sys.exit(0)
    except CatalogRejected as e:
        print(json.dumps({'status':'PRODUCT_CATEGORY_CATALOG_FAILED','reason':str(e)},indent=2));sys.exit(1)
