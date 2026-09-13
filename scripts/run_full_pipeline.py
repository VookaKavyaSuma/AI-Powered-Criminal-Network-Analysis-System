"""
run_full_pipeline.py — Master End-to-End Orchestrator for the Criminal Network Analysis System.

Executes the complete pipeline in sequence:
1. Database Connectivity Verification (Postgres, Mongo, Neo4j)
2. Phase 2: Ingestion (PostgreSQL structured + MongoDB unstructured envelopes)
3. Phase 3: NLP Pipeline (Regex + spaCy NER + Entity Resolution + Relation Extraction)
4. Phase 4: Neo4j Knowledge Graph Construction (Idempotent MERGE loader)
5. Phase 5: Graph Analytics (Betweenness, PageRank, Louvain Communities, Anomalies, Risk Scores)
6. Phase 8: Cryptographic Audit Chain Verification (SHA-256 integrity check)

Usage:
    python scripts/run_full_pipeline.py
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analytics.run_all import run_pipeline as run_analytics_pipeline
from graph.loader import GraphLoader
from ingestion.run_all import run_pipeline as run_ingestion_pipeline
from nlp.pipeline import NLPPipeline
from scripts.test_connections import test_all_connections
from security.audit_chain import audit_chain


def main():
    print("\n" + "=" * 75)
    print("  AI-POWERED CRIMINAL NETWORK ANALYSIS SYSTEM — MASTER PIPELINE")
    print("=" * 75)
    overall_start = time.time()

    # ── STEP 1: Test DB Connections ───────────────────────────────────────────
    print("\n[Step 1/6] Verifying Database Connectivity...")
    all_ok = test_all_connections()
    if not all_ok:
        print("\n❌ One or more database connections failed. Please check Docker containers.")
        sys.exit(1)

    # ── STEP 2: Phase 2 Data Ingestion ────────────────────────────────────────
    print("\n[Step 2/6] Running Data Ingestion Layer (PostgreSQL & MongoDB)...")
    run_ingestion_pipeline()

    # ── STEP 3: Phase 3 NLP & Relation Extraction ─────────────────────────────
    print("\n[Step 3/6] Running Master NLP Pipeline on Unstructured Documents...")
    nlp = NLPPipeline()
    nlp.run(reprocess_all=True)

    # ── STEP 4: Phase 4 Neo4j Graph Construction ──────────────────────────────
    print("\n[Step 4/6] Constructing Unified Knowledge Graph in Neo4j...")
    loader = GraphLoader()
    try:
        graph_stats = loader.load_all(reset_existing=True)
    finally:
        loader.close()

    # ── STEP 5: Phase 5 Graph Analytics & Risk Scoring ────────────────────────
    print("\n[Step 5/6] Executing Graph Analytics & Risk Scoring Pipeline...")
    analytics_stats = run_analytics_pipeline()

    # ── STEP 6: Phase 8 Audit Chain Verification ──────────────────────────────
    print("\n[Step 6/6] Verifying Cryptographic Audit Hash-Chain Integrity...")
    is_valid, corrupted_id, msg = audit_chain.verify_chain()
    if is_valid:
        print(f"   ✅ Cryptographic Audit Chain SECURE: {msg}")
    else:
        print(f"   ❌ TAMPER DETECTED at Block #{corrupted_id}: {msg}")

    total_elapsed = time.time() - overall_start

    print("\n" + "=" * 75)
    print("  🎉 MASTER PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 75)
    print(f"  Total Execution Time : {total_elapsed:.2f} seconds")
    print(f"  Total Graph Nodes    : {graph_stats['total_nodes']}")
    print(f"  Total Relationships  : {graph_stats['total_edges']}")
    print(f"  Operational Clusters : {analytics_stats['communities_count']}")
    print(f"  Predicted Links      : {analytics_stats['predicted_links_count']}")
    print(f"  Core Leadership Match: {analytics_stats['core_overlap_top5']} / 5 ({analytics_stats['core_overlap_top5'] * 20}%)")
    print(f"  Audit Chain Integrity: {'✅ SECURE' if is_valid else '❌ TAMPERED'}")
    print("=" * 75)
    print("\n📌 Next steps for demo:")
    print("   1. Start Backend API:  uvicorn backend.main:app --reload")
    print("   2. Open Swagger Docs:  http://localhost:8000/docs")
    print("   3. Neo4j Browser UI :  http://localhost:7474\n")


if __name__ == "__main__":
    main()
