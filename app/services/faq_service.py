import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func

from app.database.db import SessionLocal
from app.database.models import FAQItem

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


BASE_DIR = Path(__file__).resolve().parents[2]
FAQ_PATH = BASE_DIR / "app" / "data" / "faqs.json"

# Semantic model: good for Arabic + English.
SEMANTIC_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_cached_faqs = None
_cached_docs = None
_cached_embeddings = None
_cached_version = None


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()

    # Arabic normalization
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي")
    text = text.replace("ة", "ه")
    text = text.replace("ؤ", "و")
    text = text.replace("ئ", "ي")
    text = text.replace("ـ", "")

    # remove tashkeel
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

    # remove punctuation
    text = re.sub(r"[؟?!.,،؛:()\[\]{}\"']", " ", text)

    # spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clear_faq_cache():
    """Call this after FAQ add/edit/delete/enable/disable."""
    global _cached_faqs, _cached_docs, _cached_embeddings, _cached_version
    _cached_faqs = None
    _cached_docs = None
    _cached_embeddings = None
    _cached_version = None


def get_model():
    global _model

    if _model is not None:
        return _model

    if SentenceTransformer is None:
        print("sentence-transformers is not installed. Using TF-IDF fallback only.")
        return None

    try:
        print("Loading semantic FAQ model...")
        _model = SentenceTransformer(SEMANTIC_MODEL_NAME)
        print("Semantic FAQ model loaded.")
        return _model

    except Exception as e:
        print("Could not load semantic model:", e)
        return None


def _faq_row_to_dict(row: FAQItem) -> Dict:
    return {
        "id": row.id,
        "category": row.category,
        "intent": row.intent,
        "question": row.question,
        "examples": row.examples or [],
        "answer": row.answer,
        "keywords": row.keywords or "",
        "action": row.action or "auto_reply",
        "needs_human": bool(row.needs_human),
        "priority": row.priority if row.priority is not None else 50,
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _db_faq_version() -> Tuple[int, str]:
    db = SessionLocal()
    try:
        count = db.query(func.count(FAQItem.id)).filter(FAQItem.is_active == True).scalar() or 0
        max_updated = db.query(func.max(FAQItem.updated_at)).filter(FAQItem.is_active == True).scalar()
        return int(count), str(max_updated)
    except Exception:
        return -1, "db_error"
    finally:
        db.close()


def _load_faqs_from_db() -> List[Dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(FAQItem)
            .filter(FAQItem.is_active == True)
            .order_by(FAQItem.priority.desc(), FAQItem.id.asc())
            .all()
        )
        return [_faq_row_to_dict(row) for row in rows]
    except Exception as e:
        print("Error loading FAQ items from database:", e)
        return []
    finally:
        db.close()


def _load_faqs_from_file() -> List[Dict]:
    """Fallback only. Main source should be PostgreSQL faq_items."""
    if not FAQ_PATH.exists():
        print(f"FAQ file not found: {FAQ_PATH}")
        return []

    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = data.get("faqs", [])

        if not isinstance(data, list):
            print("Invalid faqs.json format. Expected list.")
            return []

        return [item for item in data if item.get("is_active", True)]

    except Exception as e:
        print("Error loading faqs.json:", e)
        return []


def _faq_to_document(faq: Dict) -> str:
    examples = faq.get("examples", [])

    if isinstance(examples, list):
        examples_text = " ".join(str(x) for x in examples)
    else:
        examples_text = str(examples)

    parts = [
        faq.get("intent", ""),
        faq.get("category", ""),
        faq.get("question", ""),
        examples_text,
        faq.get("keywords", ""),
        faq.get("answer", ""),
    ]

    return normalize_text(" ".join(str(p) for p in parts if p is not None))


def _load_faqs_cached():
    """
    Load FAQs and build semantic embeddings once.
    Source: database table faq_items.
    Fallback: app/data/faqs.json only if the database has no FAQs.
    """
    global _cached_faqs, _cached_docs, _cached_embeddings, _cached_version

    current_version = _db_faq_version()

    if (
        _cached_faqs is not None
        and _cached_docs is not None
        and _cached_version == current_version
    ):
        return _cached_faqs, _cached_docs, _cached_embeddings

    faqs = _load_faqs_from_db()
    source = "database"

    if not faqs:
        faqs = _load_faqs_from_file()
        source = "json_fallback"

    docs = [_faq_to_document(faq) for faq in faqs]

    embeddings = None
    model = get_model()

    if model is not None and docs:
        try:
            print(f"Building semantic embeddings for {len(docs)} FAQs...")
            embeddings = model.encode(
                docs,
                convert_to_tensor=False,
                normalize_embeddings=True,
            )
            print("FAQ embeddings ready.")
        except Exception as e:
            print("FAQ embedding error:", e)
            embeddings = None

    _cached_faqs = faqs
    _cached_docs = docs
    _cached_embeddings = embeddings
    _cached_version = current_version

    print(f"Loaded {len(faqs)} FAQs from {source}")

    return faqs, docs, embeddings


def _exact_example_match(user_message: str, faqs: List[Dict]) -> Optional[Dict]:
    user_text = normalize_text(user_message)

    for faq in faqs:
        question = normalize_text(faq.get("question", ""))

        if user_text == question:
            result = faq.copy()
            result["score"] = 1.0
            result["match_type"] = "exact_question"
            return result

        examples = faq.get("examples", [])
        if isinstance(examples, list):
            for ex in examples:
                if user_text == normalize_text(str(ex)):
                    result = faq.copy()
                    result["score"] = 1.0
                    result["match_type"] = "exact_example"
                    return result

    return None


def _semantic_match(user_message: str, faqs: List[Dict], embeddings) -> Optional[Dict]:
    model = get_model()

    if model is None or embeddings is None or not faqs:
        return None

    try:
        user_text = normalize_text(user_message)

        user_embedding = model.encode(
            [user_text],
            convert_to_tensor=False,
            normalize_embeddings=True,
        )

        similarities = cosine_similarity(user_embedding, embeddings).flatten()

        best_index = similarities.argmax()
        best_score = float(similarities[best_index])

        result = faqs[best_index].copy()
        result["score"] = round(best_score, 3)
        result["match_type"] = "semantic"

        return result

    except Exception as e:
        print("Semantic matching error:", e)
        return None


def _tfidf_match(user_message: str, faqs: List[Dict], docs: List[str]) -> Optional[Dict]:
    if not faqs or not docs:
        return None

    try:
        user_text = normalize_text(user_message)

        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            lowercase=False,
        )

        vectors = vectorizer.fit_transform([user_text] + docs)

        similarities = cosine_similarity(
            vectors[0:1],
            vectors[1:],
        ).flatten()

        best_index = similarities.argmax()
        best_score = float(similarities[best_index])

        result = faqs[best_index].copy()
        result["score"] = round(best_score, 3)
        result["match_type"] = "tfidf"

        return result

    except Exception as e:
        print("TF-IDF FAQ matching error:", e)
        return None


def find_best_faq(user_message: str) -> Optional[Dict]:
    """
    Hybrid FAQ matching:
    1) exact question/example match
    2) semantic meaning match
    3) TF-IDF fallback
    """

    if not user_message or not user_message.strip():
        return None

    faqs, docs, embeddings = _load_faqs_cached()

    if not faqs:
        return None

    exact = _exact_example_match(user_message, faqs)
    if exact:
        return exact

    semantic = _semantic_match(user_message, faqs, embeddings)
    tfidf = _tfidf_match(user_message, faqs, docs)

    if semantic and tfidf:
        semantic_score = float(semantic.get("score", 0.0))
        tfidf_score = float(tfidf.get("score", 0.0))

        if semantic_score >= 0.45:
            return semantic

        if tfidf_score > semantic_score:
            return tfidf

        return semantic

    return semantic or tfidf
