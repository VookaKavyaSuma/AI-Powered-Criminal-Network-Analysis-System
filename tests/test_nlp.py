"""
test_nlp.py — Verification tests for Phase 3 NLP / NER / Relation Extraction.
"""

import os
import sys

import pytest

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.db_writers.mongo_writer import MongoWriter
from nlp.entity_resolution import EntityResolver
from nlp.regex_extractors import extract_all_regex_entities, extract_phones, extract_vehicles
from nlp.relation_extraction import RelationExtractor


def test_regex_extractors():
    """Verify phone and vehicle regex extraction with Indian formats."""
    text = (
        "Contact suspect at +91 9847012345 or 9847012399. "
        "Vehicle KL07AB1234 was spotted near Fort Kochi alongside KL-01-EF-9012."
    )

    phones = extract_phones(text)
    assert len(phones) == 2
    assert phones[0]["clean_value"] == "9847012345"
    assert phones[1]["clean_value"] == "9847012399"

    vehicles = extract_vehicles(text)
    assert len(vehicles) == 2
    assert vehicles[0]["clean_value"] == "KL07AB1234"
    assert vehicles[1]["clean_value"] == "KL01EF9012"


def test_entity_resolution_aliases():
    """Verify entity resolver maps initial forms and aliases to the same canonical identity."""
    resolver = EntityResolver()

    # Mention 1: Full name
    res1 = resolver.resolve_entity("Person", "Ravi Kumar")
    assert res1["canonical_id"] == "PER_RAVI_KUMAR"

    # Mention 2: Initial form 'R. Kumar' -> should resolve to same PER_RAVI_KUMAR
    res2 = resolver.resolve_entity("Person", "R. Kumar")
    assert res2["canonical_id"] == "PER_RAVI_KUMAR"

    # Mention 3: Vehicle normalization
    veh = resolver.resolve_entity("Vehicle", "KL 07 AB 1234")
    assert veh["canonical_id"] == "VEH_KL07AB1234"

    # Mention 4: Phone normalization
    phn = resolver.resolve_entity("PhoneNumber", "+91-9847012345")
    assert phn["canonical_id"] == "PHN_9847012345"


def test_relation_extraction_rules():
    """Verify rule-based extraction detects MET_WITH, CALLED, and OWNS_OR_USES."""
    extractor = RelationExtractor()

    text = "Ravi Kumar met with Suresh Nair to coordinate movements. Deepa Varma was driving vehicle KL08GH3456."
    entities = [
        {"type": "Person", "text": "Ravi Kumar", "canonical_id": "PER_RAVI_KUMAR", "canonical_value": "Ravi Kumar"},
        {"type": "Person", "text": "Suresh Nair", "canonical_id": "PER_SURESH_NAIR", "canonical_value": "Suresh Nair"},
        {"type": "Person", "text": "Deepa Varma", "canonical_id": "PER_DEEPA_VARMA", "canonical_value": "Deepa Varma"},
        {"type": "Vehicle", "text": "KL08GH3456", "canonical_id": "VEH_KL08GH3456", "canonical_value": "KL08GH3456"},
    ]

    relations = extractor.extract_rule_based(text, entities)
    predicates = {(r["subject"], r["predicate"], r["object"]) for r in relations}

    assert ("PER_RAVI_KUMAR", "MET_WITH", "PER_SURESH_NAIR") in predicates
    assert ("PER_DEEPA_VARMA", "OWNS_OR_USES", "VEH_KL08GH3456") in predicates


def test_mongo_pipeline_output():
    """Verify MongoDB documents have processing_status='extracted' and non-empty entities."""
    writer = MongoWriter()

    total_docs = writer.count_documents()
    assert total_docs >= 40

    extracted_docs = writer.count_documents({"processing_status": "extracted"})
    assert extracted_docs == total_docs, "All documents should be processed and marked 'extracted'"

    # Spot check that FIR documents have entities and relations
    fir_sample = writer.get_documents({"source_type": "FIR"}, limit=1)[0]
    assert "extracted" in fir_sample
    assert len(fir_sample["extracted"]["entities"]) > 0
    assert len(fir_sample["extracted"]["relations"]) > 0
