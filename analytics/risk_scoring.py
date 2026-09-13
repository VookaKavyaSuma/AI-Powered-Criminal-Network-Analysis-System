"""
risk_scoring.py — Explainable Composite Risk Scoring for Crime Intelligence.

Implements the official SIH 2026 formula:
risk_score = 0.30 * normalized(betweenness_centrality)
           + 0.25 * normalized(pagerank)
           + 0.20 * normalized(criminal_history_severity)
           + 0.15 * normalized(suspicious_transaction_count)
           + 0.10 * normalized(communication_anomaly_score)

Stores composite risk_score (0-100) and all individual components on Person nodes
in Neo4j to satisfy the full explainability requirement.
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


class RiskScorer:
    """Calculates multi-criteria risk scores for all Person entities in the graph."""

    def __init__(self, driver=None):
        self.driver = driver or get_neo4j_driver()

    def compute_risk_scores(self) -> List[Dict[str, Any]]:
        """
        Pull raw component values, normalize, calculate explainable composite score,
        and write scores back to Neo4j.
        """
        print("🎯 Calculating Multi-Factor Explainable Risk Scores (0-100)...")

        with self.driver.session() as session:
            # 1. Fetch raw metrics for all Person entities
            fetch_query = """
            MATCH (p:Person)
            RETURN p.canonical_id AS id,
                   coalesce(p.name, p.canonical_id) AS name,
                   coalesce(p.betweenness, 0.0) AS betweenness,
                   coalesce(p.pagerank, 0.0) AS pagerank,
                   coalesce(p.risk_flag, 'LOW') AS risk_flag,
                   coalesce(p.past_case_count, 0) AS past_cases,
                   coalesce(p.suspicious_txns_count, 0) AS suspicious_txns,
                   coalesce(p.comm_anomaly_score, 0.0) AS comm_anomaly
            """
            nodes = session.run(fetch_query).data()

            if not nodes:
                print("   ⚠️ No Person nodes found in graph.")
                return []

            # 2. Compute normalization min/max baselines
            max_bet = max((n["betweenness"] for n in nodes), default=1.0)
            max_pr = max((n["pagerank"] for n in nodes), default=1.0)
            min_pr = min((n["pagerank"] for n in nodes), default=0.0)
            pr_range = max(max_pr - min_pr, 0.00001)
            max_struct = max((n["suspicious_txns"] for n in nodes), default=1.0)
            if max_struct == 0:
                max_struct = 1.0

            scored_entities = []

            # 3. Calculate scores per person
            for n in nodes:
                # Component 1: Normalized Betweenness (0 - 1)
                norm_bet = (n["betweenness"] / max_bet) if max_bet > 0 else 0.0

                # Component 2: Normalized PageRank (0 - 1)
                norm_pr = (n["pagerank"] - min_pr) / pr_range

                # Component 3: Criminal History Severity (0 - 1)
                flag = str(n["risk_flag"]).upper()
                if flag == "HIGH":
                    base_crim = 0.85
                elif flag == "MEDIUM":
                    base_crim = 0.50
                else:
                    base_crim = 0.10
                norm_crim = min(1.0, base_crim + (n["past_cases"] * 0.05))

                # Component 4: Suspicious Transactions (0 - 1)
                norm_txn = min(1.0, n["suspicious_txns"] / max_struct)

                # Component 5: Communication Anomaly (0 - 1)
                norm_comm = float(n["comm_anomaly"])

                # Weighted components (scaled to 100 max)
                c_bet = round(0.30 * norm_bet * 100, 2)
                c_pr = round(0.25 * norm_pr * 100, 2)
                c_crim = round(0.20 * norm_crim * 100, 2)
                c_txn = round(0.15 * norm_txn * 100, 2)
                c_comm = round(0.10 * norm_comm * 100, 2)

                composite_score = round(c_bet + c_pr + c_crim + c_txn + c_comm, 2)

                scored_entities.append({
                    "id": n["id"],
                    "name": n["name"],
                    "risk_score": composite_score,
                    "score_betweenness": c_bet,
                    "score_pagerank": c_pr,
                    "score_criminal_history": c_crim,
                    "score_suspicious_txns": c_txn,
                    "score_comm_anomaly": c_comm,
                })

            # 4. Batch write scores back to Neo4j
            write_query = """
            UNWIND $batch AS item
            MATCH (p:Person {canonical_id: item.id})
            SET
                p.risk_score = item.risk_score,
                p.score_betweenness = item.score_betweenness,
                p.score_pagerank = item.score_pagerank,
                p.score_criminal_history = item.score_criminal_history,
                p.score_suspicious_txns = item.score_suspicious_txns,
                p.score_comm_anomaly = item.score_comm_anomaly
            """
            session.run(write_query, {"batch": scored_entities})

            # Sort descending by composite score
            scored_entities.sort(key=lambda x: x["risk_score"], reverse=True)
            print(f"   ✅ Computed and stored explainable risk scores for {len(scored_entities)} persons.")
            return scored_entities


if __name__ == "__main__":
    scorer = RiskScorer()
    ranked = scorer.compute_risk_scores()
    print("\n🏆 Top 10 High-Risk Suspects (Composite Risk Scores):")
    print(f"  {'Rank':<4} {'Name':<22} {'Risk Score':<12} {'Betweenness':<12} {'PageRank':<10} {'History':<10} {'Txns':<8} {'Comm':<6}")
    print(f"  {'-'*4} {'-'*22} {'-'*12} {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*6}")
    for i, p in enumerate(ranked[:10], 1):
        print(f"  {i:2d}.  {p['name']:<22} {p['risk_score']:>6.2f} / 100   {p['score_betweenness']:>6.2f}       {p['score_pagerank']:>6.2f}     {p['score_criminal_history']:>6.2f}     {p['score_suspicious_txns']:>5.2f}    {p['score_comm_anomaly']:>5.2f}")
