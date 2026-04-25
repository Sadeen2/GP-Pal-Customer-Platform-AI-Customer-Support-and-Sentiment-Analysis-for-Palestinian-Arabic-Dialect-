import json
import random
import re
from collections import Counter
from pathlib import Path

# =========================
# Paths
# =========================
INPUT_FILE = "data/baseline_dataset/generated_data_combined.json"
OUTPUT_FILE = "data/baseline_dataset/baseline_clean.json"

USE_SEMANTIC_DEDUP = True
SEMANTIC_THRESHOLD = 0.85

VALID_SENTIMENT = {"Positive", "Neutral", "Negative"}
VALID_INTENT = {"Inquiry", "Complaint", "Request", "Feedback", "Other"}
VALID_URGENCY = {"Normal", "Urgent", "Critical"}

URGENCY_MAPPING = {
    "Low": "Normal",
    "Medium": "Urgent",
    "High": "Critical",
    "Normal": "Normal",
    "Urgent": "Urgent",
    "Critical": "Critical",
}


def clean_text(text):
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_json_file():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                print(f"Loaded {len(data)} records from {INPUT_FILE}")
                return data
            else:
                print("Input file is not a JSON list.")
                return []
        except json.JSONDecodeError:
            print("Invalid JSON file.")
            return []


def basic_clean_and_validate(data):
    cleaned = []
    invalid = []

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            invalid.append((idx, "not_dict"))
            continue

        text = clean_text(item.get("text") or item.get("msg", ""))

        sentiment = item.get("sentiment", "")
        intent = item.get("intent", "")
        urgency = item.get("urgency", "")

        urgency = URGENCY_MAPPING.get(urgency, urgency)

        if not text:
            invalid.append((idx, "empty_text"))
            continue

        if sentiment not in VALID_SENTIMENT:
            invalid.append((idx, f"invalid_sentiment: {sentiment}"))
            continue

        if intent not in VALID_INTENT:
            invalid.append((idx, f"invalid_intent: {intent}"))
            continue

        if urgency not in VALID_URGENCY:
            invalid.append((idx, f"invalid_urgency: {urgency}"))
            continue

        cleaned.append({
            "id": item.get("id"),
            "text": text,
            "sentiment": sentiment,
            "intent": intent,
            "urgency": urgency,
            "source": item.get("source", "baseline_generated")
        })

    if invalid:
        print("\nInvalid examples:")
        for ex in invalid[:10]:
            print(ex)

    return cleaned, invalid


def exact_dedup(data):
    seen = set()
    unique = []

    for item in data:
        key = item["text"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def semantic_dedup(data, threshold=0.85):
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        print("sentence-transformers not installed. Skipping semantic dedup.")
        return data

    print("Loading semantic model...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    texts = [item["text"] for item in data]
    embeddings = model.encode(texts, convert_to_tensor=True)

    keep = []
    removed = set()

    for i in range(len(data)):
        if i in removed:
            continue

        keep.append(data[i])

        for j in range(i + 1, len(data)):
            if j in removed:
                continue

            sim = util.cos_sim(embeddings[i], embeddings[j]).item()

            if sim >= threshold:
                removed.add(j)

    print(f"Semantic duplicates removed: {len(removed)}")
    return keep


def print_distribution(data):
    print("\n===== Distribution =====")
    print("Total:", len(data))
    print("Sentiment:", Counter(item["sentiment"] for item in data))
    print("Intent:", Counter(item["intent"] for item in data))
    print("Urgency:", Counter(item["urgency"] for item in data))


def save_output(data):
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(data, start=1):
        item["id"] = i

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved clean baseline dataset to: {OUTPUT_FILE}")


def main():
    print("Starting baseline processing pipeline...\n")

    raw_data = load_json_file()
    print("Total before cleaning:", len(raw_data))

    cleaned, invalid = basic_clean_and_validate(raw_data)
    print("After validation:", len(cleaned))
    print("Invalid removed:", len(invalid))

    deduped = exact_dedup(cleaned)
    print("After exact dedup:", len(deduped))
    print("Exact duplicates removed:", len(cleaned) - len(deduped))

    final_data = deduped

    if USE_SEMANTIC_DEDUP:
        final_data = semantic_dedup(final_data, SEMANTIC_THRESHOLD)
        print("After semantic dedup:", len(final_data))
    else:
        print("Semantic dedup skipped.")

    random.seed(42)
    random.shuffle(final_data)

    print_distribution(final_data)
    save_output(final_data)

    print("\nDone.")


if __name__ == "__main__":
    main()