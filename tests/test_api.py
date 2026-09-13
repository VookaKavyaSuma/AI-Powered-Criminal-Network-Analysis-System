"""
test_api.py — Comprehensive end-to-end integration tests for FastAPI backend.

Tests:
1. Healthcheck (/health) & root
2. JWT Authentication (/auth/login & /auth/me)
3. Role-Based Access Control (RBAC enforcement)
4. Entity Search, Dossier, and Cytoscape Subgraph (/entity)
5. Graph Analytics endpoints (/analytics)
6. Cryptographic Audit Chain & Tamper Detection (/audit)
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app

client = TestClient(app)


# ── Fixtures for Tokens ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def analyst_token():
    resp = client.post("/auth/login", json={"username": "analyst", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def investigator_token():
    resp = client.post("/auth/login", json={"username": "investigator", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


# ── System Endpoints ──────────────────────────────────────────────────────────

def test_health_check():
    """Verify healthcheck endpoint reports all 3 databases connected."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["databases"]["postgresql"] == "connected"
    assert data["databases"]["mongodb"] == "connected"
    assert data["databases"]["neo4j"] == "connected"


def test_root_endpoint():
    """Verify root endpoint returns system links."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "documentation" in resp.json()


# ── Auth & RBAC ───────────────────────────────────────────────────────────────

def test_invalid_login():
    """Verify login fails with invalid password."""
    resp = client.post("/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert resp.status_code == 401


def test_get_me_profile(investigator_token):
    """Verify /auth/me returns current user profile."""
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {investigator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "investigator"
    assert data["role"] == "investigator"


# ── Entity & Graph Endpoints ──────────────────────────────────────────────────

def test_entity_search(investigator_token):
    """Verify entity search locates Ravi Kumar."""
    resp = client.get("/entity/search?q=Ravi", headers={"Authorization": f"Bearer {investigator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0
    ids = [r["id"] for r in data["results"]]
    assert any("RAVI" in cid for cid in ids)


def test_entity_profile(investigator_token):
    """Verify full intelligence dossier for Kingpin Ravi Kumar."""
    resp = client.get("/entity/PER_RAVI_KUMAR", headers={"Authorization": f"Bearer {investigator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "PER_RAVI_KUMAR"
    assert data["label"] == "Person"
    assert "risk_score" in data["properties"]
    assert len(data["direct_connections"]) > 0


def test_entity_cytoscape_subgraph(investigator_token):
    """Verify Cytoscape-formatted N-hop subgraph expansion."""
    resp = client.get("/entity/PER_RAVI_KUMAR/graph?hops=1", headers={"Authorization": f"Bearer {investigator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    elements = data["elements"]
    assert len(elements["nodes"]) > 0
    assert len(elements["edges"]) > 0
    # Verify Cytoscape format: each node has a 'data' key with 'id'
    assert "data" in elements["nodes"][0]
    assert "id" in elements["nodes"][0]["data"]


# ── Analytics Endpoints & RBAC ────────────────────────────────────────────────

def test_analytics_influencers_allowed_analyst(analyst_token):
    """Verify analyst can view top influencers."""
    resp = client.get("/analytics/influencers?limit=5", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 5
    assert len(data["suspects"]) == 5


def test_analytics_rbac_forbidden_investigator(investigator_token):
    """Verify investigator is forbidden from viewing advanced analytics (RBAC)."""
    resp = client.get("/analytics/influencers", headers={"Authorization": f"Bearer {investigator_token}"})
    assert resp.status_code == 403


def test_analytics_communities(analyst_token):
    """Verify communities endpoint returns Louvain clusters."""
    resp = client.get("/analytics/communities", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_communities"] >= 3


def test_analytics_alerts(analyst_token):
    """Verify active anomaly alerts endpoint."""
    resp = client.get("/analytics/alerts", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0


def test_analytics_link_predictions(analyst_token):
    """Verify link predictions endpoint."""
    resp = client.get("/analytics/link-predictions", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0


# ── Cryptographic Audit Chain & Tamper Detection ──────────────────────────────

def test_audit_verify_admin_allowed(admin_token):
    """Verify admin can call cryptographic audit verification."""
    resp = client.get("/audit/verify", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SECURE"
    assert data["is_valid"] is True


def test_audit_verify_forbidden_analyst(analyst_token):
    """Verify analyst cannot verify audit chain (admin only)."""
    resp = client.get("/audit/verify", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 403


def test_audit_logs(admin_token):
    """Verify audit log list returns cryptographic SHA-256 hashes."""
    resp = client.get("/audit/logs?limit=5", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0
    first_block = data["blocks"][0]
    assert len(first_block["data_hash"]) == 64
    assert len(first_block["previous_hash"]) == 64
