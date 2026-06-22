"""
Danger: drops all project tables and recreates them.
Use only if you are still testing and do not care about existing data.
"""
from app.database.db import Base, engine
from app.database import models  # noqa: F401
from app.database.init_db import ensure_database_ready

answer = input("This will DROP all project tables. Type YES to continue: ")
if answer != "YES":
    print("Cancelled.")
    raise SystemExit(0)

Base.metadata.drop_all(bind=engine)
ensure_database_ready(import_json_faqs=True)
print("Database reset done ✅")
