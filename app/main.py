from dotenv import load_dotenv
load_dotenv()

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import models so SQLAlchemy registers all tables.
from app.database import models  # noqa: F401
from app.database.init_db import ensure_database_ready
from app.rate_limit import limiter

from app.routes.predict import router as predict_router
from app.routes.auth import router as auth_router
from app.routes.whatsapp import router as whatsapp_router
from app.routes.instagram import router as instagram_router
from app.routes.bot import router as bot_router
from app.routes.faq import router as faq_router
from app.realtime import router as realtime_router


# Creates tables, repairs old local DB columns, and imports faqs.json into faq_items if empty.
ensure_database_ready(import_json_faqs=True)

app = FastAPI(
    title="Pal-CustomerAI Backend",
    version="1.1.0-postgres-ready",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict_router)
app.include_router(auth_router)
app.include_router(whatsapp_router)
app.include_router(instagram_router)
app.include_router(bot_router)
app.include_router(faq_router)
app.include_router(realtime_router)

# Mount frontend only if the folder exists. This avoids backend startup failure if you run backend alone.
if os.path.isdir("frontend"):
    app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="dashboard")


@app.get("/")
def home():
    return {
        "message": "Pal-CustomerAI Backend is running"
    }
