"""
analytics.py — Analytics endpoints exposing centrality influencers, communities, link predictions, and anomaly alerts.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from neo4j import Session

from analytics.run_all import run_pipeline
from backend.auth.rbac import require_role
from backend.db.connections import get_neo4j_session
from security.audit_chain import audit_chain

router = APIRouter(prefix="/analytics", tags=["Graph Analytics"])


@router.get("/influencers")
async def get_top_influencers(
    sort_by: str = Query("risk_score", enum=["risk_score", "betweenness", "pagerank", "degree"]),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Retrieve top ranked criminal suspects sorted by multi-criteria risk score or centrality.
    Includes full explainability sub-score breakdown.
    """
    field_map = {
        "risk_score": "p.risk_score",
        "betweenness": "p.betweenness",
        "pagerank": "p.pagerank",
        "degree": "p.degree",
    }
    sort_field = field_map.get(sort_by, "p.risk_score")

    query = f"""
    MATCH (p:Person)
    WHERE {sort_field} IS NOT NULL
    RETURN p.canonical_id AS id,
           p.name AS name,
           p.risk_flag AS risk_flag,
           coalesce(p.risk_score, 0.0) AS risk_score,
           coalesce(p.betweenness, 0.0) AS betweenness,
           coalesce(p.pagerank, 0.0) AS pagerank,
           coalesce(p.degree, 0) AS degree,
           coalesce(p.score_betweenness, 0.0) AS score_betweenness,
           coalesce(p.score_pagerank, 0.0) AS score_pagerank,
           coalesce(p.score_criminal_history, 0.0) AS score_criminal_history,
           coalesce(p.score_suspicious_txns, 0.0) AS score_suspicious_txns,
           coalesce(p.score_comm_anomaly, 0.0) AS score_comm_anomaly,
           coalesce(p.community_id, 0) AS community_id
    ORDER BY {sort_field} DESC
    LIMIT $limit
    """
    rows = session.run(query, {"limit": limit}).data()

    audit_chain.append_block(
        action="ANALYTICS_INFLUENCERS_VIEWED",
        actor=current_user["username"],
        details={"sort_by": sort_by, "limit": limit},
    )

    return {
        "sort_by": sort_by,
        "count": len(rows),
        "suspects": rows,
    }


@router.get("/communities")
async def get_communities(
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Retrieve detected Louvain operational cells, sizes, and leading member profiles.
    """
    query = """
    MATCH (p:Person)
    WHERE p.community_id IS NOT NULL
    WITH p.community_id AS comm_id, collect(p) AS members
    RETURN comm_id AS community_id,
           size(members) AS member_count,
           [m in members[0..6] | {
               id: m.canonical_id,
               name: m.name,
               risk_score: coalesce(m.risk_score, 0.0),
               risk_flag: coalesce(m.risk_flag, 'LOW')
           }] AS top_members
    ORDER BY member_count DESC
    """
    communities = session.run(query).data()

    return {
        "total_communities": len(communities),
        "communities": communities,
    }


@router.get("/link-predictions")
async def get_link_predictions(
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Retrieve suggested hidden or unobserved criminal relationships with confidence scores.
    """
    query = """
    MATCH (p1:Person)-[r:PREDICTED_LINK]->(p2:Person)
    RETURN p1.canonical_id AS source_id,
           p1.name AS source_name,
           p2.canonical_id AS target_id,
           p2.name AS target_name,
           coalesce(r.confidence, 0.75) AS confidence,
           coalesce(r.common_neighbors, 0) AS common_neighbors,
           coalesce(r.jaccard_similarity, 0.0) AS jaccard_similarity
    ORDER BY r.confidence DESC, r.common_neighbors DESC
    LIMIT $limit
    """
    links = session.run(query, {"limit": limit}).data()

    return {
        "count": len(links),
        "predictions": links,
    }


@router.get("/alerts")
async def get_active_alerts(
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Retrieve active behavioral anomalies: smurfing/structuring and communication bursts.
    """
    query = """
    MATCH (p:Person)
    WHERE p.comm_anomaly_score > 0.5 OR p.has_structuring_alert = true
    RETURN p.canonical_id AS id,
           p.name AS name,
           coalesce(p.risk_score, 0.0) AS risk_score,
           coalesce(p.comm_anomaly_score, 0.0) AS comm_anomaly_score,
           coalesce(p.suspicious_txns_count, 0) AS suspicious_txns_count,
           coalesce(p.has_structuring_alert, false) AS has_structuring_alert
    ORDER BY p.suspicious_txns_count DESC, p.comm_anomaly_score DESC
    """
    alerts = session.run(query).data()

    return {
        "count": len(alerts),
        "alerts": alerts,
    }


@router.post("/rerun")
async def trigger_analytics_recalculation(
    current_user: dict = Depends(require_role("admin")),
):
    """
    Trigger full recalculation of graph centralities, communities, anomalies,
    and risk scores on-demand (admin only).
    """
    results = run_pipeline()

    audit_chain.append_block(
        action="ANALYTICS_RECALCULATED",
        actor=current_user["username"],
        details={"result": "SUCCESS"},
    )

    return {
        "status": "success",
        "message": "Graph analytics and risk scoring recalculated successfully.",
        "summary": results,
    }
