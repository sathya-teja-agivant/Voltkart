from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.database.connection import engine
from app.database.base import Base
from app import models  # noqa: F401
from app.routers import products, conversations, chat

app = FastAPI(
    title="VoltKart AI Shopping Assistant",
    description="MVP laptop recommendations, comparisons and policy support.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"name": "VoltKart", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        return {"database": "disconnected"}
