"""
active_learning.py — Find likely-mislabeled samples for human review.

This implements the Active Learning step. Instead of manually
reviewing all ~20,000 samples (impractical), we let the trained model
itself flag the samples it most strongly disagrees with. Those are the
samples most likely to have a WRONG label, so reviewing just the top
few hundred fixes most of the label noise with a fraction of the
effort (the Pareto / 80-20 principle).

How it works:
    1. Load the best trained model + label encoders.
    2. Run it over the WHOLE dataset.
    3. For each task, when the model's prediction disagrees with the
       stored label AND the model is very confident (prob > THRESHOLD),
       record it as a "conflict".
    4. Sort conflicts so the most suspicious samples come first.
    5. Write conflicts_review.json for the human reviewers.

Run AFTER train_v2.py:
    python active_learning.py
"""

import json
import os
import pickle

import numpy as np
import torch
from torch.utils.data import DataLoader

from transformers import AutoTokenizer

# Reuse the exact same classes / data loading as the training script
# so behavior is guaranteed to be consistent.
from train_v2 import (
    MultiTaskMARBERT,
    ArabicMessageDataset,
    load_dataset,
    SAVE_DIR,
    MAX_LEN,
    BATCH_SIZE,
    DATASET_PATH,
)

# Only flag a disagreement if the model is at least this confident.
# Higher threshold = fewer but higher-quality candidates to review.
CONFIDENCE_THRESHOLD = 0.85

# How many top conflicts to highlight as the priority review batch.
TOP_K_HINT = 400

OUTPUT_FILE = "conflicts_review.json"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model_and_encoders():
    """Load the best checkpoint, tokenizer and label encoders.

    Returns:
        (model, tokenizer, le_sent, le_cat, le_urg)
    """
    with open(os.path.join(SAVE_DIR, "label_encoders.pkl"), "rb") as f:
        enc = pickle.load(f)
    le_sent, le_cat, le_urg = enc["sentiment"], enc["category"], enc["urgency"]

    with open(os.path.join(SAVE_DIR, "model_name.txt")) as f:
        model_name = f.read().strip()

    tokenizer = AutoTokenizer.from_pretrained(SAVE_DIR)

    model = MultiTaskMARBERT(
        model_name,
        n_sent=len(le_sent.classes_),
        n_cat=len(le_cat.classes_),
        n_urg=len(le_urg.classes_),
    ).to(device)
    model.load_state_dict(
        torch.load(os.path.join(SAVE_DIR, "best_model.pt"), map_location=device)
    )
    model.eval()

    return model, tokenizer, le_sent, le_cat, le_urg


def find_conflicts(model, loader, records, le_sent, le_cat, le_urg):
    """Scan the dataset and collect high-confidence disagreements.

    For every sample and every task, if the model's top prediction
    differs from the stored label but the model's softmax confidence
    exceeds CONFIDENCE_THRESHOLD, that task is flagged. A sample with
    one or more flagged tasks becomes a conflict record.

    Args:
        model: The trained MultiTaskMARBERT.
        loader: DataLoader over the full dataset (no shuffling).
        records: The original records list (for the raw text).
        le_*: Fitted LabelEncoders for readable names.

    Returns:
        A list of conflict dicts.
    """
    conflicts = []
    cursor = 0

    with torch.no_grad():
        for batch in loader:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)

            log_s, log_c, log_u = model(ids, mask)

            prob_s = torch.softmax(log_s, dim=1)
            prob_c = torch.softmax(log_c, dim=1)
            prob_u = torch.softmax(log_u, dim=1)

            pred_s = prob_s.argmax(1).cpu().numpy()
            pred_c = prob_c.argmax(1).cpu().numpy()
            pred_u = prob_u.argmax(1).cpu().numpy()

            conf_s = prob_s.max(1).values.cpu().numpy()
            conf_c = prob_c.max(1).values.cpu().numpy()
            conf_u = prob_u.max(1).values.cpu().numpy()

            true_s = batch["label_sent"].numpy()
            true_c = batch["label_cat"].numpy()
            true_u = batch["label_urg"].numpy()

            for i in range(len(pred_s)):
                ridx = cursor + i
                details = {}
                n_disagree = 0

                if pred_s[i] != true_s[i] and conf_s[i] > CONFIDENCE_THRESHOLD:
                    n_disagree += 1
                    details["sentiment"] = {
                        "current_label": le_sent.inverse_transform([true_s[i]])[0],
                        "model_suggests": le_sent.inverse_transform([pred_s[i]])[0],
                        "model_confidence": round(float(conf_s[i]), 4),
                    }
                if pred_c[i] != true_c[i] and conf_c[i] > CONFIDENCE_THRESHOLD:
                    n_disagree += 1
                    details["category"] = {
                        "current_label": le_cat.inverse_transform([true_c[i]])[0],
                        "model_suggests": le_cat.inverse_transform([pred_c[i]])[0],
                        "model_confidence": round(float(conf_c[i]), 4),
                    }
                if pred_u[i] != true_u[i] and conf_u[i] > CONFIDENCE_THRESHOLD:
                    n_disagree += 1
                    details["urgency"] = {
                        "current_label": le_urg.inverse_transform([true_u[i]])[0],
                        "model_suggests": le_urg.inverse_transform([pred_u[i]])[0],
                        "model_confidence": round(float(conf_u[i]), 4),
                    }

                if n_disagree > 0:
                    avg_conf = float(
                        np.mean([
                            d["model_confidence"] for d in details.values()
                        ])
                    )
                    conflicts.append({
                        "text": records[ridx]["text"],
                        "disagreements_count": n_disagree,
                        "avg_model_confidence": round(avg_conf, 4),
                        "conflicts": details,
                        "reviewed": False,        # reviewers flip this to true
                        "corrected_labels": {},   # reviewers fill if needed
                    })

            cursor += len(pred_s)

    # Most suspicious first: more disagreeing tasks, then higher model
    # confidence in the disagreement.
    conflicts.sort(
        key=lambda x: (-x["disagreements_count"], -x["avg_model_confidence"])
    )
    return conflicts


def main():
    """Generate conflicts_review.json from the trained model."""
    print("[1/4] loading model + encoders...")
    model, tokenizer, le_sent, le_cat, le_urg = load_model_and_encoders()

    print("[2/4] loading full dataset...")
    records = load_dataset(DATASET_PATH)
    texts = [r["text"] for r in records]
    y_s = le_sent.transform([r["sentiment"] for r in records])
    y_c = le_cat.transform([r["category"] for r in records])
    y_u = le_urg.transform([r["urgency"] for r in records])

    ds = ArabicMessageDataset(texts, y_s, y_c, y_u, tokenizer, MAX_LEN)
    loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    print("[3/4] scanning for high-confidence disagreements...")
    conflicts = find_conflicts(model, loader, records, le_sent, le_cat, le_urg)

    print("[4/4] writing output...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(conflicts, f, ensure_ascii=False, indent=2)

    total = len(records)
    n_conf = len(conflicts)
    pct = (n_conf / total * 100) if total else 0.0

    print("\n" + "=" * 60)
    print(f"  total samples scanned     : {total:,}")
    print(f"  conflicts found           : {n_conf:,} ({pct:.1f}%)")
    print(f"  confidence threshold      : {CONFIDENCE_THRESHOLD}")
    print(f"  -> review the TOP {TOP_K_HINT} rows of {OUTPUT_FILE} first")
    print("=" * 60)
    print(f"\n[DONE] written: {OUTPUT_FILE}")
    print("[NEXT] A human reviews the top conflicts, fixes wrong labels")
    print("       in the dataset, then you re-run train_v2.py.")


if __name__ == "__main__":
    main()
