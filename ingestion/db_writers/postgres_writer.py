"""
postgres_writer.py — PostgreSQL writer for the structured ingestion layer.

Handles batched inserts into:
- cdr_records
- transactions
- criminal_records
- vehicle_records

Uses psycopg v3 with proper parameter binding and array/JSONB handling.
"""

import json
import os
import sys
from typing import List

import psycopg
from dotenv import load_dotenv

from ingestion.schemas import (
    CDRRecordSchema,
    CriminalRecordSchema,
    TransactionRecordSchema,
    VehicleRecordSchema,
)

# Load environment variables
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def get_postgres_connection():
    """Create and return a new connection to PostgreSQL."""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "cna_user"),
        password=os.getenv("POSTGRES_PASSWORD", "cna_secret_2026"),
        dbname=os.getenv("POSTGRES_DB", "criminal_network"),
        autocommit=True,
    )


class PostgresWriter:
    """Provides bulk write operations for structured crime intelligence tables."""

    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.user = os.getenv("POSTGRES_USER", "cna_user")
        self.password = os.getenv("POSTGRES_PASSWORD", "cna_secret_2026")
        self.dbname = os.getenv("POSTGRES_DB", "criminal_network")

    def _get_conn(self):
        return psycopg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.dbname,
            autocommit=True,
        )

    def insert_cdr_records(self, records: List[CDRRecordSchema], batch_size: int = 500) -> int:
        """Bulk insert CDR records into cdr_records."""
        if not records:
            return 0

        query = """
        INSERT INTO cdr_records (
            caller_number, callee_number, call_timestamp,
            duration_sec, call_type, tower_id, tower_lat, tower_lng, source_name
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
        """
        rows = [
            (
                r.caller_number,
                r.callee_number,
                r.call_timestamp,
                r.duration_sec,
                r.call_type,
                r.tower_id,
                r.tower_lat,
                r.tower_lng,
                r.source_name,
            )
            for r in records
        ]

        inserted = 0
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    cur.executemany(query, batch)
                    inserted += len(batch)
        return inserted

    def insert_transaction_records(
        self, records: List[TransactionRecordSchema], batch_size: int = 500
    ) -> int:
        """Bulk insert financial records into transactions."""
        if not records:
            return 0

        query = """
        INSERT INTO transactions (
            sender_account, receiver_account, amount,
            txn_timestamp, txn_type, bank_name, flagged_structuring, source_name
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        );
        """
        rows = [
            (
                r.sender_account,
                r.receiver_account,
                r.amount,
                r.txn_timestamp,
                r.txn_type,
                r.bank_name,
                r.flagged_structuring,
                r.source_name,
            )
            for r in records
        ]

        inserted = 0
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    cur.executemany(query, batch)
                    inserted += len(batch)
        return inserted

    def insert_criminal_records(
        self, records: List[CriminalRecordSchema], batch_size: int = 500
    ) -> int:
        """Bulk insert criminal profiles into criminal_records."""
        if not records:
            return 0

        query = """
        INSERT INTO criminal_records (
            name, aliases, date_of_birth,
            known_address, past_cases, known_associates, risk_flag
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s
        );
        """
        rows = [
            (
                r.name,
                r.aliases,  # psycopg maps python list to postgres text[]
                r.date_of_birth,
                r.known_address,
                json.dumps(r.past_cases) if r.past_cases else "[]",  # jsonb
                r.known_associates,  # text[]
                r.risk_flag,
            )
            for r in records
        ]

        inserted = 0
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    cur.executemany(query, batch)
                    inserted += len(batch)
        return inserted

    def insert_vehicle_records(
        self, records: List[VehicleRecordSchema], batch_size: int = 500
    ) -> int:
        """Bulk insert vehicle registrations into vehicle_records."""
        if not records:
            return 0

        query = """
        INSERT INTO vehicle_records (
            registration_number, owner_name, vehicle_type, registered_address
        ) VALUES (
            %s, %s, %s, %s
        );
        """
        rows = [
            (
                r.registration_number,
                r.owner_name,
                r.vehicle_type,
                r.registered_address,
            )
            for r in records
        ]

        inserted = 0
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    cur.executemany(query, batch)
                    inserted += len(batch)
        return inserted
