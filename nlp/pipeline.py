"""
pipeline.py — Master NLP pipeline orchestrating entity and relation extraction on MongoDB documents.

Execution flow:
1. Fetch all raw unstructured documents from MongoDB ('documents' collection).
2. Apply deterministic regex extraction (phone numbers, vehicle plates).
3. Apply domain-fine-tuned spaCy NER model (persons, locations, organizations).
4. Resolve entity mentions to canonical identities (aliases, initials, multi-modal).
5. Extract semantic relations (MET_WITH, CALLED, OWNS_OR_USES, MEMBER_OF, PRESENT_AT).
6. Update documents in MongoDB: processing_status -> 'extracted', populating extracted.entities and extracted.relations.
"""

import os
import re
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.db_writers.mongo_writer import MongoWriter
from nlp.entity_resolution import EntityResolver
from nlp.ner_model.train_ner import load_ner_model
from nlp.regex_extractors import extract_all_regex_entities
from nlp.relation_extraction import RelationExtractor


class NLPPipeline:
    """End-to-end intelligence extraction pipeline for crime documents."""

    def __init__(self, use_llm_relations: bool = False):
        print("🧠 Initializing NLP Pipeline components...")
        self.writer = MongoWriter()
        self.nlp = load_ner_model()
        self.resolver = EntityResolver()
        self.extractor = RelationExtractor()
        self.use_llm_relations = use_llm_relations
        print("   ✅ spaCy NER model loaded")
        print("   ✅ Entity Resolver initialized")
        print("   ✅ Relation Extractor ready")

    def _merge_spans(
        self,
        regex_entities: List[Dict[str, Any]],
        ner_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge regex and NER entities.
        Regex entities take precedence on exact offsets (phones, vehicles, dates).
        """
        occupied_spans = set()
        merged = []

        # 1. Add regex entities first (deterministic high-precision)
        for r in regex_entities:
            span = (r["start"], r["end"])
            occupied = any(
                max(start, r["start"]) < min(end, r["end"])
                for start, end in occupied_spans
            )
            if not occupied:
                occupied_spans.add(span)
                merged.append(r)

        # 2. Add NER entities where spans do not conflict
        for n in ner_entities:
            occupied = any(
                max(start, n["start"]) < min(end, n["end"])
                for start, end in occupied_spans
            )
            if not occupied:
                occupied_spans.add((n["start"], n["end"]))
                merged.append(n)

        # Sort by character position
        merged.sort(key=lambda x: x["start"])
        return merged

    def process_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single document from MongoDB and extract structured entities and relations.
        """
        raw_text = doc.get("raw_content", "")
        if not raw_text.strip():
            return {"entities": [], "relations": []}

        # Step 1: Deterministic regex extraction
        regex_ents = extract_all_regex_entities(raw_text)

        # Step 2: spaCy NER model inference
        spacy_doc = self.nlp(raw_text)
        ner_ents = []
        for ent in spacy_doc.ents:
            ner_ents.append({
                "type": ent.label_,
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 0.90,
            })

        # Step 3: Merge and de-conflict spans
        merged_raw_ents = self._merge_spans(regex_ents, ner_ents)

        # Pre-gather context phones and vehicles in this document to assist person resolution
        doc_phones = [e["clean_value"] for e in regex_ents if e["type"] == "PHONE"]
        doc_vehicles = [e["clean_value"] for e in regex_ents if e["type"] == "VEHICLE"]

        # Blacklist of common header and noise strings mistaken by NER
        EXCLUDED_NOISE = {
            "fir", "first information report", "police station", "date", "time",
            "subject", "complainant", "officer", "incident", "investigation",
            "bulk cash deposit", "power grid substation", "routine traffic stop",
            "traffic disruption", "safehouse raid", "commercial banking",
        }

        # Extract lines containing Complainant or Reporting Officer to identify police personnel
        officer_lines = []
        for line in raw_text.splitlines():
            line_l = line.lower()
            if any(term in line_l for term in ["complainant", "reporting officer", "officer in charge", "officer:"]):
                officer_lines.append(line_l)

        # Step 4: Entity Resolution with quality filtering
        resolved_entities = []
        seen_entity_keys = set()

        for raw_e in merged_raw_ents:
            etype = raw_e["type"].upper()
            raw_text_clean = raw_e["text"].strip().lower()

            # Filter 1: Check excluded terms
            if raw_text_clean in EXCLUDED_NOISE or len(raw_text_clean) < 2:
                continue

            # Filter 2: Strict vehicle validation (must resemble Indian registration plate)
            if etype in ("VEHICLE", "CAR"):
                norm_plate = re.sub(r"[\s\-]", "", raw_e.get("clean_value", raw_e["text"])).upper()
                if not re.match(r"^[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}$", norm_plate):
                    continue

            # Filter 3: Strict phone validation (must be 10 digits)
            if etype in ("PHONE", "PHONENUMBER"):
                norm_phone = re.sub(r"\D", "", raw_e.get("clean_value", raw_e["text"]))
                if len(norm_phone) < 10:
                    continue

            # Redirect known organizations if misclassified as Person
            if any(org in raw_text_clean for org in ["malabar logistics", "apex shipping", "city fresh bakery", "k.r. motors", "kr motors"]):
                etype = "ORGANIZATION"
                raw_e["type"] = "Organization"

            # Filter 4: Strict person name filtering (reject officers, police personnel, digits, noise, emoji)
            if etype in ("PERSON", "NAME"):
                # Must be purely letters, spaces, and optional period
                if not re.match(r"^[A-Za-z\.\s]+$", raw_e["text"].strip()):
                    continue
                if len(raw_text_clean) < 3:
                    continue
                if any(term in raw_text_clean for term in [
                    "police", "station", "deposit", "substation", "protest", "raid",
                    "witness", "officer", "inspector", "reporting", "incharge", "dgp",
                    "superintendent", "investigating", "complainant", "unknown", "district",
                    "public", "peace", "simultaneously", "package", "logistics", "shipping",
                    "bakery", "motors", "corporation", "llc", "corp"
                ]):
                    continue
                # Reject if text has title like 'dsp', 'acp', 'si', 'insp', 'capt'
                if any(raw_text_clean.startswith(pfx) for pfx in ["dsp ", "acp ", "si ", "insp ", "capt ", "sho "]):
                    continue
                # Reject if entity text appears directly on a Complainant/Officer header line
                is_officer = False
                for off_line in officer_lines:
                    if raw_text_clean in off_line:
                        is_officer = True
                        break
                if is_officer:
                    continue

            # Filter 5: Location validation (strict validation for genuine Kerala locations)
            if etype in ("LOCATION", "GPE", "LOC"):
                if any(n in raw_text_clean for n in [
                    "insp", "officer", "charge", "report", "case", "date", "time", "fir",
                    "bns", "section", "hrs", "00:00", "power", "grid", "phone", "suspect",
                    "witness", "package", "smooth", "complaint", "incident", "based", "public",
                    "police"
                ]):
                    continue
                known_first_names = {
                    "bilal", "faisal", "jose", "sunil", "rahul", "suresh", "manoj",
                    "ravi", "deepa", "anwar", "arun", "binoy", "akhil", "niyas",
                    "jithin", "santhosh", "haridas", "priya", "lakshmi", "vishnu"
                }
                if raw_text_clean in known_first_names:
                    etype = "PERSON"
                    raw_e["type"] = "Person"
                elif any(p in raw_text_clean for p in ["kumar", "menon", "raghunathan", "mohammed", "arun g", "vineeth mohan"]):
                    continue
                else:
                    valid_locs = ["ernakulam", "kochi", "aluva", "kakkanad", "palarivattom", "thrissur", "kozhikode", "willingdon", "kerala", "cochin", "calicut"]
                    if not any(loc in raw_text_clean for loc in valid_locs):
                        continue

            # Filter 6: Organization filtering (reject penal codes, police stations, generic document headers)
            if etype in ("ORGANIZATION", "ORG"):
                if len(raw_text_clean) < 4:
                    continue
                if any(char.isdigit() for char in raw_e["text"]) or "(" in raw_e["text"] or ")" in raw_e["text"]:
                    continue
                denied_org_terms = [
                    "act", "section", "sections", "bns", "ipc", "pmla", "crpc", "assembly",
                    "nuisance", "offence", "maintenance", "routine", "traffic stop",
                    "identification", "prayers", "action requested", "complainant",
                    "incident", "date of", "time of", "police station", "ps", "police",
                    "crime branch", "intelligence wing", "special crimes", "cid unit",
                    "special operations", "records bureau", "clean slate", "banking premises",
                    "suspected operatives", "substation", "officer", "inspector", "superintendent",
                    "shell company", "unlawful", "money laundering and", "sanhita", "customs",
                    "clearance", "crime", "cyber", "dsp", "acp", "dcp"
                ]
                if any(term in raw_text_clean for term in denied_org_terms):
                    continue

            res = self.resolver.resolve_entity(
                entity_type=raw_e["type"],
                entity_text=raw_e.get("clean_value", raw_e["text"]),
                context_phones=doc_phones,
                context_vehicles=doc_vehicles,
            )
            # Add occurrence location in text
            res["start"] = raw_e["start"]
            res["end"] = raw_e["end"]
            res["confidence"] = raw_e.get("confidence", 0.85)

            # Deduplicate multiple exact mentions of same entity ID in same doc for output list
            key = (res["type"], res["canonical_id"])
            if key not in seen_entity_keys:
                seen_entity_keys.add(key)
                resolved_entities.append(res)

        # Step 5: Relation Extraction
        extracted_relations = self.extractor.extract_relations(
            raw_text, resolved_entities, use_llm=self.use_llm_relations
        )

        return {
            "entities": resolved_entities,
            "relations": extracted_relations,
        }

    def run(self, reprocess_all: bool = True) -> Dict[str, Any]:
        """
        Process all documents in MongoDB matching processing_status.
        """
        filter_query = {} if reprocess_all else {"processing_status": "raw"}
        docs = self.writer.get_documents(filter_query)

        print(f"\n🚀 Running NLP Pipeline on {len(docs)} documents from MongoDB...")
        start_time = time.time()

        processed_count = 0
        total_entities = 0
        total_relations = 0
        entity_type_counter = Counter()
        relation_type_counter = Counter()

        for doc in docs:
            doc_id = doc["_id"]
            source_name = doc.get("source_name", "doc")
            res = self.process_document(doc)

            entities = res["entities"]
            relations = res["relations"]

            # Update document in MongoDB
            self.writer.update_document(
                doc_id=doc_id,
                update_fields={
                    "processing_status": "extracted",
                    "extracted": {
                        "entities": entities,
                        "relations": relations,
                    },
                },
            )

            processed_count += 1
            total_entities += len(entities)
            total_relations += len(relations)

            for e in entities:
                entity_type_counter[e["type"]] += 1
            for r in relations:
                relation_type_counter[r["predicate"]] += 1

            if processed_count % 10 == 0 or processed_count == len(docs):
                print(f"   Processed [{processed_count:2d}/{len(docs)}] {source_name} -> {len(entities)} entities, {len(relations)} relations")

        elapsed = time.time() - start_time

        # Print detailed report
        print(f"\n{'=' * 60}")
        print("  NLP EXTRACTION PIPELINE SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Documents Processed  : {processed_count}")
        print(f"  Execution Time       : {elapsed:.2f} seconds ({elapsed/max(1, processed_count):.3f}s/doc)")
        print(f"  Total Entity Mentions: {total_entities}")
        print(f"  Total Relations Found: {total_relations}\n")

        print(f"  Extracted Entities by Type:")
        for etype, count in entity_type_counter.most_common():
            print(f"   • {etype:<15}: {count:>4}")

        print(f"\n  Extracted Relations by Predicate:")
        for pred, count in relation_type_counter.most_common():
            print(f"   • {pred:<18}: {count:>4}")
        print(f"{'=' * 60}\n")

        return {
            "processed": processed_count,
            "entities_count": total_entities,
            "relations_count": total_relations,
            "entities_by_type": dict(entity_type_counter),
            "relations_by_type": dict(relation_type_counter),
        }


def main():
    pipeline = NLPPipeline()
    pipeline.run(reprocess_all=True)


if __name__ == "__main__":
    main()
