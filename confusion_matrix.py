"""
confusion_matrix.py — Generate confusion matrices for the test set.

Run this AFTER train_v2.py has finished. train_v2.py saves the test
predictions to saved_model/test_predictions.npz, so this script does
NOT need a GPU and does NOT re-run the model — it just draws the
matrices from the saved predictions. This guarantees the matrices
correspond exactly to the unbiased test evaluation in the report.

Usage:
    python confusion_matrix.py

Output (saved next to this script):
    cm_sentiment.png  / cm_sentiment_normalized.png
    cm_category.png   / cm_category_normalized.png
    cm_urgency.png    / cm_urgency_normalized.png
"""

import os
import pickle

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

SAVE_DIR = "saved_model"


def load_predictions():
    """Load saved test predictions and the label encoders.

    Returns:
        (preds, encoders) where preds is the npz archive of
        true/pred arrays for the three tasks, and encoders is a dict
        of fitted LabelEncoders for human-readable class names.
    """
    pred_path = os.path.join(SAVE_DIR, "test_predictions.npz")
    if not os.path.exists(pred_path):
        raise FileNotFoundError(
            f"{pred_path} not found. Run train_v2.py first — it saves "
            f"the test predictions used here."
        )
    preds = np.load(pred_path)

    with open(os.path.join(SAVE_DIR, "label_encoders.pkl"), "rb") as f:
        encoders = pickle.load(f)

    return preds, encoders


def plot_confusion(true, pred, classes, title, filename):
    """Draw and save two confusion matrices: raw counts and normalized.

    The normalized version (row-wise percentages) is the one to put in
    the report when classes are imbalanced, because it shows the rate
    of confusion per true class rather than raw counts.

    Args:
        true: List/array of ground-truth integer labels.
        pred: List/array of predicted integer labels.
        classes: Ordered class-name list (from the LabelEncoder).
        title: Plot title.
        filename: Output filename for the raw-count version
                  (the normalized one appends "_normalized").
    """
    labels_idx = list(range(len(classes)))

    # ---- Raw counts -----------------------------------------------------
    cm = confusion_matrix(true, pred, labels=labels_idx)
    plt.figure(figsize=(7, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes,
                cbar_kws={"label": "Count"})
    plt.title(title, fontsize=14, fontweight="bold")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[SAVED] {filename}")

    # ---- Row-normalized (percentages) -----------------------------------
    row_sums = cm.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1                  # avoid divide-by-zero
    cm_norm = cm.astype(float) / row_sums

    norm_name = filename.replace(".png", "_normalized.png")
    plt.figure(figsize=(7, 6))
    sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=classes, yticklabels=classes,
                cbar_kws={"label": "Proportion"})
    plt.title(f"{title} (Normalized)", fontsize=14, fontweight="bold")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    plt.savefig(norm_name, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[SAVED] {norm_name}")


def main():
    """Build all three confusion matrices and print the test reports."""
    preds, encoders = load_predictions()
    le_sent = encoders["sentiment"]
    le_cat = encoders["category"]
    le_urg = encoders["urgency"]

    tasks = [
        ("sentiment", preds["true_s"], preds["pred_s"], le_sent.classes_,
         "Sentiment Confusion Matrix (Test Set)", "cm_sentiment.png"),
        ("category", preds["true_c"], preds["pred_c"], le_cat.classes_,
         "Category Confusion Matrix (Test Set)", "cm_category.png"),
        ("urgency", preds["true_u"], preds["pred_u"], le_urg.classes_,
         "Urgency Confusion Matrix (Test Set)", "cm_urgency.png"),
    ]

    for name, true, pred, classes, title, fname in tasks:
        plot_confusion(true, pred, list(classes), title, fname)
        print(f"\n=== {name.upper()} (Test Set) ===")
        print(classification_report(true, pred, target_names=list(classes),
                                    zero_division=0))

    print("\n[DONE] 6 images saved (3 raw + 3 normalized).")
    print("[TIP] Use the *_normalized.png versions in the report — they")
    print("      are clearer when classes are imbalanced (e.g. 'critical').")


if __name__ == "__main__":
    main()
