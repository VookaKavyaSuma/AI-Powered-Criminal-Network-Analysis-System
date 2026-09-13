"""
anomaly_detection.py — Behavioral Anomaly Detection on Criminal Graph.

Detects:
1. Communication Spikes: Sudden bursts of calls between suspect phones.
2. Financial Structuring / Smurfing: Multiple sub-₹50,000 transfers linked to suspect accounts.

Writes computed anomaly indicators to Person nodes in Neo4j:
- p.comm_anomaly_score
- p.suspicious_txns_count
- p.has_structuring_alert
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


class AnomalyDetector:
    """Identifies anomalous communication and money-laundering structuring patterns."""

    def __init__(self, driver=None):
        self.driver = driver or get_neo4j_driver()

    def detect_communication_anomalies(self) -> int:
        """
        Identify suspects with high-frequency communication spikes or call bursts.
        Computes continuous, non-clamped p.comm_anomaly_score on Person nodes.
        """
        # Step 1: Collect raw telecom metrics per Person
        raw_query = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:OWNS_OR_USES]->(ph:PhoneNumber)-[c:CALLED]-(other)
        WITH p,
             sum(coalesce(c.frequency, 1)) AS total_calls,
             max(coalesce(c.frequency, 0)) AS max_call_spike,
             sum(coalesce(c.total_duration_sec, 0)) AS total_duration
        SET p.comm_total_calls = total_calls,
            p.comm_max_spike = max_call_spike,
            p.comm_total_duration = total_duration
        """

        # Step 2: Continuous min-max scaling across network
        scale_query = """
        MATCH (p:Person)
        WITH max(p.comm_max_spike) AS max_spike, max(p.comm_total_calls) AS max_calls
        MATCH (p:Person)
        WITH p, max_spike, max_calls,
             coalesce(p.comm_max_spike, 0) AS spike,
             coalesce(p.comm_total_calls, 0) AS calls
        SET p.comm_anomaly_score = CASE
            WHEN calls = 0 THEN 0.0
            ELSE round((
                0.60 * (toFloat(spike) / CASE WHEN max_spike > 0 THEN max_spike ELSE 1 END) +
                0.40 * (toFloat(calls) / CASE WHEN max_calls > 0 THEN max_calls ELSE 1 END)
            ) * 100) / 100.0
        END
        RETURN count(p) AS updated
        """
        with self.driver.session() as session:
            session.run(raw_query)
            res = session.run(scale_query).single()
            return res["updated"] if res else 0

    def detect_financial_structuring(self) -> int:
        """
        Identify suspects whose accounts are engaged in smurfing / sub-₹50k structuring.
        Sets p.suspicious_txns_count and p.has_structuring_alert.
        """
        query = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:OWNS_OR_USES]->(a:Account)-[t:TRANSFERRED_MONEY_TO]-(other:Account)
        WHERE t.flagged_structuring = true
        WITH p, count(DISTINCT t) AS struct_count
        SET p.suspicious_txns_count = struct_count,
            p.has_structuring_alert = (struct_count > 0)
        RETURN count(p) AS updated
        """
        with self.driver.session() as session:
            res = session.run(query).single()
            return res["updated"] if res else 0

    def run_anomaly_detection(self) -> Dict[str, Any]:
        """Run all anomaly detection algorithms and return flagged suspects."""
        print("🚨 Running Anomaly Detection (Comm Spikes & Structuring)...")

        comm_count = self.detect_communication_anomalies()
        txn_count = self.detect_financial_structuring()

        with self.driver.session() as session:
            flagged = session.run("""
                MATCH (p:Person)
                WHERE p.comm_anomaly_score > 0.5 OR p.has_structuring_alert = true
                RETURN p.canonical_id AS id, p.name AS name,
                       p.comm_anomaly_score AS comm_anomaly,
                       p.suspicious_txns_count AS struct_txns,
                       p.has_structuring_alert AS struct_alert
                ORDER BY p.suspicious_txns_count DESC, p.comm_anomaly_score DESC
            """).data()

        print(f"   ✅ Flagged {len(flagged)} suspects with behavioral anomalies.")
        return {
            "comm_updated": comm_count,
            "txn_updated": txn_count,
            "flagged_suspects": flagged,
        }


if __name__ == "__main__":
    detector = AnomalyDetector()
    results = detector.run_anomaly_detection()
    print("\n⚠️ Anomaly Alerts:")
    for f in results["flagged_suspects"]:
        print(f"  • {f['name']:<20} | Structuring Txns: {f['struct_txns']} | Comm Anomaly: {f['comm_anomaly']:.2f}")
