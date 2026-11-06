"""Conservative pre-routing language normalization. No SQL, no data-side permissions.

Corrections are exact, reviewed lexical substitutions. Never use edit-distance fuzzy
matching or an LLM's unconstrained guesses to authorize a metric execution.
"""
from dataclasses import dataclass
import re
import unicodedata

# Phrase substitutions are narrow; intentional unsupported concepts stay visible.
PHRASES = (
    (r'(?<!\w)health\s*(?:&|and)\s*beuty(?!\w)', 'health and beauty'),
    (r'(?<!\w)health\s*(?:&|and)\s*beauty(?!\w)', 'health and beauty'),
    (r'(?<!\w)beuty(?!\w)', 'health and beauty'),
    (r'(?<!\w)beauty(?!\w)', 'health and beauty'),
    (r'(?<!\w)reveneu(?!\w)', 'revenue'),
    (r'(?<!\w)revnue(?!\w)', 'revenue'),
    (r'(?<!\w)profitt(?!\w)', 'profit'),
    (r'(?<!\w)delivry(?!\w)', 'delivery'),
    (r'(?<!\w)jun\s*[\'’]?\s*18(?!\w)', 'June 2018'),
    (r'(?<!\w)jun\s+2018(?!\w)', 'June 2018'),
    (r'(?<!\w)may\s*[\'’]?\s*18(?!\w)', 'May 2018'),
    (r'(?<!\w)gmv(?!\w)', 'GMV'),
)
# For Chinese, only carefully bounded product phrases are supported. No broad translation.
CHINESE_PRODUCT = (
    ('健康美容', 'health and beauty'),
    ('美容保健', 'health and beauty'),
    ('六月', 'June '),
    ('五月', 'May '),
    ('件数', 'units sold'),
    ('卖了多少件', 'how many units sold'),
    ('商品销售额', 'item GMV'),
)
AMBIGUOUS = re.compile(r'^(?:how(?:\s+is|\s+are|\x27s)?\s+(?:sales|business)(?:\s+doing)?|sales\??|销售额[？?]?)\s*[?.!]*$', re.I)
# Do not normalize or reinterpret intentionally sensitive/instructional content.
SUSPICIOUS = re.compile(r'(?:;|--|/\*|\*/|\b(?:drop|delete|insert|update|alter|grant|revoke)\b|\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b)',re.I)

@dataclass(frozen=True)
class Interpretation:
    status: str
    original: str
    normalized: str
    corrections: tuple[str,...]
    reason: str = ''


def interpret(question):
    if not isinstance(question,str) or not question.strip() or len(question)>500:
        return Interpretation('NEEDS_CLARIFICATION',str(question),'',(), 'Provide a question of 1–500 characters')
    source=question.strip()
    if SUSPICIOUS.search(source):
        return Interpretation('NOT_INTERPRETED',source,source,(), 'Potential instruction or query syntax; no automatic correction')
    q=unicodedata.normalize('NFKC',source)
    corrections=[]
    for old,new in CHINESE_PRODUCT:
        if old in q:
            q=q.replace(old,new);corrections.append(old+' → '+new)
    # One-pass leftmost match over the ORIGINAL text after bounded Chinese mappings.
    # Longest/most-specific alternatives win at the same start position. Crucially,
    # generated text is never searched again in this call.
    combined = re.compile('|'.join('(?:' + pattern + ')' for pattern, _ in PHRASES), re.I)
    def replace_once(match):
        token = match.group(0)
        for pattern, replacement in PHRASES:
            if re.fullmatch(pattern, token, flags=re.I):
                # Preserve already-canonical text without emitting spurious corrections.
                if token == replacement:
                    return token
                corrections.append(replacement)
                return replacement
        raise AssertionError('Unrecognized lexical match')
    q = combined.sub(replace_once, q)
    q=re.sub(r'\s+',' ',q).strip()
    if AMBIGUOUS.fullmatch(q) or AMBIGUOUS.fullmatch(source):
        return Interpretation('NEEDS_CLARIFICATION',source,q,tuple(corrections),
                              'Specify a metric (item GMV, audited financial revenue, or units sold), category if relevant, and period')
    # A fragmentary translation must not bypass metric/period validation downstream.
    if re.search(r'[\u3400-\u9fff]',q):
        return Interpretation('NEEDS_CLARIFICATION',source,q,tuple(corrections),
                              'Only selected Chinese product terms are supported; please clarify in English')
    return Interpretation('INTERPRETED',source,q,tuple(corrections))


class LanguageSession:
    """Preprocess before existing 4C20 dispatch; preserves its domain/context logic."""
    def __init__(self,product_session):
        self.product_session=product_session

    async def dispatch(self,question,*args):
        i=interpret(question)
        if i.status!='INTERPRETED':
            return {'route':'language_understanding','status':i.status,'executable':False,
                    'reason':i.reason,'original_question':i.original,'corrections':list(i.corrections),
                    'causal_claim':False,'inventory_claim_allowed':False}
        result=await self.product_session.dispatch(i.normalized,*args)
        # Preserve underlying evidence and disclose corrections for inspection.
        result=dict(result)
        result['language']={'original_question':i.original,'interpreted_question':i.normalized,
                            'corrections':list(i.corrections),'policy':'explicit_lexical_rules_v1'}
        return result
