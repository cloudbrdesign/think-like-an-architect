"""Response handling (CTL-015, CTL-016).

  * Citations are built here, only from chunks that passed verification and relevance — never from the model's text,
    never from anything that was withheld.
  * Every non-answer — nothing eligible, nothing relevant, withheld, authorization unavailable, not employed, any
    error — returns the SAME body with the SAME status. Nothing says whether restricted material exists, why the
    request was refused, or how many results there were. The content-free audit record keeps the distinction.
"""
import json

from core import classification

UNIFORM_NO_ANSWER = "I can't answer that from the information available to me."
HEADERS = {"content-type": "application/json", "cache-control": "no-store"}


def _http(body):
    return {"statusCode": 200, "headers": dict(HEADERS), "body": json.dumps(body, sort_keys=True)}


def uniform(request_id):
    return _http({"answer": UNIFORM_NO_ANSWER, "citations": [], "request_id": request_id})


def citations(kept_chunks, records):
    """One citation per verified section used for the answer: identifiers and titles from the current record."""
    titles = {}
    for record in records.values():
        if record is not None:
            for section_id, section in classification.classify(record)[0].items():
                titles[(section.document_id, section_id)] = (section.document_title, section.section_title)
    result, seen = [], set()
    for chunk in kept_chunks:
        key = (chunk.document_id, chunk.section_id)
        if key in seen or key not in titles:
            continue
        seen.add(key)
        result.append({"document_id": key[0], "section_id": key[1], "document_title": titles[key][0],
                       "section_title": titles[key][1]})
    return result


def answered(request_id, text, cited):
    return _http({"answer": text, "citations": cited, "request_id": request_id})
