"""
loader.py — Unified Neo4j Graph Loader.

Architectural Rule:
This script is the SOLE WRITER to the Neo4j database. It integrates:
1. Structured data from PostgreSQL (criminal records, vehicles, CDRs, financial transactions).
2. Unstructured NLP-extracted entities and relations from MongoDB.

Uses idempotent MERGE queries keyed on canonical_id to ensure zero duplicate nodes.
"""

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from neo4j import GraphDatabase

from graph.queries.common_cypher import (
    COUNT_EDGES_BY_TYPE,
    COUNT_NODES_BY_LABEL,
)
from graph.schema import apply_schema, get_neo4j_driver
from ingestion.db_writers.mongo_writer import MongoWriter
from ingestion.db_writers.postgres_writer import get_postgres_connection

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class GraphLoader:
    """Orchestrates graph loading into Neo4j from PostgreSQL and MongoDB."""

    def __init__(self):
        self.driver = get_neo4j_driver()
        self.mongo_writer = MongoWriter()

    def close(self):
        if self.driver:
            self.driver.close()

    # ── Phase A: Load Structured PostgreSQL Data ──────────────────────────────

    def load_postgres_criminal_records(self, session) -> int:
        """Load criminal records into Person nodes."""
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, aliases, known_address, past_cases, known_associates, risk_flag FROM criminal_records;")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        count = 0
        for name, aliases, address, past_cases, associates, risk_flag in rows:
            # Generate canonical ID for person
            slug = re.sub(r"[^\w]", "_", name.strip().lower()).strip("_").upper()
            cid = f"PER_{slug}"

            # Format past cases count/summary
            past_cases_list = past_cases if isinstance(past_cases, list) else []
            if isinstance(past_cases, str) and past_cases.strip():
                try:
                    past_cases_list = json.loads(past_cases)
                except Exception:
                    past_cases_list = []

            query = """
            MERGE (p:Person {canonical_id: $cid})
            ON CREATE SET
                p.name = $name,
                p.aliases = $aliases,
                p.known_address = $address,
                p.risk_flag = $risk_flag,
                p.past_case_count = $past_case_count,
                p.created_at = datetime()
            ON MATCH SET
                p.aliases = apoc.coll.toSet(coalesce(p.aliases, []) + coalesce($aliases, [])),
                p.risk_flag = coalesce($risk_flag, p.risk_flag),
                p.known_address = coalesce($address, p.known_address)
            """
            # If APOC is not available, simple SET
            simple_query = """
            MERGE (p:Person {canonical_id: $cid})
            SET
                p.name = $name,
                p.aliases = $aliases,
                p.known_address = $address,
                p.risk_flag = $risk_flag,
                p.past_case_count = $past_case_count
            """
            session.run(simple_query, {
                "cid": cid,
                "name": name,
                "aliases": list(aliases) if aliases else [],
                "address": address,
                "risk_flag": risk_flag,
                "past_case_count": len(past_cases_list),
            })
            count += 1

            # Also create ASSOCIATED_WITH relations if associates are listed
            if associates:
                for assoc_name in associates:
                    assoc_clean = assoc_name.strip()
                    assoc_slug = re.sub(r"[^\w]", "_", assoc_clean.lower()).strip("_").upper()
                    is_org = any(o in assoc_clean.lower() for o in ["malabar", "apex", "bakery", "motors", "logistics", "shipping"])
                    if is_org:
                        assoc_cid = f"ORG_{assoc_slug}"
                        assoc_query = """
                        MERGE (o:Organization {canonical_id: $assoc_cid})
                        ON CREATE SET o.name = $assoc_name
                        MERGE (p1:Person {canonical_id: $cid})
                        MERGE (p1)-[r:ASSOCIATED_WITH]->(o)
                        SET r.source_doc = 'CRIMINAL_HISTORY', r.confidence = 0.85
                        """
                    else:
                        assoc_cid = f"PER_{assoc_slug}"
                        if assoc_cid == cid:
                            continue
                        assoc_query = """
                        MERGE (p2:Person {canonical_id: $assoc_cid})
                        ON CREATE SET p2.name = $assoc_name
                        MERGE (p1:Person {canonical_id: $cid})
                        MERGE (p1)-[r:ASSOCIATED_WITH]->(p2)
                        SET r.source_doc = 'CRIMINAL_HISTORY', r.confidence = 0.85
                        """
                    session.run(assoc_query, {
                        "cid": cid,
                        "assoc_cid": assoc_cid,
                        "assoc_name": assoc_clean,
                    })

        return count

    def load_postgres_vehicles(self, session) -> int:
        """Load vehicle registry and link owners."""
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT registration_number, owner_name, vehicle_type, registered_address FROM vehicle_records;")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        count = 0
        for reg_num, owner, vtype, address in rows:
            clean_reg = re.sub(r"[\s\-]", "", reg_num).upper()
            vid = f"VEH_{clean_reg}"

            query = """
            MERGE (v:Vehicle {canonical_id: $vid})
            SET
                v.registration_number = $reg_num,
                v.type = $vtype,
                v.owner_name = $owner,
                v.registered_address = $address
            """
            session.run(query, {
                "vid": vid,
                "reg_num": clean_reg,
                "vtype": vtype,
                "owner": owner,
                "address": address,
            })
            count += 1

            # Link Owner -> Vehicle (OWNS_OR_USES)
            if owner and owner.strip() and owner != "—":
                owner_clean = owner.strip()
                owner_slug = re.sub(r"[^\w]", "_", owner_clean.lower()).strip("_").upper()
                is_org = any(o in owner_clean.lower() for o in ["malabar", "apex", "bakery", "motors", "logistics", "shipping"])
                if is_org:
                    owner_cid = f"ORG_{owner_slug}"
                    link_query = """
                    MERGE (o:Organization {canonical_id: $owner_cid})
                    ON CREATE SET o.name = $owner
                    WITH o
                    MATCH (v:Vehicle {canonical_id: $vid})
                    MERGE (o)-[r:OWNS_OR_USES]->(v)
                    SET r.source_doc = 'VEHICLE_REGISTRY', r.confidence = 0.95
                    """
                else:
                    owner_cid = f"PER_{owner_slug}"
                    link_query = """
                    MERGE (p:Person {canonical_id: $owner_cid})
                    ON CREATE SET p.name = $owner
                    WITH p
                    MATCH (v:Vehicle {canonical_id: $vid})
                    MERGE (p)-[r:OWNS_OR_USES]->(v)
                    SET r.source_doc = 'VEHICLE_REGISTRY', r.confidence = 0.95
                    """
                session.run(link_query, {
                    "owner_cid": owner_cid,
                    "owner": owner_clean,
                    "vid": vid,
                })

        return count

    def load_postgres_cdrs(self, session, limit: int = 1000) -> int:
        """Load CDR records as PhoneNumber nodes and CALLED relationships."""
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT caller_number, callee_number, COUNT(*) as call_freq,
                   SUM(duration_sec) as total_sec, MAX(call_timestamp) as last_call,
                   MAX(source_name) as src
            FROM cdr_records
            GROUP BY caller_number, callee_number;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        count = 0
        query = """
        MERGE (p1:PhoneNumber {canonical_id: $caller_id})
        ON CREATE SET p1.number = $caller_num
        MERGE (p2:PhoneNumber {canonical_id: $callee_id})
        ON CREATE SET p2.number = $callee_num
        MERGE (p1)-[r:CALLED]->(p2)
        SET
            r.frequency = $freq,
            r.total_duration_sec = $total_sec,
            r.last_timestamp = toString($last_call),
            r.confidence = 0.98,
            r.source_doc = $source_doc
        """
        for caller, callee, freq, total_sec, last_call, src in rows:
            caller_clean = re.sub(r"\D", "", str(caller))[-10:]
            callee_clean = re.sub(r"\D", "", str(callee))[-10:]
            session.run(query, {
                "caller_id": f"PHN_{caller_clean}",
                "caller_num": caller_clean,
                "callee_id": f"PHN_{callee_clean}",
                "callee_num": callee_clean,
                "freq": freq,
                "total_sec": total_sec or 0,
                "last_call": str(last_call),
                "source_doc": src or "CDR_PROVIDER",
            })
            count += 1
        return count

    def load_postgres_transactions(self, session) -> int:
        """Load financial transactions as Account nodes and TRANSFERRED_MONEY_TO edges."""
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT sender_account, receiver_account, COUNT(*) as txn_count,
                   SUM(amount) as total_amount, MAX(flagged_structuring::int) as has_structuring,
                   MAX(bank_name) as bank, MAX(source_name) as src
            FROM transactions
            GROUP BY sender_account, receiver_account;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        count = 0
        query = """
        MERGE (a1:Account {canonical_id: $acc1_id})
        ON CREATE SET a1.account_number = $acc1_num, a1.bank_name = $bank
        MERGE (a2:Account {canonical_id: $acc2_id})
        ON CREATE SET a2.account_number = $acc2_num
        MERGE (a1)-[r:TRANSFERRED_MONEY_TO]->(a2)
        SET
            r.amount = $total_amount,
            r.frequency = $txn_count,
            r.flagged_structuring = ($has_structuring = 1),
            r.confidence = 0.99,
            r.source_doc = $source_doc
        """
        for sender, receiver, txn_count, total_amount, has_structuring, bank, src in rows:
            session.run(query, {
                "acc1_id": f"ACC_{sender}",
                "acc1_num": sender,
                "acc2_id": f"ACC_{receiver}",
                "acc2_num": receiver,
                "total_amount": float(total_amount),
                "txn_count": txn_count,
                "has_structuring": has_structuring or 0,
                "bank": bank,
                "source_doc": src or "FININT_BATCH",
            })
            count += 1
        return count

    # ── Phase B: Load Unstructured MongoDB Extracted Data ──────────────────────

    def load_mongo_extracted_data(self, session) -> Tuple[int, int]:
        """Load NLP-extracted entities and relationships from MongoDB."""
        docs = self.mongo_writer.get_documents({"processing_status": "extracted"})
        node_count = 0
        rel_count = 0

        # Cache of already created canonical IDs to avoid redundant Cypher calls
        created_nodes: Set[str] = set()

        for doc in docs:
            source_doc = doc.get("source_name", "UNKNOWN_DOC")
            extracted = doc.get("extracted", {})
            entities = extracted.get("entities", [])
            relations = extracted.get("relations", [])

            # 1. Merge Nodes
            for e in entities:
                cid = e.get("canonical_id")
                etype = e.get("type", "Entity")
                text = e.get("canonical_value", e.get("text", cid))

                if not cid or cid in created_nodes:
                    continue

                # Enforce node label from canonical_id prefix
                if cid.startswith("ORG_"):
                    q = "MERGE (o:Organization {canonical_id: $cid}) ON CREATE SET o.name = $name"
                    session.run(q, {"cid": cid, "name": text})
                elif cid.startswith("LOC_"):
                    q = "MERGE (l:Location {canonical_id: $cid}) ON CREATE SET l.name = $name"
                    session.run(q, {"cid": cid, "name": text})
                elif cid.startswith("VEH_"):
                    q = "MERGE (v:Vehicle {canonical_id: $cid}) ON CREATE SET v.registration_number = $name"
                    session.run(q, {"cid": cid, "name": text})
                elif cid.startswith("PHN_"):
                    q = "MERGE (ph:PhoneNumber {canonical_id: $cid}) ON CREATE SET ph.number = $name"
                    session.run(q, {"cid": cid, "name": text})
                elif cid.startswith("PER_"):
                    q = "MERGE (p:Person {canonical_id: $cid}) ON CREATE SET p.name = $name"
                    session.run(q, {"cid": cid, "name": text})
                else:
                    if etype == "Person":
                        q = "MERGE (p:Person {canonical_id: $cid}) ON CREATE SET p.name = $name"
                        session.run(q, {"cid": cid, "name": text})
                    elif etype == "Location":
                        q = "MERGE (l:Location {canonical_id: $cid}) ON CREATE SET l.name = $name"
                        session.run(q, {"cid": cid, "name": text})
                    elif etype == "Organization":
                        q = "MERGE (o:Organization {canonical_id: $cid}) ON CREATE SET o.name = $name"
                        session.run(q, {"cid": cid, "name": text})

                created_nodes.add(cid)
                node_count += 1

            # 2. Merge Relations
            for r in relations:
                subj = r.get("subject")
                pred = r.get("predicate", "ASSOCIATED_WITH")
                obj = r.get("object")
                conf = float(r.get("confidence", 0.80))

                if not subj or not obj or subj == obj:
                    continue

                # Ensure valid predicate
                if pred not in ("MET_WITH", "CALLED", "OWNS_OR_USES", "MEMBER_OF", "PRESENT_AT", "RESIDES_AT", "ASSOCIATED_WITH", "TRANSFERRED_MONEY_TO"):
                    pred = "ASSOCIATED_WITH"

                # Link Person to Phone if CALLED/OWNS_OR_USES or Person to Person
                rel_query = f"""
                MATCH (a {{canonical_id: $subj}})
                MATCH (b {{canonical_id: $obj}})
                WHERE a <> b
                MERGE (a)-[rel:{pred}]->(b)
                SET
                    rel.confidence = CASE WHEN $conf > coalesce(rel.confidence, 0.0) THEN $conf ELSE rel.confidence END,
                    rel.source_doc = $source_doc
                """
                try:
                    session.run(rel_query, {
                        "subj": subj,
                        "obj": obj,
                        "conf": conf,
                        "source_doc": source_doc,
                    })
                    rel_count += 1
                except Exception as ex:
                    pass

        return node_count, rel_count

    # ── Phase C: Connect Phones/Vehicles to Persons based on Ground Truth & Signals ──

    def link_multimodal_identifiers(self, session) -> Tuple[int, int]:
        """
        Step [6/6]: Establish Multi-Modal Ownership Links (KYC & Telecom).
        
        Per 03_DESIGN.md §4:
        1. Telecom SIM Ownership: Maps official subscriber registrations from telecom records
           (phone numbers) to the subscriber's canonical identity:
           (Person|Organization)-[:OWNS_OR_USES {confidence: 0.98, source_doc: 'TELECOM_REGISTRY'}]->(PhoneNumber)
        2. Banking KYC Account Ownership: Matches bank account identifier prefixes (ACC_{PREFIX}_{NUM})
           against normalized subscriber names in banking KYC records:
           (Person|Organization)-[:OWNS_OR_USES {confidence: 0.95, source_doc: 'BANKING_KYC'}]->(Account)
        
        Returns:
            Tuple[int, int]: (phone_links_count, account_links_count)
        """
        phone_links_count = 0
        account_links_count = 0

        # 1. Match PhoneNumbers to Persons/Orgs dynamically from subscriber registry
        entities_file = os.path.join(PROJECT_ROOT, "data-generation", "Entities.xlsx")
        if os.path.exists(entities_file):
            import pandas as pd
            df_ent = pd.read_excel(entities_file)
            for _, row in df_ent.iterrows():
                name = str(row["name"]).strip()
                etype = str(row.get("type", "Person")).strip()
                phone = row.get("phone")
                if pd.notna(phone) and str(phone) != "—":
                    phone_clean = re.sub(r"\D", "", str(phone))
                    slug = re.sub(r"[^\w]", "_", name.lower()).strip("_").upper()
                    prefix = "ORG_" if etype.lower() == "organization" else "PER_"
                    cid = f"{prefix}{slug}"

                    link_ph_q = """
                    MATCH (owner {canonical_id: $cid})
                    MATCH (ph:PhoneNumber)
                    WHERE ph.number = $phone OR ph.canonical_id = 'PHN_' + $phone
                    MERGE (owner)-[r:OWNS_OR_USES]->(ph)
                    SET r.confidence = 0.98, r.source_doc = 'TELECOM_REGISTRY'
                    """
                    session.run(link_ph_q, {"cid": cid, "phone": phone_clean})
                    phone_links_count += 1

        # 2. Match Accounts to Persons and Organizations by KYC name prefix (ACC_{PREFIX}_{NUM})
        accounts = session.run("MATCH (a:Account) RETURN a.canonical_id AS id, a.account_number AS num").data()
        persons = session.run("MATCH (p:Person) WHERE p.name IS NOT NULL RETURN p.canonical_id AS id, p.name AS name").data()
        orgs = session.run("MATCH (o:Organization) WHERE o.name IS NOT NULL RETURN o.canonical_id AS id, o.name AS name").data()

        link_stmt = """
        MATCH (owner {canonical_id: $owner_id})
        MATCH (acc:Account {canonical_id: $acc_id})
        MERGE (owner)-[r:OWNS_OR_USES]->(acc)
        SET r.confidence = 0.95, r.source_doc = 'BANKING_KYC'
        """

        for acc in accounts:
            anum = acc.get("num", "")
            parts = anum.split("_")
            if len(parts) < 2:
                continue
            prefix_clean = re.sub(r"[^A-Z]", "", parts[1].upper())
            if not prefix_clean:
                continue

            matched = False
            # Check Person first
            for p in persons:
                p_first = re.sub(r"[^A-Z]", "", p["name"].split()[0].upper())
                p_full = re.sub(r"[^A-Z]", "", p["name"].upper())
                if p_first.startswith(prefix_clean) or p_full.startswith(prefix_clean):
                    session.run(link_stmt, {"owner_id": p["id"], "acc_id": acc["id"]})
                    account_links_count += 1
                    matched = True
                    break

            # Check Organization if not matched to Person
            if not matched:
                for o in orgs:
                    o_clean = re.sub(r"[^A-Z]", "", o["name"].upper())
                    if o_clean.startswith(prefix_clean) or prefix_clean in o_clean:
                        session.run(link_stmt, {"owner_id": o["id"], "acc_id": acc["id"]})
                        account_links_count += 1
                        break

        return phone_links_count, account_links_count

    # ── Master Load Orchestration ─────────────────────────────────────────────

    def load_all(self, reset_existing: bool = True) -> Dict[str, Any]:
        """Execute full graph construction pipeline."""
        print("=" * 60)
        print("  Criminal Network Analysis — Graph Construction Pipeline")
        print("=" * 60)
        start_time = time.time()

        # Step 1: Ensure constraints and indexes
        apply_schema(self.driver)

        with self.driver.session() as session:
            # Step 2: Clear existing graph if requested
            if reset_existing:
                print("🧹 Resetting existing Neo4j graph nodes and relationships...")
                session.run("MATCH (n) DETACH DELETE n")

            # Step 3: Load PostgreSQL structured data
            print("\n📥 [1/4] Loading PostgreSQL Criminal Profiles...")
            c_count = self.load_postgres_criminal_records(session)
            print(f"   ✅ Merged {c_count} criminal profile nodes")

            print("\n📥 [2/4] Loading PostgreSQL Vehicle Registrations...")
            v_count = self.load_postgres_vehicles(session)
            print(f"   ✅ Merged {v_count} vehicles and ownership links")

            print("\n📥 [3/4] Loading PostgreSQL CDR Telecommunication Edges...")
            cdr_count = self.load_postgres_cdrs(session)
            print(f"   ✅ Merged {cdr_count} telecommunication interaction pairs")

            print("\n📥 [4/4] Loading PostgreSQL Financial Transaction Edges...")
            txn_count = self.load_postgres_transactions(session)
            print(f"   ✅ Merged {txn_count} transaction flow pairs")

            # Step 4: Load MongoDB NLP-extracted entities and relations
            print("\n📥 [5/5] Loading MongoDB NLP-Extracted Entities & Relations...")
            m_nodes, m_rels = self.load_mongo_extracted_data(session)
            print(f"   ✅ Merged {m_nodes} new entity nodes & {m_rels} semantic relationships")

            # Step 5: Multi-modal Identity Resolution
            print("\n🔗 [6/6] Establishing Multi-Modal Ownership Links (KYC & Telecom)...")
            ph_links, acc_links = self.link_multimodal_identifiers(session)
            print(f"   ✅ Multi-modal identity links created ({ph_links} telecom SIM links, {acc_links} banking KYC links)")

            # Step 6: Query final graph statistics
            print(f"\n{'=' * 60}")
            print("  NEO4J GRAPH SUMMARY")
            print(f"{'=' * 60}")

            node_stats = session.run(COUNT_NODES_BY_LABEL).data()
            total_nodes = sum(row["count"] for row in node_stats)
            print(f"  Total Nodes: {total_nodes}")
            for row in node_stats:
                print(f"   • {row['label']:<16}: {row['count']:>4}")

            print()
            edge_stats = session.run(COUNT_EDGES_BY_TYPE).data()
            total_edges = sum(row["count"] for row in edge_stats)
            print(f"  Total Relationships: {total_edges}")
            for row in edge_stats:
                print(f"   • {row['rel_type']:<22}: {row['count']:>4}")

            elapsed = time.time() - start_time
            print(f"\n✨ Graph construction completed in {elapsed:.2f} seconds.")
            print(f"{'=' * 60}\n")

            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "nodes_by_label": {r["label"]: r["count"] for r in node_stats},
                "edges_by_type": {r["rel_type"]: r["count"] for r in edge_stats},
            }


def main():
    loader = GraphLoader()
    try:
        loader.load_all(reset_existing=True)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
