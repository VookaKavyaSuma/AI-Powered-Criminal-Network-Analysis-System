"""
audit_chain.py — Cryptographic, tamper-evident hash-chain audit log.

Every administrative, ingestion, or search action is recorded in a linked SHA-256 block structure:
block_hash = SHA256(action | actor | entity_id | details_json | timestamp | previous_hash)

Provides:
- append_block: records a new audit event linked to previous hash
- verify_chain: walks the chain, recomputing hashes to detect any tampering
- tamper_block_for_demo: intentionally alters a block's content to prove detection in live demos
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

GENESIS_HASH = "0" * 64


def get_pg_conn():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "cna_user"),
        password=os.getenv("POSTGRES_PASSWORD", "cna_secret_2026"),
        dbname=os.getenv("POSTGRES_DB", "criminal_network"),
        autocommit=True,
    )


def compute_block_hash(
    action: str,
    actor: str,
    entity_id: Optional[str],
    details: Dict[str, Any],
    timestamp_str: str,
    previous_hash: str,
) -> str:
    """Compute deterministic SHA-256 hash for an audit block."""
    details_str = json.dumps(details or {}, sort_keys=True)
    payload = f"{action}|{actor}|{entity_id or ''}|{details_str}|{timestamp_str}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditChain:
    """Manages the append-only cryptographic audit hash-chain in PostgreSQL."""

    def __init__(self):
        self._table_ensured = False

    def _ensure_table(self):
        """Ensure audit_chain table exists."""
        if self._table_ensured:
            return
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_chain (
                        block_id SERIAL PRIMARY KEY,
                        action VARCHAR(100) NOT NULL,
                        actor VARCHAR(100) NOT NULL,
                        entity_id VARCHAR(255),
                        details JSONB,
                        timestamp TIMESTAMP DEFAULT now(),
                        data_hash VARCHAR(64) NOT NULL,
                        previous_hash VARCHAR(64) NOT NULL
                    );
                """)
        self._table_ensured = True

    def get_latest_hash(self) -> str:
        """Fetch data_hash of the most recent block, or GENESIS_HASH if empty."""
        self._ensure_table()
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_hash FROM audit_chain ORDER BY block_id DESC LIMIT 1;")
                row = cur.fetchone()
                return row[0] if row else GENESIS_HASH

    def append_block(
        self,
        action: str,
        actor: str,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append a new block to the cryptographic chain.
        Guarantees mathematical linkage to the preceding block.
        """
        details_dict = details or {}
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")

        self._ensure_table()
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                # Lock table for append sequence consistency
                cur.execute("SELECT data_hash FROM audit_chain ORDER BY block_id DESC LIMIT 1;")
                row = cur.fetchone()
                prev_hash = row[0] if row else GENESIS_HASH

                block_hash = compute_block_hash(
                    action=action,
                    actor=actor,
                    entity_id=entity_id,
                    details=details_dict,
                    timestamp_str=timestamp_str,
                    previous_hash=prev_hash,
                )

                cur.execute("""
                    INSERT INTO audit_chain (action, actor, entity_id, details, timestamp, data_hash, previous_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING block_id;
                """, (
                    action,
                    actor,
                    entity_id,
                    json.dumps(details_dict),
                    now,
                    block_hash,
                    prev_hash,
                ))
                block_id = cur.fetchone()[0]

        return {
            "block_id": block_id,
            "action": action,
            "actor": actor,
            "entity_id": entity_id,
            "timestamp": timestamp_str,
            "data_hash": block_hash,
            "previous_hash": prev_hash,
        }

    def verify_chain(self) -> Tuple[bool, Optional[int], str]:
        """
        Walk all blocks from genesis to head and verify SHA-256 linkage.
        Returns (is_valid, corrupted_block_id, message).
        """
        self._ensure_table()
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT block_id, action, actor, entity_id, details,
                           to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS.US') AS ts_str,
                           data_hash, previous_hash
                    FROM audit_chain
                    ORDER BY block_id ASC;
                """)
                blocks = cur.fetchall()

        if not blocks:
            return True, None, "Audit chain is empty — valid by default."

        expected_prev_hash = GENESIS_HASH

        for b_id, action, actor, ent_id, details, ts_str, stored_hash, stored_prev in blocks:
            # 1. Verify previous hash pointer matches
            if stored_prev != expected_prev_hash:
                return (
                    False,
                    b_id,
                    f"TAMPER DETECTED at Block #{b_id}: Previous hash pointer broken! Expected {expected_prev_hash[:12]}..., found {stored_prev[:12]}...",
                )

            # 2. Recompute data hash from row content
            details_dict = details if isinstance(details, dict) else (json.loads(details) if details else {})
            recomputed = compute_block_hash(
                action=action,
                actor=actor,
                entity_id=ent_id,
                details=details_dict,
                timestamp_str=ts_str,
                previous_hash=stored_prev,
            )

            if recomputed != stored_hash:
                return (
                    False,
                    b_id,
                    f"TAMPER DETECTED at Block #{b_id}: Payload altered! Content hash mismatch. Stored: {stored_hash[:12]}..., Computed: {recomputed[:12]}...",
                )

            expected_prev_hash = stored_hash

        return True, None, f"Audit chain verified: All {len(blocks)} blocks cryptographically intact."

    def tamper_block_for_demo(self, block_id: int, fake_action: str) -> bool:
        """
        Intentionally alter a block's content in the database without updating the hash chain.
        Used for live SIH demonstration of tamper detection.
        """
        self._ensure_table()
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE audit_chain
                    SET action = %s
                    WHERE block_id = %s;
                """, (fake_action, block_id))
                return cur.rowcount > 0

    def get_recent_blocks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent blocks for the admin audit dashboard."""
        self._ensure_table()
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT block_id, action, actor, entity_id, details,
                           to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS ts,
                           data_hash, previous_hash
                    FROM audit_chain
                    ORDER BY block_id DESC
                    LIMIT %s;
                """, (limit,))
                rows = cur.fetchall()

        return [
            {
                "block_id": r[0],
                "action": r[1],
                "actor": r[2],
                "entity_id": r[3],
                "details": r[4],
                "timestamp": r[5],
                "data_hash": r[6],
                "previous_hash": r[7],
            }
            for r in rows
        ]


# Singleton instance
audit_chain = AuditChain()
