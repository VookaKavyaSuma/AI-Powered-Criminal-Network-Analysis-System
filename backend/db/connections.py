"""
connections.py — Database connection pool and dependency injection providers for FastAPI.
"""

import os
from typing import Generator

import psycopg
from dotenv import load_dotenv
from neo4j import GraphDatabase, Session
from pymongo import MongoClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


# ── PostgreSQL Connection ─────────────────────────────────────────────────────

def get_pg_connection():
    """Create a new connection to PostgreSQL."""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "cna_user"),
        password=os.getenv("POSTGRES_PASSWORD", "cna_secret_2026"),
        dbname=os.getenv("POSTGRES_DB", "criminal_network"),
        autocommit=True,
    )


# ── MongoDB Client ────────────────────────────────────────────────────────────

_mongo_client = None


def get_mongo_db():
    """Return MongoDB database instance."""
    global _mongo_client
    if _mongo_client is None:
        host = os.getenv("MONGO_HOST", "localhost")
        port = int(os.getenv("MONGO_PORT", "27017"))
        _mongo_client = MongoClient(host=host, port=port)
    db_name = os.getenv("MONGO_DB", "criminal_network")
    return _mongo_client[db_name]


# ── Neo4j Driver ──────────────────────────────────────────────────────────────

_neo4j_driver = None


def get_neo4j_driver():
    """Return singleton Neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "cna_neo4j_2026")
        _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
    return _neo4j_driver


def get_neo4j_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a Neo4j session."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        yield session
