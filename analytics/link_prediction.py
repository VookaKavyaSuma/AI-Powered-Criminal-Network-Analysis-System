"""
link_prediction.py — Predict hidden or unobserved links between criminal actors.

Uses:
1. Common Neighbors / Jaccard similarity across network topology.
2. Shared multi-modal connections (shared phone calls, shared locations, co-occurrences).

Merges top predicted connections into Neo4j as PREDICTED_LINK relationships.
"""

import os
import sys
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.schema import get_neo4j_driver

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class LinkPredictor:
    """Predicts unobserved relationships between suspects based on shared neighborhood."""

    def __init__(self, driver=None):
        self.driver = driver or get_neo4j_driver()

    def predict_links(self, min_shared_neighbors: int = 2, top_k: int = 25) -> List[Dict[str, Any]]:
        """
        Compute top unlinked pairs with high common-neighbor count and Jaccard similarity.
        Inserts PREDICTED_LINK relationships into Neo4j.
        """
        print("🔗 Predicting Unobserved Criminal Links (Link Prediction)...")

        query = """
        MATCH (p1:Person), (p2:Person)
        WHERE elementId(p1) < elementId(p2)
          AND NOT (p1)-[:MET_WITH|CALLED|ASSOCIATED_WITH]-(p2)
        MATCH (p1)--(shared)--(p2)
        WHERE NOT shared:Person OR (shared:Person AND shared <> p1 AND shared <> p2)
        WITH p1, p2, count(DISTINCT shared) AS common_neighbors, collect(DISTINCT coalesce(shared.name, shared.number, shared.canonical_id))[0..3] AS sample_shared
        WHERE common_neighbors >= $min_shared
        MATCH (p1)-[]-(n1) WITH p1, p2, common_neighbors, sample_shared, count(DISTINCT n1) AS deg1
        MATCH (p2)-[]-(n2) WITH p1, p2, common_neighbors, sample_shared, deg1, count(DISTINCT n2) AS deg2
        WITH p1, p2, common_neighbors, sample_shared,
             round(toFloat(common_neighbors) / (deg1 + deg2 - common_neighbors) * 100) / 100.0 AS jaccard_score
        ORDER BY common_neighbors DESC, jaccard_score DESC
        LIMIT $top_k
        RETURN p1.canonical_id AS id1, p1.name AS name1,
               p2.canonical_id AS id2, p2.name AS name2,
               common_neighbors, jaccard_score, sample_shared
        """

        with self.driver.session() as session:
            # Clean previous predicted links
            session.run("MATCH ()-[r:PREDICTED_LINK]->() DELETE r")

            candidates = session.run(query, {
                "min_shared": min_shared_neighbors,
                "top_k": top_k,
            }).data()

            # Write PREDICTED_LINK edges into Neo4j
            write_query = """
            MATCH (p1:Person {canonical_id: $id1}), (p2:Person {canonical_id: $id2})
            MERGE (p1)-[r:PREDICTED_LINK]->(p2)
            SET
                r.jaccard_similarity = $jaccard,
                r.common_neighbors = $common,
                r.confidence = $conf,
                r.created_at = datetime()
            """
            for row in candidates:
                conf = min(0.95, round(row["jaccard_score"] * 0.5 + 0.45, 2))
                session.run(write_query, {
                    "id1": row["id1"],
                    "id2": row["id2"],
                    "jaccard": row["jaccard_score"],
                    "common": row["common_neighbors"],
                    "conf": conf,
                })

        print(f"   ✅ Discovered {len(candidates)} predicted criminal links.")
        return candidates


if __name__ == "__main__":
    predictor = LinkPredictor()
    links = predictor.predict_links()
    print("\n🔍 Top Predicted Criminal Links:")
    for i, l in enumerate(links[:10], 1):
        print(f"  {i:2d}. {l['name1']} <---> {l['name2']} | Common: {l['common_neighbors']} | Jaccard: {l['jaccard_score']} | Shared: {', '.join(l['sample_shared'])}")
