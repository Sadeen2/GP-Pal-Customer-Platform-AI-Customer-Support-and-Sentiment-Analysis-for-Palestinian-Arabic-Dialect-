import json
import random
import re
import os
from collections import Counter


# ═══════════════════════════════════════════
# Step 1: Load and normalize
# ═══════════════════════════════════════════

def load_and_normalize(filepath, source_name):
    """Load a JSON file and normalize its schema"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    normalized = []
    for item in data:
        src = item.get("source", source_name)
        if src == "generated":
            src = source_name

        normalized.append({
            "text":      str(item.get("text", "")).strip(),
            "sentiment": item.get("sentiment", ""),
            "intent":    item.get("intent", ""),
            "urgency":   item.get("urgency", ""),
            "dialect":   item.get("dialect", "Palestinian"),
            "source":    src,
        })
    return normalized


# ═══════════════════════════════════════════
# Step 2: Clean text
# ═══════════════════════════════════════════

def clean_text(text):
    """Remove URLs, phone numbers, emojis, extra spaces"""
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'[\+]?[0-9][0-9\-\s]{7,}', '', text)
    return re.sub(r'\s+', ' ', text).strip()


# ═══════════════════════════════════════════
# Step 3: Validate labels
# ═══════════════════════════════════════════

VALID_S = {"Positive", "Neutral", "Negative"}
VALID_I = {"Inquiry", "Complaint", "Request", "Feedback", "Other"}
VALID_U = {"Normal", "Urgent", "Critical"}


def is_valid(item):
    """Check label validity and minimum length"""
    if len(item["text"].split()) < 4:
        return False
    if item["sentiment"] not in VALID_S:
        return False
    if item["intent"] not in VALID_I:
        return False
    if item["urgency"] not in VALID_U:
        return False
    return True


# ═══════════════════════════════════════════
# Step 4: Deduplication
# ═══════════════════════════════════════════

def exact_dedup(records):
    """Remove exact duplicates"""
    seen, unique, dupes = set(), [], 0
    for r in records:
        key = r["text"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
        else:
            dupes += 1
    return unique, dupes


def fuzzy_dedup(records, threshold=0.85):
    """Remove near-duplicate records using Jaccard similarity"""
    def jaccard(a, b):
        sa, sb = set(a.split()), set(b.split())
        if not sa or not sb:
            return 0
        return len(sa & sb) / len(sa | sb)

    texts, skip, kept, removed = [r["text"] for r in records], set(), [], 0
    for i in range(len(records)):
        if i in skip:
            continue
        kept.append(records[i])
        for j in range(i + 1, len(records)):
            if j not in skip and jaccard(texts[i], texts[j]) >= threshold:
                skip.add(j)
                removed += 1
    return kept, removed


# ═══════════════════════════════════════════
# Step 5: Stratified shuffle
# ═══════════════════════════════════════════

def stratified_shuffle(records, seed=42):
    """Round-robin shuffle by sentiment — no class appears in long consecutive blocks"""
    random.seed(seed)
    groups = {}
    for r in records:
        groups.setdefault(r["sentiment"], []).append(r)
    for g in groups:
        random.shuffle(groups[g])

    result, keys = [], list(groups.keys())
    iters, active = {k: iter(groups[k]) for k in keys}, set(keys)
    while active:
        for k in list(keys):
            if k not in active:
                continue
            try:
                result.append(next(iters[k]))
            except StopIteration:
                active.discard(k)
    return result


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main(file_paths, output_file="generated_data_combined.json"):

    print("🚀 Starting merge...\n")

    # 1. Load & merge
    all_records = []
    for path, source in file_paths:
        if not os.path.exists(path):
            print(f"  ⚠️  File not found: {path}")
            continue
        records = load_and_normalize(path, source)
        print(f"  ✅  {source:<28} {len(records):>4} records")
        all_records.extend(records)

    print(f"\n  📦 Total before cleaning : {len(all_records)}")

    # 2. Clean text
    for r in all_records:
        r["text"] = clean_text(r["text"])

    # 3. Validate
    valid = [r for r in all_records if is_valid(r)]
    print(f"  🗑️  Removed (invalid)     : {len(all_records) - len(valid)}")

    # 4. Exact dedup
    after_exact, exact_dupes = exact_dedup(valid)
    print(f"  🔁 Exact duplicates       : {exact_dupes}")

    # 5. Fuzzy dedup
    print("  🔍 Running fuzzy dedup (Jaccard ≥ 0.85)...")
    after_fuzzy, fuzzy_dupes = fuzzy_dedup(after_exact, threshold=0.85)
    print(f"  🔁 Fuzzy duplicates       : {fuzzy_dupes}")
    print(f"  📦 Total after cleaning   : {len(after_fuzzy)}")

    # 6. Stratified shuffle
    shuffled = stratified_shuffle(after_fuzzy)
    for i, r in enumerate(shuffled, 1):
        r["id"] = i

    # 7. Quick distribution summary
    total = len(shuffled)
    print(f"\n📊 Distribution:")
    for field in ["sentiment", "intent", "urgency"]:
        counts = Counter(r[field] for r in shuffled)
        parts  = ", ".join(f"{k}: {v} ({v/total*100:.0f}%)" for k, v in counts.most_common())
        print(f"  {field:<10} → {parts}")

    # 8. Save single file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(shuffled, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved → {output_file}  ({total} records)")
    print("🎉 Done!")


# ═══════════════════════════════════════════
# Entry point — update paths before running
# ═══════════════════════════════════════════

if __name__ == "__main__":

    file_paths = [
        ("ChatGPT_compined_data.json",  "generated_chatgpt"),
        ("claude_data.json",            "generated_claude"),
        ("copilot_combined_data.json",  "generated_copilot"),
        ("deepseek_combined_data.json", "generated_deepseek"),
        ("gemini_data.json",            "generated_gemini"),
    ]

    main(file_paths, output_file="generated_data_combined.json")