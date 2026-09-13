"""
mongo_writer.py — MongoDB writer for the unstructured ingestion layer.

Persists raw and normalized documents into the 'documents' collection using
the Envelope Schema pattern. Ensures proper indexes for fast status queries.
"""

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, UpdateOne

from ingestion.schemas import UnstructuredDocumentSchema

# Load environment variables
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class MongoWriter:
    """Provides operations for storing and querying unstructured intelligence documents in MongoDB."""

    def __init__(self):
        host = os.getenv("MONGO_HOST", "localhost")
        port = int(os.getenv("MONGO_PORT", "27017"))
        self.db_name = os.getenv("MONGO_DB", "criminal_network")

        self.client = MongoClient(host=host, port=port, serverSelectionTimeoutMS=5000)
        self.db = self.client[self.db_name]
        self.collection = self.db["documents"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensure necessary indexes are in place for fast retrieval."""
        try:
            self.collection.create_index([("processing_status", ASCENDING)])
            self.collection.create_index([("source_type", ASCENDING)])
            self.collection.create_index([("source_name", ASCENDING)])
            self.collection.create_index([("metadata.fir_number", ASCENDING)])
            self.collection.create_index([("metadata.post_id", ASCENDING)])
        except Exception as e:
            print(f"Warning: Could not create Mongo indexes: {e}")

    def insert_documents(
        self, documents: List[UnstructuredDocumentSchema], upsert_by_source: bool = True
    ) -> int:
        """
        Insert or upsert multiple unstructured documents.
        If upsert_by_source is True, documents with the same source_name are updated to avoid duplicates.
        """
        if not documents:
            return 0

        operations = []
        for doc in documents:
            doc_dict = doc.model_dump(by_alias=True)
            doc_id = doc_dict.pop("_id", doc.id)

            if upsert_by_source:
                # Upsert by source_name or unique metadata identifier
                filter_query = {"source_name": doc.source_name}
                if doc.metadata.get("fir_number"):
                    filter_query = {"metadata.fir_number": doc.metadata["fir_number"]}
                elif doc.metadata.get("post_id"):
                    filter_query = {"metadata.post_id": doc.metadata["post_id"]}

                operations.append(
                    UpdateOne(
                        filter_query,
                        {
                            "$setOnInsert": {"_id": doc_id},
                            "$set": doc_dict,
                        },
                        upsert=True,
                    )
                )
            else:
                operations.append(
                    UpdateOne(
                        {"_id": doc_id},
                        {"$set": doc_dict},
                        upsert=True,
                    )
                )

        if operations:
            result = self.collection.bulk_write(operations, ordered=False)
            return (result.upserted_count or 0) + (result.modified_count or 0) + (result.inserted_count or 0)
        return 0

    def get_documents(
        self, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve documents matching query filter."""
        query = filter_dict or {}
        cursor = self.collection.find(query)
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update_document(self, doc_id: str, update_fields: Dict[str, Any]) -> bool:
        """Update specific fields of an existing document."""
        result = self.collection.update_one({"_id": doc_id}, {"$set": update_fields})
        return result.modified_count > 0

    def count_documents(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents matching filter."""
        query = filter_dict or {}
        return self.collection.count_documents(query)

    def insert_envelope_document(
        self,
        source_type: str,
        source_name: str,
        raw_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        processing_status: str = "raw",
        doc_id: Optional[str] = None,
        extracted: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert or upsert a single envelope document into MongoDB."""
        import uuid
        from datetime import datetime, timezone

        _id = doc_id or str(uuid.uuid4())
        doc_dict = {
            "_id": _id,
            "source_type": source_type,
            "source_name": source_name,
            "ingested_at": datetime.now(timezone.utc),
            "raw_content": raw_content,
            "metadata": metadata or {},
            "processing_status": processing_status,
            "extracted": extracted or {"entities": [], "relations": []},
        }
        self.collection.update_one({"_id": _id}, {"$set": doc_dict}, upsert=True)
        return _id

    def update_extracted_entities(
        self, doc_id: str, entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]
    ) -> bool:
        """Update a document's extracted entities and relations and mark status as extracted."""
        return self.update_document(
            doc_id=doc_id,
            update_fields={
                "extracted": {"entities": entities, "relations": relations},
                "processing_status": "extracted",
            },
        )
