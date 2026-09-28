"""
backend/schema_mapping package

TERRANODE FEATURE 01: SMART SCHEMA MAPPING
"""

from backend.schema_mapping.mapping_models import (
    CanonicalField,
    MappingStatus,
    MatchType,
    FieldMappingSuggestion,
    SchemaMappingRequest,
    SchemaMappingResponse,
    ConfirmMappingRequest,
    ConfirmedSchemaRecord,
)
from backend.schema_mapping.field_dictionary import (
    CANONICAL_DICTIONARY,
    COMMON_ABBREVIATIONS,
    CanonicalFieldDefinition,
)
from backend.schema_mapping.schema_mapper import (
    SmartSchemaMapper,
    normalize_field_name,
    score_field_similarity,
    AUTO_SUGGEST_THRESHOLD,
    CANDIDATE_MIN_THRESHOLD,
)
from backend.schema_mapping.mapping_service import (
    SchemaMappingService,
)

__all__ = [
    "CanonicalField",
    "MappingStatus",
    "MatchType",
    "FieldMappingSuggestion",
    "SchemaMappingRequest",
    "SchemaMappingResponse",
    "ConfirmMappingRequest",
    "ConfirmedSchemaRecord",
    "CANONICAL_DICTIONARY",
    "COMMON_ABBREVIATIONS",
    "CanonicalFieldDefinition",
    "SmartSchemaMapper",
    "normalize_field_name",
    "score_field_similarity",
    "AUTO_SUGGEST_THRESHOLD",
    "CANDIDATE_MIN_THRESHOLD",
    "SchemaMappingService",
]
