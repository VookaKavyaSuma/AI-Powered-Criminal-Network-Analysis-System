"""
test_connections.py — Verify all 3 database connections are working.

Run after `docker compose up -d`:
    python scripts/test_connections.py

Expected output: all 3 databases show ✅.
If any show ❌, check that Docker containers are running (`docker ps`).
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env at project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

results = {}


def test_postgres():
    """Test PostgreSQL connection."""
    print("1️⃣  Testing PostgreSQL (localhost:5432)...")
    try:
        import psycopg

        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "cna_user"),
            password=os.getenv("POSTGRES_PASSWORD", "cna_secret_2026"),
            dbname=os.getenv("POSTGRES_DB", "criminal_network"),
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"   ✅ PostgreSQL connected: {version[:60]}...")
        results["PostgreSQL"] = True
    except Exception as e:
        print(f"   ❌ PostgreSQL FAILED: {e}")
        results["PostgreSQL"] = False


def test_mongodb():
    """Test MongoDB connection."""
    print("\n2️⃣  Testing MongoDB (localhost:27017)...")
    try:
        from pymongo import MongoClient

        client = MongoClient(
            host=os.getenv("MONGO_HOST", "localhost"),
            port=int(os.getenv("MONGO_PORT", "27017")),
            serverSelectionTimeoutMS=5000,
        )
        # Force a connection by running a command
        server_info = client.server_info()
        db = client[os.getenv("MONGO_DB", "criminal_network")]
        # Insert and remove a test doc to verify write access
        test_collection = db["_connection_test"]
        test_collection.insert_one({"test": True})
        test_collection.delete_many({"test": True})
        client.close()
        print(f"   ✅ MongoDB connected: v{server_info['version']}")
        results["MongoDB"] = True
    except Exception as e:
        print(f"   ❌ MongoDB FAILED: {e}")
        results["MongoDB"] = False


def test_neo4j():
    """Test Neo4j connection."""
    print("\n3️⃣  Testing Neo4j (localhost:7687)...")
    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "cna_neo4j_2026")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            assert record["test"] == 1

        # Check if GDS plugin is available
        gds_available = False
        with driver.session() as session:
            try:
                result = session.run("RETURN gds.version() AS version")
                gds_version = result.single()["version"]
                gds_available = True
            except Exception:
                gds_version = "NOT INSTALLED"

        driver.close()
        print(f"   ✅ Neo4j connected")
        if gds_available:
            print(f"   ✅ GDS plugin: v{gds_version}")
        else:
            print(f"   ⚠️  GDS plugin: {gds_version} (needed for Phase 5 analytics)")
        results["Neo4j"] = True
    except Exception as e:
        print(f"   ❌ Neo4j FAILED: {e}")
        results["Neo4j"] = False


def main():
    """Run all connection tests."""
    print("=" * 60)
    print("  Criminal Network Analysis — Database Connection Tests")
    print("=" * 60)
    print()

    test_postgres()
    test_mongodb()
    test_neo4j()

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    all_passed = True
    for db, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {db}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All databases connected successfully!")
    else:
        print("⚠️  Some databases failed to connect.")
    return all_passed


def test_all_connections() -> bool:
    """Convenience helper returning True if all databases are connected."""
    results.clear()
    test_postgres()
    test_mongodb()
    test_neo4j()
    return all(results.values())


if __name__ == "__main__":
    main()
