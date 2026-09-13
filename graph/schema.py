"""
schema.py — Neo4j graph schema, uniqueness constraints, and index definitions.

Defines uniqueness constraints on canonical_id for all 7 ontology node types:
- Person
- Location
- Vehicle
- PhoneNumber
- Organization
- Event
- Account
"""

import os
import sys
from typing import List

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def get_neo4j_driver():
    """Create and return Neo4j Bolt driver."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "cna_neo4j_2026")
    return GraphDatabase.driver(uri, auth=(user, password))


# Uniqueness constraints ensure idempotent MERGE operations on canonical_id
CONSTRAINTS = [
    "CREATE CONSTRAINT person_canonical_id IF NOT EXISTS FOR (p:Person) REQUIRE p.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT location_canonical_id IF NOT EXISTS FOR (l:Location) REQUIRE l.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT vehicle_canonical_id IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT phone_canonical_id IF NOT EXISTS FOR (p:PhoneNumber) REQUIRE p.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT org_canonical_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT event_canonical_id IF NOT EXISTS FOR (e:Event) REQUIRE e.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT account_canonical_id IF NOT EXISTS FOR (a:Account) REQUIRE a.canonical_id IS UNIQUE",
]

# Secondary lookup indexes for performance
INDEXES = [
    "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
    "CREATE INDEX person_risk_idx IF NOT EXISTS FOR (p:Person) ON (p.risk_score)",
    "CREATE INDEX vehicle_reg_idx IF NOT EXISTS FOR (v:Vehicle) ON (v.registration_number)",
    "CREATE INDEX phone_num_idx IF NOT EXISTS FOR (p:PhoneNumber) ON (p.number)",
    "CREATE INDEX account_num_idx IF NOT EXISTS FOR (a:Account) ON (a.account_number)",
]


def apply_schema(driver=None) -> List[str]:
    """Apply all uniqueness constraints and indexes to the Neo4j instance."""
    own_driver = False
    if driver is None:
        driver = get_neo4j_driver()
        own_driver = True

    created = []
    print("📐 Applying Neo4j schema constraints and indexes...")
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            try:
                session.run(stmt)
                name = stmt.split()[2]
                created.append(f"Constraint: {name}")
                print(f"   ✅ Constraint applied: {name}")
            except Exception as e:
                print(f"   ⚠️ Could not apply constraint: {e}")

        for stmt in INDEXES:
            try:
                session.run(stmt)
                name = stmt.split()[2]
                created.append(f"Index: {name}")
                print(f"   ✅ Index applied: {name}")
            except Exception as e:
                print(f"   ⚠️ Could not apply index: {e}")

    if own_driver:
        driver.close()

    print(f"🎉 Neo4j Schema applied successfully ({len(created)} constraints/indexes active).\n")
    return created


def clear_database(driver=None):
    """Utility to clear all graph data (nodes and relationships) — used during resets."""
    own_driver = False
    if driver is None:
        driver = get_neo4j_driver()
        own_driver = True

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        print("🧹 Neo4j database cleared.")

    if own_driver:
        driver.close()


if __name__ == "__main__":
    apply_schema()
