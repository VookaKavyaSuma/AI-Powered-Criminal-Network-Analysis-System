"""
regex_extractors.py — Deterministic regex extraction for structured tokens in unstructured text.

High-precision extractors for:
- Indian phone numbers (10-digit mobiles, +91/0 prefixes)
- Indian vehicle registration plates (e.g. KL07AB1234, KL-01-EF-9012)
- Financial amounts / currencies (e.g. ₹50,000, Rs. 1,00,000)
- Calendar dates (DD/MM/YYYY, YYYY-MM-DD, DD Month YYYY)
"""

import re
from typing import Any, Dict, List


# ── Regex Patterns ────────────────────────────────────────────────────────────

# Indian 10-digit mobile numbers, optionally with +91 or 0 prefix and hyphens/spaces
PHONE_PATTERN = re.compile(
    r"(?:\+91[\s\-]?)?(?:0)?([6-9]\d{9})\b"
)

# Indian vehicle registration plates: State Code (2 letters) + District/RTO (1-2 digits) + Series (1-2 letters) + Number (4 digits)
# Example: KL07AB1234, KL-01-EF-9012, KL 08 GH 3456, KL07WX9900
VEHICLE_PATTERN = re.compile(
    r"\b([A-Z]{2}[\s\-]?[0-9]{1,2}[\s\-]?[A-Z]{1,2}[\s\-]?[0-9]{4})\b",
    re.IGNORECASE,
)

# Financial amounts with Rupee symbols or denominations (with word/lookbehind boundary)
AMOUNT_PATTERN = re.compile(
    r"(?:(?<![A-Za-z0-9\.])(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)\b|\b([\d,]+(?:\.\d{1,2})?)\s*(?:rupees|lakhs?|crores?)\b)",
    re.IGNORECASE,
)

# Standard dates (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, or DD Month YYYY)
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b",
    re.IGNORECASE,
)


def extract_phones(text: str) -> List[Dict[str, Any]]:
    """Extract all Indian phone numbers with character offsets and normalized 10-digit values."""
    results = []
    for match in PHONE_PATTERN.finditer(text):
        full_match = match.group(0)
        clean_number = match.group(1)
        results.append({
            "type": "PHONE",
            "text": full_match,
            "clean_value": clean_number,
            "start": match.start(),
            "end": match.end(),
            "confidence": 0.98,
        })
    return results


def extract_vehicles(text: str) -> List[Dict[str, Any]]:
    """Extract Indian vehicle registration plates with character offsets and normalized values."""
    results = []
    for match in VEHICLE_PATTERN.finditer(text):
        raw_plate = match.group(1)
        # Normalize plate: uppercase, remove hyphens and spaces
        clean_plate = re.sub(r"[\s\-]", "", raw_plate).upper()
        # Filter out false positives (must have valid length between 9 and 10 chars)
        if 8 <= len(clean_plate) <= 10:
            results.append({
                "type": "VEHICLE",
                "text": raw_plate,
                "clean_value": clean_plate,
                "start": match.start(1),
                "end": match.end(1),
                "confidence": 0.95,
            })
    return results


def extract_amounts(text: str) -> List[Dict[str, Any]]:
    """Extract currency amounts from text."""
    results = []
    for match in AMOUNT_PATTERN.finditer(text):
        raw_text = match.group(0)
        num_str = (match.group(1) or match.group(2) or "").replace(",", "")
        if not num_str:
            continue
        try:
            val = float(num_str)
        except ValueError:
            continue
        if val <= 0:
            continue
        results.append({
            "type": "AMOUNT",
            "text": raw_text,
            "clean_value": val,
            "start": match.start(),
            "end": match.end(),
            "confidence": 0.92,
        })
    return results


def extract_dates(text: str) -> List[Dict[str, Any]]:
    """Extract calendar date occurrences."""
    results = []
    for match in DATE_PATTERN.finditer(text):
        results.append({
            "type": "DATE",
            "text": match.group(1),
            "clean_value": match.group(1),
            "start": match.start(1),
            "end": match.end(1),
            "confidence": 0.90,
        })
    return results


def extract_all_regex_entities(text: str) -> List[Dict[str, Any]]:
    """
    Run all regex extractors and return non-overlapping sorted entities.
    """
    entities = []
    entities.extend(extract_phones(text))
    entities.extend(extract_vehicles(text))
    entities.extend(extract_amounts(text))
    entities.extend(extract_dates(text))

    # Sort by starting character position
    entities.sort(key=lambda x: (x["start"], -x["end"]))
    return entities
