"""
common_cypher.py — Reusable Cypher queries and templates for the Neo4j graph layer.
"""

# ── Node Merge Queries ────────────────────────────────────────────────────────

MERGE_PERSON = """
MERGE (p:Person {canonical_id: $canonical_id})
ON CREATE SET
    p.name = $name,
    p.aliases = $aliases,
    p.risk_flag = $risk_flag,
    p.known_address = $known_address,
    p.risk_score = 0.0,
    p.betweenness = 0.0,
    p.pagerank = 0.0,
    p.created_at = datetime()
ON MATCH SET
    p.name = coalesce(p.name, $name),
    p.aliases = apoc.coll.toSet(coalesce(p.aliases, []) + coalesce($aliases, [])),
    p.risk_flag = coalesce($risk_flag, p.risk_flag),
    p.known_address = coalesce($known_address, p.known_address)
RETURN p.canonical_id AS id
"""

MERGE_LOCATION = """
MERGE (l:Location {canonical_id: $canonical_id})
ON CREATE SET
    l.name = $name,
    l.lat = $lat,
    l.lng = $lng,
    l.created_at = datetime()
ON MATCH SET
    l.name = coalesce(l.name, $name),
    l.lat = coalesce(l.lat, $lat),
    l.lng = coalesce(l.lng, $lng)
RETURN l.canonical_id AS id
"""

MERGE_VEHICLE = """
MERGE (v:Vehicle {canonical_id: $canonical_id})
ON CREATE SET
    v.registration_number = $registration_number,
    v.type = $type,
    v.owner_name = $owner_name,
    v.created_at = datetime()
ON MATCH SET
    v.type = coalesce($type, v.type),
    v.owner_name = coalesce($owner_name, v.owner_name)
RETURN v.canonical_id AS id
"""

MERGE_PHONE = """
MERGE (ph:PhoneNumber {canonical_id: $canonical_id})
ON CREATE SET
    ph.number = $number,
    ph.created_at = datetime()
RETURN ph.canonical_id AS id
"""

MERGE_ORGANIZATION = """
MERGE (o:Organization {canonical_id: $canonical_id})
ON CREATE SET
    o.name = $name,
    o.type = $type,
    o.created_at = datetime()
ON MATCH SET
    o.name = coalesce(o.name, $name)
RETURN o.canonical_id AS id
"""

MERGE_ACCOUNT = """
MERGE (a:Account {canonical_id: $canonical_id})
ON CREATE SET
    a.account_number = $account_number,
    a.bank_name = $bank_name,
    a.created_at = datetime()
ON MATCH SET
    a.bank_name = coalesce($bank_name, a.bank_name)
RETURN a.canonical_id AS id
"""

MERGE_EVENT = """
MERGE (e:Event {canonical_id: $canonical_id})
ON CREATE SET
    e.description = $description,
    e.date = $date,
    e.location = $location,
    e.created_at = datetime()
RETURN e.canonical_id AS id
"""

# ── Dynamic Relationship Merge ────────────────────────────────────────────────

def get_merge_rel_query(predicate: str, label_from: str = None, label_to: str = None) -> str:
    """
    Generate Cypher query to merge a relationship of given predicate.
    Labels can be specified or wildcard matched on canonical_id.
    """
    from_match = f"(a:{label_from} {{canonical_id: $from_id}})" if label_from else "(a {canonical_id: $from_id})"
    to_match = f"(b:{label_to} {{canonical_id: $to_id}})" if label_to else "(b {canonical_id: $to_id})"

    return f"""
    MATCH {from_match}
    MATCH {to_match}
    WHERE a <> b
    MERGE (a)-[r:{predicate}]->(b)
    ON CREATE SET
        r.confidence = $confidence,
        r.source_doc = $source_doc,
        r.weight = coalesce($weight, 1.0),
        r.created_at = datetime()
    ON MATCH SET
        r.confidence = CASE WHEN $confidence > coalesce(r.confidence, 0.0) THEN $confidence ELSE r.confidence END,
        r.weight = coalesce(r.weight, 1.0) + coalesce($weight, 0.0)
    RETURN count(r) AS count
    """

# ── Graph Query Templates for API ─────────────────────────────────────────────

QUERY_N_HOP_SUBGRAPH = """
MATCH (start {canonical_id: $canonical_id})
CALL apoc.path.subgraphAll(start, {
    maxLevel: $hops,
    bfs: true
})
YIELD nodes, relationships
RETURN
    [n in nodes | {
        id: n.canonical_id,
        label: labels(n)[0],
        name: coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id),
        properties: properties(n)
    }] AS nodes,
    [r in relationships | {
        source: startNode(r).canonical_id,
        target: endNode(r).canonical_id,
        type: type(r),
        properties: properties(r)
    }] AS edges
"""

QUERY_SHORTEST_PATH = """
MATCH (a {canonical_id: $from_id}), (b {canonical_id: $to_id})
MATCH p = shortestPath((a)-[*..6]-(b))
RETURN
    [n in nodes(p) | {
        id: n.canonical_id,
        label: labels(n)[0],
        name: coalesce(n.name, n.number, n.registration_number, n.account_number, n.canonical_id)
    }] AS path_nodes,
    [r in relationships(p) | {
        source: startNode(r).canonical_id,
        target: endNode(r).canonical_id,
        type: type(r)
    }] AS path_edges
"""

COUNT_NODES_BY_LABEL = """
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
"""

COUNT_EDGES_BY_TYPE = """
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS count
ORDER BY count DESC
"""
