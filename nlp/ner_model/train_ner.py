"""
train_ner.py — Train and evaluate a domain-adapted spaCy NER model.

Trains on labeled dataset to extract:
- PERSON (e.g. Ravi Kumar, Suresh Nair)
- LOCATION (e.g. Fort Kochi, Ernakulam, Aluva, Thrissur)
- ORGANIZATION (e.g. Malabar Logistics LLC, Apex Shipping Corp)
- VEHICLE (e.g. KL07AB1234)
- PHONE (e.g. 9847012345)

Saves trained model to nlp/ner_model/model/ and documents Precision, Recall, and F1.
"""

import json
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

import spacy
from spacy.scorer import Scorer
from spacy.training import Example
from spacy.util import minibatch, compounding

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(MODULE_DIR, "model")
DATA_PATH = os.path.join(MODULE_DIR, "labeled_data", "ner_training.jsonl")


def load_dataset(file_path: str) -> List[Tuple[str, Dict]]:
    """Load jsonl labeled data into spaCy training format."""
    if not os.path.exists(file_path):
        # Fallback to data-generation output if not in labeled_data
        fallback = os.path.join(PROJECT_ROOT, "data-generation", "output", "labeled_ner_data", "ner_training.jsonl")
        if os.path.exists(fallback):
            file_path = fallback
        else:
            raise FileNotFoundError(f"Training data not found at {file_path}")

    dataset = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            text = item["text"]
            raw_entities = item.get("entities", [])
            # Format: (start, end, label)
            entities = [(int(e[0]), int(e[1]), str(e[2])) for e in raw_entities]
            dataset.append((text, {"entities": entities}))
    return dataset


def train_spacy_ner(
    train_data: List[Tuple[str, Dict]],
    test_data: List[Tuple[str, Dict]],
    output_dir: str = MODEL_DIR,
    n_iter: int = 25,
) -> Dict[str, Any]:
    """Train spaCy NER pipeline on provided training data and evaluate on test set."""
    print(f"🧠 Initializing base NLP model (en_core_web_sm)...")
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        print("   Notice: en_core_web_sm not found, initializing blank English model.")
        nlp = spacy.blank("en")

    # Add or get NER pipeline component
    if "ner" not in nlp.pipe_names:
        ner = nlp.add_pipe("ner", last=True)
    else:
        ner = nlp.get_pipe("ner")

    # Register labels
    for _, annotations in train_data:
        for ent in annotations.get("entities"):
            ner.add_label(ent[2])

    # Convert training data to Example objects, filtering misaligned entities
    train_examples = []
    for text, annotations in train_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        train_examples.append(example)

    test_examples = []
    for text, annotations in test_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        test_examples.append(example)

    print(f"🏋️ Training NER model across {n_iter} iterations ({len(train_examples)} train, {len(test_examples)} test)...")

    # Only train NER, disable other pipes during training
    other_pipes = [pipe for pipe in nlp.pipe_names if pipe != "ner"]
    with nlp.disable_pipes(*other_pipes):
        optimizer = nlp.resume_training()
        for it in range(1, n_iter + 1):
            random.shuffle(train_examples)
            losses = {}
            batches = minibatch(train_examples, size=compounding(4.0, 32.0, 1.001))
            for batch in batches:
                nlp.update(batch, drop=0.2, losses=losses, sgd=optimizer)

            if it % 5 == 0 or it == n_iter:
                print(f"   Epoch {it:2d}/{n_iter} - Loss: {losses.get('ner', 0.0):.4f}")

    # Evaluate on held-out test data
    print("\n📊 Evaluating model on held-out test set...")
    scorer = Scorer()
    evaluated_examples = []
    for example in test_examples:
        pred_doc = nlp(example.text)
        evaluated_examples.append(Example(pred_doc, example.reference))

    scores = scorer.score(evaluated_examples)
    ents_f = scores.get("ents_f", 0.0)
    ents_p = scores.get("ents_p", 0.0)
    ents_r = scores.get("ents_r", 0.0)
    ents_per_type = scores.get("ents_per_type", {})

    print(f"\n============================================================")
    print(f"  NER MODEL EVALUATION METRICS")
    print(f"============================================================")
    print(f"  Overall Precision : {ents_p * 100:.1f}%")
    print(f"  Overall Recall    : {ents_r * 100:.1f}%")
    print(f"  Overall F1-Score  : {ents_f * 100:.1f}%\n")
    print(f"  Per-Entity Breakdown:")
    print(f"  {'Label':<15} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
    print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*12}")
    for label, metrics in sorted(ents_per_type.items()):
        p = metrics.get("p", 0.0) * 100
        r = metrics.get("r", 0.0) * 100
        f = metrics.get("f", 0.0) * 100
        print(f"  {label:<15} {p:>8.1f}%   {r:>8.1f}%   {f:>8.1f}%")
    print(f"============================================================\n")

    # Save trained model to disk
    os.makedirs(output_dir, exist_ok=True)
    nlp.to_disk(output_dir)
    print(f"💾 Trained model saved to: {output_dir}")

    # Save metrics JSON alongside model
    metrics_path = os.path.join(output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "overall_precision": ents_p,
            "overall_recall": ents_r,
            "overall_f1": ents_f,
            "per_type": ents_per_type,
            "test_samples": len(test_data),
            "train_samples": len(train_data),
        }, f, indent=2)

    return scores


def load_ner_model() -> spacy.language.Language:
    """
    Load the trained custom NER model from disk.
    If the custom model is not found, loads base en_core_web_sm.
    """
    if os.path.exists(os.path.join(MODEL_DIR, "meta.json")):
        return spacy.load(MODEL_DIR)
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return spacy.blank("en")


def main():
    print("=" * 60)
    print("  Criminal Network Analysis — NER Model Training")
    print("=" * 60)

    dataset = load_dataset(DATA_PATH)
    print(f"📁 Loaded {len(dataset)} labeled sentences.")

    # 80/20 train/test split with deterministic seed
    random.seed(42)
    random.shuffle(dataset)
    split_idx = int(len(dataset) * 0.8)
    train_data = dataset[:split_idx]
    test_data = dataset[split_idx:]

    print(f"✂️ Split: {len(train_data)} train samples, {len(test_data)} test samples.")
    train_spacy_ner(train_data, test_data)


if __name__ == "__main__":
    main()
