# Known Issues & Required Fixes
## AI-Powered Criminal Network Analysis System — Post Phase-5 Pipeline Review

**Context:** `scripts/run_full_pipeline.py` was run end-to-end successfully (Phases 2-5 + audit verification). The pipeline completes without errors and produces a working graph with ground-truth validation (80% Top-5 overlap). However, review of the output log surfaced several issues that should be fixed before Phase 6/7 integration and before the demo. This document lists each issue for an agent (Antigravity) to investigate and fix, in priority order.

Refer to `02_ARCHITECTURE.md` for folder/layer boundaries and `03_DESIGN.md` for the intended schema/formula each fix must remain consistent with.

---

## Status Update (after 2nd pipeline run)

| # | Issue | Status |
|---|---|---|
| 1 | Txns/Comm risk components not discriminating | ✅ **Fixed** — both now show real variation across people |
| 2 | Organization & Location node over-extraction | ✅ **Fixed** — Org 52→4, Location 44→15 |
| 3 | Amount entity extraction non-functional | ✅ **Improved** — 1→10 extracted, proportionate to dataset |
| 4 | Undocumented "Multi-Modal Ownership Links" step | ⏳ **Still open** — confirm `03_DESIGN.md §4` has been updated to describe it |
| 5 | Person node inflation / weak entity resolution | ✅ **Improved** — 53→27, within/near ground-truth range |
| 6 | CALLED edge count mismatch | ✅ **Resolved (non-issue)** — correct partial dedup via MERGE, intended behavior |
| 7 | Backend API not yet verified end-to-end | ✅ **Fixed** — 33/33 live HTTP checks passed, including 12 confirmed RBAC 403 rejections from two under-privileged roles, and a live tamper-detection demo (`POST /audit/tamper-demo`) |

**Remaining before demo-ready:**
- **#4** — confirm the ownership-linking step is documented.
- **New (#8)** — `03_DESIGN.md §6`'s endpoint table is now stale: live testing revealed real endpoints (`/health`, `/auth/me`, `/audit/logs`, `/audit/tamper-demo`, `/analytics/rerun`, `/entity/search`) that aren't in the original design spec. Update the Design doc's API table to match what was actually built, so the frontend developer has an accurate reference rather than discovering extra/renamed endpoints via trial and error.
- Confirm actual `pytest tests/` pass/fail counts (the run was executed but results weren't shown in this evidence).

---

## Priority 1 — Risk Scoring: `Txns` and `Comm` components not discriminating

**Symptom:** In the Top-10 risk-ranked output, every single person has `Txns: 0.00` and `Comm: 10.00` (the exact same value across all 10+ people), while `Betweenness`, `PageRank`, and `History` vary correctly per person.

**Why this matters:** Per `03_DESIGN.md §9`, the composite risk score is:
```
risk_score = 0.30 * normalized(betweenness_centrality)
           + 0.25 * normalized(pagerank)
           + 0.20 * normalized(criminal_history_severity)
           + 0.15 * normalized(suspicious_transaction_count)
           + 0.10 * normalized(communication_anomaly_score)
```
Two of five weighted components (35% of the total score) are currently constant across every person, meaning they contribute no real signal — the risk score is effectively only using 3 of 5 factors right now, which undermines the "explainable, multi-factor risk score" claim in the PRD.

**Suspected root causes (investigate both):**
1. **`Txns` = 0.00 for everyone:** `TRANSFERRED_MONEY_TO` edges exist between `Account` nodes, not `Person` nodes (per the ontology in `03_DESIGN.md §1`). The transaction-anomaly query likely queries `Person` nodes directly for this relationship instead of traversing `Person -[OWNS_OR_USES]-> Account -[TRANSFERRED_MONEY_TO]-> Account`. Fix the Cypher/query in `analytics/anomaly_detection.py` (or wherever `suspicious_transaction_count` is computed) to traverse through the `Account` node correctly.
2. **`Comm` = 10.00 (max) for everyone:** Likely a min-max normalization bug — e.g., dividing by a zero/constant denominator, or the normalization function clamping incorrectly. Inspect the normalization step for `communication_anomaly_score` in `analytics/anomaly_detection.py` and confirm it actually produces a spread of values across the real underlying data (call frequency/burst counts per person), not a constant.

**Fix location:** `analytics/anomaly_detection.py`, `analytics/risk_scoring.py`

**Verification:** Re-run `run_full_pipeline.py`; confirm the Top-10 table shows genuinely varying `Txns` and `Comm` values per person (not identical across all rows). Spot-check 2-3 people manually against their actual transaction/call data in Postgres to confirm the numbers make sense.

---

## Priority 2 — Location & Organization node over-extraction (NER false positives)

**Symptom:** Final graph shows **52 Organization nodes** and **44 Location nodes**, despite the ground-truth network (`ground_truth.xlsx`) designing only a handful of real organizations and locations (likely single digits to low teens for each).

**Why this matters:** This strongly suggests spaCy's NER is over-tagging text as `ORG`/`LOCATION` — station names, department names, sentence fragments, or generic capitalized phrases getting misclassified — polluting the graph with noise nodes for both entity types. This distorts centrality/community results and would look bad if a judge inspects the graph directly (e.g., clicking through and finding nonsense "organizations").

**Investigation steps:**
1. Query `MATCH (o:Organization) RETURN o.name` and `MATCH (l:Location) RETURN l.name` in Neo4j Browser and manually review both lists.
2. Identify which extracted names are genuinely meaningful vs. NER noise, for both types.
3. If noise is confirmed: tighten the NER confidence filtering in `nlp/pipeline.py` — consider a minimum confidence threshold before an ORG or LOCATION entity is accepted, and/or cross-check candidates against the known vocabulary in `ground_truth.xlsx` (allowlist) plus a small denylist of common false-positive patterns (e.g., generic police station name formats that shouldn't become "Organization" nodes).

**Fix location:** `nlp/pipeline.py`, `nlp/ner_model/` (confidence thresholding), possibly `nlp/regex_extractors.py`

**Verification:** Re-run pipeline; Organization and Location node counts should both drop to numbers consistent with the ground truth (allowing some legitimate NER-discovered entities not in the original ground truth, but not 4-5x inflation).

---

## Priority 3 — Amount entity extraction is effectively non-functional

**Symptom:** NLP extraction summary shows only **1 total `Amount` entity** extracted across all 44 documents — despite `03_DESIGN.md` specifying an `AMOUNT_PATTERN` regex extractor intended to catch monetary amounts mentioned in FIR/surveillance/social-media text.

**Why this matters:** This is a near-total miss on one of the five documented entity types. It suggests either the regex extractor isn't being invoked in the NLP pipeline at all, or its pattern doesn't match how amounts are actually phrased in the generated text (e.g., if Groq-generated FIRs write amounts in words — "fifty thousand rupees" — rather than digits/currency symbols — "₹50,000" — a symbol/digit-based regex would miss them entirely). While structured transaction amounts already flow into the graph via PostgreSQL (unaffected by this bug), text-based financial evidence is currently not reaching the graph at all.

**Investigation steps:**
1. Confirm `AMOUNT_PATTERN` regex (from `nlp/regex_extractors.py`) is actually being called as part of `nlp/pipeline.py`'s per-document extraction loop — check for a missing function call, not just a missing pattern.
2. Manually inspect 3-5 of the generated FIR/social-media documents in `data-generation/output/fir_reports/` for how amounts are actually written, and confirm the regex pattern matches that real format.
3. If amounts are written in words rather than digits, either adjust the Groq generation prompts (Phase 1) to consistently use digit/currency-symbol format, or broaden the regex/NER approach to also catch word-form amounts.

**Fix location:** `nlp/regex_extractors.py`, `nlp/pipeline.py`, possibly `data-generation/fir_generator.py` (prompt adjustment)

**Verification:** Re-run pipeline; `Amount` entity count should scale roughly with how many documents actually reference a monetary figure in their text (not necessarily all 44, but meaningfully more than 1).

---

## Priority 4 — Undocumented pipeline step: "Multi-Modal Ownership Links (KYC & Telecom)"

**Symptom:** Graph construction logs a step — "🔗 [6/6] Establishing Multi-Modal Ownership Links (KYC & Telecom)... ✅ Multi-modal identity links created" — that does not correspond to any relationship type or process described in `03_DESIGN.md`'s ontology (§1) or graph-loader design.

**Why this matters:** This step is clearly doing something (likely resolving/linking a person to accounts/phone numbers via shared identifiers across sources), and it may be a genuinely valuable piece of entity resolution — but right now it exists only as code, with no written specification. This is a real risk for the demo: if a judge asks "what does this step do and why," there needs to be a documented answer, not just working code nobody can fully explain on the spot. It also means this logic isn't currently reviewed against the same design standards as the rest of the pipeline.

**Required action (documentation, not necessarily a code fix):**
1. Locate the code implementing this step (likely in `graph/loader.py`).
2. Write up exactly what identifiers it matches on (e.g., phone number + KYC name, account number + registered owner) and what relationship/property it creates as a result.
3. Add this as a documented step in `03_DESIGN.md §4` (Neo4j Graph Schema) so it's an intentional, explainable part of the system with the same level of specification as every other relationship type.
4. If, on review, this logic turns out to be doing something unintended or redundant with existing `OWNS_OR_USES` edges, decide deliberately whether to keep, merge, or remove it — rather than leaving undocumented logic running in the pipeline.

**Fix location:** `graph/loader.py` (review), `03_DESIGN.md §4` (documentation)

**Verification:** `03_DESIGN.md` updated with a clear description of this step; team can explain it in one sentence if asked during judging.

---

## Priority 5 — Person node count inflation / entity resolution under-merging

**Symptom:** Final graph shows **53 Person nodes**, notably higher than the ground-truth design (~30-40). The Top-10 list itself shows this directly: both **"R. Nair"** and **"Suresh Nair"** (and separately, other name variants) appear as if they may not have been merged into single canonical identities.

**Why this matters:** Per `03_DESIGN.md §1` and the Phase 3 entity-resolution step in `04_PHASES.md`, near-duplicate name mentions (e.g., "R. Nair" vs "Suresh Nair" vs a nickname) should resolve to one `canonical_id`. If they don't, the same real person's connections get split across two nodes, artificially lowering both nodes' centrality scores and inflating total person count.

**Investigation steps:**
1. Cross-reference the 53 extracted person names against the ~30-40 names/aliases in `ground_truth.xlsx`'s `Entities` sheet — identify which "extra" names are actually duplicates of an existing ground-truth person under a different format.
2. Review the fuzzy-matching threshold in `nlp/entity_resolution.py` (`rapidfuzz` score cutoff) — it is likely currently too strict (requiring too high a similarity score to merge), letting name variants slip through as distinct entities.
3. Confirm the rule-based scoring also checks shared hard identifiers (phone number, vehicle number) as a strong merge signal, per the original design intent — not name similarity alone.

**Fix location:** `nlp/entity_resolution.py`

**Verification:** Re-run pipeline; Person node count should move closer to the ground-truth entity count (~30-40, allowing a small margin for legitimately new/noise people the NLP pipeline correctly identified as distinct). Manually confirm "R. Nair" and "Suresh Nair" (or whichever variants are actually duplicates) now resolve to one node.

---

## Priority 6 — CALLED edge count mismatch (minor, investigate only)

**Symptom:** Graph loader log reports "337 telecommunication interaction pairs" merged from CDR data, but the final graph summary shows `CALLED: 350` edges — a discrepancy of 13.

**Likely explanation:** NLP-extracted `CALLED` relations (from FIR/social media text mentioning calls) may be creating additional `CALLED` edges on top of the CDR-sourced ones, which is plausibly correct behavior (two different sources both provide evidence of a call) — but this should be confirmed, not assumed.

**Investigation steps:** Check whether `graph/loader.py`'s `MERGE` for `CALLED` edges is keyed in a way that would correctly deduplicate a CDR-based CALLED edge and an NLP-extracted CALLED edge between the same two people (if they refer to the same real-world call), vs. creating two separate edges when they should be one.

**Fix location:** `graph/loader.py`

**Verification:** Document the finding either way — if the 13-edge difference is legitimate multi-source corroboration, note it as a design decision (and perhaps surface it in the UI as "corroborated by multiple sources," which is actually a nice feature). If it's true duplication, fix the `MERGE` key to prevent it.

---

## Priority 7 — Backend API layer not yet verified against Design spec

**Status:** Not tested in the pipeline run reviewed. Phases 2-5 (ingestion → NLP → graph → analytics) and audit chain verification are confirmed working. Phase 6 (`backend/`) code may exist but has not been confirmed to serve correct responses.

**Required before handoff to frontend:**
1. Run `uvicorn backend.main:app --reload` and manually exercise every endpoint listed in `03_DESIGN.md §6` via Swagger UI (`localhost:8000/docs`):
   - `/entity/{id}`, `/entity/{id}/graph?hops=N`
   - `/analytics/influencers`, `/analytics/communities`, `/analytics/link-predictions`, `/analytics/alerts`
   - `/audit/verify`
   - `/auth/login`
2. Confirm each response's JSON shape matches what's documented in `03_DESIGN.md §6` and the node/edge property names match `03_DESIGN.md §1` ontology exactly (frontend will be built against these exact field names).
3. **Explicitly test RBAC:** call an admin-only endpoint (e.g. `/audit/verify`) using a token generated for an `investigator` role and confirm it is rejected (403), not silently allowed.
4. Confirm field-level encryption (per `03_DESIGN.md §8`) is actually invoked on sensitive fields, not just implemented as unused code.

**Fix/verify location:** `backend/`, `security/`

**Verification:** A checklist run-through of every endpoint with both a valid and an invalid-role token, documented with pass/fail, before the frontend developer starts building against these endpoints.

---

## Summary Table

| # | Issue | Severity | Files to fix |
|---|---|---|---|
| 1 | Txns/Comm risk components not discriminating | High — affects core deliverable | `analytics/anomaly_detection.py`, `analytics/risk_scoring.py` |
| 2 | Organization & Location node over-extraction | Medium — affects graph quality/demo | `nlp/pipeline.py`, `nlp/ner_model/` |
| 3 | Amount entity extraction non-functional | Medium — text-based financial evidence missing | `nlp/regex_extractors.py`, `nlp/pipeline.py` |
| 4 | Undocumented "Multi-Modal Ownership Links" step | Medium — unexplainable logic risk for demo | `graph/loader.py`, `03_DESIGN.md §4` |
| 5 | Person node inflation / weak entity resolution | Medium — affects centrality accuracy | `nlp/entity_resolution.py` |
| 6 | CALLED edge count mismatch | Low — investigate, may be non-issue | `graph/loader.py` |
| 7 | Backend API not yet verified end-to-end | High — blocks frontend handoff | `backend/`, `security/` |

**Recommended fix order:** 1 → 5 → 2 → 3 → 4 → 7 → 6

- Fix risk scoring first (1) since it's the headline accuracy metric.
- Fix entity resolution next (5) since it affects everything downstream, including re-validating item 1's numbers.
- Then NER noise cleanup (2) and the amount-extraction gap (3), since both affect graph/evidence quality.
- Document the undocumented ownership-linking step (4) once you understand what the rest of the pipeline is doing around it.
- Verify the backend API layer (7) once the graph/analytics numbers are trustworthy, since the frontend will build directly against these responses.
- Investigate the minor CALLED edge-count question (6) last — lowest impact, may not even be a bug.

Once Priority 1, 2, 3, and 5 are fixed, **re-run the full ground-truth validation** (the Top-10 table + Top-5/Top-10 overlap percentage) to confirm accuracy didn't regress and ideally improved now that entity resolution and risk scoring are corrected.
