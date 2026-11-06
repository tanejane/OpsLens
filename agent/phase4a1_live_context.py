"""Fail-closed MCP metadata adapter for Phase 4A context building.

All metadata is acquired through the running OpsLens MCP server. No SQL, no
local hard-coded relation catalog, and no evaluator truth are accessed here.
"""
from __future__ import annotations
import json
from typing import Any
from mcp import Client
from mcp_server.server import mcp
from agent.phase4a_context import ALLOWED_DOMAINS, ContextPacket, build_context

class CatalogProtocolError(RuntimeError):
    pass


def _payload(response: Any, tool: str) -> Any:
    if getattr(response, 'is_error', False):
        raise CatalogProtocolError(f'{tool}: MCP tool reported an error')
    data = getattr(response, 'structured_content', None)
    if data is None:
        # MCP SDKs differ on whether dictionaries are returned in a structured
        # content envelope. Do not parse arbitrary text as trusted metadata.
        raise CatalogProtocolError(f'{tool}: missing structured MCP output')
    if not isinstance(data, dict):
        raise CatalogProtocolError(f'{tool}: unexpected structured output type')
    if data.get('ok') is False or data.get('error'):
        raise CatalogProtocolError(f'{tool}: {data.get("error") or "tool failure"}')
    # Handle common SDK wrapping: {'result':...}, {'data': ...},
    # or a direct object. Never convert a bad payload into empty success.
    for key in ('data','result'):
        if key in data and data[key] is not None:
            return data[key]
    return data


def _records(payload: Any, keys: tuple[str,...], tool: str) -> list[dict]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = next((payload[k] for k in keys if isinstance(payload.get(k), list)), None)
        if items is None:
            raise CatalogProtocolError(f'{tool}: expected list under {keys}, received keys {list(payload)}')
    else:
        raise CatalogProtocolError(f'{tool}: expected records')
    if not all(isinstance(i, dict) for i in items):
        raise CatalogProtocolError(f'{tool}: records are not dictionaries')
    return items


def _metric(item: dict) -> dict | None:
    name=item.get('name') or item.get('metric_name')
    if not isinstance(name,str) or not name.strip():
        return None
    return {'name': name, 'domain': item.get('domain'), 'definition':
        item.get('business_definition') or item.get('definition') or item.get('description') or ''}


def _relation(item: dict, domain: str) -> dict | None:
    raw=item.get('name') or item.get('relation') or item.get('table_name') or item.get('view_name')
    if not isinstance(raw,str):
        return None
    name=raw if '.' in raw else f'{domain}.{raw}'
    if name.split('.',1)[0]!=domain:
        return None
    return {'name':name,'domain':domain,'grain':item.get('grain') or item.get('description') or ''}


async def fetch_live_catalog(*, domains: tuple[str,...] | None = None) -> tuple[list[dict],list[dict],dict]:
    requested=domains or ('semantic','finance','operations','cx','inventory','marketing','behavior','commerce','catalog')
    if not requested or any(x not in ALLOWED_DOMAINS for x in requested):
        raise ValueError('Only approved domains may be discovered')
    metrics=[]; relations=[]; errors=[]
    async with Client(mcp) as client:
        m=_payload(await client.call_tool('list_metrics',{}),'list_metrics')
        for entry in _records(m,('metrics','items','results'),'list_metrics'):
            val=_metric(entry)
            if val: metrics.append(val)
        if not metrics:
            raise CatalogProtocolError('No usable metrics returned by live MCP')
        for domain in requested:
            try:
                raw=_payload(await client.call_tool('discover_schema',{'domain':domain}),f'discover_schema({domain})')
                entries=_records(raw,('relations','tables','views','items','results'),f'discover_schema({domain})')
                for entry in entries:
                    val=_relation(entry,domain)
                    if val: relations.append(val)
            except CatalogProtocolError as exc:
                errors.append(str(exc))
    # Report partial catalog failures. For now, fail closed rather than
    # pretend that an incomplete catalog represents the whole business domain.
    if errors:
        raise CatalogProtocolError('Live MCP schema discovery incomplete: '+' | '.join(errors))
    if not relations:
        raise CatalogProtocolError('No usable approved relations returned by live MCP')
    metrics=list({m['name']:m for m in metrics}.values())
    relations=list({v['name']:v for v in relations}.values())
    return metrics,relations,{'source':'live_mcp','domain_count':len(requested),
        'metric_count':len(metrics),'relation_count':len(relations)}


async def build_live_context(question: str, *, max_chars: int=11000,
                             domains: tuple[str,...] | None=None,
                             evidence: list[dict] | None=None) -> tuple[ContextPacket,dict]:
    metrics,relations,provenance=await fetch_live_catalog(domains=domains)
    packet=build_context(question,metrics=metrics,relations=relations,evidence=evidence,max_chars=max_chars)
    if not packet.metric_catalog or not packet.relation_catalog:
        raise CatalogProtocolError('Context budget excluded all usable live catalog entries')
    return packet,provenance
