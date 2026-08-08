"""Query classifier – determines query type for optimal retrieval strategy."""

from __future__ import annotations

import re
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class QueryType(str, Enum):
    LOOKUP = "lookup"           # Specific fact: "What is my PAN number?"
    SYNTHESIS = "synthesis"     # Summary: "Summarize my insurance policy"
    COMPARISON = "comparison"   # Compare: "Compare Resume V1 with Resume V2"
    LISTING = "listing"         # List: "Show all tax documents"
    HELP = "help"               # Meta: "What prompts can I ask?"
    GENERAL = "general"         # General chat


_COMPARISON_PATTERNS = [
    r"\bcompar[ei]\b", r"\bdifferen[ct]", r"\bvs\.?\b", r"\bversus\b",
    r"\bbetween\b.*\band\b",
]

# Only "list my documents" style — bare "list out top 10 risks" is content, not inventory.
_LISTING_PATTERNS = [
    r"\blist\s+(?:all\s+)?(?:my\s+)?(?:\w+\s+){0,3}documents?\b",
    r"\bshow\s+all\b.*\bdocuments?\b",
    r"\ball\s+(?:my\s+)?documents?\b",
    r"\bwhat\s+documents?\b",
    r"\bhow\s+many\s+documents?\b",
    r"\bwhich\s+documents?\b",
]

_LOOKUP_PATTERNS = [
    r"\bwhat\s+is\s+my\b", r"\bwhat'?s\s+my\b", r"\bmy\s+\w+\s+number\b",
    r"\bexpir(?:y|e|es|ing)\b", r"\bvalid\s+(?:till|until|through)\b",
    r"\bdate\s+of\b", r"\bname\s+on\b",
]

_SYNTHESIS_PATTERNS = [
    r"\bsummari[sz]e\b", r"\bsummary\b", r"\boverview\b",
    r"\bexplain\b", r"\bdescribe\b", r"\bbreak\s*down\b",
]

_HELP_PATTERNS = [
    r"\bsuggest(?:\s+\w+){0,4}\s+prompts?\b",
    r"\bprompts?\s+(?:i\s+can|can\s+i|to\s+(?:ask|use|try))\b",
    r"\bwhat\s+(?:can|should)\s+i\s+(?:ask|query)\b",
    r"\bhow\s+(?:do\s+i|to)\s+(?:use|ask|query)\b",
    r"\bexample\s+(?:questions?|prompts?)\b",
    r"\bwhat\s+(?:questions?|prompts?)\s+(?:can|should)\b",
    r"\bhelp\s+me\s+(?:ask|get\s+started)\b",
]


def classify_query(query: str) -> QueryType:
    """Classify the user query into a QueryType for retrieval strategy selection."""
    q = query.lower().strip()

    for pattern in _HELP_PATTERNS:
        if re.search(pattern, q):
            logger.debug("query_classified", query_type=QueryType.HELP, query=query[:80])
            return QueryType.HELP

    for pattern in _COMPARISON_PATTERNS:
        if re.search(pattern, q):
            logger.debug("query_classified", query_type=QueryType.COMPARISON, query=query[:80])
            return QueryType.COMPARISON

    for pattern in _LISTING_PATTERNS:
        if re.search(pattern, q):
            logger.debug("query_classified", query_type=QueryType.LISTING, query=query[:80])
            return QueryType.LISTING

    for pattern in _LOOKUP_PATTERNS:
        if re.search(pattern, q):
            logger.debug("query_classified", query_type=QueryType.LOOKUP, query=query[:80])
            return QueryType.LOOKUP

    for pattern in _SYNTHESIS_PATTERNS:
        if re.search(pattern, q):
            logger.debug("query_classified", query_type=QueryType.SYNTHESIS, query=query[:80])
            return QueryType.SYNTHESIS

    logger.debug("query_classified", query_type=QueryType.GENERAL, query=query[:80])
    return QueryType.GENERAL
