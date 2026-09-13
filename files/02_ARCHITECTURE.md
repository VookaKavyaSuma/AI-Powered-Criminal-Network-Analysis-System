# System Architecture Document
## AI-Powered Criminal Network Analysis System

---

## 1. High-Level Architecture Diagram (textual)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES (synthetic)                     │
│  FIR text | CDRs | Transactions | Surveillance | Social Media |      │
│  Criminal History DB | News articles                                 │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA INGESTION                                            │
│  FastAPI ingestion endpoints → parsers/validators (pandas, pydantic, │
│  PyMuPDF, Tesseract OCR) → normalized "envelope" schema              │
│  Structured → PostgreSQL   |   Unstructured (raw) → MongoDB          │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — NLP / NER / RELATION EXTRACTION                           │
│  Regex (phone/vehicle/amount) + spaCy/IndicNER (fine-tuned) +        │
│  dependency parsing / LLM-assisted relation extraction (Groq API,    │
│  Llama 3.3 70B) + entity resolution (rapidfuzz + rule scoring)       │
│  Output: structured entities & relations JSON → written back to      │
│  MongoDB record + queued for graph load                              │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — GRAPH CONSTRUCTION                                        │
│  Loader script (Cypher MERGE) → Neo4j                                │
│  Nodes: Person, Location, Vehicle, PhoneNumber, Organization, Event   │
│  Edges: CALLED, MET_WITH, TRANSFERRED_MONEY_TO, OWNS_OR_USES,        │
│  RESIDES_AT, MEMBER_OF, ASSOCIATED_WITH, RELATED_TO                  │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — GRAPH ANALYTICS                                           │
│  Neo4j GDS: Betweenness / Degree / PageRank centrality, Louvain      │
│  community detection, Node Similarity (link prediction)              │
│  Custom Python: communication spike detection, transaction           │
│  structuring detection, composite risk scoring → written back to     │
│  Neo4j node properties                                               │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — API + VISUALIZATION                                       │
│  FastAPI REST backend (serves Neo4j/Postgres/Mongo data as JSON)     │
│  React frontend: Cytoscape.js graph view, Recharts dashboard,        │
│  entity profile pages, (optional) NL-to-Cypher query box             │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 6 — SECURITY & BLOCKCHAIN (cross-cutting)                     │
│  JWT auth + RBAC on every endpoint | Encryption at rest/in transit   │
│  | Field-level redaction | Hash-chained audit log (SHA-256, custom   │
│  chain) recording every ingest/query/flag/access action              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

| Layer | Responsibility | Does NOT do |
|---|---|---|
| 1. Ingestion | Read, validate, normalize raw files into a common schema | Understand content, extract entities |
| 2. NLP/NER | Read text, extract entities & relations, resolve duplicates | Build the graph, score anyone |
| 3. Graph Construction | Turn entities/relations into nodes/edges in Neo4j, dedupe via canonical IDs | Decide who's "important" |
| 4. Analytics | Compute centrality, communities, anomalies, risk scores | Render anything visually |
| 5. Visualization | Serve and display data to investigators, interactive drill-down | Perform new analysis (calls Layer 4's precomputed results) |
| 6. Security/Blockchain | Auth, encryption, tamper-evident logging (cross-cutting, touches every layer) | Store/duplicate the actual case data |

---

## 3. Data Storage Architecture (Polyglot Persistence)

| Store | Holds | Why this store |
|---|---|---|
| **PostgreSQL** | CDR records, transactions, criminal history, vehicle registry, users, access logs | Fixed, predictable schema; strong validation; relational integrity |
| **MongoDB** | Raw FIR text, surveillance reports, social media posts, news articles (pre- and post-NLP) | Variable schema per source; flexible document storage |
| **Neo4j** | Entities (nodes) and relationships (edges), plus analytics results (risk scores, centrality, community IDs) as node/edge properties | Purpose-built for multi-hop relationship queries; built-in Graph Data Science algorithms and visualization tooling |

See `03_DESIGN.md` for full table/collection/node schemas.

---

## 4. Tech Stack Summary

| Concern | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Structured DB | PostgreSQL |
| Unstructured/document DB | MongoDB |
| Graph DB + analytics | Neo4j + Graph Data Science (GDS) library |
| NER | spaCy (fine-tuned) / IndicNER (for Hindi/Hinglish) |
| Relation extraction | spaCy dependency parsing rules + LLM-assisted extraction (**Groq API**, model: `llama-3.3-70b-versatile`, free tier) |
| Entity resolution | `rapidfuzz` fuzzy matching + rule-based scoring |
| PDF/OCR | PyMuPDF, Tesseract OCR |
| LLM provider (data generation + relation extraction) | **Groq** (console.groq.com) — free developer tier, no credit card; ~30 req/min, ~100K tokens/day on `llama-3.3-70b-versatile`, comfortably covers prototype-scale generation and extraction volume |
| Frontend | React |
| Graph visualization | Cytoscape.js (or Neo4j Bloom as fallback) |
| Charts | Recharts |
| Auth | JWT (`python-jose` / `fastapi-users`) |
| Encryption | TLS (transit), `cryptography`/Fernet (field-level), native DB encryption (at rest) |
| Audit trail | Custom Python SHA-256 hash-chain (Hyperledger Fabric noted as production path) |
| Containerization | Docker + docker-compose (Postgres, MongoDB, Neo4j all run locally) |
| Synthetic data generation | Python scripts + LLM-assisted text generation (Groq API, `llama-3.3-70b-versatile`) |

---

## 5. Deployment View (Prototype)

Everything runs **locally via Docker** for the hackathon demo (no dependency on venue internet, no cloud cost/quota risk). See `docker-compose.yml` referenced in the build guide.

```
Presenter's laptop
 ├── Docker: postgres container   (localhost:5432)
 ├── Docker: mongodb container    (localhost:27017)
 ├── Docker: neo4j container      (localhost:7474 / 7687)
 ├── FastAPI backend              (localhost:8000)
 └── React frontend                (localhost:3000)
```

**Production deployment (future scope, for the report / Q&A):** on-premise or secured government cloud infrastructure (not public cloud, given data sensitivity), integrated with real law enforcement data systems via authorized APIs/data-sharing agreements, with Hyperledger Fabric replacing the simplified hash-chain for a fully distributed, permissioned audit ledger across agencies.

---

## 6. Project Folder Structure

The repository is organized so each top-level folder maps 1:1 to an architecture layer / build phase (see `04_PHASES.md`). A coding agent should treat each folder as the working scope for its corresponding phase, and should not scatter layer-specific code outside its designated folder.

```
criminal-network-analysis/
│
├── docs/
│   ├── 01_PRD.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_DESIGN.md
│   └── 04_PHASES.md
│
├── docker-compose.yml                # Postgres, MongoDB, Neo4j (local, Phase 0)
├── .env.example
├── README.md
│
├── data-generation/                  # Phase 1
│   ├── ground_truth.xlsx
│   ├── cdr_generator.py
│   ├── transaction_generator.py
│   ├── fir_generator.py
│   ├── social_media_generator.py
│   ├── criminal_history_seed.csv
│   ├── vehicle_registry_seed.csv
│   └── output/
│       ├── cdr_records.csv
│       ├── transactions.csv
│       ├── fir_reports/
│       ├── social_media_posts/
│       └── labeled_ner_data/
│
├── ingestion/                        # Phase 2
│   ├── schemas.py
│   ├── structured_ingest.py
│   ├── unstructured_ingest.py
│   ├── pdf_ocr_utils.py
│   └── db_writers/
│       ├── postgres_writer.py
│       └── mongo_writer.py
│
├── nlp/                              # Phase 3
│   ├── regex_extractors.py
│   ├── ner_model/
│   │   ├── train_ner.py
│   │   ├── model/
│   │   └── labeled_data/
│   ├── relation_extraction.py
│   ├── entity_resolution.py
│   └── pipeline.py
│
├── graph/                            # Phase 4
│   ├── schema.py
│   ├── loader.py
│   └── queries/
│       └── common_cypher.py
│
├── analytics/                        # Phase 5
│   ├── centrality.py
│   ├── community_detection.py
│   ├── link_prediction.py
│   ├── anomaly_detection.py
│   └── risk_scoring.py
│
├── backend/                          # Phase 6
│   ├── main.py
│   ├── routers/
│   │   ├── ingest.py
│   │   ├── entity.py
│   │   ├── analytics.py
│   │   ├── query_nl.py
│   │   └── audit.py
│   ├── auth/
│   │   ├── jwt_handler.py
│   │   └── rbac.py
│   ├── db/
│   │   ├── postgres.py
│   │   ├── mongo.py
│   │   └── neo4j.py
│   └── requirements.txt
│
├── security/                         # Phase 8
│   ├── audit_chain.py
│   ├── encryption.py
│   └── access_anomaly.py
│
├── frontend/                         # Phase 7
│   ├── package.json
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── GraphView.jsx
│   │   │   ├── EntityProfile.jsx
│   │   │   ├── Search.jsx
│   │   │   └── AdminAuditLog.jsx
│   │   ├── components/
│   │   │   ├── GraphCanvas.jsx
│   │   │   ├── RiskScoreBadge.jsx
│   │   │   ├── EvidencePanel.jsx
│   │   │   └── FilterBar.jsx
│   │   └── api/
│   │       └── client.js
│   └── public/
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_ner.py
│   ├── test_entity_resolution.py
│   ├── test_graph_loader.py
│   ├── test_analytics.py
│   └── test_audit_chain.py
│
└── scripts/
    ├── run_full_pipeline.py          # ingestion -> nlp -> graph -> analytics, one command
    ├── reset_databases.py
    └── seed_demo_data.py             # pre-load everything before the live demo
```

**Rules for a coding agent working in this repo:**
- `data-generation/` only ever *produces* files into its own `output/` folder — it must never be imported by `ingestion/` or later layers; ingestion should be able to run against real data dropped in the same format, not just synthetic output.
- `ingestion/` writes only to PostgreSQL and MongoDB (via `db_writers/`) — it must not call Neo4j directly.
- `nlp/` reads from MongoDB, writes extraction results back into MongoDB (`extracted` field) — it must not write to Neo4j directly; `graph/loader.py` is the only component that writes to Neo4j.
- `analytics/` reads/writes Neo4j node/edge properties only — it must not modify Postgres/MongoDB.
- `backend/` is the only layer allowed to be called by `frontend/`; the frontend must never connect to Postgres/MongoDB/Neo4j directly.
- `security/audit_chain.py` must be invoked from within `backend/` on every write/query endpoint — it is a cross-cutting import, not a standalone phase folder that runs independently.

---

## 7. Cross-Cutting Concern: Traceability

Every entity and relationship in the graph must be traceable back to:
1. The source document/record it came from (`source_doc` / `source_name` property)
2. The confidence of the extraction (`confidence` property)
3. The audit log entry recording when it was ingested/by what process

This traceability chain (Graph → Mongo/Postgres source record → Audit log) is what makes the system's outputs explainable and defensible — a deliberate design principle running through every layer, not an afterthought.
