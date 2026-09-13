# Design Document
## AI-Powered Criminal Network Analysis System

This document specifies concrete schemas, ontology, API contracts, and UI structure — detailed enough to hand directly to a coding agent (e.g. Antigravity) layer by layer.

---

## 1. Ontology (Entity & Relationship Types)

### Node (Entity) types

| Type | Key properties |
|---|---|
| `Person` | canonical_id, name, aliases[], dob, address, risk_score, betweenness, pagerank, community_id |
| `Location` | canonical_id, name, lat, lng, type (residence/meeting_point/etc.) |
| `Vehicle` | canonical_id, registration_number, type, owner_ref |
| `PhoneNumber` | canonical_id, number, carrier |
| `Organization` | canonical_id, name, type (shell_company/gang/legit_business) |
| `Event` | canonical_id, description, date, location_ref |
| `Account` | canonical_id, account_number, bank_name, owner_ref |

### Relationship types

| Relationship | Direction | Key properties |
|---|---|---|
| `CALLED` | Person → Person (via PhoneNumber) | date, duration_sec, frequency, confidence, source_doc |
| `MET_WITH` | Person → Person | date, location_ref, confidence, source_doc |
| `TRANSFERRED_MONEY_TO` | Account → Account | amount, date, flagged_structuring, confidence, source_doc |
| `OWNS_OR_USES` | Person → Vehicle/PhoneNumber/Account | since_date, confidence, source_doc |
| `RESIDES_AT` | Person → Location | confidence, source_doc |
| `MEMBER_OF` | Person → Organization | role, since_date, confidence, source_doc |
| `PRESENT_AT` | Person → Event | confidence, source_doc |
| `ASSOCIATED_WITH` | Person → Person | weak/co-occurrence-based, confidence, source_doc |
| `RELATED_TO` | Person → Person | relation_type (family), confidence, source_doc |

Keep this list fixed for the prototype — it is the contract between the NER labels (Layer 2), the graph loader (Layer 3), and the frontend legend (Layer 5).

---

## 2. PostgreSQL Schema (Structured Data)

```sql
-- CDR Records
CREATE TABLE cdr_records (
    record_id UUID PRIMARY KEY,
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

-- Financial Transactions
CREATE TABLE transactions (
    txn_id UUID PRIMARY KEY,
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

-- Criminal History
CREATE TABLE criminal_records (
    person_id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    aliases TEXT[],
    date_of_birth DATE,
    known_address TEXT,
    past_cases JSONB,
    known_associates TEXT[],
    risk_flag VARCHAR(20),
    ingested_at TIMESTAMP DEFAULT now()
);

-- Vehicle Registry
CREATE TABLE vehicle_records (
    vehicle_id UUID PRIMARY KEY,
    registration_number VARCHAR(15) NOT NULL,
    owner_name VARCHAR(100),
    vehicle_type VARCHAR(20),
    registered_address TEXT,
    ingested_at TIMESTAMP DEFAULT now()
);

-- Users (RBAC)
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,        -- investigator / analyst / admin
    created_at TIMESTAMP DEFAULT now()
);

-- Access Logs (underlying record; hash-chained wrapper described in section 8)
CREATE TABLE access_logs (
    log_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    action VARCHAR(50),
    entity_accessed VARCHAR(100),
    timestamp TIMESTAMP DEFAULT now()
);
```

---

## 3. MongoDB Schema (Unstructured Data — flexible documents)

Common "envelope" every raw document is normalized into on ingestion:

```json
{
  "_id": "uuid",
  "source_type": "FIR | SURVEILLANCE | SOCIAL_MEDIA | NEWS",
  "source_name": "string",
  "ingested_at": "ISODate",
  "raw_content": "string (the actual text)",
  "metadata": { "...variable per source type..." },
  "processing_status": "raw | cleaned | extracted",
  "extracted": {
     "entities": [ { "type": "PERSON", "text": "...", "canonical_id": "..." } ],
     "relations": [ { "subject": "...", "predicate": "...", "object": "...", "confidence": 0.0 } ]
  }
}
```

Example `metadata` per source type:
- FIR: `{ "fir_number": "...", "station": "...", "officer": "..." }`
- SOCIAL_MEDIA: `{ "platform": "...", "username": "...", "post_id": "..." }`
- SURVEILLANCE: `{ "officer": "...", "location": "...", "time_window": "..." }`

---

## 4. Neo4j Graph Schema

Example Cypher for the loader (MERGE-based, idempotent):

```cypher
MERGE (p:Person {canonical_id: $id})
SET p.name = $name, p.aliases = $aliases, p.risk_score = coalesce(p.risk_score, null)

MERGE (a)-[r:CALLED {date: $date}]->(b)
SET r.duration_sec = $duration, r.confidence = $confidence, r.source_doc = $source_doc
```

Analytics results are written back as node properties:
`risk_score`, `betweenness`, `pagerank`, `community_id`, `degree`, `comm_anomaly_score`, `suspicious_txns_count`.

### Multi-Modal Ownership Linking (KYC & Telecom Integration) — Pipeline Step [6/6]
During graph construction (Step 6/6 of `graph/loader.py`), cross-modal entity links are established between abstract entity nodes (`Person`, `Organization`) and physical/financial identity handles (`PhoneNumber`, `Account`, `Vehicle`):

1. **Telecom SIM Ownership:** 
   - **Matched Identifiers:** Maps official subscriber registrations from telecom records (`phone` numbers) to the subscriber's canonical identity.
   - **Edge Created:** `(Person|Organization)-[:OWNS_OR_USES]->(PhoneNumber)` with properties `{confidence: 0.98, source_doc: 'TELECOM_REGISTRY'}`.
2. **Banking KYC Account Ownership:**
   - **Matched Identifiers:** Extracts bank account identifier prefixes (`ACC_{PREFIX}_{NUM}`) and matches them against normalized subscriber names in banking KYC records.
   - **Edge Created:** `(Person|Organization)-[:OWNS_OR_USES]->(Account)` with properties `{confidence: 0.95, source_doc: 'BANKING_KYC'}`.
3. **Motor Vehicle Registry Ownership:**
   - **Matched Identifiers:** Maps motor vehicle registration records (`registration_number`) to the registered vehicle owner (`owner_name`).
   - **Edge Created:** `(Person|Organization)-[:OWNS_OR_USES]->(Vehicle)` with properties `{confidence: 0.95, source_doc: 'VEHICLE_REGISTRY'}`.

**Downstream Analytical Role:**
Enables graph traversal algorithms in `analytics/anomaly_detection.py` and `analytics/risk_scoring.py`:
- Financial Structuring Traversal: `Person -[OWNS_OR_USES]-> Account -[TRANSFERRED_MONEY_TO {flagged_structuring: true}]-> Account` to compute `suspicious_txns_count`.
- Telecommunication Burst Traversal: `Person -[OWNS_OR_USES]-> PhoneNumber -[CALLED]-> PhoneNumber` to compute `comm_anomaly_score`.

**Jury Explanation (One-Sentence Pitch):**
> *"Step 6 establishes cross-modal identity links by fusing banking KYC and telecom subscriber registries into `OWNS_OR_USES` edges, allowing our graph analytics to trace money laundering flows and communication spikes back to the masterminds controlling those accounts and SIM cards."*

### Multi-Source Relationship Corroboration (CALLED Edges)
The knowledge graph's `CALLED` relationships demonstrate multi-source corroboration:
- **Quantitative CDR Records (PostgreSQL):** 337 telecommunication interaction pairs extracted directly from carrier Call Detail Records, tracking call frequency, timestamps, and total call durations.
- **Qualitative Intelligence Mentions (MongoDB):** Call interactions extracted by the hybrid NLP pipeline from First Information Reports and social media intercepts.
When both sources report an interaction between the same entities, the edge represents multi-modal corroboration (corroborated by independent signal types).

---

## 5. Synthetic Data / Ground-Truth Design

- Maintain a master spreadsheet (`ground_truth.xlsx`) with sheets: `Entities`, `Relationships`, `Events`.
- `Entities` sheet columns: entity_id, type, name, phone, vehicle_reg, address, role (kingpin/lieutenant/operative/financier/noise).
- `Relationships` sheet columns: subject_id, predicate, object_id, notes.
- Generator scripts (Python) read this spreadsheet and produce:
  - `cdr_generator.py` → CDR CSV
  - `transaction_generator.py` → transactions CSV
  - `fir_generator.py` → calls the **Groq API** (`llama-3.3-70b-versatile`, free tier) with ground-truth facts, constrained to a "do not invent facts beyond what's given" prompt, to produce FIR narrative text files
  - `social_media_generator.py` → same Groq call pattern, prompted for informal-register posts
- Deliberately inject: name-format inconsistency, missing fields, noise entities/records, scattered evidence (no single doc reveals the full network).

**Groq API configuration:** store the key as `GROQ_API_KEY` in `.env` (never hardcoded/committed). Both `fir_generator.py`/`social_media_generator.py` (Phase 1) and `nlp/relation_extraction.py` (Phase 3) read from this same env var via the `groq` Python package. Because the free tier is rate-limited (~30 requests/minute), generator scripts should include a short delay/retry-on-429 between calls when generating batches of documents.

---

## 6. API Design (FastAPI, representative endpoints)

| Endpoint | Method | Purpose | Auth role |
|---|---|---|---|
| `/auth/login` | POST | Get JWT | public |
| `/auth/me` | GET | Get current authenticated user profile | investigator+ |
| `/entity/search` | GET | Search entities by name, phone, plate | investigator+ |
| `/entity/{id}` | GET | Get entity profile | investigator+ |
| `/entity/{id}/graph?hops=N` | GET | Get N-hop subgraph for visualization | investigator+ |
| `/analytics/influencers` | GET | Top-N ranked centrality list | analyst+ |
| `/analytics/communities` | GET | Detected clusters | analyst+ |
| `/analytics/link-predictions` | GET | Suggested hidden relationships | analyst+ |
| `/analytics/alerts` | GET | Active anomaly flags | analyst+ |
| `/analytics/rerun` | POST | Trigger graph analytics recalculation | admin |
| `/ingest/fir` | POST | Upload/ingest a FIR document | investigator+ |
| `/ingest/cdr` | POST | Upload CDR CSV batch | analyst+ |
| `/ingest/transactions` | POST | Upload transaction CSV batch | analyst+ |
| `/query/natural-language` | POST | NL → Cypher → results | analyst+ |
| `/audit/verify` | GET | Verify hash-chain integrity | admin |
| `/audit/logs` | GET | Fetch recent audit chain blocks | admin |
| `/audit/tamper-demo` | POST | Simulate a tamper attack for live demo | admin |
| `/health` | GET | API health check | public |

Every non-public endpoint: (1) validates JWT, (2) checks role, (3) writes an entry to the audit hash-chain describing the action taken.

---

## 7. Frontend Structure (React)

```
src/
 ├── pages/
 │   ├── Dashboard.jsx        (top influencers, communities, alerts)
 │   ├── GraphView.jsx        (Cytoscape.js interactive graph)
 │   ├── EntityProfile.jsx    (single entity deep-dive + risk breakdown)
 │   ├── Search.jsx
 │   └── AdminAuditLog.jsx    (admin-only: view/verify hash chain)
 ├── components/
 │   ├── GraphCanvas.jsx
 │   ├── RiskScoreBadge.jsx
 │   ├── EvidencePanel.jsx    (shows source_doc on edge click)
 │   └── FilterBar.jsx
 └── api/
     └── client.js            (calls FastAPI backend)
```

**Node styling convention:** node size ∝ risk_score, node color by community_id, icon by entity type (Person/Location/Vehicle/Phone/Org).

---

## 8. Security & Audit Design

- JWT-based auth; roles: `investigator`, `analyst`, `admin`.
- Sensitive fields (e.g., informant identity) stored encrypted (Fernet) and redacted for lower roles.
- Hash-chain block structure:
```json
{
  "action": "ENTITY_FLAGGED",
  "actor": "investigator_042",
  "entity_id": "RAVI001",
  "timestamp": "...",
  "data_hash": "sha256:...",
  "previous_hash": "sha256:..."
}
```
- `verify_chain()` re-walks all blocks and confirms each `previous_hash` matches — used both automatically (on every write) and on-demand via `/audit/verify` for the live tamper-detection demo.

---

## 9. Composite Risk Score Formula (baseline, tune later)

```
risk_score = 0.30 * normalized(betweenness_centrality)
           + 0.25 * normalized(pagerank)
           + 0.20 * normalized(criminal_history_severity)
           + 0.15 * normalized(suspicious_transaction_count)
           + 0.10 * normalized(communication_anomaly_score)
```

Store each component alongside the final score so the UI can show a breakdown ("why did this person score 82/100") — this is the explainability requirement from the PRD.
