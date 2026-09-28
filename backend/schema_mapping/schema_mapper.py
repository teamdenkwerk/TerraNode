"""
backend/schema_mapping/schema_mapper.py

TERRANODE FEATURE 01: SMART SCHEMA MAPPER ENGINE

Normalizes raw source column names, evaluates semantic and abbreviation equivalence,
calculates sound mathematical mapping confidence without fabrication,
and flags low-confidence or conflicting candidate mappings.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.schema_mapping.field_dictionary import (
    CANONICAL_DICTIONARY,
    COMMON_ABBREVIATIONS,
    CanonicalField,
    CanonicalFieldDefinition,
)
from backend.schema_mapping.mapping_models import (
    FieldMappingSuggestion,
    MappingStatus,
    MatchType,
)

logger = logging.getLogger(__name__)

# Minimum confidence threshold to recommend automatic mapping without low-confidence warning
AUTO_SUGGEST_THRESHOLD = 0.75
# Minimum confidence threshold to consider even a weak/low-confidence candidate
CANDIDATE_MIN_THRESHOLD = 0.40


def normalize_field_name(raw_name: str) -> str:
    """
    Normalizes a column name:
    1. Lowercase
    2. Convert camelCase / PascalCase to snake_case
    3. Strip non-alphanumeric punctuation (replace with spaces or underscores)
    4. Tokenize and expand domain abbreviations
    """
    if not raw_name:
        return ""

    s = str(raw_name).strip()

    # Split camelCase / PascalCase: e.g. "surveyNo" -> "survey No"
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = s.lower()

    # Replace punctuation / special symbols with underscores
    s = re.sub(r"[^\w\s]", "_", s)
    tokens = [t for t in re.split(r"[_\s]+", s) if t]

    # Expand abbreviations
    expanded_tokens = []
    for token in tokens:
        expanded = COMMON_ABBREVIATIONS.get(token, token)
        expanded_tokens.append(expanded)

    return "_".join(expanded_tokens)


def _token_jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    inter = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    return inter / union if union > 0 else 0.0


def score_field_similarity(
    raw_source_field: str,
    normalized_source_field: str,
    canonical_def: CanonicalFieldDefinition,
) -> Tuple[float, MatchType, str]:
    """
    Computes deterministic mapping confidence between a source field and a canonical definition.
    Zero fabrication: derived from exact match, synonym dictionary, abbreviation expansion,
    token overlap, and string distance ratio.
    """
    raw_lower = raw_source_field.lower().strip()
    canon_name = canonical_def.field_name.value
    synonyms = canonical_def.synonyms

    # 1. Exact match on canonical field name
    if raw_lower == canon_name or normalized_source_field == canon_name:
        return 1.0, MatchType.EXACT, f"Exact match with canonical field '{canon_name}'"

    # 2. Exact match with known synonym list
    if raw_lower in synonyms or normalized_source_field in synonyms:
        return 0.95, MatchType.SYNONYM, f"Direct synonym match with domain term in '{canon_name}' registry"

    # 3. Normalized abbreviation expansion match
    # Check if replacing abbreviations in raw produces a canonical synonym
    raw_no_punct = re.sub(r"[^\w]", "", raw_lower)
    canon_no_punct = re.sub(r"[^\w]", "", canon_name)
    if raw_no_punct == canon_no_punct:
        return 0.92, MatchType.EXACT, f"Character-identical match ignoring punctuation"

    for syn in synonyms:
        syn_no_punct = re.sub(r"[^\w]", "", syn)
        if raw_no_punct == syn_no_punct:
            return 0.90, MatchType.SYNONYM, f"Synonym match ignoring punctuation with '{syn}'"

    # 4. Token overlap similarity
    source_tokens = set(normalized_source_field.split("_"))
    canon_tokens = set(canon_name.split("_"))
    jaccard = _token_jaccard_similarity(source_tokens, canon_tokens)

    # Check jaccard against any multi-token synonym
    best_syn_jaccard = jaccard
    best_matching_syn = canon_name
    for syn in synonyms:
        syn_tokens = set(syn.split("_"))
        sj = _token_jaccard_similarity(source_tokens, syn_tokens)
        if sj > best_syn_jaccard:
            best_syn_jaccard = sj
            best_matching_syn = syn

    if best_syn_jaccard >= 0.70:
        conf = round(0.75 + 0.15 * best_syn_jaccard, 3)
        return conf, MatchType.TOKEN_OVERLAP, f"High token alignment ({int(best_syn_jaccard*100)}%) with synonym '{best_matching_syn}'"

    # 5. Fuzzy string distance (difflib SequenceMatcher / Ratcliff-Obershelp)
    ratio = difflib.SequenceMatcher(None, normalized_source_field, canon_name).ratio()
    for syn in synonyms:
        r = difflib.SequenceMatcher(None, normalized_source_field, syn).ratio()
        if r > ratio:
            ratio = r
            best_matching_syn = syn

    if ratio >= 0.75:
        # Scale to max 0.74 so fuzzy matches without exact tokens are marked low-confidence
        conf = round(ratio * 0.85, 3)
        return conf, MatchType.FUZZY_STRING, f"Fuzzy morphological similarity ({int(ratio*100)}%) with '{best_matching_syn}'"

    if best_syn_jaccard >= 0.40:
        conf = round(0.40 + 0.20 * best_syn_jaccard, 3)
        return conf, MatchType.TOKEN_OVERLAP, f"Partial token overlap with '{best_matching_syn}'"

    if ratio >= 0.55:
        conf = round(ratio * 0.70, 3)
        return conf, MatchType.FUZZY_STRING, f"Weak string resemblance to '{best_matching_syn}'"

    return 0.0, MatchType.UNKNOWN, "No semantic or lexical relationship detected"


class SmartSchemaMapper:
    """
    Orchestrates schema inspection, normalization, candidate evaluation,
    confidence scoring, and conflict arbitration.
    """

    def map_columns(
        self,
        columns: List[str],
        sample_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[FieldMappingSuggestion]:
        raw_suggestions: List[FieldMappingSuggestion] = []

        # Step 1: Evaluate each column against all canonical fields
        for col in columns:
            normalized = normalize_field_name(col)

            # Sample values preview
            samples = []
            if sample_records:
                for rec in sample_records[:3]:
                    val = rec.get(col)
                    if val is not None and str(val).strip():
                        samples.append(val)

            best_field: Optional[CanonicalField] = None
            best_score: float = 0.0
            best_match_type: MatchType = MatchType.UNKNOWN
            best_reason: str = "Unknown field"

            for c_enum, c_def in CANONICAL_DICTIONARY.items():
                score, m_type, reason = score_field_similarity(col, normalized, c_def)
                if score > best_score:
                    best_score = score
                    best_field = c_enum
                    best_match_type = m_type
                    best_reason = reason

            # Status determination
            if best_score >= AUTO_SUGGEST_THRESHOLD:
                status = MappingStatus.SUGGESTED
                is_low_conf = False
                canonical_str = best_field.value if best_field else None
            elif best_score >= CANDIDATE_MIN_THRESHOLD:
                status = MappingStatus.LOW_CONFIDENCE
                is_low_conf = True
                canonical_str = best_field.value if best_field else None
                best_reason = f"Low confidence match ({int(best_score*100)}%): {best_reason}. Requires manual officer review."
            else:
                status = MappingStatus.UNMAPPED
                is_low_conf = False
                canonical_str = None
                best_reason = f"Unmapped field: No confident semantic equivalent in canonical schema."

            raw_suggestions.append(
                FieldMappingSuggestion(
                    source_field=col,
                    normalized_source_field=normalized,
                    suggested_canonical_field=canonical_str,
                    confidence=round(best_score, 3),
                    match_type=best_match_type,
                    status=status,
                    is_low_confidence=is_low_conf,
                    is_conflicting=False,
                    sample_values=samples,
                    decision_reason=best_reason,
                )
            )

        # Step 2: Detect & Resolve Conflicting Mappings
        # e.g., if multiple source fields mapped to the same canonical field
        canonical_usage: Dict[str, List[int]] = {}
        for idx, sugg in enumerate(raw_suggestions):
            if sugg.suggested_canonical_field and sugg.status in (MappingStatus.SUGGESTED, MappingStatus.LOW_CONFIDENCE):
                c_field = sugg.suggested_canonical_field
                canonical_usage.setdefault(c_field, []).append(idx)

        for c_field, indices in canonical_usage.items():
            if len(indices) > 1:
                # Multiple source columns claimed the same canonical field!
                # Sort by confidence descending
                sorted_by_conf = sorted(indices, key=lambda i: raw_suggestions[i].confidence, reverse=True)
                winner_idx = sorted_by_conf[0]
                runner_up_indices = sorted_by_conf[1:]

                for r_idx in runner_up_indices:
                    competing = raw_suggestions[r_idx]
                    competing.is_conflicting = True
                    competing.status = MappingStatus.CONFLICTING
                    competing.decision_reason = (
                        f"Conflicting mapping: Canonical field '{c_field}' is also claimed by '{raw_suggestions[winner_idx].source_field}' "
                        f"(confidence {raw_suggestions[winner_idx].confidence*100:.1f}%). Officer confirmation required."
                    )

        return raw_suggestions
