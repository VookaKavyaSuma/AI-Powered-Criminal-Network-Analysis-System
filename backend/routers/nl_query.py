"""
nl_query.py — Natural Language to Cypher translation via Groq LLM with safety guardrails and offline fallback.

Allows investigators to query the crime network in plain English:
e.g. "Show all people connected to Ravi Kumar within 2 hops"
     "Who received money from Malabar Logistics?"
     "Which suspects have high risk scores above 70?"

Security Guardrails:
- Strictly enforces READ-ONLY Cypher queries (blocks CREATE, MERGE, DELETE, DETACH, SET, DROP, etc.)
- Enforces maximum result LIMIT (default 50)
- Injects full Neo4j ontology into LLM context
- Offline rule-based regex template fallback if Groq API is unreachable
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from neo4j import Session
from pydantic import BaseModel

from backend.auth.rbac import require_role
from backend.db.connections import get_neo4j_session
from security.audit_chain import audit_chain

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

router = APIRouter(prefix="/query", tags=["Natural Language Query"])

FORBIDDEN_CYPHER_KEYWORDS = [
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bDELETE\b",
    r"\bDETACH\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bLOAD\s+CSV\b",
    r"\bCALL\b",
]

CYPHER_SCHEMA_PROMPT = """
You are an expert Cypher query generator for a Neo4j Criminal Network Analysis graph.
Given an investigator's question in plain English, output ONLY a valid, read-only Cypher query.

Graph Ontology:
Nodes:
- (:Person {canonical_id, name, risk_score, risk_flag, degree, betweenness, pagerank, community_id, past_case_count})
- (:PhoneNumber {canonical_id, number})
- (:Vehicle {canonical_id, registration_number, type, owner_name})
- (:Account {canonical_id, account_number, bank_name})
- (:Organization {canonical_id, name, type})
- (:Location {canonical_id, name})
- (:Event {canonical_id, description, date})

Relationships:
- (:Person)-[:OWNS_OR_USES]->(:PhoneNumber | :Vehicle | :Account)
- (:Person)-[:MET_WITH]->(:Person)
- (:Person)-[:MEMBER_OF]->(:Organization)
- (:Person)-[:PRESENT_AT]->(:Location | :Event)
- (:Person)-[:ASSOCIATED_WITH]->(:Person)
- (:Person)-[:PREDICTED_LINK]->(:Person)
- (:PhoneNumber)-[:CALLED]->(:PhoneNumber)
- (:Account)-[:TRANSFERRED_MONEY_TO]->(:Account)

Rules:
1. Output ONLY the raw Cypher query. Do not wrap in markdown or explanation.
2. The query MUST be strictly READ-ONLY (use MATCH, OPTIONAL MATCH, WHERE, RETURN, ORDER BY, LIMIT).
3. If returning graph elements for visualization, return nodes and relationships or path: 'RETURN path' or 'RETURN p, r, m'.
4. Always append 'LIMIT 50' if no limit is specified.
5. Use case-insensitive matching where appropriate: 'toUpper(n.name) CONTAINS toUpper($val)'.
"""


class NLQueryRequest(BaseModel):
    question: str


def validate_cypher(cypher: str) -> str:
    """
    Ensure the generated Cypher query is read-only and safe.
    Raises HTTPException if destructive or mutation operations are detected.
    """
    clean = cypher.strip()
    # Strip markdown if present
    clean = re.sub(r"^```(cypher)?", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"```$", "", clean).strip()

    for pattern in FORBIDDEN_CYPHER_KEYWORDS:
        if re.search(pattern, clean, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security violation: Cypher query contains forbidden mutation keyword matching '{pattern}'.",
            )

    # Ensure LIMIT exists
    if not re.search(r"\bLIMIT\s+\d+\b", clean, re.IGNORECASE):
        clean = f"{clean.rstrip(';')} LIMIT 50"

    return clean


def generate_cypher_with_groq(question: str) -> Optional[str]:
    """Call Groq LLM to translate English question to Cypher."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CYPHER_SCHEMA_PROMPT},
                {"role": "user", "content": f"Investigator Question: {question}"},
            ],
            temperature=0.0,
            max_tokens=250,
        )
        content = response.choices[0].message.content.strip()
        return content
    except Exception as e:
        print(f"  [Notice] Groq NL query error: {e}, falling back to template engine.")
        return None


def generate_cypher_template_fallback(question: str) -> str:
    """Offline rule-based fallback generating Cypher for common investigator queries."""
    q = question.lower().strip()

    # Pattern 1: High risk / top suspects
    if any(k in q for k in ["high risk", "top suspects", "most dangerous", "highest risk", "who is the kingpin"]):
        return """
        MATCH (p:Person)
        WHERE p.risk_score IS NOT NULL
        RETURN p.canonical_id AS id, p.name AS name, p.risk_score AS risk_score, p.risk_flag AS risk_flag
        ORDER BY p.risk_score DESC
        LIMIT 10
        """.strip()

    # Pattern 2: Financial structuring / smurfing
    if any(k in q for k in ["structuring", "smurfing", "money laundering", "suspicious transactions"]):
        return """
        MATCH path = (a1:Account)-[r:TRANSFERRED_MONEY_TO]->(a2:Account)
        WHERE r.flagged_structuring = true
        RETURN path
        LIMIT 25
        """.strip()

    # Pattern 3: Communication / Phone calls for a person
    if "call" in q or "phone" in q:
        name_match = re.search(r"(?:of|for|from|did|with)\s+([A-Za-z\s]+)", q)
        target_name = name_match.group(1).strip() if name_match else "Ravi"
        return f"""
        MATCH path = (p:Person)-[:OWNS_OR_USES]->(ph:PhoneNumber)-[r:CALLED]->(ph2:PhoneNumber)
        WHERE toUpper(p.name) CONTAINS toUpper('{target_name}')
        RETURN path
        LIMIT 30
        """.strip()

    # Pattern 4: Communities / operational cells
    if "community" in q or "cell" in q or "cluster" in q:
        return """
        MATCH (p:Person)
        WHERE p.community_id IS NOT NULL
        RETURN p.community_id AS cell_id, count(p) AS member_count, collect(p.name)[0..5] AS sample_members
        ORDER BY member_count DESC
        LIMIT 10
        """.strip()

    # Pattern 5: Default 2-hop ego network for named suspect
    name_match = re.search(r"(?:about|for|of|connected to)\s+([A-Za-z\s]+)", q)
    target = name_match.group(1).strip() if name_match else "Ravi"
    return f"""
    MATCH path = (p:Person)-[*1..2]-(connected)
    WHERE toUpper(p.name) CONTAINS toUpper('{target}')
    RETURN path
    LIMIT 40
    """.strip()


@router.post("/natural-language")
async def natural_language_query(
    req: NLQueryRequest,
    session: Session = Depends(get_neo4j_session),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Translate plain English questions to Cypher, execute safely against Neo4j,
    and return structured records and visual Cytoscape subgraph.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty.")

    # 1. Translate using Groq or Fallback
    cypher_raw = generate_cypher_with_groq(question)
    if not cypher_raw:
        cypher_raw = generate_cypher_template_fallback(question)

    # 2. Validate Cypher with strict security guardrails
    validated_cypher = validate_cypher(cypher_raw)

    # 3. Execute Cypher in Neo4j
    try:
        raw_results = session.run(validated_cypher).data()
    except Exception as e:
        # If generated Cypher had a syntax issue, use template fallback
        fallback_cypher = validate_cypher(generate_cypher_template_fallback(question))
        validated_cypher = fallback_cypher
        raw_results = session.run(fallback_cypher).data()

    # 4. Extract Cytoscape visual graph elements if paths/nodes are present
    nodes_map: Dict[str, Any] = {}
    edges_list: List[Dict[str, Any]] = []

    for row in raw_results:
        for val in row.values():
            # Check for path object
            if hasattr(val, "nodes") and hasattr(val, "relationships"):
                for n in val.nodes:
                    cid = n.get("canonical_id", str(n.id))
                    if cid not in nodes_map:
                        nodes_map[cid] = {
                            "data": {
                                "id": cid,
                                "label": list(n.labels)[0] if n.labels else "Entity",
                                "name": n.get("name", n.get("number", n.get("registration_number", cid))),
                                "risk_score": n.get("risk_score", 0.0),
                            }
                        }
                for r in val.relationships:
                    edges_list.append({
                        "data": {
                            "id": r.element_id,
                            "source": r.start_node.get("canonical_id", str(r.start_node.id)),
                            "target": r.end_node.get("canonical_id", str(r.end_node.id)),
                            "label": r.type,
                            "confidence": r.get("confidence", 1.0),
                        }
                    })

    # Log query to cryptographic audit chain
    audit_chain.append_block(
        action="NL_QUERY_EXECUTED",
        actor=current_user["username"],
        details={"question": question, "cypher": validated_cypher, "result_count": len(raw_results)},
    )

    return {
        "question": question,
        "generated_cypher": validated_cypher,
        "result_count": len(raw_results),
        "results": raw_results,
        "subgraph": {
            "nodes": list(nodes_map.values()),
            "edges": edges_list,
        },
    }
