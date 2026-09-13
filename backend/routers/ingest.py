"""
ingest.py — Real-time data ingestion endpoints for FIR documents, CDR batches, and Transactions.
"""

import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.auth.rbac import require_role
from backend.db.connections import get_neo4j_driver
from graph.loader import GraphLoader
from ingestion.db_writers.mongo_writer import MongoWriter
from ingestion.db_writers.postgres_writer import PostgresWriter
from ingestion.schemas import CDRRecordSchema, TransactionRecordSchema
from nlp.pipeline import NLPPipeline
from security.audit_chain import audit_chain

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])

_mongo_writer = None
_nlp_pipeline = None


def get_mongo_writer():
    global _mongo_writer
    if _mongo_writer is None:
        _mongo_writer = MongoWriter()
    return _mongo_writer


def get_nlp_pipeline():
    global _nlp_pipeline
    if _nlp_pipeline is None:
        _nlp_pipeline = NLPPipeline()
    return _nlp_pipeline


class FIRIngestRequest(BaseModel):
    content: str
    fir_number: Optional[str] = None
    station: Optional[str] = None
    officer: Optional[str] = None
    source_name: Optional[str] = "LIVE_API_INGEST.txt"


@router.post("/fir")
async def ingest_fir_document(
    req: FIRIngestRequest,
    current_user: dict = Depends(require_role("investigator")),
):
    """
    Ingest a First Information Report (FIR) narrative.
    Applies real-time NER, entity resolution, and relation extraction,
    storing the document in MongoDB and merging extracted entities into the Neo4j graph.
    """
    if not req.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FIR content cannot be empty.",
        )

    writer = get_mongo_writer()
    nlp = get_nlp_pipeline()

    doc_id = str(uuid.uuid4())
    metadata = {
        "fir_number": req.fir_number or f"FIR_{doc_id[:8]}",
        "station": req.station or "Kerala State Police",
        "officer": req.officer or current_user["username"],
    }

    # 1. Store raw envelope document in MongoDB
    writer.insert_envelope_document(
        source_type="FIR",
        source_name=req.source_name,
        raw_content=req.content,
        metadata=metadata,
        processing_status="raw",
        doc_id=doc_id,
    )

    # 2. Run NLP Extraction
    extracted_data = nlp.process_document({"raw_content": req.content})

    # 3. Update document with extracted data
    writer.update_extracted_entities(
        doc_id=doc_id,
        entities=extracted_data["entities"],
        relations=extracted_data["relations"],
    )

    # 4. Merge new entities and relationships directly into Neo4j
    driver = get_neo4j_driver()
    loader = GraphLoader()
    with driver.session() as session:
        # Load the newly extracted entities/relations
        loader.load_mongo_extracted_data(session)

    # 5. Log to cryptographic audit chain
    audit_chain.append_block(
        action="INGEST_FIR",
        actor=current_user["username"],
        entity_id=metadata["fir_number"],
        details={
            "doc_id": doc_id,
            "entities_found": len(extracted_data["entities"]),
            "relations_found": len(extracted_data["relations"]),
        },
    )

    return {
        "status": "success",
        "doc_id": doc_id,
        "fir_number": metadata["fir_number"],
        "extracted_entities_count": len(extracted_data["entities"]),
        "extracted_relations_count": len(extracted_data["relations"]),
        "entities": extracted_data["entities"],
        "relations": extracted_data["relations"],
    }


@router.post("/cdr")
async def ingest_cdr_batch(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Upload and ingest a batch of Call Detail Records (CSV format).
    Inserts records into PostgreSQL and merges telecommunication edges into Neo4j.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file.",
        )

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV: {e}",
        )

    records: List[CDRRecordSchema] = []
    errors = 0
    for _, row in df.iterrows():
        try:
            r = CDRRecordSchema(
                caller_number=str(row["caller_number"]),
                callee_number=str(row["callee_number"]),
                call_timestamp=str(row["call_timestamp"]),
                duration_sec=int(row["duration_sec"]),
                call_type=str(row.get("call_type", "voice")),
                tower_id=str(row.get("tower_id", "TWR_UNKNOWN")),
                tower_lat=float(row.get("tower_lat", 0.0)) if pd.notna(row.get("tower_lat")) else None,
                tower_lng=float(row.get("tower_lng", 0.0)) if pd.notna(row.get("tower_lng")) else None,
                source_name=str(row.get("source_name", file.filename)),
            )
            records.append(r)
        except Exception:
            errors += 1

    pg_writer = PostgresWriter()
    ingested_count = pg_writer.insert_cdrs(records)

    # Merge into Neo4j
    driver = get_neo4j_driver()
    loader = GraphLoader()
    with driver.session() as session:
        loader.load_postgres_cdrs(session)

    audit_chain.append_block(
        action="INGEST_CDR",
        actor=current_user["username"],
        details={"filename": file.filename, "records_ingested": ingested_count, "errors": errors},
    )

    return {
        "status": "success",
        "filename": file.filename,
        "records_ingested": ingested_count,
        "errors": errors,
    }


@router.post("/transactions")
async def ingest_transactions_batch(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("analyst")),
):
    """
    Upload and ingest a batch of Financial Transactions (CSV format).
    Inserts records into PostgreSQL and updates transaction edges in Neo4j.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file.",
        )

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV: {e}",
        )

    records: List[TransactionRecordSchema] = []
    errors = 0
    for _, row in df.iterrows():
        try:
            r = TransactionRecordSchema(
                sender_account=str(row["sender_account"]),
                receiver_account=str(row["receiver_account"]),
                amount=float(row["amount"]),
                txn_timestamp=str(row["txn_timestamp"]),
                txn_type=str(row.get("txn_type", "NEFT")),
                bank_name=str(row.get("bank_name", "UNKNOWN_BANK")),
                flagged_structuring=bool(row.get("flagged_structuring", False)),
                source_name=str(row.get("source_name", file.filename)),
            )
            records.append(r)
        except Exception:
            errors += 1

    pg_writer = PostgresWriter()
    ingested_count = pg_writer.insert_transactions(records)

    # Merge into Neo4j
    driver = get_neo4j_driver()
    loader = GraphLoader()
    with driver.session() as session:
        loader.load_postgres_transactions(session)

    audit_chain.append_block(
        action="INGEST_TRANSACTIONS",
        actor=current_user["username"],
        details={"filename": file.filename, "records_ingested": ingested_count, "errors": errors},
    )

    return {
        "status": "success",
        "filename": file.filename,
        "records_ingested": ingested_count,
        "errors": errors,
    }
