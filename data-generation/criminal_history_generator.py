"""
criminal_history_generator.py — Generate criminal history seed CSV from ground truth.

Usage: python data-generation/criminal_history_generator.py
Output: data-generation/output/criminal_history_seed.csv
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_GEN_DIR = os.path.join(PROJECT_ROOT, "data-generation")
OUTPUT_DIR = os.path.join(DATA_GEN_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def random_date(start_year: int = 1970, end_year: int = 2000) -> str:
    """Generate a random date of birth between start_year and end_year."""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def generate_aliases(name: str) -> str:
    """Generate 1-2 alternate name forms from a full name."""
    parts = str(name).strip().split()
    aliases = []
    if len(parts) > 1:
        first, last = parts[0], parts[-1]
        aliases.append(f"{first[0]}. {last}")  # R. Kumar
        aliases.append(first)  # Ravi
    elif len(parts) == 1:
        aliases.append(parts[0])
    return ", ".join(aliases)


def main():
    """Generate criminal history seed CSV."""
    print("📋 Generating criminal history records...")

    # Load ground truth
    entities_df = pd.read_excel(os.path.join(DATA_GEN_DIR, "Entities.xlsx"))
    relationships_df = pd.read_excel(os.path.join(DATA_GEN_DIR, "Relationships.xlsx"))

    # Filter to Person entities only
    persons = entities_df[entities_df["type"].str.lower() == "person"].copy()
    id_to_name = dict(zip(entities_df["entity_id"], entities_df["name"]))

    output_data = []
    for _, row in persons.iterrows():
        name = str(row.get("name", ""))
        entity_id = row.get("entity_id")
        role = str(row.get("role", "")).lower()
        address = str(row.get("address", ""))

        # Generate aliases
        aliases = generate_aliases(name)

        # Assign risk flag based on role
        if role in ["kingpin", "lieutenant"]:
            risk_flag = "HIGH"
        elif role in ["operative", "financier"]:
            risk_flag = "MEDIUM"
        else:
            risk_flag = "LOW"

        # Generate past criminal cases for non-noise entities
        past_cases = []
        if risk_flag != "LOW":
            num_cases = random.randint(0, 3)
            charges = [
                "NDPS Act Sec 22",
                "NDPS Act Sec 27A",
                "Extortion - IPC 384",
                "Money Laundering - PMLA",
                "Arms Act Sec 25",
                "Criminal Conspiracy - IPC 120B",
                "Attempt to Murder - IPC 307",
            ]
            statuses = ["convicted", "pending", "acquitted", "under trial"]
            for _ in range(num_cases):
                past_cases.append(
                    {
                        "case_id": f"CR/{random.randint(2015, 2023)}/{random.randint(1000, 9999)}",
                        "charge": random.choice(charges),
                        "status": random.choice(statuses),
                    }
                )
        past_cases_json = json.dumps(past_cases) if past_cases else "[]"

        # Find known associates from relationships
        # Relationships.xlsx columns: subject_id, predicate, object_id, notes
        associates = []
        if risk_flag != "LOW" and not relationships_df.empty:
            # Match on subject_id or object_id (the correct column names)
            related = relationships_df[
                (relationships_df["subject_id"] == entity_id)
                | (relationships_df["object_id"] == entity_id)
            ]
            for _, r in related.iterrows():
                other_id = (
                    r["object_id"]
                    if r["subject_id"] == entity_id
                    else r["subject_id"]
                )
                if other_id in id_to_name and other_id != entity_id:
                    associates.append(id_to_name[other_id])

            # Limit to 3 associates
            if len(associates) > 3:
                associates = random.sample(associates, 3)

        known_associates_str = ", ".join(associates) if associates else ""

        output_data.append(
            {
                "name": name,
                "aliases": aliases,
                "date_of_birth": random_date(),
                "known_address": address,
                "past_cases": past_cases_json,
                "known_associates": known_associates_str,
                "risk_flag": risk_flag,
            }
        )

    out_df = pd.DataFrame(output_data)
    out_path = os.path.join(OUTPUT_DIR, "criminal_history_seed.csv")
    out_df.to_csv(out_path, index=False)
    print(f"✅ Generated {len(out_df)} criminal history records in {out_path}")


if __name__ == "__main__":
    main()
