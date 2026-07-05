import json
import os
import pickle

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel

SAVE_DIR = "saved_model"
MAX_LEN = 128

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class MultiTaskMARBERT(nn.Module):
    def __init__(self, model_name, n_sent, n_cat, n_urg, dropout=0.3):
        super().__init__()

        self.bert = AutoModel.from_pretrained(model_name)
        hidden_size = self.bert.config.hidden_size
        head_hidden = 384

        self.head_sent = nn.Sequential(
            nn.Linear(hidden_size, head_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, n_sent)
        )

        self.head_cat = nn.Sequential(
            nn.Linear(hidden_size, head_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, n_cat)
        )

        self.head_urg = nn.Sequential(
            nn.Linear(hidden_size, head_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(head_hidden, n_urg)
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        cls_output = outputs.last_hidden_state[:, 0, :]

        sentiment_logits = self.head_sent(cls_output)
        category_logits = self.head_cat(cls_output)
        urgency_logits = self.head_urg(cls_output)

        return sentiment_logits, category_logits, urgency_logits


def _required_model_files():
    return [
        "model_name.txt",
        "model_config.json",
        "label_encoders.pkl",
        "best_model.pt",
        "tokenizer_config.json",
        "vocab.txt",
    ]


def validate_saved_model():
    missing = [
        name for name in _required_model_files()
        if not os.path.exists(os.path.join(SAVE_DIR, name))
    ]

    if missing:
        raise RuntimeError(
            "saved_model is not ready. Missing files: "
            + ", ".join(missing)
            + ". Train the model first using train.py, or copy saved_model beside the app folder."
        )


def load_model():
    validate_saved_model()

    with open(os.path.join(SAVE_DIR, "model_name.txt"), encoding="utf-8") as f:
        model_name = f.read().strip()

    with open(os.path.join(SAVE_DIR, "model_config.json"), encoding="utf-8") as f:
        config = json.load(f)

    with open(os.path.join(SAVE_DIR, "label_encoders.pkl"), "rb") as f:
        encoders = pickle.load(f)

    tokenizer = AutoTokenizer.from_pretrained(SAVE_DIR)

    model = MultiTaskMARBERT(
        model_name=model_name,
        n_sent=config["n_sent"],
        n_cat=config["n_cat"],
        n_urg=config["n_urg"],
        dropout=config.get("dropout", 0.3)
    ).to(device)

    state_dict = torch.load(
        os.path.join(SAVE_DIR, "best_model.pt"),
        map_location=device
    )

    model.load_state_dict(state_dict)
    model.eval()

    return model, tokenizer, encoders, config


# Lazy cache: do not load MARBERT during FastAPI startup/import.
_model = None
_tokenizer = None
_encoders = None
_config = None


def get_model_objects():
    global _model, _tokenizer, _encoders, _config

    if _model is not None:
        return _model, _tokenizer, _encoders, _config

    _model, _tokenizer, _encoders, _config = load_model()
    return _model, _tokenizer, _encoders, _config


def get_prediction(logits, encoder):
    probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().tolist()
    labels = encoder.classes_.tolist()

    best_index = probs.index(max(probs))

    scores = {
        labels[i]: round(probs[i], 4)
        for i in range(len(labels))
    }

    return labels[best_index], scores


def predict(text: str):
    model, tokenizer, encoders, config = get_model_objects()

    inputs = tokenizer(
        text,
        max_length=config.get("max_len", MAX_LEN),
        padding="max_length",
        truncation=True,
        return_tensors="pt"
    )

    input_ids = inputs["input_ids"].to(device)
    attention_mask = inputs["attention_mask"].to(device)

    with torch.no_grad():
        sentiment_logits, category_logits, urgency_logits = model(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

    sentiment_label, sentiment_scores = get_prediction(
        sentiment_logits,
        encoders["sentiment"]
    )

    category_label, category_scores = get_prediction(
        category_logits,
        encoders["category"]
    )

    urgency_label, urgency_scores = get_prediction(
        urgency_logits,
        encoders["urgency"]
    )

    return {
        "sentiment": {
            "label": sentiment_label,
            "scores": sentiment_scores
        },
        "category": {
            "label": category_label,
            "scores": category_scores
        },
        "urgency": {
            "label": urgency_label,
            "scores": urgency_scores
        }
    }
