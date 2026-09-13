"""
community_detection.py — Louvain Community Detection on Criminal Network.

Identifies operational cells, sub-syndicates, and crime clusters.
Writes community_id to Person nodes in Neo4j:
- p.community_id
"""

import os
import sys
from collections import Counter
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.schema import get_neo4j_driver

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class CommunityDetector:
    """Discovers cohesive operational cells using Louvain modularity optimization."""

    def __init__(self, driver=None):
        self.driver = driver or get_neo4j_driver()

    def run_gds_louvain(self) -> bool:
        """Run Louvain algorithm via Neo4j GDS."""
        graph_name = "criminal_community_proj"

        with self.driver.session() as session:
            session.run(f"CALL gds.graph.drop('{graph_name}', false) YIELD graphName")

            try:
                # Project Person-to-Person interactions
                project_query = f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    'Person',
                    {{
                        MET_WITH: {{type: 'MET_WITH', orientation: 'UNDIRECTED'}},
                        CALLED: {{type: 'CALLED', orientation: 'UNDIRECTED'}},
                        ASSOCIATED_WITH: {{type: 'ASSOCIATED_WITH', orientation: 'UNDIRECTED'}}
                    }}
                )
                """
                session.run(project_query)

                # Write Louvain community ID
                session.run(f"""
                CALL gds.louvain.write('{graph_name}', {{
                    writeProperty: 'community_id'
                }})
                """)

                session.run(f"CALL gds.graph.drop('{graph_name}', false) YIELD graphName")
                return True
            except Exception as e:
                print(f"  [Notice] GDS Louvain error ({e}), falling back to NetworkX communities.")
                return False

    def run_networkx_louvain(self):
        """Fallback community detection using NetworkX Louvain communities."""
        import networkx as nx

        with self.driver.session() as session:
            edges = session.run("""
                MATCH (p1:Person)-[:MET_WITH|CALLED|ASSOCIATED_WITH]-(p2:Person)
                WHERE p1 <> p2
                RETURN p1.canonical_id AS u, p2.canonical_id AS v
            """).data()

            G = nx.Graph()
            for row in edges:
                G.add_edge(row["u"], row["v"])

            # Detect communities using greedy modularity or louvain
            try:
                communities = nx.community.louvain_communities(G, seed=42)
            except Exception:
                communities = nx.community.greedy_modularity_communities(G)

            # Assign integer community ID
            for comm_id, members in enumerate(communities):
                for pid in members:
                    session.run("""
                        MATCH (p:Person {canonical_id: $pid})
                        SET p.community_id = $cid
                    """, {"pid": pid, "cid": comm_id})

            # Handle isolated Person nodes with no edges
            session.run("""
                MATCH (p:Person)
                WHERE p.community_id IS NULL
                SET p.community_id = 999
            """)

    def detect_communities(self) -> Dict[str, Any]:
        """Execute community detection and return cluster distributions."""
        print("👥 Running Louvain Community Detection on Criminal Network...")

        success = self.run_gds_louvain()
        if not success:
            self.run_networkx_louvain()

        with self.driver.session() as session:
            # Query community sizes
            stats = session.run("""
                MATCH (p:Person)
                WHERE p.community_id IS NOT NULL
                RETURN p.community_id AS community_id,
                       count(p) AS member_count,
                       collect(p.name)[0..5] AS sample_members
                ORDER BY member_count DESC
            """).data()

        print(f"   ✅ Detected {len(stats)} operational communities.")
        return {
            "total_communities": len(stats),
            "communities": stats,
        }


if __name__ == "__main__":
    detector = CommunityDetector()
    results = detector.detect_communities()
    print("\n🔍 Community Breakdown:")
    for comm in results["communities"]:
        print(f"  • Cell #{comm['community_id']:<3} | Size: {comm['member_count']:>2} members | Sample: {', '.join(comm['sample_members'])}")
