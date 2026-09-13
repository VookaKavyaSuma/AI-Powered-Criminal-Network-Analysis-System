"""
schemas.py — Pydantic schemas for data validation across the ingestion layer.

Every record is validated against these schemas before being written to
PostgreSQL (structured) or MongoDB (unstructured envelope).
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Structured Schemas (PostgreSQL destination)
# =============================================================================

class CDRRecordSchema(BaseModel):
    """Call Detail Record (CDR) schema matching postgres cdr_records table."""
    caller_number: str = Field(..., max_length=15, description="Caller MSISDN/phone number")
    callee_number: str = Field(..., max_length=15, description="Callee MSISDN/phone number")
    call_timestamp: datetime = Field(..., description="Timestamp of the call")
    duration_sec: Optional[int] = Field(None, ge=0, description="Duration in seconds")
    call_type: Optional[str] = Field("voice", max_length=10, description="voice | sms")
    tower_id: Optional[str] = Field(None, max_length=20, description="Cell tower ID")
    tower_lat: Optional[float] = Field(None, description="Cell tower latitude")
    tower_lng: Optional[float] = Field(None, description="Cell tower longitude")
    source_name: Optional[str] = Field("CDR_PROVIDER", max_length=50)

    @field_validator("caller_number", "callee_number", mode="before")
    @classmethod
    def clean_phone(cls, v: Any) -> str:
        if v is None:
            return ""
        # Remove trailing .0 from float conversions or scientific notation
        s = str(v).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s


class TransactionRecordSchema(BaseModel):
    """Financial transaction schema matching postgres transactions table."""
    sender_account: str = Field(..., max_length=30)
    receiver_account: str = Field(..., max_length=30)
    amount: float = Field(..., gt=0)
    txn_timestamp: datetime
    txn_type: Optional[str] = Field("NEFT", max_length=20)
    bank_name: Optional[str] = Field(None, max_length=50)
    flagged_structuring: Optional[bool] = False
    source_name: Optional[str] = Field("FININT_BATCH", max_length=50)

    @field_validator("flagged_structuring", mode="before")
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "t", "yes")
        return bool(v)


class CriminalRecordSchema(BaseModel):
    """Criminal record schema matching postgres criminal_records table."""
    name: str = Field(..., max_length=100)
    aliases: List[str] = Field(default_factory=list)
    date_of_birth: Optional[date] = None
    known_address: Optional[str] = None
    past_cases: List[Dict[str, Any]] = Field(default_factory=list)
    known_associates: List[str] = Field(default_factory=list)
    risk_flag: Optional[str] = Field("LOW", max_length=20)

    @field_validator("aliases", "known_associates", mode="before")
    @classmethod
    def parse_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            if not v.strip():
                return []
            return [x.strip() for x in v.split(",") if x.strip()]
        return []

    @field_validator("past_cases", mode="before")
    @classmethod
    def parse_past_cases(cls, v: Any) -> List[Dict[str, Any]]:
        import json
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s or s == "[]":
                return []
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return []


class VehicleRecordSchema(BaseModel):
    """Vehicle registry schema matching postgres vehicle_records table."""
    registration_number: str = Field(..., max_length=15)
    owner_name: Optional[str] = Field(None, max_length=100)
    vehicle_type: Optional[str] = Field(None, max_length=20)
    registered_address: Optional[str] = None


# =============================================================================
# Unstructured Schema (MongoDB destination — Envelope pattern)
# =============================================================================

class UnstructuredDocumentSchema(BaseModel):
    """
    MongoDB envelope document schema.
    Every raw document (FIR, Social Media, Surveillance, News) is normalized into this structure.
    """
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    source_type: str = Field(..., description="FIR | SOCIAL_MEDIA | SURVEILLANCE | NEWS")
    source_name: str = Field(..., description="Original filename or feed name")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_content: str = Field(..., description="Raw text content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_status: str = Field("raw", description="raw | cleaned | extracted")
    extracted: Dict[str, Any] = Field(
        default_factory=lambda: {"entities": [], "relations": []}
    )
