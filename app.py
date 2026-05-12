"""
app.py — Web interface for Arabic Customer Interaction Platform
Run: python app.py
"""

import json
import os
import pickle
import re
import torch
import torch.nn as nn
from flask import Flask, request, jsonify, render_template_string
from transformers import AutoTokenizer, AutoModel

SAVE_DIR = "saved_model"
MAX_LEN = 128
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class MultiTaskMARBERT(nn.Module):
    def __init__(self, model_name, n_sent, n_cat, n_urg, dropout=0.3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        hidden = self.bert.config.hidden_size
        self.drop = nn.Dropout(dropout)
        self.head_sent = nn.Linear(hidden, n_sent)
        self.head_cat = nn.Linear(hidden, n_cat)
        self.head_urg = nn.Linear(hidden, n_urg)

    def forward(self, input_ids, attention_mask):
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.drop(out.last_hidden_state[:, 0, :])
        return self.head_sent(cls), self.head_cat(cls), self.head_urg(cls)


def normalize_ar(text):
    text = text.lower()
    text = re.sub(r"[إأآا]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    text = text.replace("ة", "ه")
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


NEGATIVE_WORDS = [
    "سيء", "سيئ", "سيئه", "سيئة", "اسوء", "اسوا", "اسوأ",
    "بتخزي", "بخزي", "زباله", "زبالة", "مقرف", "قرف",
    "مش منيح", "مش حلو", "مش عاجب", "مش راضي",
    "خربان", "خربانه", "غلط", "سيئين", "رديء", "رديئ",
    "فاشل", "فاشله", "كارثه", "كارثة", "مشكله", "مشكلة",
    "تأخير", "تاخير", "تأخر", "تاخر", "بطيء", "بطيئ",
    "نصب", "احتيال", "حرام", "زعلان", "زعلت", "مدايق",
    "مش محترم", "مش مهني", "سيئه جدا", "سيء جدا",
    "ما عجبني", "مش مقبول", "تعبان", "تعبانه"
]

POSITIVE_WORDS = [
    "ممتاز", "ممتازه", "رائع", "رائعه", "حلو", "حلوه",
    "منيح", "منيحه", "تمام", "ممتازين", "رهيب", "رهيبه",
    "شكرا", "شكرًا", "مشكورين", "يسلمو", "يسلموا",
    "يعطيكم العافيه", "يعطيكم العافية", "احسنتم", "احسن",
    "مرتب", "مرتبه", "سريع", "سريعه", "محترم", "محترمين",
    "مبسوط", "راضي", "خدمة ممتازة", "خدمه ممتازه",
    "تجربه حلوه", "تجربة حلوة", "كل الاحترام"
]

URGENT_WORDS = [
    "ضروري", "مستعجل", "عاجل", "بسرعه", "بسرعة",
    "فورا", "فوراً", "هلأ", "هلا", "حالا", "حالاً",
    "لازم", "اليوم", "ما بستنى", "مهم جدا", "بدي حل سريع",
    "ردوا بسرعه", "ردو بسرعة"
]

CRITICAL_WORDS = [
    "خطر", "كارثه", "كارثة", "انسرق", "سرقه", "سرقة",
    "احتيال", "نصب", "تهديد", "بلاغ", "شرطة",
    "طوارئ", "حرج", "حرجة", "مشكلة كبيرة"
]

COMPLAINT_WORDS = [
    "شكوى", "بدي اشتكي", "اشتكيت", "بشتكي",
    "مشكله", "مشكلة", "غلط", "خربان", "تأخير", "تاخير",
    "ما وصل", "وصل غلط", "سيء", "سيئ", "بتخزي",
    "زباله", "زبالة", "فاشل", "مش شغال", "مش مقبول"
]

INQUIRY_WORDS = [
    "كيف", "وين", "متى", "كم", "شو", "هل",
    "بدي اعرف", "استفسار", "بسال", "بسأل", "سؤال",
    "ممكن اعرف", "وينه", "قديش"
]

REQUEST_WORDS = [
    "بدي", "ممكن", "لو سمحت", "اريد", "بدنا",
    "اطلب", "الغاء", "الغي", "ألغي", "تعديل",
    "استبدال", "بدل", "رجع", "ارجاع", "ارجع",
    "غير", "تغيير", "ابعث", "ارسل"
]

FEEDBACK_WORDS = [
    "رايي", "رأيي", "ملاحظتي", "اقتراح", "تقييم",
    "تجربتي", "الخدمه", "الخدمة", "التجربه", "التجربة",
    "كانت", "حاب احكي"
]


def has_any(text, words):
    return any(w in text for w in words)


def apply_rule_correction(original_text, result):
    text = normalize_ar(original_text)

    # Sentiment
    if has_any(text, NEGATIVE_WORDS):
        result["sentiment"]["label"] = "negative"
        result["sentiment"]["rule_override"] = "negative_keywords"
    elif has_any(text, POSITIVE_WORDS):
        result["sentiment"]["label"] = "positive"
        result["sentiment"]["rule_override"] = "positive_keywords"

    # Urgency
    if has_any(text, CRITICAL_WORDS):
        result["urgency"]["label"] = "critical"
        result["urgency"]["rule_override"] = "critical_keywords"
    elif has_any(text, URGENT_WORDS):
        result["urgency"]["label"] = "urgent"
        result["urgency"]["rule_override"] = "urgent_keywords"

    # Category / Intent
    if has_any(text, COMPLAINT_WORDS):
        result["category"]["label"] = "complaint"
        result["category"]["rule_override"] = "complaint_keywords"
    elif has_any(text, INQUIRY_WORDS):
        result["category"]["label"] = "inquiry"
        result["category"]["rule_override"] = "inquiry_keywords"
    elif has_any(text, REQUEST_WORDS):
        result["category"]["label"] = "request"
        result["category"]["rule_override"] = "request_keywords"
    elif has_any(text, FEEDBACK_WORDS):
        result["category"]["label"] = "feedback"
        result["category"]["rule_override"] = "feedback_keywords"

    return result


def load_artifacts():
    required = ["best_model.pt", "label_encoders.pkl", "model_config.json", "model_name.txt"]
    missing = [f for f in required if not os.path.exists(os.path.join(SAVE_DIR, f))]
    if missing:
        raise FileNotFoundError(f"Missing files in {SAVE_DIR}: {missing}")

    with open(os.path.join(SAVE_DIR, "model_name.txt"), encoding="utf-8") as f:
        model_name = f.read().strip()

    with open(os.path.join(SAVE_DIR, "model_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    with open(os.path.join(SAVE_DIR, "label_encoders.pkl"), "rb") as f:
        encoders = pickle.load(f)

    tokenizer = AutoTokenizer.from_pretrained(SAVE_DIR)

    model = MultiTaskMARBERT(
        model_name,
        n_sent=cfg["n_sent"],
        n_cat=cfg["n_cat"],
        n_urg=cfg["n_urg"],
        dropout=cfg.get("dropout", 0.3),
    ).to(device)

    model.load_state_dict(torch.load(os.path.join(SAVE_DIR, "best_model.pt"), map_location=device))
    model.eval()

    print(f"✔ Model loaded from {SAVE_DIR} | device={device}")
    return model, tokenizer, encoders, cfg


def predict_text(text, model, tokenizer, encoders, max_len=MAX_LEN):
    le_sent = encoders["sentiment"]
    le_cat = encoders["category"]
    le_urg = encoders["urgency"]

    enc = tokenizer(
        text,
        max_length=max_len,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    ids = enc["input_ids"].to(device)
    mask = enc["attention_mask"].to(device)

    with torch.no_grad():
        logit_s, logit_c, logit_u = model(ids, mask)

    def top_probs(logits, encoder):
        probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().tolist()
        labels = encoder.classes_.tolist()
        ranked = sorted(zip(labels, probs), key=lambda x: -x[1])
        return ranked[0][0], {lbl: round(p * 100, 1) for lbl, p in ranked}

    sent_label, sent_probs = top_probs(logit_s, le_sent)
    cat_label, cat_probs = top_probs(logit_c, le_cat)
    urg_label, urg_probs = top_probs(logit_u, le_urg)

    result = {
        "sentiment": {"label": sent_label, "scores": sent_probs},
        "category": {"label": cat_label, "scores": cat_probs},
        "urgency": {"label": urg_label, "scores": urg_probs},
    }

    result = apply_rule_correction(text, result)
    return result


app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Pal-CustomerAI</title>
<style>
body {
  background:#0d1117;
  color:#e6edf3;
  font-family:Arial, sans-serif;
  display:flex;
  justify-content:center;
  padding:40px;
}
.container {
  width:800px;
  background:#161b22;
  padding:30px;
  border-radius:16px;
  border:1px solid #30363d;
}
h1 { text-align:center; color:#a78bfa; }
textarea {
  width:100%;
  min-height:130px;
  background:#1f2937;
  color:white;
  border:1px solid #30363d;
  border-radius:10px;
  padding:15px;
  font-size:18px;
  direction:rtl;
}
button {
  margin-top:15px;
  width:100%;
  padding:14px;
  border:0;
  border-radius:10px;
  background:#6366f1;
  color:white;
  font-size:18px;
  cursor:pointer;
}
.card {
  background:#1f2937;
  margin-top:20px;
  padding:20px;
  border-radius:12px;
}
.label { font-size:24px; font-weight:bold; }
.positive { color:#10b981; }
.negative { color:#ef4444; }
.neutral { color:#3b82f6; }
.urgent { color:#f59e0b; }
.critical { color:#ef4444; }
.normal { color:#10b981; }
pre {
  direction:ltr;
  text-align:left;
  background:#0d1117;
  padding:15px;
  border-radius:10px;
  overflow:auto;
}
</style>
</head>
<body>
<div class="container">
<h1>Pal-CustomerAI</h1>
<textarea id="text" placeholder="اكتب رسالة العميل هون..."></textarea>
<button onclick="analyze()">تحليل الرسالة</button>
<div id="result"></div>
</div>

<script>
const SENT_AR = {positive:"إيجابي", negative:"سلبي", neutral:"محايد"};
const CAT_AR = {complaint:"شكوى", inquiry:"استفسار", request:"طلب", feedback:"تغذية راجعة", other:"أخرى"};
const URG_AR = {normal:"عادي", urgent:"عاجل", critical:"حرج"};

async function analyze() {
  const text = document.getElementById("text").value.trim();
  if (!text) {
    alert("اكتب نص أولاً");
    return;
  }

  const res = await fetch("/predict", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({text})
  });

  const data = await res.json();

  if (!res.ok) {
    document.getElementById("result").innerHTML = `<div class="card">Error: ${data.error}</div>`;
    return;
  }

  document.getElementById("result").innerHTML = `
    <div class="card">
      <div>Sentiment:</div>
      <div class="label ${data.sentiment.label}">${SENT_AR[data.sentiment.label] || data.sentiment.label}</div>
      <pre>${JSON.stringify(data.sentiment, null, 2)}</pre>
    </div>

    <div class="card">
      <div>Category:</div>
      <div class="label">${CAT_AR[data.category.label] || data.category.label}</div>
      <pre>${JSON.stringify(data.category, null, 2)}</pre>
    </div>

    <div class="card">
      <div>Urgency:</div>
      <div class="label ${data.urgency.label}">${URG_AR[data.urgency.label] || data.urgency.label}</div>
      <pre>${JSON.stringify(data.urgency, null, 2)}</pre>
    </div>
  `;
}
</script>
</body>
</html>
"""


model_obj = None
tokenizer_obj = None
encoders_obj = None
cfg_obj = None


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/predict", methods=["POST"])
def predict_route():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "النص فارغ"}), 400

    try:
        result = predict_text(text, model_obj, tokenizer_obj, encoders_obj, cfg_obj["max_len"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("▶ Loading model artifacts ...")
    model_obj, tokenizer_obj, encoders_obj, cfg_obj = load_artifacts()
    print("▶ Starting web server on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)