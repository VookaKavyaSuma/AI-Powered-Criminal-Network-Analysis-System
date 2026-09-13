"""
centrality.py — Centrality analytics using Neo4j GDS & Graph Algorithms.

Computes:
1. Degree Centrality (direct connectivity)
2. Betweenness Centrality (brokerage / bottleneck detection)
3. PageRank (global network influence)

Writes computed centrality metrics back to Person nodes in Neo4j:
- p.degree
- p.betweenness
- p.pagerank
"""

import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.schema import get_neo4j_driver

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class CentralityAnalyzer:
    """Computes centrality metrics on the criminal network graph."""

    def __init__(self, driver=None):
        self.driver = driver or get_neo4j_driver()

    def run_gds_centrality(self) -> bool:
        """
        Run GDS projected graph centrality algorithms (Betweenness and PageRank).
        Falls back to Cypher/NetworkX if GDS memory projection is not available.
        """
        graph_name = "criminal_centrality_proj"

        with self.driver.session() as session:
            # 1. Drop existing projection if it exists
            session.run(f"CALL gds.graph.drop('{graph_name}', false) YIELD graphName")

            try:
                # 2. Project Person-to-Person subgraph into GDS
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

                # 3. Write PageRank
                session.run(f"""
                CALL gds.pageRank.write('{graph_name}', {{
                    writeProperty: 'pagerank',
                    maxIterations: 20,
                    dampingFactor: 0.85
                }})
                """)

                # 4. Write Betweenness Centrality
                session.run(f"""
                CALL gds.betweenness.write('{graph_name}', {{
                    writeProperty: 'betweenness'
                }})
                """)

                # 5. Cleanup in-memory projection
                session.run(f"CALL gds.graph.drop('{graph_name}', false) YIELD graphName")
                return True
            except Exception as e:
                print(f"  [Notice] GDS projection error ({e}), falling back to Cypher centrality.")
                return False

    def run_cypher_fallback_centrality(self):
        """
        Computes Degree, approximate Betweenness, and PageRank via Cypher & NetworkX fallback.
        Guarantees metrics are populated even if GDS projection fails.
        """
        import networkx as nx

        with self.driver.session() as session:
            # Build NetworkX graph from Neo4j edges
            edges = session.run("""
                MATCH (p1:Person)-[r:MET_WITH|CALLED|ASSOCIATED_WITH]-(p2:Person)
                WHERE p1 <> p2
                RETURN p1.canonical_id AS u, p2.canonical_id AS v, type(r) AS rel
            """).data()

            G = nx.Graph()
            for row in edges:
                G.add_edge(row["u"], row["v"])

            # Compute PageRank & Betweenness
            pagerank_scores = nx.pagerank(G, alpha=0.85) if len(G) > 0 else {}
            betweenness_scores = nx.betweenness_centrality(G) if len(G) > 0 else {}

            # Write properties back to Neo4j
            for pid in G.nodes():
                pr = float(pagerank_scores.get(pid, 0.0))
                bet = float(betweenness_scores.get(pid, 0.0))
                deg = int(G.degree[pid])

                session.run("""
                    MATCH (p:Person {canonical_id: $pid})
                    SET p.pagerank = $pr, p.betweenness = $bet, p.degree = $deg
                """, {"pid": pid, "pr": pr, "bet": bet, "deg": deg})

    def run_degree_centrality(self):
        """Compute and set total degree for all Person nodes in Neo4j."""
        with self.driver.session() as session:
            session.run("""
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r]-()
                WITH p, count(r) AS deg
                SET p.degree = deg
            """)

    def compute_all_centralities(self) -> List[Dict[str, Any]]:
        """Compute all centralities and return top influencers."""
        print("📐 Computing Graph Centrality Metrics (Degree, Betweenness, PageRank)...")

        # Step 1: Degree Centrality
        self.run_degree_centrality()

        # Step 2: GDS or Fallback for Betweenness & PageRank
        success = self.run_gds_centrality()
        if not success:
            self.run_cypher_fallback_centrality()

        # Step 3: Fetch Top Influencers
        with self.driver.session() as session:
            top_nodes = session.run("""
                MATCH (p:Person)
                WHERE p.betweenness IS NOT NULL
                RETURN p.canonical_id AS id, p.name AS name, p.risk_flag AS risk_flag,
                       p.degree AS degree, p.betweenness AS betweenness, p.pagerank AS pagerank
                ORDER BY p.betweenness DESC, p.pagerank DESC
                LIMIT 10
            """).data()

        print("   ✅ Centrality metrics written to Person nodes.")
        return top_nodes


if __name__ == "__main__":
    analyzer = CentralityAnalyzer()
    top = analyzer.compute_all_centralities()
    print("\n🏆 Top 10 Influencers by Betweenness Centrality:")
    for i, p in enumerate(top, 1):
        print(f"  {i:2d}. {p['name']:<20} | Betweenness: {p['betweenness']:.4f} | PageRank: {p['pagerank']:.4f} | Degree: {p['degree']}")
