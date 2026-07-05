from dotenv import load_dotenv
import os

load_dotenv()
t = os.getenv("INSTAGRAM_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")

print("exists:", t is not None)
print("len:", len(t) if t else 0)
print("start:", repr(t[:12]) if t else None)
print("has_bearer_word:", t.lower().startswith("bearer") if t else None)
print("has_space_or_newline:", (" " in t or "\n" in t) if t else None)