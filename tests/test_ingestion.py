"""
test_ingestion.py — Verification tests for Phase 2 data ingestion layer.
"""

import os
import sys

import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.db_writers.mongo_writer import MongoWriter
from ingestion.db_writers.postgres_writer import get_postgres_connection
from ingestion.schemas import (
    CDRRecordSchema,
    CriminalRecordSchema,
    TransactionRecordSchema,
    UnstructuredDocumentSchema,
    VehicleRecordSchema,
)


def test_schema_validations():
    """Verify Pydantic schemas enforce type safety and conversions."""
    # 1. Phone number float-to-string cleanup
    cdr = CDRRecordSchema(
        caller_number="9847012345.0",
        callee_number="9847012399",
        call_timestamp="2024-08-20T10:00:00",
        duration_sec=120,
    )
    assert cdr.caller_number == "9847012345"
    assert cdr.callee_number == "9847012399"

    # 2. Boolean parsing in transactions
    txn = TransactionRecordSchema(
        sender_account="ACC_TEST_01",
        receiver_account="ACC_TEST_02",
        amount=48500.0,
        txn_timestamp="2024-08-21T12:00:00",
        flagged_structuring="True",
    )
    assert txn.flagged_structuring is True

    # 3. Comma-separated list parsing in criminal records
    crm = CriminalRecordSchema(
        name="Test Person",
        aliases="T. Person, Tester",
        known_associates="Associate A, Associate B",
        risk_flag="HIGH",
    )
    assert len(crm.aliases) == 2
    assert crm.aliases[0] == "T. Person"
    assert len(crm.known_associates) == 2

    # 4. Unstructured document envelope
    doc = UnstructuredDocumentSchema(
        source_type="FIR",
        source_name="FIR_TEST.txt",
        raw_content="Suspect seen near port.",
        metadata={"station": "Central"},
    )
    assert doc.processing_status == "raw"
    assert doc.extracted == {"entities": [], "relations": []}


def test_postgres_ingestion_counts():
    """Verify PostgreSQL tables hold the expected ingested rows."""
    conn = get_postgres_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM cdr_records;")
    cdr_count = cur.fetchone()[0]
    assert cdr_count >= 500, f"Expected >= 500 CDRs, got {cdr_count}"

    cur.execute("SELECT COUNT(*) FROM transactions;")
    txn_count = cur.fetchone()[0]
    assert txn_count >= 200, f"Expected >= 200 transactions, got {txn_count}"

    cur.execute("SELECT COUNT(*) FROM criminal_records;")
    crm_count = cur.fetchone()[0]
    assert crm_count >= 20, f"Expected >= 20 criminal records, got {crm_count}"

    cur.execute("SELECT COUNT(*) FROM vehicle_records;")
    veh_count = cur.fetchone()[0]
    assert veh_count >= 15, f"Expected >= 15 vehicle records, got {veh_count}"

    cur.close()
    conn.close()


def test_mongo_ingestion_counts():
    """Verify MongoDB documents collection holds expected envelope documents."""
    writer = MongoWriter()

    total = writer.count_documents()
    assert total >= 40, f"Expected >= 40 documents in MongoDB, got {total}"

    valid_docs = writer.count_documents({"processing_status": {"$in": ["raw", "extracted"]}})
    assert valid_docs == total, "All documents should have processing_status of 'raw' or 'extracted'"

    # Verify envelope structure of a random doc
    sample = writer.get_documents(limit=1)[0]
    for key in ["_id", "source_type", "source_name", "ingested_at", "raw_content", "metadata", "processing_status", "extracted"]:
        assert key in sample, f"Missing key '{key}' in MongoDB envelope document"
