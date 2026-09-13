"""
main.py — FastAPI application entry point for the Criminal Network Analysis System.

Exposes REST APIs for:
- Authentication & JWT-based RBAC (/auth)
- Entity Search, Dossiers & Cytoscape Graph Subgraphs (/entity)
- Centrality, Louvain Communities, Link Prediction & Risk Scoring (/analytics)
- Real-time Multi-Modal Data Ingestion (/ingest)
- Tamper-Evident SHA-256 Audit Chain Verification (/audit)
"""

import os
import sys
import time

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.db.connections import get_mongo_db, get_neo4j_driver, get_pg_connection
from backend.routers import analytics, audit, auth, entity, ingest, nl_query
from security.audit_chain import audit_chain

app = FastAPI(
    title="AI-Powered Criminal Network Analysis System (CNA)",
    description=(
        "Production-grade intelligence backend integrating multi-modal data ingestion, "
        "hybrid NER, Neo4j knowledge graph construction, GDS centrality, Louvain clustering, "
        "explainable risk scoring, and a SHA-256 cryptographic audit chain."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Sub-Routers ───────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(entity.router)
app.include_router(analytics.router)
app.include_router(ingest.router)
app.include_router(audit.router)
app.include_router(nl_query.router)


# ── System Healthcheck ────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Verify live connectivity to PostgreSQL, MongoDB, and Neo4j."""
    status_report = {
        "status": "healthy",
        "timestamp": time.time(),
        "databases": {},
    }

    # 1. Test PostgreSQL
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                status_report["databases"]["postgresql"] = "connected"
    except Exception as e:
        status_report["databases"]["postgresql"] = f"error: {str(e)}"
        status_report["status"] = "degraded"

    # 2. Test MongoDB
    try:
        db = get_mongo_db()
        db.command("ping")
        status_report["databases"]["mongodb"] = "connected"
    except Exception as e:
        status_report["databases"]["mongodb"] = f"error: {str(e)}"
        status_report["status"] = "degraded"

    # 3. Test Neo4j
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("RETURN 1;").single()
            status_report["databases"]["neo4j"] = "connected"
    except Exception as e:
        status_report["databases"]["neo4j"] = f"error: {str(e)}"
        status_report["status"] = "degraded"

    return status_report


@app.get("/", tags=["System"])
async def root():
    """Root endpoint welcoming investigators and directing to interactive Swagger docs."""
    return {
        "system": "AI-Powered Criminal Network Analysis System (CNA)",
        "version": "1.0.0",
        "documentation": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "auth": "/auth/login",
            "entity_search": "/entity/search?q={query}",
            "entity_dossier": "/entity/{id}",
            "entity_graph": "/entity/{id}/graph?hops=2",
            "influencers": "/analytics/influencers",
            "communities": "/analytics/communities",
            "link_predictions": "/analytics/link-predictions",
            "anomaly_alerts": "/analytics/alerts",
            "audit_verify": "/audit/verify",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
