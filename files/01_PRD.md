# Product Requirements Document (PRD)
## AI-Powered Criminal Network Analysis System

**Event:** Smart India Hackathon 2026
**Theme:** Blockchain & Cybersecurity
**Document version:** 1.0

---

## 1. Problem Statement (as given)

Modern criminal activities are increasingly organized and interconnected. Criminals operate through networks involving associates, intermediaries, financial channels, communication links, locations, and events. Law enforcement agencies collect large volumes of data from FIRs, Call Detail Records (CDRs), financial transaction records, surveillance reports, social media intelligence, criminal history databases, and intelligence agency reports.

Investigators struggle to identify hidden relationships among suspects because this data is fragmented, unstructured, and distributed across multiple systems. Manual analysis is slow, labor-intensive, and prone to missing critical connections.

**Goal:** Build an AI-powered system that automatically analyzes structured and unstructured crime-related data to uncover hidden networks, identify key influencers, detect suspicious patterns, and provide actionable, explainable intelligence to investigators — with a tamper-evident audit trail (Blockchain) and strong data protection (Cybersecurity), consistent with the assigned theme.

---

## 2. Objectives

1. Ingest structured (CDR, transactions, criminal history) and unstructured (FIRs, surveillance reports, social media, news) data from multiple simulated sources into one normalized pipeline.
2. Automatically extract entities (people, locations, phone numbers, vehicles, organizations) and relationships from unstructured text using NLP/NER.
3. Build a unified relationship graph connecting all entities across all sources.
4. Identify key influencers, brokers, and communities within the network using graph analytics.
5. Detect suspicious/anomalous patterns (communication spikes, financial structuring, hidden link prediction).
6. Present all of this through an interactive, explainable visual dashboard for investigators.
7. Maintain a tamper-evident, hash-chained audit trail of every system action, and enforce role-based access control and encryption — directly addressing the Blockchain & Cybersecurity theme.

---

## 3. Target Users (Personas)

| Persona | Needs |
|---|---|
| **Field Investigator** | Search a suspect, see their direct connections, view case-relevant evidence quickly |
| **Intelligence Analyst / Supervisor** | See the full network, identify key influencers/communities, review flagged anomalies, approve/verify AI-suggested links |
| **System Admin** | Manage users/roles, view audit logs, ensure data integrity |

---

## 4. Scope

### In scope (Prototype for SIH)
- Synthetic dataset generation (ground-truth network + generated CDRs, transactions, FIR text, social media posts, criminal history)
- Multi-source ingestion pipeline with validation and normalization
- NER + relation extraction (hybrid: regex + fine-tuned model + LLM-assisted via Groq API — free tier)
- Entity resolution (deduplication across sources)
- Graph construction in Neo4j
- Graph analytics: centrality (degree, betweenness, PageRank), community detection (Louvain), link prediction (node similarity), anomaly detection (communication spikes, transaction structuring), composite risk scoring
- Interactive graph visualization + investigator dashboard
- RBAC, encryption, and a hash-chained tamper-evident audit trail
- Optional: natural-language-to-Cypher query interface

### Out of scope (Prototype)
- Real government data integration (explicitly noted as future work / requires MOUs and legal clearance)
- Production-grade blockchain network (Hyperledger Fabric) — prototype uses a simplified custom hash-chain that demonstrates the same tamper-evidence concept
- Mobile app (web dashboard only)
- Real-time streaming ingestion (batch/on-demand ingestion is sufficient for demo)

---

## 5. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | System shall ingest CDR, transaction, and criminal history CSV/JSON files, validate them, and store them in a structured database |
| FR2 | System shall ingest FIR text, surveillance reports, social media posts (PDF/text/JSON) and store raw content with metadata |
| FR3 | System shall extract entities (PERSON, LOCATION, VEHICLE, PHONE, ORGANIZATION) from unstructured text |
| FR4 | System shall extract relationships between entities (MET_WITH, CALLED, TRANSFERRED_MONEY_TO, OWNS_OR_USES, etc.) |
| FR5 | System shall resolve duplicate entity mentions across documents into a single canonical entity |
| FR6 | System shall construct and incrementally update a graph of all entities and relationships |
| FR7 | System shall compute centrality scores (degree, betweenness, PageRank) for all persons in the graph |
| FR8 | System shall detect communities/clusters within the network |
| FR9 | System shall suggest likely hidden relationships via link prediction |
| FR10 | System shall detect suspicious patterns: communication spikes, financial structuring |
| FR11 | System shall compute and display a composite, explainable risk score per person |
| FR12 | System shall provide an interactive graph visualization with filtering, expansion, and node/edge drill-down to source evidence |
| FR13 | System shall provide a dashboard listing top influencers, communities, and active alerts |
| FR14 | System shall enforce role-based access (Investigator / Analyst / Admin) |
| FR15 | System shall log every significant action (ingestion, query, flag, view) into a tamper-evident hash chain |
| FR16 | System shall encrypt sensitive data at rest and in transit |
| FR17 | (Optional) System shall accept natural language queries and translate them into graph queries |

---

## 6. Non-Functional Requirements

- **Explainability:** Every AI-generated insight (risk score, suggested link, flagged anomaly) must be traceable back to source evidence.
- **Performance (prototype scale):** Handle a synthetic network of 100–300 entities and thousands of structured records with sub-second to few-second query response for the demo dataset.
- **Security:** RBAC enforced on every API endpoint; sensitive fields encrypted.
- **Integrity:** Audit hash-chain must detect any retroactive tampering of logged actions (demonstrable live).
- **Usability:** Dashboard must be understandable by a non-technical investigator without training.
- **Portability:** Entire system must run locally via Docker with no external dependency required during the live demo (except LLM API calls to Groq — free tier, no cost risk — which should have a template-based fallback for offline/no-internet demo conditions).

---

## 7. Success Metrics (for judging & self-evaluation)

| Metric | How measured |
|---|---|
| Entity extraction accuracy | Precision/recall against the known ground-truth entity list |
| Relationship extraction accuracy | Precision/recall against ground-truth relationships |
| Key influencer identification accuracy | Does centrality analysis correctly surface the ground-truth "kingpin"/"broker" roles? |
| Link prediction usefulness | % of top suggested hidden links that match ground-truth-but-undocumented relationships |
| Audit chain integrity | Live demo: tampering with a past log entry is detected by chain verification |
| Demo clarity | Can a judge unfamiliar with the system understand a suspect's risk profile within 30 seconds of clicking their node? |

---

## 8. Constraints & Assumptions

- No real government/PII data will be used; a synthetic dataset with a designed ground truth will substitute for it, and this will be stated transparently in the pitch.
- The prototype is a proof-of-concept; production deployment would require legal/procedural integration with actual law enforcement data systems (noted as future scope, not attempted here).
- Team has limited build time (hackathon timeline) — feature depth will be prioritized per the Phases document.

---

## 9. Theme Justification (Blockchain & Cybersecurity)

- **Cybersecurity:** RBAC, encryption at rest/in transit, field-level redaction for sensitive identities, and access-anomaly detection on the system's own audit logs.
- **Blockchain:** A tamper-evident, hash-chained audit trail of every ingestion/query/flag/access action — ensuring evidentiary integrity, which is a genuine legal requirement for any AI-assisted investigative tool. The prototype implements this as a custom SHA-256 hash chain (conceptually identical to blockchain's core guarantee), with Hyperledger Fabric noted as the production-grade path.
