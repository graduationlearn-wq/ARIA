"""
Knowledge Base Lookup.

Simple keyword-based search for Phase 1.
In Phase 3 this gets upgraded to vector similarity search (embeddings).
"""

from sqlalchemy.orm import Session
from models.knowledge_base import KnowledgeBase


def search_kb(query: str, db: Session, max_results: int = 3) -> list[KnowledgeBase]:
    """
    Search the knowledge base for entries relevant to the query.
    Returns active, non-placeholder entries sorted by relevance.

    Phase 1 strategy: count how many words from the query appear in the question.
    Phase 3 upgrade: replace with cosine similarity on sentence embeddings.
    """
    query_words = set(query.lower().split())

    # Fetch all active, ready entries
    entries = db.query(KnowledgeBase).filter(
        KnowledgeBase.active == True,           # noqa: E712
        KnowledgeBase.is_placeholder == False,  # noqa: E712
    ).all()

    if not entries:
        return []

    # Score each entry by word overlap
    scored = []
    for entry in entries:
        entry_words = set(entry.question.lower().split())
        overlap = len(query_words & entry_words)
        if overlap > 0:
            scored.append((overlap, entry))

    # Sort by score descending, return top results
    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:max_results]]


def get_answer_for_intent(intent_label: str, db: Session) -> KnowledgeBase | None:
    """
    Map a specific intent to the most relevant KB category and return
    the best matching entry.
    """
    intent_to_category = {
        "pricing_query":    "Pricing & Plans",
        "feature_query":    "Features",
        "onboarding_query": "Onboarding & Setup",
        "objection_cost":   "Objection Handling",
        "objection_timing": "Objection Handling",
        "objection_switching": "Objection Handling",
    }
    category = intent_to_category.get(intent_label)
    if not category:
        return None

    return db.query(KnowledgeBase).filter(
        KnowledgeBase.category == category,
        KnowledgeBase.active == True,           # noqa: E712
        KnowledgeBase.is_placeholder == False,  # noqa: E712
    ).first()
