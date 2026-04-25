import json
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

INPUT_FILES = [
    "data/baseline_dataset/baseline_clean.json",
    "data/deepseek/deepseek_clean.json",
    "data/gemini/gemini_clean.json",
    "data/chatgpt/chatgpt_clean.json",
    "data/claude/claude_clean.json"
]

OUTPUT_FILE = "data/final_generated_dataset.json"

USE_SEMANTIC_DEDUP = True
SEMANTIC_THRESHOLD = 0.85


def load_all():
    all_data = []

    for file in INPUT_FILES:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

                if isinstance(data, list):
                    all_data.extend(data)
                    print(f"Loaded {len(data)} from {file}")
                else:
                    print(f"Skipped {file}: not a JSON list")

        except Exception as e:
            print(f"Error loading {file}: {e}")

    return all_data


def exact_dedup(data):
    seen = set()
    unique = []

    for item in data:
        text = item.get("text", "").strip()

        if text and text not in seen:
            seen.add(text)
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


def stratified_shuffle(data):
    groups = defaultdict(list)

    for item in data:
        key = (
            item.get("source", ""),
            item.get("sentiment", ""),
            item.get("intent", ""),
            item.get("urgency", "")
        )
        groups[key].append(item)

    for key in groups:
        random.shuffle(groups[key])
        groups[key] = deque(groups[key])

    keys = list(groups.keys())
    random.shuffle(keys)

    mixed = []

    while keys:
        next_keys = []

        for key in keys:
            if groups[key]:
                mixed.append(groups[key].popleft())

            if groups[key]:
                next_keys.append(key)

        keys = next_keys
        random.shuffle(keys)

    return mixed


def print_distribution(data):
    print("\n===== FINAL DISTRIBUTION =====")
    print("Total:", len(data))
    print("Sentiment:", Counter(item["sentiment"] for item in data))
    print("Intent:", Counter(item["intent"] for item in data))
    print("Urgency:", Counter(item["urgency"] for item in data))
    print("Source:", Counter(item.get("source", "unknown") for item in data))


def save(data):
    Path("data").mkdir(exist_ok=True)

    for i, item in enumerate(data, start=1):
        item["id"] = i

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved FINAL dataset to: {OUTPUT_FILE}")


def main():
    print("Starting FINAL merge...\n")

    data = load_all()
    print("\nTotal before dedup:", len(data))

    data = exact_dedup(data)
    print("After exact dedup:", len(data))

    if USE_SEMANTIC_DEDUP:
        data = semantic_dedup(data, SEMANTIC_THRESHOLD)
        print("After semantic dedup:", len(data))
    else:
        print("Semantic dedup skipped.")

    random.seed(42)
    data = stratified_shuffle(data)

    print_distribution(data)
    save(data)

    print("\nDONE")


if __name__ == "__main__":
    main()