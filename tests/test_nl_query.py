"""
test_nl_query.py — Automated verification tests for Phase 7 Natural Language Query Interface.
"""

import os
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app
from backend.routers.nl_query import validate_cypher

client = TestClient(app)


@pytest.fixture(scope="module")
def analyst_token():
    resp = client.post("/auth/login", json={"username": "analyst", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def investigator_token():
    resp = client.post("/auth/login", json={"username": "investigator", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_cypher_guardrail_blocks_mutations():
    """Verify validate_cypher strictly blocks CREATE, DELETE, and DROP."""
    with pytest.raises(HTTPException) as exc1:
        validate_cypher("MATCH (p:Person) DELETE p")
    assert exc1.value.status_code == 400

    with pytest.raises(HTTPException) as exc2:
        validate_cypher("CREATE (p:Person {name: 'Fake'}) RETURN p")
    assert exc2.value.status_code == 400

    with pytest.raises(HTTPException) as exc3:
        validate_cypher("MATCH (p:Person) SET p.risk_score = 0")
    assert exc3.value.status_code == 400


def test_cypher_guardrail_allows_read_only():
    """Verify validate_cypher allows safe read queries and auto-appends LIMIT if absent."""
    safe_q = "MATCH (p:Person) RETURN p.name, p.risk_score"
    validated = validate_cypher(safe_q)
    assert "LIMIT" in validated
    assert "MATCH" in validated


def test_nl_query_endpoint(analyst_token):
    """Verify /query/natural-language executes and returns query and results."""
    resp = client.post(
        "/query/natural-language",
        json={"question": "Who are the highest risk suspects?"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_cypher" in data
    assert "results" in data
    assert data["result_count"] > 0
    # Should include node properties (either direct keys or nested in 'p')
    first_result = data["results"][0]
    node_props = first_result.get("p", first_result)
    assert "risk_score" in node_props or "canonical_id" in node_props or "name" in node_props


def test_nl_query_rbac_forbidden_investigator(investigator_token):
    """Verify investigator cannot access natural language queries (requires analyst+)."""
    resp = client.post(
        "/query/natural-language",
        json={"question": "Show all phone calls"},
        headers={"Authorization": f"Bearer {investigator_token}"},
    )
    assert resp.status_code == 403
