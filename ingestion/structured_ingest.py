"""
structured_ingest.py — Ingestion pipeline for structured datasets.

Reads CSV files, validates each row through Pydantic schemas, and batch-inserts
clean records into PostgreSQL tables (cdr_records, transactions, criminal_records, vehicle_records).
"""

import csv
import os
import sys
from typing import Dict, List, Optional, Tuple

from ingestion.db_writers.postgres_writer import PostgresWriter
from ingestion.schemas import (
    CDRRecordSchema,
    CriminalRecordSchema,
    TransactionRecordSchema,
    VehicleRecordSchema,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StructuredIngestor:
    """Orchestrates structured data validation and persistence into PostgreSQL."""

    def __init__(self):
        self.writer = PostgresWriter()

    def ingest_cdrs(self, csv_path: str) -> Tuple[int, int]:
        """Validate and insert Call Detail Records from CSV."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CDR file not found: {csv_path}")

        records: List[CDRRecordSchema] = []
        errors = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    record = CDRRecordSchema(**row)
                    records.append(record)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [CDR Warning] Row {row_num} validation failed: {e}")

        inserted = self.writer.insert_cdr_records(records)
        return inserted, errors

    def ingest_transactions(self, csv_path: str) -> Tuple[int, int]:
        """Validate and insert financial transaction records from CSV."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Transactions file not found: {csv_path}")

        records: List[TransactionRecordSchema] = []
        errors = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    record = TransactionRecordSchema(**row)
                    records.append(record)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [Transaction Warning] Row {row_num} validation failed: {e}")

        inserted = self.writer.insert_transaction_records(records)
        return inserted, errors

    def ingest_criminal_records(self, csv_path: str) -> Tuple[int, int]:
        """Validate and insert criminal history seed profiles from CSV."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Criminal history file not found: {csv_path}")

        records: List[CriminalRecordSchema] = []
        errors = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    record = CriminalRecordSchema(**row)
                    records.append(record)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [Criminal Warning] Row {row_num} validation failed: {e}")

        inserted = self.writer.insert_criminal_records(records)
        return inserted, errors

    def ingest_vehicle_records(self, csv_path: str) -> Tuple[int, int]:
        """Validate and insert vehicle registrations from CSV."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Vehicle registry file not found: {csv_path}")

        records: List[VehicleRecordSchema] = []
        errors = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    record = VehicleRecordSchema(**row)
                    records.append(record)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [Vehicle Warning] Row {row_num} validation failed: {e}")

        inserted = self.writer.insert_vehicle_records(records)
        return inserted, errors

    def ingest_all(
        self, data_dir: Optional[str] = None, clean: bool = True
    ) -> Dict[str, Dict[str, int]]:
        """
        Ingest all structured files from default output directory.
        If clean=True, truncates existing structured data tables first to guarantee idempotent re-runs.
        """
        if clean:
            with self.writer._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "TRUNCATE TABLE cdr_records, transactions, criminal_records, vehicle_records;"
                    )

        target_dir = data_dir or os.path.join(PROJECT_ROOT, "data-generation", "output")
        results = {}

        # 1. CDRs
        cdr_file = os.path.join(target_dir, "cdr_records.csv")
        if os.path.exists(cdr_file):
            print(f"📥 Ingesting CDRs from {os.path.basename(cdr_file)}...")
            ins, errs = self.ingest_cdrs(cdr_file)
            results["cdr_records"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} CDR records ({errs} errors)")
        else:
            print(f"⚠️  CDR file not found at {cdr_file}")

        # 2. Transactions
        txn_file = os.path.join(target_dir, "transactions.csv")
        if os.path.exists(txn_file):
            print(f"📥 Ingesting Transactions from {os.path.basename(txn_file)}...")
            ins, errs = self.ingest_transactions(txn_file)
            results["transactions"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} transactions ({errs} errors)")
        else:
            print(f"⚠️  Transactions file not found at {txn_file}")

        # 3. Criminal Records
        crm_file = os.path.join(target_dir, "criminal_history_seed.csv")
        if os.path.exists(crm_file):
            print(f"📥 Ingesting Criminal History from {os.path.basename(crm_file)}...")
            ins, errs = self.ingest_criminal_records(crm_file)
            results["criminal_records"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} criminal records ({errs} errors)")
        else:
            print(f"⚠️  Criminal history file not found at {crm_file}")

        # 4. Vehicle Records
        veh_file = os.path.join(target_dir, "vehicle_registry_seed.csv")
        if os.path.exists(veh_file):
            print(f"📥 Ingesting Vehicles from {os.path.basename(veh_file)}...")
            ins, errs = self.ingest_vehicle_records(veh_file)
            results["vehicle_records"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} vehicle records ({errs} errors)")
        else:
            print(f"⚠️  Vehicle registry file not found at {veh_file}")

        return results


if __name__ == "__main__":
    ingestor = StructuredIngestor()
    summary = ingestor.ingest_all()
    print("\n📊 Structured Ingestion Summary:")
    for table, counts in summary.items():
        print(f"  - {table}: {counts['inserted']} rows inserted, {counts['errors']} errors")
