"""
run_all.py — Orchestrate end-to-end ingestion pipeline.

Usage:
    python -m ingestion.run_all
    or:
    python ingestion/run_all.py

Reads all generated datasets from data-generation/output/, validates them with Pydantic,
persists structured data to PostgreSQL, and normalizes unstructured data into MongoDB.
"""

import os
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.db_writers.mongo_writer import MongoWriter
from ingestion.db_writers.postgres_writer import get_postgres_connection
from ingestion.structured_ingest import StructuredIngestor
from ingestion.unstructured_ingest import UnstructuredIngestor


def verify_database_counts():
    """Query both databases directly to print exact stored record counts."""
    print("\n" + "=" * 60)
    print("  VERIFYING STORED DATABASE COUNTS")
    print("=" * 60)

    # 1. PostgreSQL counts
    print("\n📊 PostgreSQL (localhost:5432 - criminal_network):")
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        tables = ["cdr_records", "transactions", "criminal_records", "vehicle_records", "users"]
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"   • {table:<20}: {count:>6} rows")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"   ❌ Failed to query PostgreSQL: {e}")

    # 2. MongoDB counts
    print("\n📊 MongoDB (localhost:27017 - criminal_network.documents):")
    try:
        writer = MongoWriter()
        total_docs = writer.count_documents()
        fir_docs = writer.count_documents({"source_type": "FIR"})
        sm_docs = writer.count_documents({"source_type": "SOCIAL_MEDIA"})
        raw_status = writer.count_documents({"processing_status": "raw"})

        print(f"   • Total documents     : {total_docs:>6}")
        print(f"   • FIR reports         : {fir_docs:>6}")
        print(f"   • Social media posts  : {sm_docs:>6}")
        print(f"   • Status 'raw'        : {raw_status:>6}")
    except Exception as e:
        print(f"   ❌ Failed to query MongoDB: {e}")


def main():
    print("=" * 60)
    print("  Criminal Network Analysis — Data Ingestion Pipeline")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}\n")

    start_time = time.time()

    # Part 1: Structured Ingestion -> PostgreSQL
    print("------------------------------------------------------------")
    print("  STEP 1: Ingesting Structured Data -> PostgreSQL")
    print("------------------------------------------------------------")
    struct_ingestor = StructuredIngestor()
    struct_summary = struct_ingestor.ingest_all()

    print()
    # Part 2: Unstructured Ingestion -> MongoDB
    print("------------------------------------------------------------")
    print("  STEP 2: Ingesting Unstructured Data -> MongoDB")
    print("------------------------------------------------------------")
    unstruct_ingestor = UnstructuredIngestor()
    unstruct_summary = unstruct_ingestor.ingest_all()

    elapsed = time.time() - start_time
    print(f"\n✨ Ingestion pipeline executed in {elapsed:.2f} seconds.")

    # Part 3: Live Verification
    verify_database_counts()

    print("\n" + "=" * 60)
    print("🎉 Phase 2 Ingestion Complete! Ready for Phase 3 (NLP/NER).")
    print("=" * 60)


run_pipeline = main

if __name__ == "__main__":
    main()
