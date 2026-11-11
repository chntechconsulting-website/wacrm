"""
Deal-level grouping for quotations, proformas and invoices.

A single sales deal can generate several documents as it moves through the
pipeline:

    quotation -> proforma -> invoice

Reporting each document as its own deal makes one customer look like several
deals (Proposal Sent + Negotiation + Won at the same time) and double-counts
the pipeline value. This module links documents back into the deal they belong
to, using only reliable identifiers:

  * ``lead_id`` - all documents for the same lead belong to the same deal.
  * ``source_quotation_id`` - a proforma/invoice points at its source document.
  * ``source_quotation_number`` - the same link when only the number was stored.

Documents without any of those links stay in their own group. Customer names
are deliberately NOT used as a grouping key, so multiple genuine deals for the
same customer remain separate.
"""

from datetime import datetime
from typing import Any, Iterable, List, Optional


STAGE_PROPOSAL = "Proposal Sent"
STAGE_NEGOTIATION = "Negotiation"
STAGE_WON = "Won"

# Higher rank wins when a group holds documents from several pipeline stages.
PIPELINE_STAGE_RANK = {
    STAGE_PROPOSAL: 1,
    STAGE_NEGOTIATION: 2,
}


def _normalize_doc_number(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def document_stage(doc: Any) -> Optional[str]:
    """Return the pipeline stage represented by a document.

    Cancelled documents are not part of the active pipeline and return None.
    """
    if (getattr(doc, "status", "") or "").strip().lower() == "cancelled":
        return None

    doc_type = (getattr(doc, "doc_type", "") or "").strip().lower()
    if doc_type == "quotation":
        return STAGE_PROPOSAL
    if doc_type == "proforma":
        return STAGE_NEGOTIATION
    if doc_type == "invoice":
        return STAGE_WON
    return None


def document_timestamp(doc: Any) -> datetime:
    return (
        getattr(doc, "issue_date", None)
        or getattr(doc, "created_at", None)
        or datetime.min
    )


class _DisjointSet:
    """Small union-find used to connect documents that reference each other."""

    def __init__(self) -> None:
        self._parent = {}

    def add(self, key) -> None:
        self._parent.setdefault(key, key)

    def find(self, key):
        self.add(key)
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression keeps repeated lookups cheap on long chains.
        while self._parent[key] != root:
            self._parent[key], key = root, self._parent[key]
        return root

    def union(self, left, right) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


class DealGroup:
    """All documents that belong to one sales deal."""

    def __init__(self, documents: Iterable[Any]) -> None:
        self.documents = sorted(
            [doc for doc in documents if getattr(doc, "id", None) is not None],
            key=lambda doc: doc.id,
        )

    @property
    def doc_ids(self) -> List[int]:
        return [doc.id for doc in self.documents]

    @property
    def lead_id(self) -> Optional[int]:
        for doc in self.documents:
            lead_id = getattr(doc, "lead_id", None)
            if lead_id:
                return lead_id
        return None

    @property
    def key(self) -> str:
        """Stable identity for this deal across report surfaces."""
        if self.lead_id is not None:
            return f"lead_{self.lead_id}"
        return f"doc_{min(self.doc_ids)}"

    @property
    def latest_document(self) -> Optional[Any]:
        if not self.documents:
            return None
        return max(
            self.documents,
            key=lambda doc: (document_timestamp(doc), doc.id),
        )

    def best_pipeline_document(self) -> Optional[Any]:
        """Latest document in the most advanced open pipeline stage."""
        candidates = [
            doc
            for doc in self.documents
            if document_stage(doc) in PIPELINE_STAGE_RANK
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda doc: (
                PIPELINE_STAGE_RANK[document_stage(doc)],
                document_timestamp(doc),
                doc.id,
            ),
        )


def build_deal_groups(documents: Iterable[Any]) -> List[DealGroup]:
    """Link quotation/proforma/invoice rows into one group per deal.

    The input may contain any document types; non-pipeline documents are kept
    in their groups so callers can tell whether a pipeline group later became a
    won invoice.
    """
    docs = [doc for doc in documents if getattr(doc, "id", None) is not None]
    if not docs:
        return []

    sets = _DisjointSet()

    for doc in docs:
        doc_node = ("doc", doc.id)
        sets.add(doc_node)

        lead_id = getattr(doc, "lead_id", None)
        if lead_id:
            sets.union(doc_node, ("lead", lead_id))

        source_id = getattr(doc, "source_quotation_id", None)
        if source_id:
            sets.union(doc_node, ("doc", source_id))

        own_number = _normalize_doc_number(getattr(doc, "doc_number", None))
        if own_number:
            sets.union(doc_node, ("number", own_number))

        source_number = _normalize_doc_number(
            getattr(doc, "source_quotation_number", None)
        )
        if source_number:
            sets.union(doc_node, ("number", source_number))

    grouped = {}
    for doc in docs:
        root = sets.find(("doc", doc.id))
        grouped.setdefault(root, []).append(doc)

    return [DealGroup(group_docs) for group_docs in grouped.values()]


def open_pipeline_groups(
    deal_groups: Iterable[DealGroup],
    closed_lead_ids: Optional[Iterable[int]] = None,
    closed_invoice_ids: Optional[Iterable[int]] = None,
) -> List[DealGroup]:
    """Return the deal groups that are still in the open pipeline.

    A group is closed as soon as it contains a won lead or a confirmed invoice,
    so its earlier quotation/proforma can never appear as an extra open deal.
    """
    closed_lead_set = {
        lead_id for lead_id in (closed_lead_ids or []) if lead_id
    }
    closed_invoice_set = {
        invoice_id for invoice_id in (closed_invoice_ids or []) if invoice_id
    }

    result = []
    for group in deal_groups:
        if group.lead_id is not None and group.lead_id in closed_lead_set:
            continue
        if any(doc_id in closed_invoice_set for doc_id in group.doc_ids):
            continue
        if group.best_pipeline_document() is not None:
            result.append(group)
    return result
