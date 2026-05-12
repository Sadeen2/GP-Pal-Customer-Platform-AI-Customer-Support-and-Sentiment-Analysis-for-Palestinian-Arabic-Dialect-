import json
import re
from collections import Counter

INPUT_FILE = "dataset.json"
OUTPUT_FILE = "clean_dataset.json"

VALID_SENT = {"positive", "negative", "neutral"}
VALID_CAT = {"complaint", "feedback", "inquiry", "other", "request"}
VALID_URG = {"normal", "urgent", "critical"}


def light_clean(text: str) -> str:
    text = str(text).strip()

    # Remove links
    text = re.sub(r"http\S+|www\.\S+", " ", text)

    # Remove emails
    text = re.sub(r"\S+@\S+", " ", text)

    # Normalize spaces
    text = re.sub(r"\s+", " ", text)

    # Normalize Arabic letters lightly
    text = re.sub(r"[إأآا]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و")
    text = text.replace("ئ", "ي")

    # Remove tatweel
    text = text.replace("ـ", "")

    # Reduce repeated letters: كتيييير -> كتيير
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)

    return text.strip()


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned = []
    seen_exact = set()
    text_to_labels = {}

    removed_bad = 0
    removed_duplicate = 0
    conflicts = []

    for item in data:
        text = light_clean(item.get("text", ""))

        sentiment = str(item.get("sentiment", "")).strip().lower()
        category = str(item.get("category") or item.get("intent") or "").strip().lower()
        urgency = str(item.get("urgency", "")).strip().lower()

        if not text or sentiment not in VALID_SENT or category not in VALID_CAT or urgency not in VALID_URG:
            removed_bad += 1
            continue

        labels = (sentiment, category, urgency)
        exact_key = (text, sentiment, category, urgency)

        # نفس الجملة ونفس التصنيف: احذف التكرار
        if exact_key in seen_exact:
            removed_duplicate += 1
            continue

        # نفس الجملة بس تصنيف مختلف: خزّنها للمراجعة ولا تدخلها
        if text in text_to_labels and text_to_labels[text] != labels:
            conflicts.append({
                "text": text,
                "old_labels": text_to_labels[text],
                "new_labels": labels
            })
            continue

        seen_exact.add(exact_key)
        text_to_labels[text] = labels

        cleaned.append({
            "text": text,
            "sentiment": sentiment,
            "category": category,
            "urgency": urgency
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    with open("conflicts_review.json", "w", encoding="utf-8") as f:
        json.dump(conflicts, f, ensure_ascii=False, indent=2)

    print("Done.")
    print(f"Original samples: {len(data)}")
    print(f"Clean samples: {len(cleaned)}")
    print(f"Removed bad: {removed_bad}")
    print(f"Removed exact duplicates: {removed_duplicate}")
    print(f"Conflicting labels saved to: conflicts_review.json")
    print()

    print("Sentiment:", Counter(x["sentiment"] for x in cleaned))
    print("Category :", Counter(x["category"] for x in cleaned))
    print("Urgency  :", Counter(x["urgency"] for x in cleaned))


if __name__ == "__main__":
    main()