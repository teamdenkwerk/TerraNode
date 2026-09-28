"""
backend/schema_mapping/field_dictionary.py

TERRANODE FEATURE 01: CONFIGURABLE SEMANTIC FIELD DICTIONARY

Contains the canonical dictionary of attributes, normalized synonym mappings,
and domain abbreviations for Indian and global land administration systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set
from backend.schema_mapping.mapping_models import CanonicalField


@dataclass(frozen=True)
class CanonicalFieldDefinition:
    field_name: CanonicalField
    display_title: str
    description: str
    data_type: str
    synonyms: Set[str]
    sample_patterns: List[str] = field(default_factory=list)


# Domain-specific abbreviations to expand during normalization
COMMON_ABBREVIATIONS: Dict[str, str] = {
    "no": "number",
    "num": "number",
    "nbr": "number",
    "cd": "code",
    "id": "identifier",
    "ident": "identifier",
    "dt": "date",
    "prop": "property",
    "prpty": "property",
    "surv": "survey",
    "sy": "survey",
    "parc": "parcel",
    "pcl": "parcel",
    "lat": "latitude",
    "lon": "longitude",
    "lng": "longitude",
    "long": "longitude",
    "geom": "geometry",
    "shp": "geometry",
    "sqm": "area",
    "sqft": "area",
    "sq_m": "area",
    "own": "owner",
    "ownr": "owner",
    "bld": "building",
    "bldg": "building",
    "src": "source",
    "cts": "cadastral",
    "ref": "reference",
}


# Authoritative Canonical Dictionary definitions
CANONICAL_DICTIONARY: Dict[CanonicalField, CanonicalFieldDefinition] = {
    CanonicalField.PARCEL_ID: CanonicalFieldDefinition(
        field_name=CanonicalField.PARCEL_ID,
        display_title="Parcel Identifier",
        description="Unique cadastral parcel identifier or primary key in land registry",
        data_type="string",
        synonyms={
            "parcel_id", "parcelid", "parcel_no", "parcel_number", "parcel_num",
            "pid", "cadastral_id", "cad_id", "khasra", "khasra_no", "khasra_number",
            "dag_no", "dag_number", "cts_no", "cts_number", "gis_id", "footprint_id",
            "canonical_uid", "bld_id", "building_id", "plot_id", "entity_uid",
        },
        sample_patterns=[r"^CAD-\d+", r"^PCL-\d+", r"^\d+/\d+"],
    ),

    CanonicalField.SURVEY_NUMBER: CanonicalFieldDefinition(
        field_name=CanonicalField.SURVEY_NUMBER,
        display_title="Survey Number",
        description="Official revenue department village or ward survey number / sub-division",
        data_type="string",
        synonyms={
            "survey_no", "survey_number", "surveyno", "surveynumber", "sy_no", "sy_number",
            "survey_num", "revenue_survey_no", "rev_survey_no", "plot_no", "plot_number",
            "plotno", "survey", "sy_num", "revenue_no", "sub_division_no", "hissa_no",
        },
        sample_patterns=[r"^\d+/\d+[A-Z]?", r"^\d+"],
    ),

    CanonicalField.PROPERTY_ID: CanonicalFieldDefinition(
        field_name=CanonicalField.PROPERTY_ID,
        display_title="Property Identifier",
        description="Municipal corporation municipal assessment number or property tax identifier",
        data_type="string",
        synonyms={
            "property_id", "property_no", "property_number", "property_num", "prop_id",
            "prpty_id", "assessment_no", "assessment_number", "upin", "property_code",
            "holding_no", "holding_number", "khata_no", "khata_number", "door_no",
            "municipal_id", "tax_id", "folio_no", "gis_pid",
        },
        sample_patterns=[r"^MUN-\d+", r"^PROP-\d+"],
    ),

    CanonicalField.AREA: CanonicalFieldDefinition(
        field_name=CanonicalField.AREA,
        display_title="Area Extent",
        description="Physical surface area of parcel or building in square meters or acres",
        data_type="numeric",
        synonyms={
            "area", "area_sqm", "area_m2", "area_sq_m", "area_sq_meter", "parcel_area",
            "gis_area", "shape_area", "extent", "extent_sqm", "builtup_area",
            "land_area", "plot_area", "sqm", "carpet_area", "st_area",
        },
    ),

    CanonicalField.GEOMETRY: CanonicalFieldDefinition(
        field_name=CanonicalField.GEOMETRY,
        display_title="Spatial Geometry",
        description="Vector polygon coordinates (WKT, GeoJSON, or binary shape)",
        data_type="geometry",
        synonyms={
            "geometry", "geom", "the_geom", "shape", "wkt", "coordinates",
            "polygon", "spatial_geom", "geo_shape", "footprint_geom",
        },
    ),

    CanonicalField.LATITUDE: CanonicalFieldDefinition(
        field_name=CanonicalField.LATITUDE,
        display_title="Centroid Latitude",
        description="Centroid or point latitude in geographic WGS84 degrees",
        data_type="numeric",
        synonyms={
            "latitude", "lat", "centroid_y", "y", "y_coord", "point_y",
            "lat_deg", "northing", "gps_lat", "center_lat",
        },
    ),

    CanonicalField.LONGITUDE: CanonicalFieldDefinition(
        field_name=CanonicalField.LONGITUDE,
        display_title="Centroid Longitude",
        description="Centroid or point longitude in geographic WGS84 degrees",
        data_type="numeric",
        synonyms={
            "longitude", "lon", "lng", "long", "centroid_x", "x", "x_coord",
            "point_x", "lon_deg", "easting", "gps_lon", "center_lng",
        },
    ),

    CanonicalField.SOURCE: CanonicalFieldDefinition(
        field_name=CanonicalField.SOURCE,
        display_title="Data Source Agency",
        description="Department, sensor, agency, or layer of origin",
        data_type="string",
        synonyms={
            "source", "dataset_source", "data_origin", "source_name", "provider",
            "layer_name", "agency", "department", "data_source", "origin", "captured_by",
        },
    ),

    CanonicalField.DATE: CanonicalFieldDefinition(
        field_name=CanonicalField.DATE,
        display_title="Survey / Acquisition Date",
        description="Date of capture, verification, or official notification",
        data_type="date",
        synonyms={
            "date", "captured_date", "survey_date", "creation_date", "timestamp",
            "update_date", "upload_date", "valid_from", "effective_date", "as_of_date",
        },
    ),

    CanonicalField.OWNER_REFERENCE: CanonicalFieldDefinition(
        field_name=CanonicalField.OWNER_REFERENCE,
        display_title="Owner Reference",
        description="Name of title holder, proprietor, or khatedar",
        data_type="string",
        synonyms={
            "owner_name", "owner_reference", "proprietor", "holder_name", "applicant_name",
            "owner", "ownership_ref", "khatedar", "pattadar", "title_holder", "occupant_name",
        },
    ),

    CanonicalField.SURVEY_IDENTIFIER: CanonicalFieldDefinition(
        field_name=CanonicalField.SURVEY_IDENTIFIER,
        display_title="Survey Identifier",
        description="Official revenue survey number or sub-division identifier",
        data_type="string",
        synonyms={
            "survey_no", "survey_number", "surveyno", "surveynumber", "sy_no", "survey_id",
            "surv_id", "survey_ident", "khasra", "khasra_no", "dag_no", "fmb_no",
        },
    ),

    CanonicalField.PROPERTY_IDENTIFIER: CanonicalFieldDefinition(
        field_name=CanonicalField.PROPERTY_IDENTIFIER,
        display_title="Property Identifier",
        description="Municipal corporation assessment number or property tax ID",
        data_type="string",
        synonyms={
            "property_id", "property_no", "property_number", "prop_id", "upin",
            "holding_no", "khata_no", "assessment_no", "gis_pid", "municipal_id",
        },
    ),

    CanonicalField.OWNER_NAME: CanonicalFieldDefinition(
        field_name=CanonicalField.OWNER_NAME,
        display_title="Owner Name",
        description="Authoritative name of property owner, pattadar, or holder",
        data_type="string",
        synonyms={
            "owner", "owner_name", "property_owner", "land_holder", "pattadar",
            "holder_name", "proprietor", "khatedar", "title_holder",
        },
    ),

    CanonicalField.LAND_USE: CanonicalFieldDefinition(
        field_name=CanonicalField.LAND_USE,
        display_title="Land Use Category",
        description="Zoning classification (Commercial, Residential, Mixed, Institutional)",
        data_type="string",
        synonyms={
            "land_use", "landuse", "zoning", "use_type", "zone_classification", "use_category",
        },
    ),

    CanonicalField.LOCALITY: CanonicalFieldDefinition(
        field_name=CanonicalField.LOCALITY,
        display_title="Locality / Sector",
        description="Neighborhood, revenue village, or administrative sector name",
        data_type="string",
        synonyms={
            "locality", "neighborhood", "area_name", "village", "sector", "colony", "mohalla",
        },
    ),

    CanonicalField.WARD: CanonicalFieldDefinition(
        field_name=CanonicalField.WARD,
        display_title="Ward Name / Number",
        description="Municipal administrative ward boundary number or name",
        data_type="string",
        synonyms={
            "ward", "ward_no", "ward_number", "ward_id", "ward_name", "municipal_ward",
        },
    ),

    CanonicalField.ZONE: CanonicalFieldDefinition(
        field_name=CanonicalField.ZONE,
        display_title="Zone / District",
        description="Municipal corporation administrative zone or revenue district",
        data_type="string",
        synonyms={
            "zone", "zone_name", "district", "revenue_district", "sub_district", "taluk",
        },
    ),

    CanonicalField.SOURCE_RECORD_ID: CanonicalFieldDefinition(
        field_name=CanonicalField.SOURCE_RECORD_ID,
        display_title="Source Record ID",
        description="Original primary key or identifier within the ingested source dataset",
        data_type="string",
        synonyms={
            "source_record_id", "source_id", "original_id", "record_id", "raw_id", "external_id",
        },
    ),

    CanonicalField.VALID_FROM: CanonicalFieldDefinition(
        field_name=CanonicalField.VALID_FROM,
        display_title="Valid From Date",
        description="Effective start date of legal tenure or record validity",
        data_type="date",
        synonyms={
            "valid_from", "effective_from", "start_date", "tenure_start", "registered_date",
        },
    ),

    CanonicalField.VALID_TO: CanonicalFieldDefinition(
        field_name=CanonicalField.VALID_TO,
        display_title="Valid To Date",
        description="Effective expiration date or supersede date of the record",
        data_type="date",
        synonyms={
            "valid_to", "effective_to", "expiry_date", "superseded_date", "tenure_end",
        },
    ),

    CanonicalField.VERSION_ID: CanonicalFieldDefinition(
        field_name=CanonicalField.VERSION_ID,
        display_title="Dataset Version ID",
        description="Historical or sequential dataset version tracking identifier",
        data_type="string",
        synonyms={
            "version_id", "version", "revision_id", "rev_id", "dataset_version",
        },
    ),
}
