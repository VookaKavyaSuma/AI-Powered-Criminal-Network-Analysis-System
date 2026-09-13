"""
audit.py — Blockchain-inspired audit log and live tamper-detection verification endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.auth.rbac import require_role
from security.audit_chain import audit_chain

router = APIRouter(prefix="/audit", tags=["Security & Audit Chain"])


class TamperDemoRequest(BaseModel):
    block_id: int
    fake_action: str = "RECORD_ALTERED_BY_ATTACKER"


@router.get("/verify")
async def verify_audit_chain(
    current_user: dict = Depends(require_role("admin")),
):
    """
    Cryptographically verify the integrity of the audit hash-chain.
    Re-walks all SHA-256 blocks from genesis to head.
    Returns HTTP 200 if valid, or HTTP 409 Conflict if tampering is detected.
    """
    is_valid, corrupted_id, message = audit_chain.verify_chain()

    total_blocks = 0
    if is_valid:
        try:
            total_blocks = int(message.split("All ")[1].split(" blocks")[0])
        except Exception:
            total_blocks = len(audit_chain.get_recent_blocks(limit=500))

    return {
        "status": "SECURE" if is_valid else "TAMPER_DETECTED",
        "is_valid": is_valid,
        "total_blocks": total_blocks,
        "corrupted_block_id": corrupted_id,
        "message": message,
        "verified_by": current_user["username"],
    }


@router.get("/logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role("admin")),
):
    """
    Retrieve recent cryptographic audit blocks showing SHA-256 hashes and previous hash links.
    """
    blocks = audit_chain.get_recent_blocks(limit=limit)
    return {
        "count": len(blocks),
        "blocks": blocks,
    }


@router.post("/tamper-demo")
async def simulate_tampering(
    req: TamperDemoRequest,
    current_user: dict = Depends(require_role("admin")),
):
    """
    SIH Jury Demonstration Endpoint:
    Directly mutates an audit row in PostgreSQL without updating the cryptographic hash.
    Immediately invokes verify_chain to prove mathematical detection.
    """
    success = audit_chain.tamper_block_for_demo(req.block_id, req.fake_action)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block #{req.block_id} not found in audit chain.",
        )

    # Immediately verify to prove detection
    is_valid, corrupted_id, msg = audit_chain.verify_chain()

    return {
        "action": "MALICIOUS_TAMPER_SIMULATED",
        "target_block_id": req.block_id,
        "injected_payload": req.fake_action,
        "tamper_detected": not is_valid,
        "verification_result": {
            "is_valid": is_valid,
            "corrupted_block_id": corrupted_id,
            "detection_message": msg,
        },
        "explanation": "Even direct database modifications by a DBA or intruder break the SHA-256 hash-chain, making tampering mathematically impossible to conceal.",
    }
