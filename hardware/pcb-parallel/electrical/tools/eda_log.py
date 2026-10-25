#!/usr/bin/env python3
"""Read-only parser for EasyEDA Pro (嘉立创EDA专业版) V3 log documents.

Format (see %LOCALAPPDATA%/Programs/LCEDA-Pro/docs/easyeda-format.md):
    {"type":"T","id":"UUID","ticket":N}||{...payload...}|

- Every document starts with a DOCHEAD record; following records belong to it.
- Eventual consistency: for equal (type, id) keep the record with the larger ticket.
- Deletion: payload becomes the empty string.
- PCB primitive coordinates/lengths are in 0.001 inch (mil) in this file, verified
  against the 139.0 mm pour boundary (5472.4409 mil) and 1.6 mm pads (62.992 mil).

This module only reads. It never writes to a design source.
"""
import json
from pathlib import Path

MIL_PER_MM = 39.37007874015748


def mm(value):
    """mil -> mm, rounded to 1 um."""
    return round(value / MIL_PER_MM, 4)


def load_documents(path):
    """Return {doc_uuid: {'head': {...}, 'records': {(type,id): payload}}}."""
    path = Path(path)
    docs = []
    current = None
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            line = line.rstrip('\n').rstrip('\r')
            if '||' not in line:
                continue
            head_text, payload_text = line.split('||', 1)
            try:
                head = json.loads(head_text)
            except json.JSONDecodeError:
                continue
            payload_text = payload_text.rstrip('|')
            if head.get('type') == 'DOCHEAD':
                try:
                    head_payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                current = {'head': head_payload, 'raw': {}, 'ticket': {}}
                docs.append(current)
                continue
            if current is None:
                continue
            if payload_text == '' or payload_text == '""':
                key = (head.get('type'), json.dumps(head.get('id'), sort_keys=True))
                current['raw'][key] = None
                current['ticket'][key] = head.get('ticket') or 0
                continue
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            key = (head.get('type'), json.dumps(head.get('id'), sort_keys=True))
            ticket = head.get('ticket') or 0
            if key in current['ticket'] and current['ticket'][key] > ticket:
                continue
            current['raw'][key] = payload
            current['ticket'][key] = ticket
    result = {}
    for doc in docs:
        uuid = doc['head'].get('uuid')
        records = {}
        for key, payload in doc['raw'].items():
            if payload is None:
                continue
            records[key] = payload
        result[uuid] = {'head': doc['head'], 'records': records}
    return result


def find_document(documents, doc_type):
    for uuid, doc in documents.items():
        if doc['head'].get('docType') == doc_type:
            return uuid, doc
    raise KeyError('no document of type ' + doc_type)


def decode_id(rec_id):
    """Record ids are JSON-serialised; array ids are additionally double-encoded."""
    value = json.loads(rec_id)
    if isinstance(value, str) and value[:1] in '[{':
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def by_type(doc, wanted):
    """Yield (id, payload) for records of a given type."""
    for (rec_type, rec_id), payload in doc['records'].items():
        if rec_type == wanted:
            yield decode_id(rec_id), payload


if __name__ == '__main__':
    import sys
    docs = load_documents(sys.argv[1])
    for uuid, doc in docs.items():
        kinds = {}
        for (rec_type, _) in doc['records']:
            kinds[rec_type] = kinds.get(rec_type, 0) + 1
        print(uuid, doc['head'].get('docType'), len(doc['records']), 'records')
