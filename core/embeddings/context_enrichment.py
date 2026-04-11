"""
Index-time enrichment for RAG chunks.

Programmatic context injection — heading detection, keyword extraction, adjacent context
Entity NER metadata — spaCy-based entity extraction
Entity profiles — aggregate entity mentions into profile chunks
Triple extraction — entity-relation triples from co-occurring NER entities
"""

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

# ── Stop words for keyword extraction ──
_STOP_WORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "this", "that",
        "these", "those", "it", "its", "not", "no", "nor", "as", "if", "then",
        "than", "too", "very", "just", "about", "above", "below", "between",
        "into", "through", "during", "before", "after", "up", "down", "out",
        "off", "over", "under", "again", "further", "once", "here", "there",
        "when", "where", "why", "how", "all", "each", "every", "both", "few",
        "more", "most", "other", "some", "such", "only", "own", "same", "so",
        "also", "any", "many", "much", "which", "who", "whom", "what",
        # Noise from search_document prefix
        "search_document", "document", "page",
    }
)


# ── Programmatic Context Injection ──


def extract_document_keywords(full_text: str, top_n: int = 8) -> List[str]:
    """Extract top keywords from document text using term frequency."""
    if not full_text:
        return []
    words = re.findall(r"\b[a-zA-Z]{3,}\b", full_text.lower())
    word_counts: Dict[str, int] = {}
    for w in words:
        if w not in _STOP_WORDS:
            word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]


def detect_page_heading(page_text: str) -> str:
    """
    Detect section heading from the beginning of page text using heuristics.

    Looks for:
    - Numbered sections (e.g., "1.1 Introduction")
    - ALL CAPS lines
    - Short title-case lines without trailing punctuation
    """
    if not page_text:
        return ""
    lines = page_text.strip().split("\n")
    for line in lines[:5]:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # Skip very long lines (not headings)
        if len(line) > 120:
            continue
        # Numbered section (e.g., "1.1 Introduction", "Chapter 3")
        if re.match(r"^(\d+[\.\)]\s|chapter\s+\d+|section\s+\d+)", line, re.IGNORECASE):
            return line[:100]
        # ALL CAPS line (common heading style)
        if line.isupper() and len(line) > 3 and len(line) < 80:
            return line
        # Short line without ending punctuation (likely a heading)
        if len(line) < 80 and line[-1] not in ".,;:!?)\"'":
            return line
        # Only check the first non-empty candidate
        break
    return ""


def get_adjacent_sentences(
    chunks: List[str], idx: int, has_nltk: bool = True
) -> str:
    """
    Get trailing sentence of previous chunk and leading sentence of next chunk.
    Provides continuity context without full chunk duplication.
    """
    parts = []
    try:
        if has_nltk:
            from nltk.tokenize import sent_tokenize
        else:
            sent_tokenize = None
    except ImportError:
        sent_tokenize = None

    if idx > 0 and chunks[idx - 1].strip():
        if sent_tokenize:
            prev_sents = sent_tokenize(chunks[idx - 1])
            if prev_sents:
                parts.append(f"...{prev_sents[-1][:100]}")
        else:
            parts.append(f"...{chunks[idx - 1][-100:]}")

    if idx < len(chunks) - 1 and chunks[idx + 1].strip():
        if sent_tokenize:
            next_sents = sent_tokenize(chunks[idx + 1])
            if next_sents:
                parts.append(f"{next_sents[0][:100]}...")
        else:
            parts.append(f"{chunks[idx + 1][:100]}...")

    return " | ".join(parts) if parts else ""


def build_enriched_chunk(
    chunk_text: str,
    doc_title: str,
    page_no: int,
    total_pages: int,
    heading: str,
    keywords: List[str],
    adjacent_ctx: str,
    search_prefix: str = "search_document: ",
) -> str:
    """
    Build an enriched chunk with programmatic context injection.

    Format:
        search_document: Document: {title} | Page {page}/{total}[ | Section: {heading}]
        [Topics: {keywords}]
        [Context: {adjacent}]

        {chunk_text}
    """
    header = f"{search_prefix}Document: {doc_title} | Page {page_no}/{total_pages}"
    if heading:
        header += f" | Section: {heading}"

    parts = [header]
    if keywords:
        parts.append(f"Topics: {', '.join(keywords)}")
    if adjacent_ctx:
        parts.append(f"Context: {adjacent_ctx}")

    parts.append("")  # blank line before content
    parts.append(chunk_text)
    return "\n".join(parts)


# ── Entity NER ──

_nlp = None
_NER_AVAILABLE = None


def _load_spacy():
    """Lazy-load spaCy NER model."""
    global _nlp, _NER_AVAILABLE
    if _NER_AVAILABLE is not None:
        return _NER_AVAILABLE

    try:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        except OSError:
            print(
                "[NER] spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
            _NER_AVAILABLE = False
            return False
        _NER_AVAILABLE = True
        print("[NER] spaCy NER model loaded successfully.")
        return True
    except ImportError:
        print("[NER] spaCy not installed. Entity extraction disabled.")
        _NER_AVAILABLE = False
        return False


def extract_entities(text: str) -> Tuple[List[str], List[str]]:
    """
    Extract named entities from text using spaCy NER.

    Returns:
        Tuple of (entity_names, entity_types) — both as lists of strings.
        Entity names are deduplicated and normalized.
    """
    if not _load_spacy() or not text:
        return [], []

    # Limit text length for NER performance (spaCy handles up to ~1M chars but slower)
    doc = _nlp(text[:5000])

    seen = set()
    names = []
    types = []
    # Entity types we care about for RAG
    relevant_types = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "FAC", "NORP", "LOC", "MONEY", "DATE"}

    for ent in doc.ents:
        if ent.label_ not in relevant_types:
            continue
        # Normalize: strip whitespace, collapse internal spaces
        name = " ".join(ent.text.split())
        if len(name) < 2 or name.lower() in _STOP_WORDS:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            names.append(name)
            types.append(ent.label_)

    return names, types


def extract_entities_for_metadata(text: str) -> Dict[str, str]:
    """
    Extract entities and return as ChromaDB-compatible metadata fields.

    Returns dict with:
        - "entities": pipe-separated entity names (e.g., "Acme Corp|John Smith")
        - "entity_types": pipe-separated entity types (e.g., "ORG|PERSON")

    Returns empty dict if NER is unavailable or no entities found.
    """
    names, types = extract_entities(text)
    if not names:
        return {}

    # Limit to top 15 entities per chunk to keep metadata manageable
    names = names[:15]
    types = types[:15]

    return {
        "entities": "|".join(names),
        "entity_types": "|".join(types),
    }


def extract_query_entities(query: str) -> List[str]:
    """
    Extract entity names from a user query for retrieval boosting.

    Only returns high-signal entity types (PERSON, ORG, GPE, PRODUCT, EVENT,
    WORK_OF_ART, LAW, FAC). Excludes DATE, MONEY, LOC, NORP to avoid
    broad/noisy boosts from common terms like years or currency amounts.
    """
    if not _load_spacy() or not query:
        return []

    doc = _nlp(query[:2000])

    # High-signal types for query boosting — skip DATE, MONEY, LOC, NORP
    boost_types = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "FAC"}

    seen = set()
    names = []
    for ent in doc.ents:
        if ent.label_ not in boost_types:
            continue
        name = " ".join(ent.text.split())
        if len(name) < 2 or name.lower() in _STOP_WORDS:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            names.append(name)

    return names


# ── Synonym expansion for retrieval boosting ──

_SYNONYM_MAP: Dict[str, List[str]] = {
    "deliverables": ["objectives", "outcomes", "outputs", "milestones", "results"],
    "objectives": ["deliverables", "goals", "targets", "aims"],
    "goals": ["objectives", "targets", "aims", "outcomes"],
    "targets": ["goals", "objectives", "benchmarks", "milestones"],
    "revenue": ["income", "earnings", "sales", "turnover"],
    "income": ["revenue", "earnings", "profit"],
    "expenses": ["costs", "expenditure", "spending", "outlays"],
    "costs": ["expenses", "expenditure", "spending"],
    "profit": ["earnings", "income", "net income", "margin"],
    "strategy": ["plan", "approach", "roadmap", "framework"],
    "plan": ["strategy", "roadmap", "blueprint", "proposal"],
    "risks": ["threats", "challenges", "issues", "vulnerabilities"],
    "challenges": ["risks", "issues", "obstacles", "problems"],
    "stakeholders": ["partners", "participants", "collaborators"],
    "requirements": ["specifications", "criteria", "needs"],
    "specifications": ["requirements", "specs", "criteria"],
    "timeline": ["schedule", "milestones", "deadlines", "timeframe"],
    "schedule": ["timeline", "timetable", "deadlines"],
    "budget": ["funding", "allocation", "financial plan", "costs"],
    "performance": ["results", "metrics", "outcomes", "kpis"],
    "metrics": ["kpis", "measures", "indicators", "benchmarks"],
    "recommendations": ["suggestions", "proposals", "actions"],
    "findings": ["results", "conclusions", "outcomes", "observations"],
    "scope": ["coverage", "extent", "boundaries", "range"],
    "compliance": ["adherence", "conformance", "regulatory"],
    "assessment": ["evaluation", "analysis", "review", "appraisal"],
    "evaluation": ["assessment", "analysis", "review", "appraisal"],
}


def expand_keywords_with_synonyms(keywords: List[str]) -> List[str]:
    """
    Expand a list of keywords with synonyms for broader retrieval matching.

    Returns the original keywords plus any known synonyms, deduplicated.
    """
    expanded = set()
    for kw in keywords:
        kw_lower = kw.lower().strip()
        expanded.add(kw_lower)
        if kw_lower in _SYNONYM_MAP:
            expanded.update(_SYNONYM_MAP[kw_lower])

    return list(expanded)


def extract_query_keywords(query: str) -> List[str]:
    """
    Extract meaningful keywords (nouns, proper nouns) from a query for
    entity-keyword hybrid boosting. Falls back to simple word extraction
    if spaCy is unavailable.
    """
    if not query:
        return []

    if _load_spacy():
        doc = _nlp(query[:2000])
        keywords = []
        for token in doc:
            # Keep nouns, proper nouns, and adjectives that aren't stop words
            if (
                token.pos_ in ("NOUN", "PROPN")
                and token.text.lower() not in _STOP_WORDS
                and len(token.text) >= 3
            ):
                keywords.append(token.text.lower())
        return keywords

    # Fallback: simple word extraction
    words = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
    return [w for w in words if w not in _STOP_WORDS]


# ── Triple Extraction ──


def extract_entity_triples(text: str) -> List[Dict[str, str]]:
    """
    Extract (subject, predicate, object) triples between named entities
    co-occurring in the same sentence.

    Uses NLTK for sentence splitting and spaCy NER for entity detection.
    The predicate is the connecting text between two entities in a sentence.

    Returns:
        List of dicts with keys: subject, predicate, object
    """
    if not _load_spacy() or not text:
        return []

    # Use NLTK for sentence splitting (lighter than spaCy parser)
    try:
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(text[:5000])
    except ImportError:
        # Fallback: split on period+space
        sentences = [s.strip() for s in text[:5000].split(". ") if s.strip()]

    relevant_types = {
        "PERSON", "ORG", "GPE", "PRODUCT", "EVENT",
        "WORK_OF_ART", "LAW", "FAC", "NORP", "LOC",
    }

    triples = []
    for sent in sentences:
        if len(sent) < 10:
            continue

        doc = _nlp(sent)
        sent_entities = [
            ent for ent in doc.ents
            if ent.label_ in relevant_types and len(ent.text.strip()) >= 2
        ]

        if len(sent_entities) < 2:
            continue

        # For each nearby entity pair, extract the connecting text as predicate
        for i in range(len(sent_entities)):
            for j in range(i + 1, min(i + 3, len(sent_entities))):
                ent1 = sent_entities[i]
                ent2 = sent_entities[j]

                # Get text between the two entities
                start = ent1.end_char
                end = ent2.start_char
                between = sent[start:end].strip(" ,;:")

                # Filter: predicate should be short and meaningful
                if not between or len(between) > 80 or len(between) < 2:
                    continue

                # Skip if predicate is just punctuation/whitespace
                if not any(c.isalpha() for c in between):
                    continue

                triples.append(
                    {
                        "subject": ent1.text.strip(),
                        "predicate": between,
                        "object": ent2.text.strip(),
                    }
                )

    return triples


# ── Entity Profiles ──


def build_entity_profiles(
    entity_mentions: List[Dict],
    doc_title: str,
    max_profiles: int = 10,
    max_context_per_entity: int = 3,
    search_prefix: str = "search_document: ",
) -> List[Tuple[str, Dict[str, str]]]:
    """
    Build entity profile chunks from aggregated entity mentions across a document.

    Entity profiles are synthetic chunks that summarize where and how an entity
    appears across the document, naturally retrieved for entity-relationship queries.

    Args:
        entity_mentions: List of dicts with keys: name, type, chunk_text, page_no
        doc_title: Document title for the profile header
        max_profiles: Maximum number of entity profiles to generate
        max_context_per_entity: Max context excerpts per entity
        search_prefix: Embedding prefix for search

    Returns:
        List of (profile_text, extra_metadata) tuples
    """
    if not entity_mentions:
        return []

    # Group mentions by normalized entity name
    entity_data: Dict[str, Dict] = {}
    for mention in entity_mentions:
        key = mention["name"].lower()
        if key not in entity_data:
            entity_data[key] = {
                "name": mention["name"],
                "type": mention["type"],
                "pages": set(),
                "contexts": [],
            }
        entity_data[key]["pages"].add(mention["page_no"])

        # Collect context excerpts (window around entity mention)
        if len(entity_data[key]["contexts"]) < max_context_per_entity:
            chunk_text = mention["chunk_text"]
            idx = chunk_text.lower().find(mention["name"].lower())
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(chunk_text), idx + len(mention["name"]) + 60)
                context = chunk_text[start:end].strip()
                if context:
                    entity_data[key]["contexts"].append(context)

    # Sort by cross-page spread (entities on more pages → more profile-worthy)
    sorted_entities = sorted(
        entity_data.values(),
        key=lambda x: len(x["pages"]),
        reverse=True,
    )[:max_profiles]

    profiles = []
    for ent in sorted_entities:
        # Only profile entities mentioned on 2+ pages
        if len(ent["pages"]) < 2:
            continue

        pages_str = ", ".join(str(p) for p in sorted(ent["pages"]))
        contexts_str = " ... ".join(ent["contexts"])

        profile_text = (
            f"{search_prefix}Entity Profile: {ent['name']} ({ent['type']}) | "
            f"Document: {doc_title}\n"
            f"Mentioned on pages: {pages_str}\n"
            f"Contexts: {contexts_str}"
        )

        extra_metadata = {
            "chunk_type": "entity_profile",
            "entity_name": ent["name"],
            "entities": ent["name"],  # searchable via entity boosting
            "entity_types": ent["type"],
        }
        profiles.append((profile_text, extra_metadata))

    return profiles


# ── Document Summary for Index ──


def build_extractive_summary(full_text: str, title: str, max_chars: int = 500) -> str:
    """
    Build a simple extractive summary from document text.
    Uses the first few sentences that fit within max_chars.
    Falls back to truncation if sentence tokenization unavailable.
    """
    if not full_text:
        return f"Document: {title}"

    try:
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(full_text[:3000])  # only look at first ~3000 chars
        summary_parts = []
        total = 0
        for sent in sentences:
            if total + len(sent) > max_chars:
                break
            summary_parts.append(sent)
            total += len(sent)
        summary = " ".join(summary_parts) if summary_parts else full_text[:max_chars]
    except ImportError:
        summary = full_text[:max_chars]

    return f"Document: {title}\nSummary: {summary}"
