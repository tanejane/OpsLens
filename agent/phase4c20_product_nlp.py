"""Conservative, bounded product NLP backed solely by the governed 4C19 executor.

No LLM-generated SQL or guessed category translation. Other domains are delegated.
"""
from dataclasses import dataclass
from datetime import date
import re
from agent.phase4c19_product import measure, ProductRejected

MONTHS={x.lower():i for i,x in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
MONTH_TOKEN='|'.join(MONTHS)
PERIOD=re.compile(r'\b('+MONTH_TOKEN+r')\s+(20\d{2})\b',re.I)
PERIOD_FOLLOW=re.compile(r'^\s*(?:and\s+)?(?:what|how)\s+about\s+('+MONTH_TOKEN+r')\s+(20\d{2})\s*[?.!]?\s*$',re.I)
KNOWN={'beleza_saude':'beleza_saude','health_beauty':'beleza_saude','health and beauty':'beleza_saude','health & beauty':'beleza_saude'}
CAT_RE=re.compile(r'(?<!\w)(?:health\s+(?:and|&)\s+beauty|health_beauty|beleza_saude)(?!\w)',re.I)
DOMAIN=re.compile(r'\b(?:product(?:s)?|categor(?:y|ies)|units?\s+sold|items?\s+sold|item\s+gmv|item\s+sales|item\s+price|health\s+(?:and|&)\s+beauty|health_beauty|beleza_saude)\b',re.I)
OTHER_DOMAIN=re.compile(r'\b(?:delivery|delivered|shipping|late|reviews?|ratings?|satisfaction|contribution\s+profit|profit\s+margin|seller\s+rank|marketing\s+spend)\b',re.I)
UNSUPPORTED=re.compile(r'\b(?:why|caus(?:e|ed|es|al)|because|stockouts?|inventory|in.stock|out.of.stock|availability|forecast|predict|refunds?|net\s+revenue|profit(?:ability)?|top\s+\d+|rank(?:ed|ing)?|best.selling|compare|comparison|versus|vs\.?|trend|increase|decrease|difference|between)\b',re.I)
FOLLOW_METRIC=re.compile(r'^\s*(?:and\s+)?(?:what(?:\'s|\s+is|\s+about)?|how\s+about)\s+(?:the\s+)?(?:sales\s+value|item\s+gmv|gmv\s+share|share|average\s+(?:item\s+)?price|units\s+sold|order\s+count|orders)\s*[?.!]?\s*$',re.I)

@dataclass(frozen=True)
class ProductContext:
    metric_id:str
    start:str
    end:str
    category:str


def _blocked(status,reason):
    return {'route':'product_category','status':status,'executable':False,'reason':reason,'causal_claim':False,'inventory_claim_allowed':False}


def month_bounds(name,year):
    m=MONTHS[name.lower()]; y=int(year)
    if not 2010<=y<=2100:raise ValueError('Unsupported year')
    return f'{y:04d}-{m:02d}-01',f'{y+1:04d}-01-01' if m==12 else f'{y:04d}-{m+1:02d}-01'


def resolve_category(q,prev):
    cats={KNOWN[re.sub(r'\s+',' ',m.group(0)).lower()] for m in CAT_RE.finditer(q)}
    # Do not treat unresolved category text as a catch-all category.
    if len(cats)>1:raise ValueError('Ambiguous category')
    if cats:return next(iter(cats))
    if prev:return prev.category
    raise ValueError('Specify an approved category (currently health and beauty / beleza_saude)')


def metric_from_question(q,prev):
    t=q.lower()
    if re.search(r'\b(?:percent|percentage|share|proportion)\b',t):return 'category_gmv_share'
    if re.search(r'\b(?:average|mean)\b.*\bprice\b|\bprice\s+per\s+(?:item|unit)\b',t):return 'average_item_price'
    if re.search(r'\b(?:item\s+gmv|gmv|sales\s+value|item\s+sales|sales\s+amount|how\s+much\s+(?:did|was|were).{0,45}\bsell)\b',t):return 'item_gmv'
    if re.search(r'\b(?:how\s+many|number\s+of|count\s+of)\b.{0,40}\borders\b|\border\s+count\b',t):return 'category_order_count'
    if re.search(r'\b(?:how\s+many|number\s+of|count\s+of)\b.{0,45}\b(?:products?|items?|units?)\b|\bunits?\s+sold\b',t):return 'units_sold'
    if prev and (PERIOD_FOLLOW.fullmatch(q) or FOLLOW_METRIC.fullmatch(q)):
        return prev.metric_id
    raise ValueError('Specify units sold, distinct category orders, item GMV, average item price, or category GMV share')


def ground(q,prev):
    if UNSUPPORTED.search(q):return None,_blocked('NOT_YET_SUPPORTED','Comparisons, rankings, inventory, causal and financial-profit claims are not supported by this product NLP contract')
    if re.search(r'\bhow\s+many\s+customers\b',q,re.I):return None,_blocked('NEEDS_CLARIFICATION','Customer count is not category order count')
    matches=PERIOD.findall(q)
    if len(matches)>1:return None,_blocked('NEEDS_CLARIFICATION','Specify one purchase month; no implicit comparison')
    try:
        if matches:start,end=month_bounds(*matches[0])
        elif prev and (FOLLOW_METRIC.fullmatch(q) or (DOMAIN.search(q) and not PERIOD.search(q))):start,end=prev.start,prev.end
        else:raise ValueError('Specify an explicit purchase month and year')
        category=resolve_category(q,prev)
        metric=metric_from_question(q,prev)
        return ProductContext(metric,start,end,category),None
    except ValueError as e:return None,_blocked('NEEDS_CLARIFICATION',str(e))


def candidate(q,active):
    if OTHER_DOMAIN.search(q):return False
    if active and (PERIOD_FOLLOW.fullmatch(q) or FOLLOW_METRIC.fullmatch(q)):return True
    return bool(DOMAIN.search(q))


class ProductNLPSession:
    """Wrap 4C17 session without altering its existing cross-domain routing."""
    def __init__(self,prior_session):
        self.prior=prior_session
        self.product_context=None
        self.active_domain=None

    async def dispatch(self,question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation):
        prev=self.product_context if self.active_domain=='product_category' else None
        if candidate(question,prev is not None):
            new,blocked=ground(question,prev)
            if blocked:return blocked
            evidence=await measure(new.metric_id,new.start,new.end,new.category,finance_reader)
            self.product_context=new
            self.active_domain='product_category'
            return {'route':'product_category','status':evidence['status'],'executable':True,
                    'resolution':{'canonical_category':new.category,'mapping_policy':'verified_explicit_aliases_v1'},
                    'evidence':evidence,'causal_claim':False,'inventory_claim_allowed':False}
        # Any non-product question clears the product follow-up scope; the older dispatcher
        # continues to own all pre-existing domains and their internal context.
        self.active_domain=None
        return await self.prior.dispatch(question,prior_dispatch,router,finance,finance_reader,graph,planner,graph_reader,investigation)
