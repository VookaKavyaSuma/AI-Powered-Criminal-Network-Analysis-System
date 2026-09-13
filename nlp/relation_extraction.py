"""
relation_extraction.py — Extract semantic relations between resolved entities.

Implements a hybrid extraction strategy:
1. Rule-based linguistic patterns (dependency & keyword cues) for core relation types.
2. LLM-assisted extraction via Groq API (qwen/qwen3.8-27b) with structured JSON prompting.
3. Offline fallback to guarantee 100% reliability even without internet connection.

Ontology Predicates:
- MET_WITH             (Person -> Person)
- CALLED               (Person -> Person | Person -> PhoneNumber)
- OWNS_OR_USES         (Person -> Vehicle | Person -> PhoneNumber)
- MEMBER_OF            (Person -> Organization)
- PRESENT_AT           (Person -> Event | Person -> Location)
- RESIDES_AT           (Person -> Location)
- ASSOCIATED_WITH      (Person -> Person)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

VALID_PREDICATES = {
    "MET_WITH",
    "CALLED",
    "OWNS_OR_USES",
    "MEMBER_OF",
    "PRESENT_AT",
    "RESIDES_AT",
    "ASSOCIATED_WITH",
}

# ── Linguistic Trigger Patterns ───────────────────────────────────────────────

MET_PATTERNS = re.compile(
    r"\b(met\s+with|meeting\s+between|conferred\s+with|interacted\s+with|assembly\s+with|discussing\s+with|planning\s+meeting)\b",
    re.IGNORECASE,
)

CALL_PATTERNS = re.compile(
    r"\b(called|telephoned|contacted|dialed|communicating\s+with|phone\s+tap|call\s+to|short-message|sms)\b",
    re.IGNORECASE,
)

VEHICLE_PATTERNS = re.compile(
    r"\b(driving|vehicle\s+registered|spotted\s+in|alighted\s+from|bearing\s+registration|operating\s+the\s+vehicle|sedan\s+with|suv|impounded|registration\s+number)\b",
    re.IGNORECASE,
)

PHONE_OWNERSHIP_PATTERNS = re.compile(
    r"\b(contact\s+number|mobile\s+number|phone\s+number|possession\s+of\s+a\s+mobile|reachable\s+at|using\s+the\s+number)\b",
    re.IGNORECASE,
)

MEMBER_PATTERNS = re.compile(
    r"\b(manages|working\s+under|associated\s+with|shell\s+organization|vendor\s+for|firm|logistics\s+for|member\s+of|head\s+of)\b",
    re.IGNORECASE,
)

LOCATION_PATTERNS = re.compile(
    r"\b(located\s+in|spotted\s+at|residing\s+at|near|at|premises\s+in|arrived\s+at|junction|patrol\s+near)\b",
    re.IGNORECASE,
)


class RelationExtractor:
    """
    Extracts structured relationships between entities found in text.
    """

    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.client = None
        if self.groq_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.groq_key)
            except Exception as e:
                print(f"Warning: Could not initialize Groq client for relation extraction: {e}")

    def extract_rule_based(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships based on co-occurrence and linguistic cue keywords.
        """
        relations = []
        seen_keys: Set[Tuple[str, str, str]] = set()

        # Group entities by category
        persons = [e for e in entities if e["type"] == "Person"]
        phones = [e for e in entities if e["type"] == "PhoneNumber"]
        vehicles = [e for e in entities if e["type"] == "Vehicle"]
        orgs = [e for e in entities if e["type"] == "Organization"]
        locations = [e for e in entities if e["type"] == "Location"]

        # Split text into sentences for local context
        sentences = [s.strip() for s in re.split(r"[.\n]+", text) if s.strip()]

        for sent in sentences:
            sent_persons = [p for p in persons if p["text"].lower() in sent.lower() or p.get("canonical_value", "").lower() in sent.lower()]
            sent_phones = [ph for ph in phones if ph["text"] in sent or ph.get("canonical_value", "") in sent]
            sent_vehicles = [v for v in vehicles if v["text"] in sent or v.get("canonical_value", "") in sent]
            sent_orgs = [o for o in orgs if o["text"].lower() in sent.lower() or o.get("canonical_value", "").lower() in sent.lower()]
            sent_locs = [l for l in locations if l["text"].lower() in sent.lower() or l.get("canonical_value", "").lower() in sent.lower()]

            # 1. Person <-> Person (MET_WITH, CALLED, ASSOCIATED_WITH)
            if len(sent_persons) >= 2:
                for i in range(len(sent_persons)):
                    for j in range(i + 1, len(sent_persons)):
                        p1 = sent_persons[i]
                        p2 = sent_persons[j]
                        if p1["canonical_id"] == p2["canonical_id"]:
                            continue

                        predicate = "ASSOCIATED_WITH"
                        conf = 0.70

                        if MET_PATTERNS.search(sent):
                            predicate = "MET_WITH"
                            conf = 0.88
                        elif CALL_PATTERNS.search(sent):
                            predicate = "CALLED"
                            conf = 0.85

                        key = (p1["canonical_id"], predicate, p2["canonical_id"])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            relations.append({
                                "subject": p1["canonical_id"],
                                "subject_name": p1.get("canonical_value", p1["text"]),
                                "predicate": predicate,
                                "object": p2["canonical_id"],
                                "object_name": p2.get("canonical_value", p2["text"]),
                                "confidence": conf,
                                "source": "rules",
                            })

            # 2. Person -> Vehicle (OWNS_OR_USES)
            if sent_persons and sent_vehicles:
                for p in sent_persons:
                    for v in sent_vehicles:
                        conf = 0.90 if VEHICLE_PATTERNS.search(sent) else 0.75
                        key = (p["canonical_id"], "OWNS_OR_USES", v["canonical_id"])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            relations.append({
                                "subject": p["canonical_id"],
                                "subject_name": p.get("canonical_value", p["text"]),
                                "predicate": "OWNS_OR_USES",
                                "object": v["canonical_id"],
                                "object_name": v.get("canonical_value", v["text"]),
                                "confidence": conf,
                                "source": "rules",
                            })

            # 3. Person -> PhoneNumber (OWNS_OR_USES / CALLED)
            if sent_persons and sent_phones:
                for p in sent_persons:
                    for ph in sent_phones:
                        pred = "CALLED" if CALL_PATTERNS.search(sent) else "OWNS_OR_USES"
                        conf = 0.88 if PHONE_OWNERSHIP_PATTERNS.search(sent) else 0.80
                        key = (p["canonical_id"], pred, ph["canonical_id"])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            relations.append({
                                "subject": p["canonical_id"],
                                "subject_name": p.get("canonical_value", p["text"]),
                                "predicate": pred,
                                "object": ph["canonical_id"],
                                "object_name": ph.get("canonical_value", ph["text"]),
                                "confidence": conf,
                                "source": "rules",
                            })

            # 4. Person -> Organization (MEMBER_OF)
            if sent_persons and sent_orgs:
                for p in sent_persons:
                    for o in sent_orgs:
                        key = (p["canonical_id"], "MEMBER_OF", o["canonical_id"])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            relations.append({
                                "subject": p["canonical_id"],
                                "subject_name": p.get("canonical_value", p["text"]),
                                "predicate": "MEMBER_OF",
                                "object": o["canonical_id"],
                                "object_name": o.get("canonical_value", o["text"]),
                                "confidence": 0.85,
                                "source": "rules",
                            })

            # 5. Person -> Location (PRESENT_AT / RESIDES_AT)
            if sent_persons and sent_locs:
                for p in sent_persons:
                    for loc in sent_locs:
                        pred = "RESIDES_AT" if "residing" in sent.lower() or "address" in sent.lower() else "PRESENT_AT"
                        key = (p["canonical_id"], pred, loc["canonical_id"])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            relations.append({
                                "subject": p["canonical_id"],
                                "subject_name": p.get("canonical_value", p["text"]),
                                "predicate": pred,
                                "object": loc["canonical_id"],
                                "object_name": loc.get("canonical_value", loc["text"]),
                                "confidence": 0.80,
                                "source": "rules",
                            })

        return relations

    def extract_with_llm(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Use Groq API to extract subtle or non-local relationships.
        Falls back automatically if anything fails.
        """
        if not self.client:
            return []

        entity_summary = [
            f"- {e.get('canonical_id')}: {e.get('canonical_value', e['text'])} ({e['type']})"
            for e in entities
        ]
        if not entity_summary:
            return []

        prompt = f"""You are a criminal intelligence analyst. Extract semantic relationships between the provided entities from the incident report.

ALLOWED PREDICATES ONLY:
- MET_WITH (Person -> Person)
- CALLED (Person -> Person or Person -> PhoneNumber)
- OWNS_OR_USES (Person -> Vehicle or Person -> PhoneNumber)
- MEMBER_OF (Person -> Organization)
- PRESENT_AT (Person -> Location)
- ASSOCIATED_WITH (Person -> Person)

ENTITIES:
{chr(10).join(entity_summary[:25])}

INCIDENT TEXT:
{text[:1500]}

Return a JSON array of extracted relations using the exact canonical_ids listed above.
Example format:
[
  {{"subject": "PER_RAVI_KUMAR", "predicate": "MET_WITH", "object": "PER_SURESH_NAIR", "confidence": 0.90}}
]
Return ONLY valid JSON array with no other text or explanation.
"""

        try:
            response = self.client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            raw_json = response.choices[0].message.content.strip()
            # Clean markdown code block wraps if present
            if raw_json.startswith("```"):
                raw_json = re.sub(r"^```(?:json)?", "", raw_json).strip("`").strip()

            parsed = json.loads(raw_json)
            valid_relations = []
            id_set = {e["canonical_id"] for e in entities}

            if isinstance(parsed, list):
                for item in parsed:
                    subj = item.get("subject")
                    pred = item.get("predicate", "").upper()
                    obj = item.get("object")
                    if subj in id_set and obj in id_set and pred in VALID_PREDICATES and subj != obj:
                        valid_relations.append({
                            "subject": subj,
                            "predicate": pred,
                            "object": obj,
                            "confidence": float(item.get("confidence", 0.85)),
                            "source": "groq_llm",
                        })
            return valid_relations
        except Exception as e:
            # Silent fallback to rules
            return []

    def extract_relations(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        use_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Extract relations from text with deduplication and confidence scoring.
        """
        rule_relations = self.extract_rule_based(text, entities)

        if use_llm and self.client:
            llm_relations = self.extract_with_llm(text, entities)
            # Merge with deduplication (LLM updates or adds relations)
            merged = { (r["subject"], r["predicate"], r["object"]): r for r in rule_relations }
            for r in llm_relations:
                key = (r["subject"], r["predicate"], r["object"])
                merged[key] = r
            return list(merged.values())

        return rule_relations
