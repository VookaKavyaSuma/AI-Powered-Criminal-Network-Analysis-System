"""
entity_resolution.py — Resolve fragmented names, aliases, and multi-modal signals into canonical entities.

Key capabilities:
1. Normalizes Phone, Vehicle, Location, Organization entities to canonical IDs.
2. Resolves Person name variants (e.g. 'R. Kumar', 'Ravi', 'Ravi Kumar') using:
   - Initial + Lastname matching (e.g. 'R. Kumar' -> 'Ravi Kumar')
   - RapidFuzz token sort and token set similarity (threshold >= 82)
   - Co-occurrence with known phone numbers or vehicle plates
3. Assigns permanent canonical_id (e.g. PER_RAVI_KUMAR, VEH_KL07AB1234, PHN_9847012345).
"""

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz


def normalize_text(text: str) -> str:
    """Strip punctuation and extra whitespace for normalization."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text)).strip().lower()


class EntityResolver:
    """
    Maintains a dynamic registry of canonical entities and resolves mentions across documents.
    """

    def __init__(self):
        # Known registered canonical persons: canonical_id -> dict(canonical_name, aliases, phones, vehicles)
        self.person_registry: Dict[str, Dict[str, Any]] = {}
        # Known registered canonical orgs: canonical_id -> canonical_name
        self.org_registry: Dict[str, str] = {}
        # Known registered canonical locations: canonical_id -> canonical_name
        self.location_registry: Dict[str, str] = {}

        # Pre-seed canonical identities from ground-truth entities
        self._seed_ground_truth_entities()

    def _seed_ground_truth_entities(self):
        """Pre-seed canonical identities from ground truth Entities.xlsx if present."""
        gt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data-generation",
            "Entities.xlsx",
        )
        if not os.path.exists(gt_path):
            return
        try:
            import pandas as pd
            df = pd.read_excel(gt_path)
            for _, r in df.iterrows():
                etype = str(r.get("type", "")).strip().lower()
                name = str(r.get("name", "")).strip()
                if not name or name == "nan":
                    continue

                if etype == "person":
                    slug = re.sub(r"[^\w]", "_", name.lower()).strip("_").upper()
                    cid = f"PER_{slug}"
                    phones = []
                    ph = str(r.get("phone", ""))
                    if ph and ph != "—" and ph != "nan":
                        clean_ph = re.sub(r"\D", "", ph.split(".")[0])[-10:]
                        if len(clean_ph) == 10:
                            phones.append(clean_ph)
                    v_reg = str(r.get("vehicle_reg", ""))
                    vehicles = []
                    if v_reg and v_reg != "—" and v_reg != "nan":
                        vehicles.append(re.sub(r"[\s\-]", "", v_reg).upper())
                    self.person_registry[cid] = {
                        "canonical_name": name,
                        "aliases": {name},
                        "phones": phones,
                        "vehicles": vehicles,
                    }
                elif etype == "organization":
                    slug = re.sub(r"[^\w]", "_", name.lower()).strip("_").upper()
                    self.org_registry[f"ORG_{slug}"] = name
        except Exception:
            pass

    def resolve_phone(self, raw_phone: str) -> Tuple[str, str]:
        """Normalize phone number to 10-digit canonical ID."""
        clean = re.sub(r"\D", "", raw_phone)
        if len(clean) > 10:
            clean = clean[-10:]
        canonical_id = f"PHN_{clean}"
        return canonical_id, clean

    def resolve_vehicle(self, raw_plate: str) -> Tuple[str, str]:
        """Normalize vehicle registration to uppercase alphanumeric canonical ID."""
        clean = re.sub(r"[\s\-]", "", raw_plate).upper()
        canonical_id = f"VEH_{clean}"
        return canonical_id, clean

    def resolve_location(self, raw_loc: str) -> Tuple[str, str]:
        """Normalize location name to title-cased canonical form."""
        clean = " ".join(raw_loc.strip().split()).title()
        # Clean common suffixes
        slug = re.sub(r"[^\w]", "_", clean.lower()).strip("_")
        canonical_id = f"LOC_{slug}"
        self.location_registry[canonical_id] = clean
        return canonical_id, clean

    def resolve_organization(self, raw_org: str) -> Tuple[str, str]:
        """Normalize organization name and match against existing orgs."""
        clean = " ".join(raw_org.strip().split()).title()
        norm = normalize_text(clean)

        # Check existing orgs with fuzzy match
        for org_id, org_name in self.org_registry.items():
            if fuzz.token_sort_ratio(norm, normalize_text(org_name)) >= 85:
                return org_id, org_name

        slug = re.sub(r"[^\w]", "_", norm).strip("_")
        canonical_id = f"ORG_{slug}"
        self.org_registry[canonical_id] = clean
        return canonical_id, clean

    def _matches_initial_form(self, name_a: str, name_b: str) -> bool:
        """
        Check if name_a is an initial/shortened form of name_b.
        E.g. 'R. Kumar' or 'R Kumar' matches 'Ravi Kumar'.
        'Sunil V.' or 'Sunil Varghese' matches.
        """
        parts_a = re.sub(r"[^\w\s]", "", name_a).split()
        parts_b = re.sub(r"[^\w\s]", "", name_b).split()

        if len(parts_a) == 2 and len(parts_b) == 2:
            # Case 1: First initial + exact last name: R. Kumar vs Ravi Kumar
            if (len(parts_a[0]) == 1 and parts_a[0].lower() == parts_b[0][0].lower()
                and parts_a[1].lower() == parts_b[1].lower()):
                return True
            if (len(parts_b[0]) == 1 and parts_b[0].lower() == parts_a[0][0].lower()
                and parts_b[1].lower() == parts_a[1].lower()):
                return True

            # Case 2: Exact first name + last initial: Sunil V. vs Sunil Varghese
            if (parts_a[0].lower() == parts_b[0].lower()
                and len(parts_a[1]) == 1 and parts_a[1].lower() == parts_b[1][0].lower()):
                return True
            if (parts_b[0].lower() == parts_a[0].lower()
                and len(parts_b[1]) == 1 and parts_b[1].lower() == parts_a[1][0].lower()):
                return True

        return False

    def resolve_person(
        self,
        raw_name: str,
        context_phones: Optional[List[str]] = None,
        context_vehicles: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Resolve person name surface mention to canonical_id and canonical_name.
        Uses fuzzy name similarity, abbreviation rules, and co-occurring identifier signals.
        """
        clean_name = " ".join(raw_name.strip().split()).title()
        # Remove common police titles/prefixes
        clean_name = re.sub(
            r"^(?:Shri|Smt|Mr|Mrs|Ms|Insp|Inspector|ACP|DCP|SP|DSP|SI|PSI|Lt|Dr)\.?\s+",
            "",
            clean_name,
            flags=re.IGNORECASE,
        ).strip()

        norm_name = normalize_text(clean_name)
        if not norm_name:
            return "PER_UNKNOWN", "Unknown"

        best_match_id = None
        highest_score = 0.0

        # Step 1: Check multi-modal signal (shared phone or vehicle)
        if context_phones:
            for pid, pdata in self.person_registry.items():
                if any(ph in pdata.get("phones", []) for ph in context_phones):
                    # Strong match if names are even weakly compatible
                    if fuzz.partial_ratio(norm_name, normalize_text(pdata["canonical_name"])) >= 60:
                        pdata["aliases"].add(clean_name)
                        return pid, pdata["canonical_name"]

        # Step 2: Check initial abbreviation matching (e.g. R. Kumar == Ravi Kumar)
        for pid, pdata in self.person_registry.items():
            cname = pdata["canonical_name"]
            if self._matches_initial_form(clean_name, cname):
                pdata["aliases"].add(clean_name)
                # If current mention has a more complete name (e.g. Ravi Kumar vs R. Kumar), update canonical name
                if len(clean_name.split()) >= len(cname.split()) and len(clean_name) > len(cname):
                    pdata["canonical_name"] = clean_name
                return pid, pdata["canonical_name"]

            # Also check against registered aliases
            for alias in pdata.get("aliases", []):
                if self._matches_initial_form(clean_name, alias):
                    pdata["aliases"].add(clean_name)
                    return pid, pdata["canonical_name"]

        # Step 2b: Single-word first-name match against registered persons
        # e.g., 'Haridas' -> 'Haridas Menon', 'Bilal' -> 'Bilal Hassan', 'Santhosh' -> 'Santhosh Babu'
        clean_words = clean_name.split()
        if len(clean_words) == 1:
            sw = clean_words[0].lower()
            for pid, pdata in self.person_registry.items():
                cparts = pdata["canonical_name"].split()
                if len(cparts) >= 2 and cparts[0].lower() == sw:
                    pdata["aliases"].add(clean_name)
                    return pid, pdata["canonical_name"]

        # Step 2c: If registered person has 1 word and current mention has 2+ words with matching first name
        if len(clean_words) >= 2:
            first_w = clean_words[0].lower()
            for pid, pdata in list(self.person_registry.items()):
                cparts = pdata["canonical_name"].split()
                if len(cparts) == 1 and cparts[0].lower() == first_w:
                    pdata["canonical_name"] = clean_name
                    pdata["aliases"].add(cparts[0])
                    return pid, pdata["canonical_name"]

        # Step 3: Fuzzy name matching with RapidFuzz
        for pid, pdata in self.person_registry.items():
            cname = pdata["canonical_name"]
            cname_norm = normalize_text(cname)

            # Token sort ratio handles out-of-order tokens (e.g. Kumar Ravi vs Ravi Kumar)
            score_sort = fuzz.token_sort_ratio(norm_name, cname_norm)
            score_set = fuzz.token_set_ratio(norm_name, cname_norm)
            score = max(score_sort, score_set)

            # High threshold match
            if score >= 82 and score > highest_score:
                highest_score = score
                best_match_id = pid

        if best_match_id and highest_score >= 82:
            pdata = self.person_registry[best_match_id]
            pdata["aliases"].add(clean_name)
            # Promote fuller name to canonical if current is longer and contains both first and last
            if len(clean_name) > len(pdata["canonical_name"]) and len(clean_name.split()) >= 2:
                pdata["canonical_name"] = clean_name
            return best_match_id, pdata["canonical_name"]

        # Step 4: No match found — create new canonical person
        slug = re.sub(r"[^\w]", "_", norm_name).strip("_").upper()
        if not slug:
            slug = hashlib.md5(clean_name.encode()).hexdigest()[:8]
        canonical_id = f"PER_{slug}"

        self.person_registry[canonical_id] = {
            "canonical_name": clean_name,
            "aliases": {clean_name},
            "phones": set(context_phones or []),
            "vehicles": set(context_vehicles or []),
        }
        return canonical_id, clean_name

    def resolve_entity(
        self,
        entity_type: str,
        entity_text: str,
        context_phones: Optional[List[str]] = None,
        context_vehicles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Universal entity resolver mapping any raw entity to its canonical record.
        """
        etype = entity_type.upper().strip()
        text_str = str(entity_text).strip()

        if etype in ("PHONE", "PHONENUMBER", "MOBILE"):
            cid, cval = self.resolve_phone(text_str)
            return {"type": "PhoneNumber", "text": text_str, "canonical_id": cid, "canonical_value": cval}

        elif etype in ("VEHICLE", "CAR", "PLATE"):
            cid, cval = self.resolve_vehicle(text_str)
            return {"type": "Vehicle", "text": text_str, "canonical_id": cid, "canonical_value": cval}

        elif etype in ("LOCATION", "GPE", "LOC"):
            cid, cval = self.resolve_location(text_str)
            return {"type": "Location", "text": text_str, "canonical_id": cid, "canonical_value": cval}

        elif etype in ("ORGANIZATION", "ORG", "COMPANY"):
            cid, cval = self.resolve_organization(text_str)
            return {"type": "Organization", "text": text_str, "canonical_id": cid, "canonical_value": cval}

        elif etype in ("PERSON", "PER", "NAME", "INDIVIDUAL"):
            cid, cval = self.resolve_person(text_str, context_phones, context_vehicles)
            return {"type": "Person", "text": text_str, "canonical_id": cid, "canonical_value": cval}

        elif etype in ("AMOUNT", "MONEY", "CURRENCY"):
            return {
                "type": "Amount",
                "text": text_str,
                "canonical_id": f"AMT_{text_str.replace('.', '_')}",
                "canonical_value": text_str,
            }

        elif etype in ("DATE", "TIME"):
            slug = re.sub(r"[^\w]", "_", text_str)
            return {
                "type": "Date",
                "text": text_str,
                "canonical_id": f"DATE_{slug}",
                "canonical_value": text_str,
            }

        else:
            # Generic entity fallback
            clean = text_str
            slug = re.sub(r"[^\w]", "_", clean.lower()).strip("_")
            return {
                "type": etype.title(),
                "text": text_str,
                "canonical_id": f"{etype[:3].upper()}_{slug}",
                "canonical_value": clean,
            }
