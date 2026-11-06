"""CLI: python -m scripts.phase4c21_catalog_lookup CATALOG_JSON category name"""
import json,sys
from agent.phase4c21_category_catalog import load,CategoryResolver,CatalogRejected
if __name__=='__main__':
    try:
        if len(sys.argv)<3:raise CatalogRejected('USAGE: python -m scripts.phase4c21_catalog_lookup path.json category name')
        resolver=CategoryResolver(load(sys.argv[1]));res=resolver.resolve(' '.join(sys.argv[2:]))
        print(json.dumps({'status':'CATEGORY_RESOLVED',**res},indent=2))
    except CatalogRejected as e:
        print(json.dumps({'status':'CATEGORY_NOT_RESOLVED','reason':str(e)},indent=2));sys.exit(1)
