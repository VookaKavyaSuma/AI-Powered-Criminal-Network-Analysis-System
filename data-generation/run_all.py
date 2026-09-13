"""
run_all.py — Run all data generation scripts in sequence.

Usage (from project root):
    python data-generation/run_all.py

This generates all synthetic data files into data-generation/output/.
Requires GROQ_API_KEY in .env for FIR and social media generation.
"""

import os
import subprocess
import sys
import time

# Directory where this script and the generators live
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Python executable (use the same one running this script)
PYTHON = sys.executable

GENERATORS = [
    ("Ground Truth Loader (validation)", "ground_truth.py", False),
    ("Criminal History Seed", "criminal_history_generator.py", True),
    ("Vehicle Registry Seed", "vehicle_registry_generator.py", True),
    ("CDR Records", "cdr_generator.py", True),
    ("Transactions", "transaction_generator.py", True),
    ("NER Labeled Data", "ner_labeling_generator.py", True),
    ("FIR Reports (Groq API)", "fir_generator.py", True),
    ("Social Media Posts (Groq API)", "social_media_generator.py", True),
]


def main():
    print("=" * 60)
    print("  Criminal Network Analysis — Data Generation Pipeline")
    print("=" * 60)
    print()

    # Validate ground truth first
    print("📋 Validating ground truth Excel files...")
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from ground_truth import ALL_ENTITIES, ALL_RELATIONSHIPS, ALL_EVENTS
        print(f"   ✅ Entities: {len(ALL_ENTITIES)}")
        print(f"   ✅ Relationships: {len(ALL_RELATIONSHIPS)}")
        print(f"   ✅ Events: {len(ALL_EVENTS)}")
        print()
    except Exception as e:
        print(f"   ❌ Ground truth validation failed: {e}")
        print("   Make sure Entities.xlsx, Relationships.xlsx, Events.xlsx exist in data-generation/")
        sys.exit(1)

    # Run each generator
    results = {}
    for name, script, should_run in GENERATORS:
        if not should_run:
            continue

        script_path = os.path.join(SCRIPT_DIR, script)
        if not os.path.exists(script_path):
            print(f"⚠️  Skipping {name}: {script} not found")
            results[name] = "SKIPPED"
            continue

        print(f"\n{'─' * 60}")
        print(f"🔄 Running: {name} ({script})")
        print(f"{'─' * 60}")

        start = time.time()
        result = subprocess.run(
            [PYTHON, script_path],
            cwd=PROJECT_ROOT,
            capture_output=False,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            print(f"   ✅ {name} completed in {elapsed:.1f}s")
            results[name] = "OK"
        else:
            print(f"   ❌ {name} FAILED (exit code {result.returncode})")
            results[name] = "FAILED"

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    for name, status in results.items():
        icon = "✅" if status == "OK" else "❌" if status == "FAILED" else "⚠️"
        print(f"   {icon} {name}: {status}")

    # List output files
    output_dir = os.path.join(SCRIPT_DIR, "output")
    print(f"\n📂 Files in data-generation/output/:")
    for root, dirs, files in os.walk(output_dir):
        rel_root = os.path.relpath(root, output_dir)
        for f in sorted(files):
            if f == ".gitkeep":
                continue
            if rel_root == ".":
                print(f"   📄 {f}")
            else:
                print(f"   📄 {rel_root}/{f}")

    failed = [n for n, s in results.items() if s == "FAILED"]
    if failed:
        print(f"\n⚠️  {len(failed)} generator(s) failed. Check output above for errors.")
        sys.exit(1)
    else:
        print(f"\n🎉 All generators completed successfully!")


if __name__ == "__main__":
    main()
