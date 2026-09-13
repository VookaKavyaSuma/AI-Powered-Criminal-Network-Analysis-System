"""
unstructured_ingest.py — Ingestion pipeline for unstructured documents (FIRs, Social Media, Surveillance).

Normalizes raw text and JSON into the MongoDB Envelope Schema:
{
  "_id": "<uuid>",
  "source_type": "FIR | SOCIAL_MEDIA | SURVEILLANCE | NEWS",
  "source_name": "filename",
  "ingested_at": "<ISO timestamp>",
  "raw_content": "<plain text>",
  "metadata": { ... },
  "processing_status": "raw",
  "extracted": { "entities": [], "relations": [] }
}
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ingestion.db_writers.mongo_writer import MongoWriter
from ingestion.pdf_ocr_utils import extract_text_from_file
from ingestion.schemas import UnstructuredDocumentSchema

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class UnstructuredIngestor:
    """Orchestrates unstructured document normalization and persistence into MongoDB."""

    def __init__(self):
        self.writer = MongoWriter()

    def _parse_fir_metadata(self, text: str) -> Dict[str, str]:
        """Extract header metadata from FIR text if available."""
        meta = {}
        fir_match = re.search(r"FIR\s*(?:No|Number)?[:\s*]+([A-Za-z0-9_\-]+)", text, re.IGNORECASE)
        if fir_match:
            meta["fir_number"] = fir_match.group(1).strip()

        ps_match = re.search(r"Police Station[:\s*]+([^\n\r]+)", text, re.IGNORECASE)
        if ps_match:
            meta["station"] = ps_match.group(1).strip().replace("**", "")

        date_match = re.search(r"Date[:\s*]+([^\n\r]+)", text, re.IGNORECASE)
        if date_match:
            meta["date"] = date_match.group(1).strip().replace("**", "")

        officer_match = re.search(r"(?:Officer|Officer In Charge|Complainant/Officer)[:\s*]+([^\n\r]+)", text, re.IGNORECASE)
        if officer_match:
            meta["officer"] = officer_match.group(1).strip().replace("**", "")

        return meta

    def ingest_fir_directory(self, fir_dir: str) -> Tuple[int, int]:
        """Ingest all FIR text and PDF documents from a directory into MongoDB."""
        if not os.path.exists(fir_dir):
            raise FileNotFoundError(f"FIR directory not found: {fir_dir}")

        documents: List[UnstructuredDocumentSchema] = []
        errors = 0

        for fname in sorted(os.listdir(fir_dir)):
            fpath = os.path.join(fir_dir, fname)
            if not os.path.isfile(fpath) or fname.startswith("."):
                continue

            try:
                raw_text = extract_text_from_file(fpath)
                if not raw_text.strip():
                    continue

                metadata = self._parse_fir_metadata(raw_text)
                if "fir_number" not in metadata:
                    metadata["fir_number"] = os.path.splitext(fname)[0]

                doc = UnstructuredDocumentSchema(
                    source_type="FIR",
                    source_name=fname,
                    ingested_at=datetime.now(timezone.utc),
                    raw_content=raw_text,
                    metadata=metadata,
                    processing_status="raw",
                    extracted={"entities": [], "relations": []},
                )
                documents.append(doc)
            except Exception as e:
                errors += 1
                print(f"  [FIR Error] Failed processing {fname}: {e}")

        inserted = self.writer.insert_documents(documents)
        return inserted, errors

    def ingest_social_media_directory(self, sm_dir: str) -> Tuple[int, int]:
        """Ingest all social media post JSON files from a directory into MongoDB."""
        if not os.path.exists(sm_dir):
            raise FileNotFoundError(f"Social media directory not found: {sm_dir}")

        documents: List[UnstructuredDocumentSchema] = []
        errors = 0

        for fname in sorted(os.listdir(sm_dir)):
            fpath = os.path.join(sm_dir, fname)
            if not os.path.isfile(fpath) or not fname.endswith(".json") or fname.startswith("."):
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    sm_data = json.load(f)

                raw_content = sm_data.get("content", "")
                metadata = {
                    "platform": sm_data.get("platform", "Unknown"),
                    "username": sm_data.get("username", "Unknown"),
                    "post_id": sm_data.get("post_id", os.path.splitext(fname)[0]),
                    "post_timestamp": sm_data.get("timestamp"),
                    "original_metadata": sm_data.get("metadata", {}),
                }

                doc = UnstructuredDocumentSchema(
                    source_type="SOCIAL_MEDIA",
                    source_name=fname,
                    ingested_at=datetime.now(timezone.utc),
                    raw_content=raw_content,
                    metadata=metadata,
                    processing_status="raw",
                    extracted={"entities": [], "relations": []},
                )
                documents.append(doc)
            except Exception as e:
                errors += 1
                print(f"  [Social Media Error] Failed processing {fname}: {e}")

        inserted = self.writer.insert_documents(documents)
        return inserted, errors

    def ingest_all(self, data_dir: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """Ingest all unstructured data (FIRs, social media) from default directory."""
        target_dir = data_dir or os.path.join(PROJECT_ROOT, "data-generation", "output")
        results = {}

        # 1. FIR reports
        fir_dir = os.path.join(target_dir, "fir_reports")
        if os.path.exists(fir_dir):
            print(f"📥 Ingesting FIR reports from {os.path.basename(fir_dir)}...")
            ins, errs = self.ingest_fir_directory(fir_dir)
            results["fir_reports"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} FIR documents ({errs} errors)")
        else:
            print(f"⚠️  FIR directory not found at {fir_dir}")

        # 2. Social media posts
        sm_dir = os.path.join(target_dir, "social_media_posts")
        if os.path.exists(sm_dir):
            print(f"📥 Ingesting Social Media posts from {os.path.basename(sm_dir)}...")
            ins, errs = self.ingest_social_media_directory(sm_dir)
            results["social_media_posts"] = {"inserted": ins, "errors": errs}
            print(f"   ✅ Ingested {ins} social media posts ({errs} errors)")
        else:
            print(f"⚠️  Social media directory not found at {sm_dir}")

        return results


if __name__ == "__main__":
    ingestor = UnstructuredIngestor()
    summary = ingestor.ingest_all()
    print("\n📊 Unstructured Ingestion Summary:")
    for source, counts in summary.items():
        print(f"  - {source}: {counts['inserted']} documents in MongoDB, {counts['errors']} errors")
