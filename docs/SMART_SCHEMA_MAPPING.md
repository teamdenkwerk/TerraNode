# TERRANODE FEATURE 01 — SMART SCHEMA MAPPING

## 1. Overview & Operational Goal

Different geospatial and land administrative datasets (revenue cadastres, urban local body property tax databases, survey rover logs, satellite building footprints) utilize disparate naming conventions for the same semantic entity.

For example, a revenue parcel number may appear as:
- `survey_no` (Revenue Department / Bhoomi)
- `survey_number` (Karnataka KGIS)
- `plot_no` / `plot_number` (Urban Development Authority)
- `khasra_no` / `khasra_number` (Northern States Cadastre)
- `cts_no` (City Survey / Maharashtra)
- `pid` / `property_id` (Municipal Property Tax)
- `parcel_id` (TerraNode Canonical)

The **Smart Schema Mapping** module detects semantic equivalents, derives transparent mathematical confidence scores, flags potential collisions or weak associations, and requires explicit officer sign-off before downstream harmonization.

---

## 2. Canonical Fields Registry

TerraNode defines 10 canonical fields for uniform inter-agency harmonization:

| Canonical Field | Type | Description | Representative Synonyms / Abbreviations |
| :--- | :--- | :--- | :--- |
| `parcel_id` | String | Unique cadastral parcel identifier | `cad_id`, `khasra`, `pid`, `dag_no`, `cts_no`, `footprint_id` |
| `survey_number` | String | Revenue village or ward survey / sub-division number | `survey_no`, `sy_no`, `plot_no`, `hissa_no`, `revenue_no` |
| `property_id` | String | Municipal corporation tax / assessment identifier | `assessment_no`, `upin`, `door_no`, `khata_no`, `holding_no` |
| `area` | Numeric | Surface area in square meters or acres | `area_sqm`, `area_m2`, `extent`, `shape_area`, `st_area` |
| `geometry` | Geometry | Polygonal spatial boundary (WKT / GeoJSON) | `geom`, `the_geom`, `shape`, `coordinates`, `wkt` |
| `latitude` | Numeric | Centroid North coordinate (WGS84 degrees) | `lat`, `lat_deg`, `centroid_y`, `northing`, `y_coord` |
| `longitude` | Numeric | Centroid East coordinate (WGS84 degrees) | `lon`, `lng`, `lon_deg`, `centroid_x`, `easting`, `x_coord` |
| `source` | String | Dataset agency, sensor, or layer of origin | `provider`, `agency`, `layer_name`, `dataset_source`, `origin` |
| `date` | Date | Official capture or survey timestamp | `survey_date`, `creation_date`, `valid_from`, `as_of_date` |
| `owner_reference` | String | Name of title holder, khatedar, or applicant | `owner_name`, `proprietor`, `pattadar`, `khatedar`, `applicant` |

---

## 3. Four-Stage Normalization Pipeline

The normalization engine in [`backend/schema_mapping/schema_mapper.py`](file:///c:/Users/yuvas/OneDrive/Desktop/Geo-Reconciliation-master/Geo-Reconciliation-master/backend/schema_mapping/schema_mapper.py) executes:

1. **Case Normalization**: Converts all text to lowercase; expands `camelCase` / `PascalCase` word boundaries into whitespace tokens.
2. **Punctuation Stripping**: Replaces non-alphanumeric characters (brackets, hyphens, slashes, periods) with underscores.
3. **Domain Abbreviation Expansion**: Scans tokens against [`COMMON_ABBREVIATIONS`](file:///c:/Users/yuvas/OneDrive/Desktop/Geo-Reconciliation-master/Geo-Reconciliation-master/backend/schema_mapping/field_dictionary.py):
   - `no`, `num`, `nbr` $\rightarrow$ `number`
   - `surv`, `sy` $\rightarrow$ `survey`
   - `parc`, `pcl` $\rightarrow$ `parcel`
   - `sqm`, `sqft` $\rightarrow$ `area`
   - `geom`, `shp` $\rightarrow$ `geometry`
   - `prop`, `prpty` $\rightarrow$ `property`
   - `own`, `ownr` $\rightarrow$ `owner`
4. **Token Assembly**: Assembles cleaned, expanded tokens into snake_case representation for semantic comparison.

---

## 4. Non-Fabricated Confidence Scoring

Every suggestion receives a deterministic confidence score derived from structural and lexical similarity:

$$\text{Confidence} = \begin{cases}
1.00 & \text{Exact match on canonical field name} \\
0.95 & \text{Direct match in curated domain synonym dictionary} \\
0.90\text{--}0.92 & \text{Exact or synonym match ignoring punctuation} \\
0.75 + 0.15 \times \text{Jaccard} & \text{High token overlap with synonym } (\ge 0.70) \\
0.85 \times \text{Ratcliff-Obershelp} & \text{Fuzzy string distance ratio } (\ge 0.75) \\
0.00 & \text{No lexical or domain relationship (Unmapped)}
\end{cases}$$

### Strict Safety Invariants
1. **Never Silently Auto-Map Low-Confidence Fields**: Any candidate with confidence $<0.75$ is automatically flagged as `is_low_confidence = True` with status `LOW_CONFIDENCE`. It requires explicit manual confirmation.
2. **Conflicting Candidates Arbitration**: If two source fields (e.g. `parcel_id` and `cad_id`) target the same canonical field, the candidate with higher confidence is suggested, and the competing candidate is flagged with `is_conflicting = True` and status `CONFLICTING`.

---

## 5. API Endpoints

### 1. Generate Schema Mapping
- **Route**: `POST /api/schema/mapping`
- **Request Body**:
  ```json
  {
    "dataset_id": "cadastral_upload_01",
    "file_path": "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson",
    "columns": ["survey_no", "plot_number", "area_sqm", "owner_name"]
  }
  ```
- **Response**: Returns suggested mappings, match types, confidence scores, and preview sample values.

### 2. Retrieve Saved Mapping
- **Route**: `GET /api/schema/mapping/{dataset_id}`
- **Response**: Returns active suggestions and any previously confirmed officer audit record.

### 3. Confirm & Lock Schema Mapping
- **Route**: `POST /api/schema/mapping/{dataset_id}/confirm`
- **Request Body**:
  ```json
  {
    "dataset_version": "v1.0",
    "confirmed_by": "Senior Land Records Officer",
    "mappings": {
      "survey_no": "survey_number",
      "plot_number": "parcel_id",
      "area_sqm": "area",
      "owner_name": "owner_reference",
      "unneeded_col": null
    },
    "notes": "Verified against Bhoomi standard schema."
  }
  ```
- **Response**: Persisted immutable audit record (`data/schema_mappings/{dataset_id}.json`).

---

## 6. Frontend Officer Workflow

1. In **Stage 02 (Upload Documents)**, when a geospatial file is uploaded or inspected, the **Smart Schema Mapping Card** automatically renders.
2. The officer reviews:
   - **Detected Field** (raw column name)
   - **Normalized Token** (expanded abbreviation)
   - **Suggested Canonical Target** (editable dropdown)
   - **Match Type** (`EXACT`, `SYNONYM`, `ABBREVIATION`, `TOKEN_OVERLAP`, `FUZZY`)
   - **Mathematical Confidence Bar**
   - **Status & Warning Badges** (Low Confidence / Target Conflict)
3. The officer enters their name and justification notes, then clicks **"Confirm & Lock Schema Mappings"**.
4. The signed confirmation is persisted, locking the dataset schema version before spatial harmonization.
