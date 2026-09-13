"""
entity.py — Entity search, deep-dive profiles, and N-hop subgraph expansion.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from neo4j import Session

from backend.auth.rbac import require_role
from backend.db.connections import get_neo4j_session
from security.audit_chain import audit_chain
from security.encryption import decrypt_field

router = APIRouter(prefix="/entity", tags=["Entities & Graphs"])


@router.get("/search")
async def search_entities(
    q: str = Query("", description="Search term across name, phone, plate, or canonical ID"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("investigator")),
):
    """
    Search entities in the criminal graph across Person names, phone numbers,
    vehicle plates, and accounts. When query is empty, returns top high-risk suspects.
    """
    clean_q = q.strip().upper()
    if clean_q:
        query = """
        MATCH (n)
        WHERE (n:Person AND (toUpper(n.name) CONTAINS $q OR toUpper(n.canonical_id) CONTAINS $q))
           OR (n:PhoneNumber AND (n.number CONTAINS $q OR n.canonical_id CONTAINS $q))
           OR (n:Vehicle AND (toUpper(n.registration_number) CONTAINS $q OR n.canonical_id CONTAINS $q))
           OR (n:Account AND (toUpper(n.account_number) CONTAINS $q OR n.canonical_id CONTAINS $q))
           OR (n:Organization AND (toUpper(n.name) CONTAINS $q OR n.canonical_id CONTAINS $q))
        RETURN n.canonical_id AS id,
               n.canonical_id AS canonical_id,
               labels(n)[0] AS label,
               labels(n)[0] AS type,
               coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id) AS display_name,
               coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id) AS name,
               coalesce(n.risk_score, 0.0) AS risk_score,
               coalesce(n.betweenness, 0.0) AS betweenness,
               coalesce(n.pagerank, 0.0) AS pagerank,
               coalesce(n.degree, 0) AS degree,
               coalesce(n.community_id, 0) AS community_id,
               n.aliases AS aliases,
               properties(n) AS properties
        ORDER BY risk_score DESC
        LIMIT $limit
        """
        results = session.run(query, {"q": clean_q, "limit": limit}).data()
    else:
        query = """
        MATCH (n:Person)
        RETURN n.canonical_id AS id,
               n.canonical_id AS canonical_id,
               labels(n)[0] AS label,
               labels(n)[0] AS type,
               coalesce(n.name, n.canonical_id) AS display_name,
               coalesce(n.name, n.canonical_id) AS name,
               coalesce(n.risk_score, 0.0) AS risk_score,
               coalesce(n.betweenness, 0.0) AS betweenness,
               coalesce(n.pagerank, 0.0) AS pagerank,
               coalesce(n.degree, 0) AS degree,
               coalesce(n.community_id, 0) AS community_id,
               n.aliases AS aliases,
               properties(n) AS properties
        ORDER BY risk_score DESC
        LIMIT $limit
        """
        results = session.run(query, {"limit": limit}).data()

    audit_chain.append_block(
        action="ENTITY_SEARCH",
        actor=current_user["username"],
        details={"query": q, "result_count": len(results)},
    )

    return {
        "query": q,
        "count": len(results),
        "results": results,
    }


@router.get("/{entity_id}")
async def get_entity_profile(
    entity_id: str,
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("investigator")),
):
    """
    Retrieve full intelligence dossier for an entity, including risk breakdown,
    criminal history, and direct connected assets.
    """
    query = """
    MATCH (n {canonical_id: $cid})
    OPTIONAL MATCH (n)-[r]-(connected)
    RETURN n.canonical_id AS id,
           labels(n)[0] AS label,
           properties(n) AS properties,
           collect(DISTINCT {
               relation: type(r),
               target_id: connected.canonical_id,
               target_label: labels(connected)[0],
               target_name: coalesce(connected.name, connected.number, connected.registration_number, connected.account_number, connected.canonical_id),
               confidence: coalesce(r.confidence, 1.0),
               source_doc: coalesce(r.source_doc, 'INTERNAL')
           }) AS direct_connections
    """
    res = session.run(query, {"cid": entity_id}).single()
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with canonical ID '{entity_id}' not found in graph.",
        )

    props = res["properties"]
    label = res["label"]

    # Field-level encryption handling (03_DESIGN.md §8)
    if "confidential_notes" in props:
        if current_user["role"] in ("analyst", "admin"):
            props["confidential_notes"] = decrypt_field(props["confidential_notes"])
        else:
            props["confidential_notes"] = "[REDACTED — ANALYST/ADMIN CLEARANCE REQUIRED]"

    audit_chain.append_block(
        action="ENTITY_VIEWED",
        actor=current_user["username"],
        entity_id=entity_id,
        details={"label": label},
    )

    # Return flattened profile properties for direct UI access
    resolved_name = (
        props.get("name")
        or props.get("number")
        or props.get("registration_number")
        or props.get("account_number")
        or res["id"]
    )

    # Extract multi-modal connected assets
    phones = [
        c["target_name"] for c in res["direct_connections"]
        if c["target_label"] == "PhoneNumber" or (c.get("relation") == "OWNS_OR_USES" and str(c.get("target_id", "")).startswith("PHN_"))
    ]
    vehicles = [
        {"reg": c["target_name"], "type": "VEHICLE"} for c in res["direct_connections"]
        if c["target_label"] == "Vehicle" or str(c.get("target_id", "")).startswith("VEH_")
    ]
    accounts = [
        {"num": c["target_name"]} for c in res["direct_connections"]
        if c["target_label"] == "Account" or str(c.get("target_id", "")).startswith("ACC_")
    ]

    # Attempt PostgreSQL criminal_records lookup for person entities
    past_cases = props.get("past_cases", [])
    if label == "Person":
        try:
            from backend.db.connections import get_pg_connection
            with get_pg_connection() as pg_conn:
                with pg_conn.cursor() as cur:
                    cur.execute(
                        "SELECT past_cases, aliases, known_address, date_of_birth FROM criminal_records WHERE name ILIKE %s LIMIT 1",
                        (resolved_name,),
                    )
                    row = cur.fetchone()
                    if row:
                        if row[0] and not past_cases:
                            past_cases = row[0]
                        if row[1] and not props.get("aliases"):
                            props["aliases"] = row[1]
                        if row[2] and not props.get("known_address"):
                            props["known_address"] = row[2]
                        if row[3] and not props.get("date_of_birth"):
                            props["date_of_birth"] = str(row[3])
        except Exception:
            pass

    return {
        "id": res["id"],
        "canonical_id": res["id"],
        "label": label,
        "type": label,
        "name": resolved_name,
        "phone_numbers": phones,
        "vehicles": vehicles,
        "accounts": accounts,
        "past_cases": past_cases,
        **props,
        "properties": props,
        "direct_connections": res["direct_connections"],
    }


@router.get("/{entity_id}/graph")
async def get_entity_subgraph(
    entity_id: str,
    hops: int = Query(1, ge=1, le=3, description="Expansion depth (1 to 3 hops)"),
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("investigator")),
):
    """
    Extract N-hop ego subgraph around an entity, formatted for Cytoscape.js visualization.
    """
    subgraph_query = """
    MATCH (start {canonical_id: $cid})
    MATCH path = (start)-[*1..%d]-(connected)
    UNWIND nodes(path) AS n
    UNWIND relationships(path) AS r
    RETURN
        collect(DISTINCT {
            data: {
                id: n.canonical_id,
                label: coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id),
                name: coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id),
                display_name: coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id),
                risk_score: coalesce(n.risk_score, 0.0),
                community_id: coalesce(n.community_id, 0),
                type: labels(n)[0],
                label_type: labels(n)[0]
            }
        }) AS nodes,
        collect(DISTINCT {
            data: {
                id: elementId(r),
                source: startNode(r).canonical_id,
                target: endNode(r).canonical_id,
                label: type(r),
                type: type(r),
                confidence: coalesce(r.confidence, 1.0),
                source_doc: coalesce(r.source_doc, '')
            }
        }) AS edges
    """ % hops

    result = session.run(subgraph_query, {"cid": entity_id}).single()

    nodes = result["nodes"] if result and result["nodes"] else []
    edges = result["edges"] if result and result["edges"] else []

    # If entity has 0 edges, return single center node
    if not nodes:
        center = session.run("MATCH (n {canonical_id: $cid}) RETURN n, labels(n)[0] AS l", {"cid": entity_id}).single()
        if center:
            cn = center["n"]
            nodes = [{
                "data": {
                    "id": cn["canonical_id"],
                    "label": center["l"],
                    "name": cn.get("name", cn["canonical_id"]),
                    "risk_score": cn.get("risk_score", 0.0),
                    "community_id": cn.get("community_id", 0),
                    "type": center["l"],
                }
            }]

    audit_chain.append_block(
        action="ENTITY_GRAPH_EXPANDED",
        actor=current_user["username"],
        entity_id=entity_id,
        details={"hops": hops, "node_count": len(nodes), "edge_count": len(edges)},
    )

    return {
        "center_id": entity_id,
        "hops": hops,
        "elements": {
            "nodes": nodes,
            "edges": edges,
        },
    }
