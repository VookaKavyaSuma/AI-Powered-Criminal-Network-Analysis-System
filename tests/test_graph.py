"""
test_graph.py — Automated verification tests for Phase 4 Neo4j Graph Construction.
"""

import os
import sys

import pytest

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.queries.common_cypher import COUNT_EDGES_BY_TYPE, COUNT_NODES_BY_LABEL
from graph.schema import get_neo4j_driver


@pytest.fixture(scope="module")
def neo4j_driver():
    driver = get_neo4j_driver()
    yield driver
    driver.close()


def test_neo4j_connectivity(neo4j_driver):
    """Verify Neo4j driver connects and executes a test query."""
    with neo4j_driver.session() as session:
        result = session.run("RETURN 1 AS val")
        assert result.single()["val"] == 1


def test_node_counts(neo4j_driver):
    """Verify nodes exist for all core ontology labels."""
    with neo4j_driver.session() as session:
        records = session.run(COUNT_NODES_BY_LABEL).data()
        counts = {r["label"]: r["count"] for r in records}

        assert counts.get("Person", 0) >= 25, "Expected >= 25 Person nodes"
        assert counts.get("PhoneNumber", 0) >= 20, "Expected >= 20 PhoneNumber nodes"
        assert counts.get("Account", 0) >= 20, "Expected >= 20 Account nodes"
        assert counts.get("Vehicle", 0) >= 15, "Expected >= 15 Vehicle nodes"
        assert counts.get("Organization", 0) >= 4, "Expected >= 4 Organization nodes"
        assert counts.get("Location", 0) >= 10, "Expected >= 10 Location nodes"


def test_relationship_counts(neo4j_driver):
    """Verify core relationship types are present."""
    with neo4j_driver.session() as session:
        records = session.run(COUNT_EDGES_BY_TYPE).data()
        counts = {r["rel_type"]: r["count"] for r in records}

        assert counts.get("CALLED", 0) >= 100, "Expected >= 100 CALLED edges"
        assert counts.get("TRANSFERRED_MONEY_TO", 0) >= 100, "Expected >= 100 TRANSFERRED_MONEY_TO edges"
        assert counts.get("OWNS_OR_USES", 0) >= 20, "Expected >= 20 OWNS_OR_USES edges"
        assert counts.get("MEMBER_OF", 0) >= 5, "Expected >= 5 MEMBER_OF edges"


def test_ground_truth_kingpin_node(neo4j_driver):
    """Verify Ravi Kumar (kingpin) is loaded with expected attributes and edges."""
    with neo4j_driver.session() as session:
        res = session.run("""
            MATCH (p:Person {canonical_id: 'PER_RAVI_KUMAR'})
            OPTIONAL MATCH (p)-[r]-(connected)
            RETURN p.name AS name, p.risk_flag AS risk_flag, count(r) AS degree
        """).single()

        assert res is not None, "PER_RAVI_KUMAR node should exist in graph"
        assert res["risk_flag"] == "HIGH"
        assert res["degree"] > 0, "Kingpin should have active edges in the network"
