# AI-Powered Criminal Network Analysis System

> **Smart India Hackathon 2026** · Blockchain & Cybersecurity theme

An AI-powered platform for law enforcement analysts that ingests structured and unstructured crime data, extracts entities and relationships using NLP, builds a Neo4j knowledge graph, runs graph analytics (centrality, community detection, link prediction, anomaly detection), and presents actionable intelligence through an interactive dashboard — secured with RBAC, encryption, and a SHA-256 hash-chained audit trail.

## Architecture

```
Data Sources → Ingestion (Postgres/MongoDB) → NLP/NER → Graph (Neo4j) → Analytics → FastAPI Backend → Frontend
                                                                                         ↑
                                                              Security & Blockchain (cross-cutting)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Structured DB | PostgreSQL 16 |
| Document DB | MongoDB 7 |
| Graph DB | Neo4j 5 + GDS |
| NLP | spaCy + Groq API (Llama 3.3 70B) |
| Frontend | React + Cytoscape.js |
| Auth | JWT + RBAC |
| Audit Trail | SHA-256 hash chain |

## Quick Start

### 1. Clone and configure
```bash
git clone <repo-url>
cd AI-Powered-Criminal-Network-Analysis-System
cp .env.example .env
# Edit .env → paste your GROQ_API_KEY (get free at https://console.groq.com/keys)
```

### 2. Start databases
```bash
docker compose up -d
docker ps  # verify 3 containers: cna-postgres, cna-mongodb, cna-neo4j
```

### 3. Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Initialize databases and run full pipeline
```bash
python scripts/init_db.py
python scripts/run_full_pipeline.py
```

### 5. Start the API
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# API docs: http://localhost:8000/docs
```

## Project Structure

```
├── docs/                  # Specification documents (PRD, Architecture, Design, Phases)
├── data-generation/       # Phase 1: Synthetic dataset generators
├── ingestion/             # Phase 2: Data ingestion pipeline (→ Postgres/MongoDB)
├── nlp/                   # Phase 3: NLP/NER/relation extraction (reads/writes MongoDB)
├── graph/                 # Phase 4: Neo4j graph construction (only writer to Neo4j)
├── analytics/             # Phase 5: Graph analytics (reads/writes Neo4j properties)
├── backend/               # Phase 6: FastAPI REST API
├── frontend/              # Phase 7: React + Cytoscape.js (separate build)
├── security/              # Phase 8: Audit chain, encryption, RBAC
├── tests/                 # Unit and integration tests
└── scripts/               # Pipeline orchestration, DB init, demo seeding
```

## Verification (No Frontend Required)

- **Swagger UI:** `http://localhost:8000/docs`
- **Neo4j Browser:** `http://localhost:7474`
- **Postman:** Import `docs/postman_collection.json`
- **pgAdmin/DBeaver:** Connect to `localhost:5432`
- **MongoDB Compass:** Connect to `mongodb://localhost:27017`

## License

For SIH 2026 evaluation purposes. Not licensed for production use with real data.
