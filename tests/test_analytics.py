"""
test_analytics.py — Automated verification tests for Phase 5 Graph Analytics & Risk Scoring.
"""

import os
import sys

import pytest

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.schema import get_neo4j_driver


@pytest.fixture(scope="module")
def driver():
    drv = get_neo4j_driver()
    yield drv
    drv.close()


def test_centrality_properties_populated(driver):
    """Verify betweenness, pagerank, and degree are written to Person nodes."""
    with driver.session() as session:
        res = session.run("""
            MATCH (p:Person)
            WHERE p.betweenness IS NOT NULL AND p.pagerank IS NOT NULL AND p.degree IS NOT NULL
            RETURN count(p) AS count
        """).single()
        assert res["count"] >= 25, f"Expected >= 25 Person nodes with centrality, got {res['count']}"


def test_community_detection_populated(driver):
    """Verify community_id is assigned to Person nodes and multiple clusters exist."""
    with driver.session() as session:
        res = session.run("""
            MATCH (p:Person)
            WHERE p.community_id IS NOT NULL
            RETURN count(DISTINCT p.community_id) AS num_communities
        """).single()
        assert res["num_communities"] >= 3, f"Expected >= 3 communities, got {res['num_communities']}"


def test_risk_score_and_explainability_breakdown(driver):
    """Verify risk_score is within [0, 100] and component breakdowns are stored."""
    with driver.session() as session:
        records = session.run("""
            MATCH (p:Person)
            WHERE p.risk_score IS NOT NULL
            RETURN p.canonical_id AS id, p.name AS name, p.risk_score AS total,
                   p.score_betweenness AS bet, p.score_pagerank AS pr,
                   p.score_criminal_history AS crim, p.score_suspicious_txns AS txn,
                   p.score_comm_anomaly AS comm
        """).data()

        assert len(records) >= 25, f"Expected >= 25 scored Person nodes, got {len(records)}"

        # Verify that Txns and Comm scores vary across individuals (Priority 1 verification)
        txn_scores = {r["txn"] for r in records}
        comm_scores = {r["comm"] for r in records}
        assert len(txn_scores) > 1, "Expected varying transaction structuring scores across suspects"
        assert len(comm_scores) > 1, "Expected varying communication anomaly scores across suspects"

        for r in records:
            total = r["total"]
            assert 0.0 <= total <= 100.0, f"Risk score {total} out of bounds for {r['name']}"
            # Check components sum roughly to total (within rounding margin)
            comp_sum = r["bet"] + r["pr"] + r["crim"] + r["txn"] + r["comm"]
            assert abs(total - comp_sum) < 0.25, f"Component sum {comp_sum} != total {total} for {r['name']}"


def test_kingpin_leadership_in_analytics(driver):
    """Verify Ravi Kumar (kingpin) is ranked among top high-risk suspects."""
    with driver.session() as session:
        top_ids = session.run("""
            MATCH (p:Person)
            WHERE p.risk_score IS NOT NULL
            RETURN p.canonical_id AS id
            ORDER BY p.risk_score DESC
            LIMIT 5
        """).value()

        assert "PER_RAVI_KUMAR" in top_ids, f"Kingpin PER_RAVI_KUMAR expected in Top-5, got: {top_ids}"
