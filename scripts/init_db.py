"""
init_db.py — Initialize PostgreSQL tables for the Criminal Network Analysis System.

Run this ONCE after starting Docker containers:
    python scripts/init_db.py

Tables created (from 03_DESIGN.md §2):
    - cdr_records       (Call Detail Records)
    - transactions      (Financial transactions)
    - criminal_records  (Criminal history)
    - vehicle_records   (Vehicle registry)
    - users             (RBAC users)
    - access_logs       (Raw access logs)
    - audit_chain       (Hash-chained audit trail — Phase 8)
"""

import os
import sys

import psycopg
from dotenv import load_dotenv

# Load environment variables from .env at project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_connection():
    """Create a PostgreSQL connection using environment variables."""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "cna_user"),
        password=os.getenv("POSTGRES_PASSWORD", "cna_secret_2026"),
        dbname=os.getenv("POSTGRES_DB", "criminal_network"),
        autocommit=True,
    )


SQL_STATEMENTS = [
    # ── CDR Records ──────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cdr_records (
        record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        caller_number VARCHAR(15) NOT NULL,
        callee_number VARCHAR(15) NOT NULL,
        call_timestamp TIMESTAMP NOT NULL,
        duration_sec INT,
        call_type VARCHAR(10),
        tower_id VARCHAR(20),
        tower_lat DECIMAL(9,6),
        tower_lng DECIMAL(9,6),
        source_name VARCHAR(50),
        ingested_at TIMESTAMP DEFAULT now()
    );
    """,
    # ── Financial Transactions ───────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS transactions (
        txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sender_account VARCHAR(30) NOT NULL,
        receiver_account VARCHAR(30) NOT NULL,
        amount DECIMAL(12,2) NOT NULL,
        txn_timestamp TIMESTAMP NOT NULL,
        txn_type VARCHAR(20),
        bank_name VARCHAR(50),
        flagged_structuring BOOLEAN DEFAULT FALSE,
        source_name VARCHAR(50),
        ingested_at TIMESTAMP DEFAULT now()
    );
    """,
    # ── Criminal History ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS criminal_records (
        person_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL,
        aliases TEXT[],
        date_of_birth DATE,
        known_address TEXT,
        past_cases JSONB,
        known_associates TEXT[],
        risk_flag VARCHAR(20),
        ingested_at TIMESTAMP DEFAULT now()
    );
    """,
    # ── Vehicle Registry ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS vehicle_records (
        vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        registration_number VARCHAR(15) NOT NULL,
        owner_name VARCHAR(100),
        vehicle_type VARCHAR(20),
        registered_address TEXT,
        ingested_at TIMESTAMP DEFAULT now()
    );
    """,
    # ── Users (RBAC) ─────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL,
        created_at TIMESTAMP DEFAULT now()
    );
    """,
    # ── Access Logs ──────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS access_logs (
        log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES users(user_id),
        action VARCHAR(50),
        entity_accessed VARCHAR(100),
        timestamp TIMESTAMP DEFAULT now()
    );
    """,
    # ── Audit Chain (Phase 8 — hash-chained tamper-evident log) ──────────
    """
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
    """,
]


def main():
    """Create all tables and seed default users."""
    print("🔌 Connecting to PostgreSQL...")
    conn = get_connection()
    cursor = conn.cursor()

    print("📋 Creating tables...")
    for i, sql in enumerate(SQL_STATEMENTS, 1):
        # Extract table name for logging
        table_name = sql.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
        cursor.execute(sql)
        print(f"   ✅ [{i}/{len(SQL_STATEMENTS)}] {table_name}")

    # Seed default users with a known bcrypt hash for password "admin123"
    # Generated with: from passlib.hash import bcrypt; bcrypt.hash("admin123")
    print("\n👤 Seeding default users...")
    seed_sql = """
    INSERT INTO users (username, password_hash, role)
    VALUES
        (%s, %s, %s)
    ON CONFLICT (username) DO NOTHING;
    """
    # Hash passwords using bcrypt directly (passlib is broken on Python 3.14)
    import bcrypt

    password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")

    for username, role in [
        ("admin", "admin"),
        ("analyst", "analyst"),
        ("investigator", "investigator"),
    ]:
        cursor.execute(seed_sql, (username, password_hash, role))
        print(f"   ✅ Created user: {username} (role: {role}, password: admin123)")

    # Verify
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name;"
    )
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Tables in database: {', '.join(tables)}")
    print(f"   Total: {len(tables)} tables")

    cursor.close()
    conn.close()
    print("\n✅ Database initialization complete!")
    print("\n📌 Next steps:")
    print("   1. Open pgAdmin/DBeaver → connect to localhost:5432")
    print("   2. Check the 'criminal_network' database")
    print("   3. You should see 7 tables listed above")
    print("   4. Run: SELECT * FROM users; → you should see 3 users")


if __name__ == "__main__":
    main()
