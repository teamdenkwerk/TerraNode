"""
matching/match_entities.py

The matching engine — rewritten to generalize across N sources (not just
a fixed source_a/source_b pair), while keeping the STRtree spatial index
for candidate generation. This replaces two things from an earlier draft
that diverged from spec:
  1. A brute-force O(n*m) nested loop — doesn't survive district scale.
  2. Losing the pairwise match score once features were grouped — the
     match score is preserved per-edge and aggregated per-cluster, so
     reconciliation/confidence_score.py can still use real match quality,
     not just "how many sources happened to agree."

Flow: load all raw_features for a tile (any number of sources) -> STRtree
candidate generation -> score every cross-source candidate pair -> keep
edges >= MATCH_SCORE_THRESHOLD -> union-find clusters edges into groups
(so a building seen by 3 sources becomes ONE cluster, not three separate
pairwise matches) -> return clusters + their member edges for
reconciliation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from shapely import wkt as shapely_wkt
from shapely.strtree import STRtree

from config import (
    MATCH_WEIGHT_IOU, MATCH_WEIGHT_DIST, MATCH_WEIGHT_ATTR,
    MATCH_SCORE_THRESHOLD, MAX_CANDIDATE_DISTANCE_M,
)
from db.connection import get_connection
from matching.similarity import ScoreWeights, MatchScore, combined_score

logger = logging.getLogger(__name__)

WEIGHTS = ScoreWeights(w_iou=MATCH_WEIGHT_IOU, w_centroid=MATCH_WEIGHT_DIST, w_attribute=MATCH_WEIGHT_ATTR)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_raw_features(tile_id: str | None = None, batch_size: int = 20000) -> list[dict]:
    """Loads raw_features rows (optionally filtered by tile) as plain
    dicts with a parsed shapely `geometry` (in the projected matching CRS
    — raw_features.geom is already stored in MATCH_SRID, no reprojection
    needed here).

    Fetches in batches (keyset pagination on `id`) rather than one
    unbounded SELECT. At real district scale (hundreds of thousands of
    rows), a single unfiltered query pulling full geometry WKT for every
    row risked hitting Supabase's Session Pooler statement timeout or an
    SSL connection drop mid-transfer — confirmed by an actual crash on a
    ~330,000-row district-scale run. Keyset pagination (id > last_seen_id)
    keeps each individual query small and fast regardless of total table
    size, and is safe even with concurrent writes (unlike LIMIT/OFFSET,
    which can skip or duplicate rows if the table changes between pages —
    not expected here, but keyset is the more robust default regardless)."""
    base_query = """
        SELECT id, entity_uid, source, building_type, area_m2,
               extraction_confidence, centroid_x, centroid_y,
               ST_AsText(geom) AS geom_wkt
        FROM raw_features
    """
    where_clauses = []
    base_params: list = []
    if tile_id:
        where_clauses.append("tile_id = %s")
        base_params.append(tile_id)

    rows: list[dict] = []
    last_id = 0
    with get_connection() as conn:
        while True:
            clauses = where_clauses + ["id > %s"]
            query = base_query + " WHERE " + " AND ".join(clauses) + " ORDER BY id LIMIT %s"
            params = tuple(base_params + [last_id, batch_size])

            with conn.cursor() as cur:
                cur.execute(query, params)
                batch = cur.fetchall()

            if not batch:
                break
            rows.extend(batch)
            last_id = batch[-1]["id"]
            logger.info("loaded batch of %d raw features (running total: %d)", len(batch), len(rows))
            if len(batch) < batch_size:
                break  # last page was partial — no more rows to fetch

    for r in rows:
        r["geometry"] = shapely_wkt.loads(r.pop("geom_wkt"))
    logger.info("loaded %d raw features%s (total)", len(rows), f" for tile={tile_id}" if tile_id else "")
    return rows


# ---------------------------------------------------------------------------
# Candidate generation + scoring (spatial index, not brute force)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchEdge:
    feature_id_a: int
    feature_id_b: int
    score: MatchScore


def find_match_edges(
    features: list[dict],
    search_radius_m: float = MAX_CANDIDATE_DISTANCE_M,
    min_score: float = MATCH_SCORE_THRESHOLD,
    weights: ScoreWeights = WEIGHTS,
) -> list[MatchEdge]:
    """STRtree-backed candidate generation across ALL sources at once.
    A pair is only scored if their geometries are within search_radius_m
    of each other AND they come from different sources — never matches
    two features from the same source against each other."""
    if len(features) < 2:
        return []

    geoms = [f["geometry"] for f in features]
    tree = STRtree(geoms)

    edges: list[MatchEdge] = []
    seen_pairs: set[tuple[int, int]] = set()

    for i, fa in enumerate(features):
        if fa["geometry"] is None or fa["geometry"].is_empty:
            continue
        query_geom = fa["geometry"].buffer(search_radius_m)
        hit_positions = tree.query(query_geom)

        for j in hit_positions:
            if j == i:
                continue
            fb = features[j]
            if fb["source"] == fa["source"]:
                continue  # never match within the same source

            pair_key = (min(fa["id"], fb["id"]), max(fa["id"], fb["id"]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            attrs_a = {"area_m2": fa["area_m2"], "building_type": fa.get("building_type")}
            attrs_b = {"area_m2": fb["area_m2"], "building_type": fb.get("building_type")}
            score = combined_score(
                fa["geometry"], fb["geometry"], attrs_a, attrs_b,
                weights=weights, max_centroid_dist=search_radius_m,
            )
            if score.total >= min_score:
                edges.append(MatchEdge(pair_key[0], pair_key[1], score))

    logger.info("found %d match edges above threshold %.2f among %d features",
                len(edges), min_score, len(features))
    return edges


# ---------------------------------------------------------------------------
# Union-find clustering (generalizes matching to N sources)
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


@dataclass
class Cluster:
    member_feature_ids: list[int] = field(default_factory=list)
    edges: list[MatchEdge] = field(default_factory=list)  # edges with BOTH endpoints in this cluster
    duplicate_source_warning: bool = False  # True if 2+ members share a source (matching anomaly)


def cluster_features(features: list[dict], edges: list[MatchEdge]) -> list[Cluster]:
    """Groups features into clusters via GREEDY union-find over accepted
    edges, processed highest-score-first, rejecting any merge that would
    put two features from the SAME source into one cluster.

    Plain union-find (merging every accepted edge unconditionally) allows
    hub-merging: if feature X matches both A and B (different features,
    same source — e.g. one large GOB polygon overlapping two adjacent OSM
    footprints), a naive union-find will transitively merge A and B
    together even though A and B never scored against each other. Since a
    cluster is meant to represent ONE real-world building, at most one
    feature per source may belong to it — so a same-source collision means
    the edge causing it must be rejected, not accepted and warned about
    after the fact.

    A feature with no accepted matching edges becomes its own singleton
    cluster (an "unmatched" entity, still carried through to reconciliation)."""
    all_ids = [f["id"] for f in features]
    source_by_id = {f["id"]: f["source"] for f in features}
    uf = UnionFind(all_ids)

    # Track which sources are already present under each root, so a
    # proposed merge can be checked for collisions in O(1) before committing.
    sources_by_root: dict[int, set[str]] = {fid: {source_by_id[fid]} for fid in all_ids}

    rejected_edges: list[MatchEdge] = []
    accepted_edges: list[MatchEdge] = []

    for edge in sorted(edges, key=lambda e: e.score.total, reverse=True):
        root_a = uf.find(edge.feature_id_a)
        root_b = uf.find(edge.feature_id_b)
        if root_a == root_b:
            accepted_edges.append(edge)  # already in the same cluster, harmless
            continue

        sources_a = sources_by_root[root_a]
        sources_b = sources_by_root[root_b]
        if sources_a & sources_b:
            # Merging would put two features from the same source in one
            # cluster — reject this edge (it's the lower-scoring one, since
            # we process highest-score-first) rather than merge and warn later.
            rejected_edges.append(edge)
            continue

        uf.union(root_a, root_b)
        new_root = uf.find(root_a)
        sources_by_root[new_root] = sources_a | sources_b
        accepted_edges.append(edge)

    if rejected_edges:
        logger.info(
            "rejected %d edge(s) that would have created same-source clusters "
            "(kept the higher-scoring edge for each conflicting feature instead)",
            len(rejected_edges),
        )

    members_by_root: dict[int, list[int]] = {}
    for fid in all_ids:
        root = uf.find(fid)
        members_by_root.setdefault(root, []).append(fid)

    clusters = []
    for member_ids in members_by_root.values():
        member_set = set(member_ids)
        cluster_edges = [e for e in accepted_edges if e.feature_id_a in member_set and e.feature_id_b in member_set]

        sources_in_cluster = [source_by_id[m] for m in member_ids]
        # Should never trigger now — kept as a safety-net assertion, since a
        # real occurrence here would mean the collision check above has a bug.
        duplicate_warning = len(sources_in_cluster) != len(set(sources_in_cluster))
        if duplicate_warning:
            logger.error(
                "UNEXPECTED: cluster %s has multiple members from the same source (%s) "
                "despite the collision check — this indicates a bug in cluster_features, "
                "not a threshold issue",
                member_ids, sources_in_cluster,
            )

        clusters.append(Cluster(
            member_feature_ids=member_ids,
            edges=cluster_edges,
            duplicate_source_warning=duplicate_warning,
        ))

    matched = sum(1 for c in clusters if len(c.member_feature_ids) > 1)
    logger.info("clustered %d features into %d clusters (%d multi-source, %d singleton)",
                len(features), len(clusters), matched, len(clusters) - matched)
    return clusters


# ---------------------------------------------------------------------------
# Persisting edges
# ---------------------------------------------------------------------------

def write_match_edges(edges: list[MatchEdge], tile_id: str | None = None) -> None:
    if not edges:
        return
    rows = [
        (e.feature_id_a, e.feature_id_b, e.score.total, e.score.iou,
         e.score.centroid_component, e.score.attribute, tile_id)
        for e in edges
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO match_edges
                    (feature_id_a, feature_id_b, score_total, score_iou,
                     score_centroid, score_attribute, tile_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (feature_id_a, feature_id_b) DO NOTHING
                """,
                rows,
            )
        conn.commit()
    logger.info("wrote %d match edges", len(rows))


# ---------------------------------------------------------------------------
# Tile-level driver
# ---------------------------------------------------------------------------

def run_matching(tile_id: str | None = None) -> tuple[list[dict], list[Cluster]]:
    features = load_raw_features(tile_id)
    if not features:
        logger.warning("no raw features found for tile=%s — run ingestion first", tile_id)
        return [], []

    edges = find_match_edges(features)
    write_match_edges(edges, tile_id=tile_id)
    clusters = cluster_features(features, edges)
    return features, clusters


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_matching()