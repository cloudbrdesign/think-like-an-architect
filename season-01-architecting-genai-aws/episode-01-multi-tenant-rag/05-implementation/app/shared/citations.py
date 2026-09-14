"""Citation isolation (CTL-018). Citations are a disclosure channel, so they are built from an explicit allow-list.

Only documents that (1) passed the tenant-constrained retrieval and (2) passed ownership verification receive a label
[D1]…[Dn] in the prompt. The model may cite labels. This module maps cited labels back to exactly four fields:

    label · document_id · title (from the ownership record) · location (the API route that opens the document)

Unknown labels (for example a document the model invented) are removed from the answer and never become citations.
Storage keys, bucket names, index identifiers, scores and x-amz-bedrock-kb-* metadata never appear.
"""
import re

CITATION_FIELDS = ("label", "document_id", "title", "location")
_LABEL = re.compile(r"\[(D\d{1,2})\]")


def assign_labels(verified_chunks):
    """One label per verified document, in retrieval order → ({label: {document_id, title}}, [(label, chunk)])."""
    labels, by_document, labelled = {}, {}, []
    for chunk in verified_chunks:
        if chunk.document_id not in by_document:
            label = f"D{len(by_document) + 1}"
            by_document[chunk.document_id] = label
            labels[label] = {"document_id": chunk.document_id, "title": chunk.title}
        labelled.append((by_document[chunk.document_id], chunk))
    return labels, labelled


def build(answer_text, labels):
    """Return (answer with unknown labels removed, citations limited to CITATION_FIELDS)."""
    citations, seen = [], set()

    def keep_or_remove(match):
        label = match.group(1)
        if label not in labels:
            return ""
        if label not in seen:
            seen.add(label)
            document = labels[label]
            citations.append({"label": label, "document_id": document["document_id"], "title": document["title"],
                              "location": f"/documents/{document['document_id']}"})
        return match.group(0)

    clean = _LABEL.sub(keep_or_remove, answer_text or "")
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean, citations
