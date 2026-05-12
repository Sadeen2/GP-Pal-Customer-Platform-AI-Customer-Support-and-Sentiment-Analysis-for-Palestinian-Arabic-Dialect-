"""
train_strong_marbert.py — Strong GPU Multi-task MARBERT training
Predicts: sentiment | category/intent | urgency

Put this file beside dataset.json then run:
    python train_strong_marbert.py

Recommended for GTX 1050 Ti 4GB:
    BATCH_SIZE=8 or 12
    GRAD_ACCUM_STEPS=2
"""

import json
import os
import pickle
import random
import warnings
from collections import Counter

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, f1_score
from sklearn.utils.class_weight import compute_class_weight

from transformers import (
    AutoTokenizer,
    AutoModel,
    get_linear_schedule_with_warmup,
)

try:
    from torch.amp import autocast, GradScaler
    AMP_NEW_API = True
except Exception:
    from torch.cuda.amp import autocast, GradScaler
    AMP_NEW_API = False

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DATASET_PATH = "clean_dataset.json"
SAVE_DIR = "saved_model"

MODEL_NAME = "UBC-NLP/MARBERTv2"
FALLBACK_MODEL = "UBC-NLP/MARBERT"

MAX_LEN = 256             # 128 is OK, 160 helps long Arabic complaints
EPOCHS = 8                 # early stopping will stop if no improvement
BATCH_SIZE = 4            # safe for GTX 1050 Ti 4GB
GRAD_ACCUM_STEPS = 4       # effective batch = 16
LR_BERT = 1e-5             # smaller LR for pretrained encoder
LR_HEADS = 3e-5            # larger LR for new classifier heads
WEIGHT_DECAY = 0.01
DROPOUT = 0.35
WARMUP_RATIO = 0.08
PATIENCE = 3
SEED = 42

# Task loss weights — urgency is imbalanced, so give it more attention
LOSS_W_SENT = 1.0
LOSS_W_CAT = 1.2
LOSS_W_URG = 1.8

USE_WEIGHTED_SAMPLER = True

os.makedirs(SAVE_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# REPRODUCIBILITY + DEVICE
# ─────────────────────────────────────────────
def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


set_seed(SEED)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = device.type == "cuda"

if device.type == "cuda":
    torch.backends.cudnn.benchmark = True
    gpu_name = torch.cuda.get_device_name(0)
    gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"[GPU] {gpu_name} | {gpu_mem:.1f} GB VRAM | AMP enabled")
else:
    print("[CPU] No CUDA GPU found. Training will be slow.")


# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────
VALID_SENT = {"positive", "negative", "neutral"}
VALID_CAT = {"complaint", "feedback", "inquiry", "other", "request"}
VALID_URG = {"normal", "urgent", "critical"}


def clean_text(text: str) -> str:
    text = str(text).strip()
    text = " ".join(text.split())
    return text


def load_dataset(path: str):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    seen = set()
    records = []
    bad = 0
    dup = 0

    for item in raw:
        text = clean_text(item.get("text", ""))
        if not text:
            bad += 1
            continue

        sentiment = str(item.get("sentiment", "")).strip().lower()
        category = str(item.get("category") or item.get("intent") or "").strip().lower()
        urgency = str(item.get("urgency", "")).strip().lower()

        if sentiment not in VALID_SENT or category not in VALID_CAT or urgency not in VALID_URG:
            bad += 1
            continue

        # Remove exact duplicates only when all labels are same.
        key = (text, sentiment, category, urgency)
        if key in seen:
            dup += 1
            continue
        seen.add(key)

        records.append({
            "text": text,
            "sentiment": sentiment,
            "category": category,
            "urgency": urgency,
        })

    print(f"[OK] loaded={len(records):,} | removed_bad={bad:,} | removed_duplicates={dup:,}")
    for field in ["sentiment", "category", "urgency"]:
        print(f"{field:10s}: {dict(Counter(r[field] for r in records))}")

    return records


def encode_labels(records):
    le_sent = LabelEncoder()
    le_cat = LabelEncoder()
    le_urg = LabelEncoder()

    y_sent_txt = [r["sentiment"] for r in records]
    y_cat_txt = [r["category"] for r in records]
    y_urg_txt = [r["urgency"] for r in records]

    le_sent.fit(sorted(set(y_sent_txt)))
    le_cat.fit(sorted(set(y_cat_txt)))
    le_urg.fit(sorted(set(y_urg_txt)))

    y_sent = le_sent.transform(y_sent_txt)
    y_cat = le_cat.transform(y_cat_txt)
    y_urg = le_urg.transform(y_urg_txt)

    print("classes sentiment:", list(le_sent.classes_))
    print("classes category :", list(le_cat.classes_))
    print("classes urgency  :", list(le_urg.classes_))

    return (le_sent, le_cat, le_urg), (y_sent, y_cat, y_urg)


def make_safe_stratify(y_sent, y_cat, y_urg):
    """
    Try stratifying by full combination: sentiment_category_urgency.
    If some combination appears once only, fallback gradually.
    """
    combo = np.array([f"{s}_{c}_{u}" for s, c, u in zip(y_sent, y_cat, y_urg)])
    if min(Counter(combo).values()) >= 2:
        print("[split] stratify = sentiment+category+urgency")
        return combo

    combo2 = np.array([f"{s}_{c}" for s, c in zip(y_sent, y_cat)])
    if min(Counter(combo2).values()) >= 2:
        print("[split] stratify = sentiment+category")
        return combo2

    print("[split] stratify = sentiment only")
    return y_sent


def class_weights(y):
    classes = np.unique(y)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)
    return torch.tensor(weights, dtype=torch.float32, device=device)


def sample_weights(y_sent, y_cat, y_urg):
    """
    Weighted sampler so rare classes, especially urgent/critical, appear more during training.
    """
    cs = Counter(y_sent)
    cc = Counter(y_cat)
    cu = Counter(y_urg)
    weights = []
    for s, c, u in zip(y_sent, y_cat, y_urg):
        w = (1.0 / cs[s]) + (1.0 / cc[c]) + (2.5 / cu[u])
        weights.append(w)
    return torch.tensor(weights, dtype=torch.double)


# ─────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────
class ArabicMessageDataset(Dataset):
    def __init__(self, texts, y_sent, y_cat, y_urg, tokenizer, max_len):
        self.texts = list(texts)
        self.y_sent = np.array(y_sent)
        self.y_cat = np.array(y_cat)
        self.y_urg = np.array(y_urg)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label_sent": torch.tensor(self.y_sent[idx], dtype=torch.long),
            "label_cat": torch.tensor(self.y_cat[idx], dtype=torch.long),
            "label_urg": torch.tensor(self.y_urg[idx], dtype=torch.long),
        }


# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────
class MultiTaskMARBERT(nn.Module):
    def __init__(self, model_name, n_sent, n_cat, n_urg, dropout=0.35):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        hidden = self.bert.config.hidden_size

        self.dropout = nn.Dropout(dropout)

        # Stronger heads than one Linear layer
        self.head_sent = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, n_sent),
        )
        self.head_cat = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, n_cat),
        )
        self.head_urg = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, n_urg),
        )

    def forward(self, input_ids, attention_mask):
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]
        cls = self.dropout(cls)

        return (
            self.head_sent(cls),
            self.head_cat(cls),
            self.head_urg(cls),
        )


# ─────────────────────────────────────────────
# TRAIN / EVAL
# ─────────────────────────────────────────────
def compute_loss(logit_s, logit_c, logit_u, ls, lc, lu, crit_s, crit_c, crit_u):
    return (
        LOSS_W_SENT * crit_s(logit_s, ls)
        + LOSS_W_CAT * crit_c(logit_c, lc)
        + LOSS_W_URG * crit_u(logit_u, lu)
    )


def amp_autocast():
    if AMP_NEW_API:
        return autocast(device_type="cuda", enabled=USE_AMP)
    return autocast(enabled=USE_AMP)


def train_epoch(model, loader, optimizer, scheduler, scaler, crit_s, crit_c, crit_u):
    model.train()
    total_loss = 0.0
    optimizer.zero_grad(set_to_none=True)

    for step, batch in enumerate(loader, start=1):
        ids = batch["input_ids"].to(device, non_blocking=True)
        mask = batch["attention_mask"].to(device, non_blocking=True)
        ls = batch["label_sent"].to(device, non_blocking=True)
        lc = batch["label_cat"].to(device, non_blocking=True)
        lu = batch["label_urg"].to(device, non_blocking=True)

        with amp_autocast():
            logit_s, logit_c, logit_u = model(ids, mask)
            loss = compute_loss(logit_s, logit_c, logit_u, ls, lc, lu, crit_s, crit_c, crit_u)
            loss = loss / GRAD_ACCUM_STEPS

        scaler.scale(loss).backward()

        if step % GRAD_ACCUM_STEPS == 0 or step == len(loader):
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            scheduler.step()

        total_loss += loss.item() * GRAD_ACCUM_STEPS

    return total_loss / len(loader)


@torch.no_grad()
def eval_epoch(model, loader, crit_s, crit_c, crit_u):
    model.eval()

    total_loss = 0.0
    pred_s, pred_c, pred_u = [], [], []
    true_s, true_c, true_u = [], [], []

    for batch in loader:
        ids = batch["input_ids"].to(device, non_blocking=True)
        mask = batch["attention_mask"].to(device, non_blocking=True)
        ls = batch["label_sent"].to(device, non_blocking=True)
        lc = batch["label_cat"].to(device, non_blocking=True)
        lu = batch["label_urg"].to(device, non_blocking=True)

        with amp_autocast():
            logit_s, logit_c, logit_u = model(ids, mask)
            loss = compute_loss(logit_s, logit_c, logit_u, ls, lc, lu, crit_s, crit_c, crit_u)

        total_loss += loss.item()

        pred_s.extend(torch.argmax(logit_s, dim=1).cpu().tolist())
        pred_c.extend(torch.argmax(logit_c, dim=1).cpu().tolist())
        pred_u.extend(torch.argmax(logit_u, dim=1).cpu().tolist())

        true_s.extend(ls.cpu().tolist())
        true_c.extend(lc.cpu().tolist())
        true_u.extend(lu.cpu().tolist())

    macro_s = f1_score(true_s, pred_s, average="macro", zero_division=0)
    macro_c = f1_score(true_c, pred_c, average="macro", zero_division=0)
    macro_u = f1_score(true_u, pred_u, average="macro", zero_division=0)

    # Main score: balanced average, urgency is important
    score = (macro_s + macro_c + 1.5 * macro_u) / 3.5

    return {
        "loss": total_loss / len(loader),
        "score": score,
        "macro_s": macro_s,
        "macro_c": macro_c,
        "macro_u": macro_u,
        "pred_s": pred_s,
        "pred_c": pred_c,
        "pred_u": pred_u,
        "true_s": true_s,
        "true_c": true_c,
        "true_u": true_u,
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    records = load_dataset(DATASET_PATH)
    encoders, (y_sent, y_cat, y_urg) = encode_labels(records)
    le_sent, le_cat, le_urg = encoders
    texts = np.array([r["text"] for r in records])

    with open(os.path.join(SAVE_DIR, "label_encoders.pkl"), "wb") as f:
        pickle.dump({"sentiment": le_sent, "category": le_cat, "urgency": le_urg}, f)

    stratify_labels = make_safe_stratify(y_sent, y_cat, y_urg)

    idx = np.arange(len(texts))
    train_idx, val_idx = train_test_split(
        idx,
        test_size=0.15,
        random_state=SEED,
        stratify=stratify_labels,
    )

    tr_txt, va_txt = texts[train_idx], texts[val_idx]
    tr_s, va_s = y_sent[train_idx], y_sent[val_idx]
    tr_c, va_c = y_cat[train_idx], y_cat[val_idx]
    tr_u, va_u = y_urg[train_idx], y_urg[val_idx]

    print(f"[split] train={len(tr_txt):,} | val={len(va_txt):,}")

    print(f"[model] loading tokenizer: {MODEL_NAME}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        used_model = MODEL_NAME
    except Exception as e:
        print(f"[WARN] {e}")
        print(f"[model] fallback tokenizer: {FALLBACK_MODEL}")
        tokenizer = AutoTokenizer.from_pretrained(FALLBACK_MODEL)
        used_model = FALLBACK_MODEL

    tokenizer.save_pretrained(SAVE_DIR)
    with open(os.path.join(SAVE_DIR, "model_name.txt"), "w", encoding="utf-8") as f:
        f.write(used_model)

    train_ds = ArabicMessageDataset(tr_txt, tr_s, tr_c, tr_u, tokenizer, MAX_LEN)
    val_ds = ArabicMessageDataset(va_txt, va_s, va_c, va_u, tokenizer, MAX_LEN)

    pin = device.type == "cuda"

    if USE_WEIGHTED_SAMPLER:
        sampler = WeightedRandomSampler(
            weights=sample_weights(tr_s, tr_c, tr_u),
            num_samples=len(tr_s),
            replacement=True,
        )
        train_loader = DataLoader(
            train_ds,
            batch_size=BATCH_SIZE,
            sampler=sampler,
            num_workers=0,
            pin_memory=pin,
        )
    else:
        train_loader = DataLoader(
            train_ds,
            batch_size=BATCH_SIZE,
            shuffle=True,
            num_workers=0,
            pin_memory=pin,
        )

    val_loader = DataLoader(
        val_ds,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=pin,
    )

    print("[model] building model...")
    model = MultiTaskMARBERT(
        used_model,
        n_sent=len(le_sent.classes_),
        n_cat=len(le_cat.classes_),
        n_urg=len(le_urg.classes_),
        dropout=DROPOUT,
    ).to(device)

    crit_s = nn.CrossEntropyLoss(weight=class_weights(tr_s))
    crit_c = nn.CrossEntropyLoss(weight=class_weights(tr_c))
    crit_u = nn.CrossEntropyLoss(weight=class_weights(tr_u))

    optimizer = torch.optim.AdamW(
        [
            {"params": model.bert.parameters(), "lr": LR_BERT},
            {"params": model.head_sent.parameters(), "lr": LR_HEADS},
            {"params": model.head_cat.parameters(), "lr": LR_HEADS},
            {"params": model.head_urg.parameters(), "lr": LR_HEADS},
        ],
        weight_decay=WEIGHT_DECAY,
    )

    optimizer_steps_per_epoch = int(np.ceil(len(train_loader) / GRAD_ACCUM_STEPS))
    total_steps = optimizer_steps_per_epoch * EPOCHS
    warmup_steps = int(total_steps * WARMUP_RATIO)

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    if AMP_NEW_API:
        scaler = GradScaler("cuda", enabled=USE_AMP)
    else:
        scaler = GradScaler(enabled=USE_AMP)

    best_score = -1.0
    bad_epochs = 0

    print("=" * 70)
    print(f"Training | epochs={EPOCHS} | batch={BATCH_SIZE} | accum={GRAD_ACCUM_STEPS}")
    print(f"MAX_LEN={MAX_LEN} | total_optimizer_steps={total_steps:,}")
    print("=" * 70)

    for epoch in range(1, EPOCHS + 1):
        tr_loss = train_epoch(model, train_loader, optimizer, scheduler, scaler, crit_s, crit_c, crit_u)
        ev = eval_epoch(model, val_loader, crit_s, crit_c, crit_u)

        print(
            f"Epoch {epoch}/{EPOCHS} | "
            f"train_loss={tr_loss:.4f} | val_loss={ev['loss']:.4f} | "
            f"score={ev['score']:.4f} | "
            f"F1 sent={ev['macro_s']:.4f} cat={ev['macro_c']:.4f} urg={ev['macro_u']:.4f}"
        )

        if ev["score"] > best_score:
            best_score = ev["score"]
            bad_epochs = 0
            torch.save(model.state_dict(), os.path.join(SAVE_DIR, "best_model.pt"))
            print(f"[SAVED] best_model.pt | score={best_score:.4f}")
        else:
            bad_epochs += 1
            print(f"[early_stop] no improvement: {bad_epochs}/{PATIENCE}")
            if bad_epochs >= PATIENCE:
                print("[early_stop] stopped.")
                break

    # Final evaluation with best model
    model.load_state_dict(torch.load(os.path.join(SAVE_DIR, "best_model.pt"), map_location=device))
    ev = eval_epoch(model, val_loader, crit_s, crit_c, crit_u)

    print("\n" + "=" * 70)
    print("FINAL VALIDATION REPORT — BEST MODEL")
    print("=" * 70)

    print("\n── Sentiment ──")
    print(classification_report(ev["true_s"], ev["pred_s"], target_names=le_sent.classes_, zero_division=0))

    print("── Category/Intent ──")
    print(classification_report(ev["true_c"], ev["pred_c"], target_names=le_cat.classes_, zero_division=0))

    print("── Urgency ──")
    print(classification_report(ev["true_u"], ev["pred_u"], target_names=le_urg.classes_, zero_division=0))

    config = {
        "model_name": used_model,
        "n_sent": int(len(le_sent.classes_)),
        "n_cat": int(len(le_cat.classes_)),
        "n_urg": int(len(le_urg.classes_)),
        "sentiment_classes": list(le_sent.classes_),
        "category_classes": list(le_cat.classes_),
        "urgency_classes": list(le_urg.classes_),
        "max_len": MAX_LEN,
        "dropout": DROPOUT,
        "loss_weights": {
            "sentiment": LOSS_W_SENT,
            "category": LOSS_W_CAT,
            "urgency": LOSS_W_URG,
        },
    }

    with open(os.path.join(SAVE_DIR, "model_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Saved everything in: {SAVE_DIR}/")


if __name__ == "__main__":
    main()
