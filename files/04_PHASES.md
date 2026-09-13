# Build Phases & Roadmap
## AI-Powered Criminal Network Analysis System

This breaks the full build into sequential phases, each with a clear deliverable and exit criteria — designed so a coding agent (e.g. Antigravity) or team member can pick up one phase at a time without needing the full context reloaded.

---

## Phase 0 — Environment & Foundations

**Goal:** Everyone can run the full stack locally before any feature code is written.

- Install Docker; set up `docker-compose.yml` (Postgres, MongoDB, Neo4j with GDS plugin)
- Verify all 3 databases start and are reachable (`docker ps`, Neo4j Browser login)
- Create project skeleton exactly as specified in `02_ARCHITECTURE.md` §6 (Project Folder Structure): `/data-generation`, `/ingestion`, `/nlp`, `/graph`, `/analytics`, `/backend`, `/frontend`, `/security`, `/tests`, `/scripts`, `/docs` — each phase below writes only into its designated folder, per the cross-layer rules listed in that section
- Set up Python virtual environment + `requirements.txt` (fastapi, psycopg2-binary, pymongo, neo4j, spacy, rapidfuzz, pydantic, cryptography, python-jose, groq, python-dotenv)
- Create a free Groq API key at console.groq.com/keys (no credit card required); store it as `GROQ_API_KEY` in a local `.env` file (add `.env` to `.gitignore`)
- Set up React app skeleton (`npx create-react-app` or Vite) with routing stubs for Dashboard/GraphView/EntityProfile

**Exit criteria:** `docker compose up -d` works, a test script inserts one record into each of the 3 databases successfully.

---

## Phase 1 — Synthetic Dataset

**Goal:** A realistic, ground-truth-backed dataset ready to feed into ingestion.

- Design ground-truth network (~30-40 entities: kingpin, lieutenants, operatives, financiers, noise entities) in `ground_truth.xlsx`
- Write `cdr_generator.py`, `transaction_generator.py` → produce CDR/transaction CSVs from ground truth (with noise + structuring patterns injected)
- Generate FIR/surveillance/social-media text via Groq API calls (`llama-3.3-70b-versatile`, free tier) seeded with ground-truth facts (20-40 documents), deliberately fragmented and with name-format inconsistencies; add small delays between calls to stay within free-tier rate limits (~30 req/min)
- Fill `criminal_records` and `vehicle_records` manually/semi-manually from ground truth
- Label ~100-200 sentences for NER fine-tuning (Doccano/Label Studio or LLM-assisted labeling)

**Exit criteria:** All raw data files exist on disk; ground-truth spreadsheet is the documented source of truth for evaluating accuracy later.

---

## Phase 2 — Data Ingestion Layer

**Goal:** Raw files → validated, normalized records in Postgres/MongoDB.

- Pydantic models for CDR, transaction, criminal record, vehicle record
- FastAPI endpoints: `/ingest/cdr`, `/ingest/transactions`, `/ingest/criminal-history`, `/ingest/fir`, `/ingest/social-media`
- Structured data → validate → write to Postgres
- Unstructured data → extract text (PyMuPDF/Tesseract for PDFs/scans) → normalize into envelope schema → write to MongoDB with `processing_status: "raw"`

**Exit criteria:** Running ingestion on the full Phase 1 dataset populates Postgres and MongoDB correctly; malformed test records are correctly rejected/flagged.

---

## Phase 3 — NLP / NER / Relation Extraction

**Goal:** Unstructured MongoDB records get `structured_fields`/`extracted` filled in.

- Regex extractors: phone numbers, vehicle numbers, amounts, dates
- Fine-tune spaCy (or use IndicNER for Hindi/Hinglish) on the Phase 1 labeled dataset for PERSON/LOCATION/ORGANIZATION
- Relation extraction: dependency-parsing rules for core relation types + LLM-assisted extraction via Groq API (structured JSON prompt, `llama-3.3-70b-versatile`) for complex cases
- Entity resolution: `rapidfuzz` fuzzy name matching + rule-based scoring (shared phone/vehicle number = strong match signal); assign canonical_id
- Update MongoDB records: `processing_status: "extracted"`, `extracted.entities`, `extracted.relations` filled

**Exit criteria:** Precision/recall of extracted entities and relations measured against ground truth; document accuracy numbers for the report.

---

## Phase 4 — Graph Construction

**Goal:** All extracted entities/relations (plus structured CDR/transaction data) become one live Neo4j graph.

- Cypher `MERGE`-based loader script, keyed on `canonical_id`
- Load structured data as graph edges too (CDR → CALLED edges, transactions → TRANSFERRED_MONEY_TO edges)
- Load NLP-extracted entities/relations from MongoDB
- Verify no duplicate nodes for the same ground-truth person (spot-check against ground truth)

**Exit criteria:** Full graph visible in Neo4j Browser; node/edge count roughly matches expectations from ground truth + noise.

---

## Phase 5 — Graph Analytics

**Goal:** Graph produces investigator-relevant insights.

- Run Neo4j GDS: degree/betweenness/PageRank centrality, Louvain community detection, node similarity (link prediction)
- Write custom Python jobs: communication spike detection, transaction structuring detection
- Compute composite risk_score per person, write back to Neo4j
- Validate: does betweenness/PageRank correctly surface the ground-truth kingpin/broker? Document this as your accuracy story.

**Exit criteria:** `/analytics/*` endpoints return sensible ranked results; at least one genuinely "hidden" link-prediction result validated against ground truth (a relationship not directly stated in any single document but correctly inferred).

---

## Phase 6 — Backend API Layer

**Goal:** All layers exposed via one consistent FastAPI service.

- Implement all endpoints listed in `03_DESIGN.md` §6
- Wire JWT auth + role checks
- Wire audit hash-chain logging into every write/query action

**Exit criteria:** Full API testable via Swagger UI (`/docs`) end-to-end, with auth enforced.

---

## Phase 7 — Frontend / Visualization

**Goal:** Investigator-facing app.

- Dashboard page (top influencers, communities, alerts)
- Graph view (Cytoscape.js): node styling by risk_score/community, click-to-expand, edge click → evidence panel
- Entity profile page with risk score breakdown
- Search
- (Optional) Natural language query box

**Exit criteria:** A judge can search a name, see their graph, click through to evidence, with no manual data manipulation needed.

---

## Phase 8 — Security & Blockchain Layer

**Goal:** RBAC, encryption, and the tamper-evident audit chain are fully wired and demoable.

- RBAC enforced across all endpoints (verify by testing as each role)
- Field-level encryption for sensitive identity fields; redacted views for lower roles
- Hash-chain `verify_chain()` implemented and exposed via `/audit/verify`
- **Prepare the tamper-detection demo:** manually alter a past log entry in the DB, show `verify_chain()` catches it live

**Exit criteria:** Live tamper-detection demo works reliably, RBAC denies access correctly when tested with a lower-privilege token.

---

## Phase 9 — Integration, Polish & Demo Prep

**Goal:** Everything works together, reliably, in a rehearsed demo flow.

- End-to-end run: fresh Docker environment → ingest full dataset → verify graph, analytics, dashboard all populate correctly
- Pre-load the demo dataset before presenting (don't run ingestion live unless intentional)
- Rehearse a scripted demo narrative: Dashboard → search suspect → expand graph → click edge for evidence → show risk score breakdown → show link-prediction "hidden connection" moment → show tamper-detection on audit log
- Prepare backup laptop with identical Docker setup
- Finalize PPT/report: include accuracy metrics (Phase 3/5 exit criteria), architecture diagram, theme justification

**Exit criteria:** Full demo run-through completed successfully at least twice without manual fixes.

---

## Suggested Team Role Mapping

| Role | Phases owned |
|---|---|
| Data/Backend Engineer | Phase 0, 1, 2, 6 |
| NLP/ML Engineer | Phase 1 (labeling), Phase 3 |
| Graph/Algorithms Engineer | Phase 4, 5 |
| Frontend Engineer | Phase 7 |
| Security Engineer | Phase 8 |
| All (shared) | Phase 9 |

Phases 0-2 should be built first and in parallel where possible (data generation and ingestion scaffolding don't block each other); Phases 3-5 are sequential (each depends on the previous layer's output); Phase 6-7 can start once Phase 4's graph schema is stable, even before Phase 5 analytics are fully polished.
